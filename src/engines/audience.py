"""Audience profiling for Section D payload (derived from author metadata)."""

from __future__ import annotations

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.contracts.section_d import Audience


class AudienceEngine:
    """
    Computes an aggregate, probabilistic audience distribution (profession
    breakdown) for the authors mapped to a topic. Applies the same
    minimum-sample-size gate as src/engines/demographics.py's
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
            prof = meta.get("profession")
            if not prof:
                continue
            known += 1
            counts[prof] = counts.get(prof, 0) + 1

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
