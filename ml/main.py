from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

import torch
from transformers import pipeline
from sentence_transformers import SentenceTransformer


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

# MVP threshold.
# Tune this using a labeled validation dataset before deployment.
STANCE_THRESHOLD = 0.60


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
    "admiration",
    "amusement",
    "approval",
    "caring",
    "desire",
    "excitement",
    "gratitude",
    "joy",
    "love",
    "optimism",
    "pride",
    "relief"
}

NEGATIVE_EMOTIONS = {
    "anger",
    "annoyance",
    "disappointment",
    "disapproval",
    "disgust",
    "embarrassment",
    "fear",
    "grief",
    "nervousness",
    "remorse",
    "sadness"
}


def derive_sentiment_from_emotion(
    emotion_label: str
) -> str:
    """
    Maps GoEmotions fine-grained emotion labels
    to broad sentiment.
    """

    if emotion_label in POSITIVE_EMOTIONS:
        return "positive"

    if emotion_label in NEGATIVE_EMOTIONS:
        return "negative"

    return "neutral"


# -------------------------------------------------------------------
# Global ML Model Container
# -------------------------------------------------------------------

models: Dict[str, Any] = {}


# -------------------------------------------------------------------
# Lifespan Context Manager
# -------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Loads all transformer models once at application startup.
    """

    device = 0 if torch.cuda.is_available() else -1

    # ---------------------------------------------------------------
    # 1. Language Detection
    # ---------------------------------------------------------------

    models["lang_detector"] = pipeline(
        "text-classification",
        model="papluca/xlm-roberta-base-language-detection",
        device=device
    )

    # ---------------------------------------------------------------
    # 2. Emotion Classification
    # ---------------------------------------------------------------

    models["emotion_classifier"] = pipeline(
        "text-classification",
        model="SamLowe/roberta-base-go_emotions",
        top_k=1,
        device=device
    )

    # ---------------------------------------------------------------
    # 3. Zero-Shot Stance Classification
    # ---------------------------------------------------------------

    models["stance_classifier"] = pipeline(
        "zero-shot-classification",
        model="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        device=device
    )

    # ---------------------------------------------------------------
    # 4. Sentence Embedding Model
    # ---------------------------------------------------------------

    models["embedding_model"] = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    yield

    # ---------------------------------------------------------------
    # Shutdown
    # ---------------------------------------------------------------

    models.clear()


# -------------------------------------------------------------------
# FastAPI Application
# -------------------------------------------------------------------

app = FastAPI(
    title="SIH26152 Social Media Analytics Backend",
    version="1.0.0",
    lifespan=lifespan
)


# -------------------------------------------------------------------
# Health Check
# -------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "models_loaded": list(models.keys())
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
    Synchronous endpoint so FastAPI can run the heavy
    transformer inference in its worker threadpool.
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

        lang_conf = round(
            float(lang_output["score"]),
            2
        )

        # -----------------------------------------------------------
        # 2. Emotion Classification
        # -----------------------------------------------------------

        emotion_output = models["emotion_classifier"](
            text,
            truncation=True,
            max_length=512
        )[0][0]

        top_emotion = emotion_output["label"]

        emotion_conf = round(
            float(emotion_output["score"]),
            2
        )

        # -----------------------------------------------------------
        # 3. Sentiment Derived from Emotion
        # -----------------------------------------------------------

        derived_sentiment = derive_sentiment_from_emotion(
            top_emotion
        )

        # Sentiment is derived from emotion, so its confidence
        # is inherited from the emotion prediction.
        sentiment_conf = emotion_conf

        # -----------------------------------------------------------
        # 4. Zero-Shot Stance Detection
        # -----------------------------------------------------------

        target = payload.target_topic

        if target:
            hypothesis = (
                f"This post expresses a stance towards "
                f"{target}: {{}}."
            )
        else:
            hypothesis = (
                "The overall stance expressed in this post is {}."
            )

        stance_candidate_labels = [
            "support",
            "oppose",
            "neutral"
        ]

        stance_output = models["stance_classifier"](
            text,
            candidate_labels=stance_candidate_labels,
            hypothesis_template=hypothesis,
            truncation=True,
            max_length=512
        )

        # Hugging Face returns labels ordered by score.
        top_stance = stance_output["labels"][0]

        top_stance_score = float(
            stance_output["scores"][0]
        )

        # -----------------------------------------------------------
        # 5. Threshold-Based Unknown Classification
        # -----------------------------------------------------------

        if top_stance_score >= STANCE_THRESHOLD:
            final_stance = top_stance
        else:
            final_stance = "unknown"

        stance_conf = round(
            top_stance_score,
            2
        )

        # -----------------------------------------------------------
        # 6. Embedding Reference
        # -----------------------------------------------------------

        # No vector database is connected yet.
        #
        # Do NOT generate an embedding just to throw it away.
        # Once Qdrant/Milvus/etc. is integrated, generate the
        # embedding here, store it, and return the resulting ID.
        embedding_ref = None

        # -----------------------------------------------------------
        # 7. Response
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

    # ---------------------------------------------------------------
    # Preserve intentional HTTP errors
    # ---------------------------------------------------------------

    except HTTPException:
        raise

    # ---------------------------------------------------------------
    # Unexpected inference/server errors
    # ---------------------------------------------------------------

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Inference failure: {str(e)}"
        )
