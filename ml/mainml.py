import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

import torch
from transformers import pipeline
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

STANCE_THRESHOLD = 0.60
EMBEDDING_DIM = 384  # sentence-transformers/all-MiniLM-L6-v2 outputs 384-dim vectors
EMBEDDINGS_COLLECTION = "nlp_embeddings"


# -------------------------------------------------------------------
# Pydantic Schemas
# -------------------------------------------------------------------

class Engagement(BaseModel):
    likes: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    views: int = Field(default=0, ge=0)


class Metadata(BaseModel):
    source_version: str = Field(min_length=1)
    collected_at_utc: datetime

    @field_validator("collected_at_utc")
    @classmethod
    def validate_collected_at_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "collected_at_utc must be timezone-aware ISO-8601 datetime"
            )
        return value


class SocialMediaEventRequest(BaseModel):
    event_id: UUID

    source: Literal[
        "x",
        "telegram",
        "reddit",
        "instagram",
        "other"
    ]

    source_post_id: str = Field(min_length=1)
    author_id_hash: str = Field(min_length=1)

    timestamp_utc: datetime

    text: str = Field(min_length=1)

    language: Optional[str] = Field(
        default="en",
        min_length=2
    )

    reply_to_id: Optional[str] = None
    parent_event_id: Optional[UUID] = None

    target_topic: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Optional target topic for zero-shot stance classification"
    )

    engagement: Engagement

    entities: List[Any] = Field(default_factory=list)

    metadata: Metadata

    @field_validator("timestamp_utc")
    @classmethod
    def validate_timestamp_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "timestamp_utc must be timezone-aware ISO-8601 datetime"
            )
        return value

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text cannot be empty")
        return value


class ClassificationResult(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)


class StanceResult(BaseModel):
    target: Optional[str] = None

    label: Literal[
        "support",
        "oppose",
        "neutral",
        "unknown"
    ]

    confidence: float = Field(ge=0.0, le=1.0)


class EvidenceItem(BaseModel):
    type: str
    event_id: UUID


class ModelMeta(BaseModel):
    name: str
    version: str


class SocialMediaEventResponse(BaseModel):
    event_id: UUID

    language: ClassificationResult
    sentiment: ClassificationResult
    emotion: ClassificationResult
    stance: StanceResult

    embedding_ref: Optional[str] = None

    evidence: List[EvidenceItem]

    model: ModelMeta


# -------------------------------------------------------------------
# Sentiment & Emotion Mapping
# -------------------------------------------------------------------

POSITIVE_EMOTIONS = {
    "admiration", "amusement", "approval", "caring", "desire",
    "excitement", "gratitude", "joy", "love", "optimism",
    "pride", "relief"
}

NEGATIVE_EMOTIONS = {
    "anger", "annoyance", "disappointment", "disapproval",
    "disgust", "embarrassment", "fear", "grief", "nervousness",
    "remorse", "sadness"
}


def derive_sentiment_from_emotion(emotion_label: str) -> str:
    """Maps GoEmotions fine-grained emotion labels to broad sentiment."""
    if emotion_label in POSITIVE_EMOTIONS:
        return "positive"
    if emotion_label in NEGATIVE_EMOTIONS:
        return "negative"
    return "neutral"


# -------------------------------------------------------------------
# Global ML Model & Database Containers
# -------------------------------------------------------------------

models: Dict[str, Any] = {}
qdrant_client: Optional[QdrantClient] = None


# -------------------------------------------------------------------
# Qdrant Database Helpers
# -------------------------------------------------------------------

def initialize_qdrant_collection():
    """Initialize Qdrant collection for embeddings if it doesn't exist."""
    global qdrant_client
    
    try:
        collections = qdrant_client.get_collections()
        collection_names = [collection.name for collection in collections.collections]
        
        if EMBEDDINGS_COLLECTION not in collection_names:
            qdrant_client.create_collection(
                collection_name=EMBEDDINGS_COLLECTION,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE
                )
            )
            print(f"Created Qdrant collection: {EMBEDDINGS_COLLECTION}")
    except Exception as e:
        print(f"Warning: Could not initialize Qdrant collection: {e}")


def store_embedding_in_qdrant(
    event_id: str,
    embedding_vector: List[float],
    metadata: Dict[str, Any]
) -> Optional[str]:
    """
    Stores embedding vector in Qdrant indexed natively by event_id.
    Returns string event_id upon successful insertion.
    """
    global qdrant_client
    
    try:
        point = PointStruct(
            id=event_id,  # Accepts standard UUID string directly
            vector=embedding_vector,
            payload={
                "event_id": event_id,
                "timestamp": metadata.get("timestamp_utc"),
                "source": metadata.get("source"),
                "author_id_hash": metadata.get("author_id_hash"),
                "language": metadata.get("language"),
                "sentiment": metadata.get("sentiment"),
                "emotion": metadata.get("emotion"),
                "stance": metadata.get("stance")
            }
        )
        
        qdrant_client.upsert(
            collection_name=EMBEDDINGS_COLLECTION,
            points=[point]
        )
        
        return str(event_id)
        
    except Exception as e:
        print(f"Error storing embedding in Qdrant: {e}")
        return None


