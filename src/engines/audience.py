"""Audience profiling for Section D payload (derived from author metadata)."""

from __future__ import annotations

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.contracts.section_d import Audience

# Every metadata field folded into the flat `categories` distribution, each
# under its own "field:value" key so the (deliberately flat -- see
# src/contracts/section_d.py's Audience docstring) shape can still carry more
# than one demographic dimension without values from different fields (e.g.
# a profession and a country) colliding under the same bare key.
CATEGORY_FIELDS: tuple[str, ...] = ("profession", "geography", "age_group")


class AudienceEngine:
    """
    Computes an aggregate, probabilistic audience distribution (profession /
    geography / age_group breakdown) for the authors mapped to a topic.
    Applies the same minimum-sample-size gate as src/engines/demographics.py's
    DemographicsEngine (the spec requires "apply minimum-sample thresholds
    and avoid individual-level demographic output" -- this engine used to
    have no such gate at all, reporting confidence=1.0 off a single author).
    """

    def __init__(self, config: PipelineConfig = DEFAULT_CONFIG):
        self.config = config

    def compute(
        self,
        author_ids: list[str],
        author_metadata: dict[str, dict] | None = None,
    ) -> Audience:
        total = len(author_ids)
        author_metadata = author_metadata or {}

        counts: dict[str, int] = {}
        known = 0
        for aid in author_ids:
            meta = author_metadata.get(aid) or {}
            has_any_field = False
            for field in CATEGORY_FIELDS:
                value = meta.get(field)
                if not value:
                    continue
                has_any_field = True
                key = f"{field}:{value}"
                counts[key] = counts.get(key, 0) + 1
            if has_any_field:
                known += 1

        confidence = round(min(1.0, known / self.config.demographics_target_sample_size), 4) if total else 0.0

        if total == 0 or known < self.config.demographics_min_sample_size:
            return Audience(
                categories={},
                unknown_share=1.0,
                sample_size=known,
                confidence=confidence,
            )

        categories = {k: round(v / known, 2) for k, v in counts.items()}

        return Audience(
            categories=categories,
            unknown_share=round(1.0 - (known / total), 2),
            sample_size=known,
            confidence=confidence,
        )
