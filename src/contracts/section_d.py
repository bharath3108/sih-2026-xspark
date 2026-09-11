"""Section D JSON Output Contract — final trend payload."""

from datetime import datetime

from pydantic import BaseModel, Field


class TimeWindow(BaseModel):
    start: datetime
    end: datetime


class TopicMetrics(BaseModel):
    volume: int
    unique_authors: int
    engagement: int
    trend_score: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    cross_community_spread: float = Field(ge=0.0, le=1.0)


class TimelineBucket(BaseModel):
    bucket_start: datetime
    volume: int
    authors: int
    status: str


class AudienceCategories(BaseModel):
    profession: dict[str, float] = Field(default_factory=dict)
    geography: dict[str, float] = Field(default_factory=dict)


class Audience(BaseModel):
    categories: AudienceCategories
    unknown_share: float = Field(ge=0.0, le=1.0, default=0.0)
    sample_size: int = Field(ge=0, default=0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class SectionDPayload(BaseModel):
    """Final Section D JSON payload."""

    topic_id: str
    name: str
    window: TimeWindow
    metrics: TopicMetrics
    timeline: list[TimelineBucket]
    audience: Audience
    evidence_event_ids: list[str]

    def to_json_dict(self) -> dict:
        return self.model_dump(mode="json")