# -------------------------------------------------------------------
# Lifespan Context Manager
# -------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Loads transformer models and connects to Qdrant at application startup."""
    global qdrant_client

    device = 0 if torch.cuda.is_available() else -1

    # 1. Language Detection
    models["lang_detector"] = pipeline(
        "text-classification",
        model="papluca/xlm-roberta-base-language-detection",
        device=device
    )

    # 2. Emotion Classification
    models["emotion_classifier"] = pipeline(
        "text-classification",
        model="SamLowe/roberta-base-go_emotions",
        top_k=1,
        device=device
    )

    # 3. Zero-Shot Stance Classification
    models["stance_classifier"] = pipeline(
        "zero-shot-classification",
        model="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        device=device
    )

    # 4. Sentence Embeddings
    models["embedding_model"] = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    # 5. Initialize Qdrant Client
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
    
    try:
        qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
        initialize_qdrant_collection()
        print(f"Connected to Qdrant at {qdrant_host}:{qdrant_port}")
    except Exception as e:
        print(f"Warning: Could not connect to Qdrant: {e}")
        qdrant_client = None

    yield

    # Cleanup resources during shutdown
    models.clear()
    if qdrant_client:
        qdrant_client.close()


# -------------------------------------------------------------------
# FastAPI Application
# -------------------------------------------------------------------

app = FastAPI(
    title="SIH26152 Social Media Analytics Backend",
    version="1.0.0",
    lifespan=lifespan
)


# -------------------------------------------------------------------
# Health Check Endpoint
# -------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "models_loaded": list(models.keys()),
        "qdrant_connected": qdrant_client is not None
    }


# -------------------------------------------------------------------
# Main Analysis Endpoint
# -------------------------------------------------------------------

@app.post(
    "/analyze",
    response_model=SocialMediaEventResponse
)
def process_social_event(
    payload: SocialMediaEventRequest
):
    """
    Synchronous 'def' forces FastAPI to handle inference in worker threads,
    preventing heavy PyTorch execution from blocking the main event loop.
    """
    try:
        text = payload.text.strip()

        if not text:
            raise HTTPException(
                status_code=400,
                detail="Text payload cannot be empty."
            )

        # -----------------------------------------------------------
        # 1. Language Detection
        # -----------------------------------------------------------
        lang_output = models["lang_detector"](
            text,
            truncation=True,
            max_length=512
        )[0]

        detected_lang = lang_output["label"]
        lang_conf = round(float(lang_output["score"]), 2)

        # -----------------------------------------------------------
        # 2. Emotion Classification & Derived Sentiment
        # -----------------------------------------------------------
        emotion_output = models["emotion_classifier"](
            text,
            truncation=True,
            max_length=512
        )[0][0]

        top_emotion = emotion_output["label"]
        emotion_conf = round(float(emotion_output["score"]), 2)

        derived_sentiment = derive_sentiment_from_emotion(top_emotion)
        sentiment_conf = emotion_conf

        # -----------------------------------------------------------
        # 3. Dynamic Zero-Shot Stance Detection
        # -----------------------------------------------------------
        target = payload.target_topic

        if target:
            hypothesis = f"This post expresses a stance towards {target}: {{}}."
        else:
            hypothesis = "The overall stance expressed in this post is {}."

        stance_candidate_labels = ["support", "oppose", "neutral"]

        stance_output = models["stance_classifier"](
            text,
            candidate_labels=stance_candidate_labels,
            hypothesis_template=hypothesis,
            truncation=True,
            max_length=512
        )

        top_stance = stance_output["labels"][0]
        top_stance_score = float(stance_output["scores"][0])

        if top_stance_score >= STANCE_THRESHOLD:
            final_stance = top_stance
        else:
            final_stance = "unknown"

        stance_conf = round(top_stance_score, 2)

        # -----------------------------------------------------------
        # 4. Generate and Store Vector Embeddings
        # -----------------------------------------------------------
        embedding_vector_list = models["embedding_model"].encode(
            text
        ).tolist()

        metadata = {
            "timestamp_utc": str(payload.timestamp_utc),
            "source": payload.source,
            "author_id_hash": payload.author_id_hash,
            "language": detected_lang,
            "sentiment": derived_sentiment,
            "emotion": top_emotion,
            "stance": final_stance
        }

        embedding_ref = None
        if qdrant_client:
            embedding_ref = store_embedding_in_qdrant(
                event_id=str(payload.event_id),
                embedding_vector=embedding_vector_list,
                metadata=metadata
            )

        # -----------------------------------------------------------
        # 5. Construct Final Response Payload
        # -----------------------------------------------------------
        return SocialMediaEventResponse(
            event_id=payload.event_id,
            language=ClassificationResult(
                label=detected_lang,
                confidence=lang_conf
            ),
            sentiment=ClassificationResult(
                label=derived_sentiment,
                confidence=sentiment_conf
            ),
            emotion=ClassificationResult(
                label=top_emotion,
                confidence=emotion_conf
            ),
            stance=StanceResult(
                target=payload.target_topic,
                label=final_stance,
                confidence=stance_conf
            ),
            embedding_ref=embedding_ref,
            evidence=[
                EvidenceItem(
                    type="source_event",
                    event_id=payload.event_id
                )
            ],
            model=ModelMeta(
                name="sih26152-ensemble-transformer",
                version="1.0.0"
            )
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Inference failure: {str(e)}"
        )
