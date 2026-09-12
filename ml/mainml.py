import hashlib
import math
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID

import transformers
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

LANG_MODEL_ID = "papluca/xlm-roberta-base-language-detection"
EMOTION_MODEL_ID = "SamLowe/roberta-base-go_emotions"
STANCE_MODEL_ID = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
EMBEDDING_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"

FALLBACK_MODEL_NAME = "local-lexicon-fallback"
FALLBACK_MODEL_VERSION = "1.0"


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
    source_post_id: Optional[str] = None


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
# Deterministic Local Fallbacks
#
# Required so the service degrades gracefully (never crashes, never blocks
# the demo) if a transformer model fails to load/run at runtime — e.g. no
# network access to the HF hub. These are intentionally simple, offline,
# reproducible heuristics, not a second ML stack.
# -------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-zA-Z']+")

_COMMON_EN_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "in", "it",
    "this", "that", "for", "on", "with", "and", "but", "not", "you", "we",
}

_POSITIVE_WORDS = {
    "good", "great", "love", "happy", "excellent", "amazing", "support",
    "win", "best", "glad", "thanks", "thank", "awesome", "proud", "hope",
}

_NEGATIVE_WORDS = {
    "bad", "hate", "terrible", "angry", "worst", "fail", "failed", "sad",
    "awful", "disgusting", "scam", "fraud", "afraid", "fear", "wrong",
}

_NEGATION_WORDS = {"not", "no", "never", "against", "oppose", "opposed", "anti", "reject"}


def fallback_detect_language(text: str) -> tuple[str, float]:
    tokens = _WORD_RE.findall(text.lower())
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
    if ascii_ratio < 0.9:
        return "und", 0.3
    hits = sum(1 for t in tokens if t in _COMMON_EN_WORDS)
    return "en", (0.5 if hits > 0 else 0.35)


