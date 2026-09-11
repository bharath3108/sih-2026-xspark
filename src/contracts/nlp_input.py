"""Person 2 NLP Output Contract — inbound ingestion payload."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Platform(str, Enum):
    X = "X"
    TELEGRAM = "Telegram"
    REDDIT = "Reddit"
    YOUTUBE = "YouTube"


class InteractionCounts(BaseModel):
    likes: int = Field(ge=0, default=0)
    shares: int = Field(ge=0, default=0)
    comments: int = Field(ge=0, default=0)

    @property
    def total(self) -> int:
        return self.likes + self.shares + self.comments


class SentimentBlock(BaseModel):
    label: str | None = None
    score: float | None = None


class MetricsBlock(BaseModel):
    engagement: int = Field(ge=0, default=0)
    likes: int = Field(ge=0, default=0)
    shares: int = Field(ge=0, default=0)
    comments: int = Field(ge=0, default=0)


class NLPOutputContract(BaseModel):
    """Input contract from Person 2 NLP pipeline (flat or nested metrics)."""

    event_id: str
    timestamp: datetime
    platform: Platform
    embedding_ref: str
    author_id: str
    likes: int = Field(ge=0, default=0)
    shares: int = Field(ge=0, default=0)
    comments: int = Field(ge=0, default=0)
    raw_text: str | None = None
    sentiment: SentimentBlock | None = None
    metrics: MetricsBlock | None = None

    @property
    def interactions(self) -> InteractionCounts:
        return InteractionCounts(
            likes=self.likes, shares=self.shares, comments=self.comments
        )

    @property
    def engagement_total(self) -> int:
        if self.metrics and self.metrics.engagement:
            return self.metrics.engagement
        return self.likes + self.shares + self.comments

    @property
    def sentiment_label(self) -> str | None:
        return self.sentiment.label if self.sentiment else None


class IngestedEvent(BaseModel):
    """Enriched event after vector resolution."""

    event_id: str
    timestamp: datetime
    platform: Platform
    author_id: str
    likes: int
    shares: int
    comments: int
    raw_text: str | None = None
    vector: list[float]
    topic_id: str | None = None

    @classmethod
    def from_nlp(cls, payload: NLPOutputContract, vector: list[float]) -> "IngestedEvent":
        return cls(
            event_id=payload.event_id,
            timestamp=payload.timestamp,
            platform=payload.platform,
            author_id=payload.author_id,
            likes=payload.likes,
            shares=payload.shares,
            comments=payload.comments,
            raw_text=payload.raw_text,
            vector=vector,
        )

    @property
    def engagement(self) -> int:
        return self.likes + self.shares + self.comments
