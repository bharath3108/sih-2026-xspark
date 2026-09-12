"""Pydantic models for the versioned JSON contracts defined in the team work plan.

Each model mirrors a contract another person owns (canonical event = Person 1,
NLP output = Person 2, topic = Person 3, network = Person 4) plus the
investigation contract Person 5 (dashboard/integration) owns. Person 5 reads
these shapes but never imports another person's internal modules — only their
published JSON.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["x", "telegram", "reddit", "instagram", "other"]
SentimentLabel = Literal["positive", "negative", "neutral"]
StanceLabel = Literal["support", "oppose", "neutral", "unknown"]


class Engagement(BaseModel):
    likes: int = 0
    shares: int = 0
    comments: int = 0
    views: int = 0


class EventMetadata(BaseModel):
    source_version: str
    collected_at_utc: str


class CanonicalEvent(BaseModel):
    """Person 1's contract. All other modules consume this."""

    event_id: str
    source: Source
    source_post_id: str
    author_id_hash: str
    timestamp_utc: str
    text: str
    language: str
    reply_to_id: str | None = None
    parent_event_id: str | None = None
    engagement: Engagement
    entities: list[str] = Field(default_factory=list)
    metadata: EventMetadata


class LabelConfidence(BaseModel):
    label: str
    confidence: float


class Stance(BaseModel):
    target: str | None
    label: StanceLabel
    confidence: float


class Evidence(BaseModel):
    type: str
    event_id: str


class ModelInfo(BaseModel):
    name: str
    version: str


class NLPOutput(BaseModel):
    """Person 2's contract. Enriches an event without replacing its text."""

    event_id: str
    language: LabelConfidence
    sentiment: LabelConfidence
    emotion: LabelConfidence | None = None
    stance: Stance
    embedding_ref: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    model: ModelInfo


class Window(BaseModel):
    start: str
    end: str


class TopicMetrics(BaseModel):
    volume: int
    unique_authors: int
    engagement: int
    trend_score: float
    novelty: float
    cross_community_spread: float


class TopicTimelinePoint(BaseModel):
    bucket_start: str
    volume: int
    unique_authors: int
    engagement: int
    avg_sentiment: float


class Audience(BaseModel):
    categories: dict[str, float]
    unknown_share: float
    sample_size: int
    confidence: float


class Topic(BaseModel):
    """Person 3's contract: topics/trends/aggregate demographics."""

    topic_id: str
    name: str
    window: Window
    metrics: TopicMetrics
    timeline: list[TopicTimelinePoint] = Field(default_factory=list)
    audience: Audience
    evidence_event_ids: list[str] = Field(default_factory=list)


class GraphMetrics(BaseModel):
    nodes: int
    edges: int
    density: float


class Community(BaseModel):
    community_id: str
    size: int
    central_nodes: list[str]


class Propagation(BaseModel):
    depth: int
    cross_community_rate: float
    key_nodes: list[str]


class NetworkOutput(BaseModel):
    """Person 4's contract: network topology, communities, propagation."""

    window: Window
    graph_metrics: GraphMetrics
    communities: list[Community]
    propagation: Propagation
    evidence_event_ids: list[str] = Field(default_factory=list)


class InvestigationQuery(BaseModel):
    topic_id: str
    start: str
    end: str


class InvestigationFinding(BaseModel):
    narrative: dict = Field(default_factory=dict)
    nlp: dict = Field(default_factory=dict)
    audience: dict = Field(default_factory=dict)
    network: dict = Field(default_factory=dict)


class Claim(BaseModel):
    claim: str
    confidence: float
    evidence_event_ids: list[str] = Field(default_factory=list)


class Investigation(BaseModel):
    """Person 5 owns the final composition. It consumes outputs; it does not
    invent analytical values — every claim must trace back to evidence_event_ids
    and every metric must come from a contract another module published."""

    investigation_id: str
    query: InvestigationQuery
    finding: InvestigationFinding
    claims: list[Claim] = Field(default_factory=list)
    models: list[ModelInfo] = Field(default_factory=list)
    generated_at_utc: str