def fallback_sentiment_emotion(text: str) -> tuple[str, str, float]:
    tokens = _WORD_RE.findall(text.lower())
    pos = sum(1 for t in tokens if t in _POSITIVE_WORDS)
    neg = sum(1 for t in tokens if t in _NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return "neutral", "neutral", 0.34
    if pos > neg:
        return "positive", "optimism", round(min(0.5 + 0.5 * (pos - neg) / total, 0.9), 2)
    if neg > pos:
        return "negative", "anger", round(min(0.5 + 0.5 * (neg - pos) / total, 0.9), 2)
    return "neutral", "neutral", 0.4


def fallback_stance(text: str, target: str) -> tuple[str, float]:
    target_tokens = set(_WORD_RE.findall(target.lower()))
    tokens = _WORD_RE.findall(text.lower())
    if not target_tokens or not (target_tokens & set(tokens)):
        return "unknown", 0.0
    neg_hits = sum(1 for t in tokens if t in _NEGATION_WORDS)
    pos_hits = sum(1 for t in tokens if t in _POSITIVE_WORDS)
    if neg_hits > pos_hits:
        return "oppose", 0.4
    if pos_hits > neg_hits:
        return "support", 0.4
    return "neutral", 0.3


def fallback_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """Deterministic hashing-trick pseudo-embedding — keeps embedding_ref /
    downstream clustering functional (right dimensionality) without a model."""
    vec = [0.0] * dim
    tokens = _WORD_RE.findall(text.lower()) or [text]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


# -------------------------------------------------------------------
# Global ML Model & Database Containers
# -------------------------------------------------------------------

models: Dict[str, Any] = {}
qdrant_client: Optional[QdrantClient] = None

# Tracks whether each transformer model loaded successfully at startup, so a
# failed download/OOM degrades a single signal to its deterministic fallback
# instead of taking down the whole /analyze endpoint.
MODEL_STATUS: Dict[str, bool] = {
    "lang_detector": False,
    "emotion_classifier": False,
    "stance_classifier": False,
    "embedding_model": False,
}


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

    # Each model load is isolated: if the HF hub is unreachable or a single
    # model OOMs, that one signal falls back to a deterministic local
    # heuristic at request time instead of the whole service failing to boot.

    # 1. Language Detection
    try:
        models["lang_detector"] = pipeline(
            "text-classification",
            model=LANG_MODEL_ID,
            device=device
        )
        MODEL_STATUS["lang_detector"] = True
    except Exception as e:
        print(f"Warning: Could not load language detector ({LANG_MODEL_ID}): {e}")

    # 2. Emotion Classification
    try:
        models["emotion_classifier"] = pipeline(
            "text-classification",
            model=EMOTION_MODEL_ID,
            top_k=1,
            device=device
        )
        MODEL_STATUS["emotion_classifier"] = True
    except Exception as e:
        print(f"Warning: Could not load emotion classifier ({EMOTION_MODEL_ID}): {e}")

    # 3. Zero-Shot Stance Classification
    try:
        models["stance_classifier"] = pipeline(
            "zero-shot-classification",
            model=STANCE_MODEL_ID,
            device=device
        )
        MODEL_STATUS["stance_classifier"] = True
    except Exception as e:
        print(f"Warning: Could not load stance classifier ({STANCE_MODEL_ID}): {e}")

    # 4. Sentence Embeddings
    try:
        models["embedding_model"] = SentenceTransformer(EMBEDDING_MODEL_ID)
        MODEL_STATUS["embedding_model"] = True
    except Exception as e:
        print(f"Warning: Could not load embedding model ({EMBEDDING_MODEL_ID}): {e}")

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
        "models_loaded": [name for name, ok in MODEL_STATUS.items() if ok],
        "models_on_fallback": [name for name, ok in MODEL_STATUS.items() if not ok],
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

        used_fallback = False

        # -----------------------------------------------------------
        # 1. Language Detection
        # -----------------------------------------------------------
        if MODEL_STATUS["lang_detector"]:
            lang_output = models["lang_detector"](
                text,
                truncation=True,
                max_length=512
            )[0]
            detected_lang = lang_output["label"]
            lang_conf = round(float(lang_output["score"]), 2)
        else:
            detected_lang, lang_conf = fallback_detect_language(text)

        # -----------------------------------------------------------
        # 2. Emotion Classification & Derived Sentiment
        # -----------------------------------------------------------
        if MODEL_STATUS["emotion_classifier"]:
            emotion_output = models["emotion_classifier"](
                text,
                truncation=True,
                max_length=512
            )[0][0]

            top_emotion = emotion_output["label"]
            emotion_conf = round(float(emotion_output["score"]), 2)
            derived_sentiment = derive_sentiment_from_emotion(top_emotion)
            sentiment_conf = emotion_conf
        else:
            used_fallback = True
            derived_sentiment, top_emotion, emotion_conf = fallback_sentiment_emotion(text)
            sentiment_conf = emotion_conf

        # -----------------------------------------------------------
        # 3. Zero-Shot Stance Detection Toward an Explicit Target
        #
        # Stance is only meaningful relative to a target; without one there
        # is nothing to be "for" or "against" so we report unknown rather
        # than scoring a made-up generic hypothesis.
        # -----------------------------------------------------------
        target = payload.target_topic

        if not target:
            final_stance = "unknown"
            stance_conf = 0.0
        elif MODEL_STATUS["stance_classifier"]:
            hypothesis = f"This post expresses a stance towards {target}: {{}}."
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

            final_stance = top_stance if top_stance_score >= STANCE_THRESHOLD else "unknown"
            stance_conf = round(top_stance_score, 2)
        else:
            used_fallback = True
            final_stance, stance_conf = fallback_stance(text, target)

        # -----------------------------------------------------------
        # 4. Generate and Store Vector Embeddings
        # -----------------------------------------------------------
        if MODEL_STATUS["embedding_model"]:
            embedding_vector_list = models["embedding_model"].encode(text).tolist()
        else:
            embedding_vector_list = fallback_embedding(text)

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
                    event_id=payload.event_id,
                    source_post_id=payload.source_post_id
                )
            ],
            model=(
                ModelMeta(name=FALLBACK_MODEL_NAME, version=FALLBACK_MODEL_VERSION)
                if used_fallback
                else ModelMeta(name=EMOTION_MODEL_ID, version=transformers.__version__)
            )
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Inference failure: {str(e)}"
        )
