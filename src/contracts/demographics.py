"""Audience demographics JSON contract — Section D standalone demographics
pillar (language / profession / geography), independent of the per-topic
`audience` field on SectionDPayload in `contracts/section_d.py`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DemographicEntry(BaseModel):
    value: str
    count: int = Field(ge=0)
    share: float = Field(ge=0.0, le=1.0)


class CategoryAudience(BaseModel):
    """One category's (language/profession/geography) distribution, always
    carrying its own sample_size/confidence/unknown_share since categories
    on the same topic can independently be under the minimum sample size."""

    distribution: list[DemographicEntry] = Field(default_factory=list)
    sample_size: int = Field(ge=0, default=0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    unknown_share: float = Field(ge=0.0, le=1.0, default=1.0)


class AudienceCategories(BaseModel):
    language: CategoryAudience = Field(default_factory=CategoryAudience)
    profession: CategoryAudience = Field(default_factory=CategoryAudience)
    geography: CategoryAudience = Field(default_factory=CategoryAudience)


class AudienceSnapshot(BaseModel):
    """Current ('now') audience snapshot for one topic."""

    topic_id: str
    as_of: datetime
    categories: AudienceCategories

    def to_json_dict(self) -> dict:
        return self.model_dump(mode="json")
