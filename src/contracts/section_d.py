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
    """Matches backend/schemas/contracts.py's TopicTimelinePoint (the
    documented/dashboard-facing contract): bucket_start/volume/unique_authors/
    engagement/avg_sentiment are all required there. `status` (lifecycle
    phase) is extra info beyond that contract, kept because the work plan
    explicitly asks for first-appearance/acceleration/peak/decline detection;
    pydantic ignores unknown fields on validation so it doesn't break
    Topic.model_validate() against the documented contract."""

    bucket_start: datetime
    volume: int
    unique_authors: int
    engagement: int = 0
    avg_sentiment: float = 0.0
    status: str


class Audience(BaseModel):
    """categories is a flat dict (e.g. {"developer": 0.42, "investor": 0.31})
    matching backend/schemas/contracts.py's Audience + data/fixtures/topics.json
    -- not the nested {profession:{}, geography:{}} shape this used to have."""

    categories: dict[str, float] = Field(default_factory=dict)
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
