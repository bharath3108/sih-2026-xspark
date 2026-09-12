"""Aggregate audience demographics (language/profession/geography) for the
authors currently mapped to a topic.

Only aggregate counts/shares are ever produced here — no author_id-to-category
mapping is returned, logged, or otherwise exposed.
"""

from __future__ import annotations

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.contracts.demographics import AudienceCategories, CategoryAudience, DemographicEntry

CATEGORY_FIELDS: tuple[str, ...] = ("language", "profession", "geography")


class DemographicsEngine:
    """
    Expects `author_metadata`: {author_id: {language?, profession?, geography?}}
    for every author currently mapped to one topic (missing authors/fields are
    unknown for that category). All three signals are optional per author —
    a missing signal in one category never blocks aggregation of another.
    """

    def __init__(self, config: PipelineConfig = DEFAULT_CONFIG):
        self.config = config

    def compute(self, author_metadata: dict[str, dict]) -> AudienceCategories:
        total_authors = len(author_metadata)
        categories = {
            field: self._compute_category(
                [meta.get(field) for meta in author_metadata.values()],
                total_authors,
            )
            for field in CATEGORY_FIELDS
        }
        return AudienceCategories(**categories)

    def _compute_category(self, values: list[str | None], total_authors: int) -> CategoryAudience:
        known = [v for v in values if v]
        sample_size = len(known)
        confidence = round(min(1.0, sample_size / self.config.demographics_target_sample_size), 4)

        if total_authors == 0 or sample_size < self.config.demographics_min_sample_size:
            return CategoryAudience(
                distribution=[],
                sample_size=sample_size,
                confidence=confidence,
                unknown_share=1.0,
            )

        counts: dict[str, int] = {}
        for value in known:
            counts[value] = counts.get(value, 0) + 1

        distribution = [
            DemographicEntry(value=value, count=count, share=round(count / sample_size, 4))
            for value, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        ]

        return CategoryAudience(
            distribution=distribution,
            sample_size=sample_size,
            confidence=confidence,
            unknown_share=round(1.0 - (sample_size / total_authors), 4),
        )
