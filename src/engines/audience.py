"""Audience profiling for Section D payload (derived from author metadata)."""

from __future__ import annotations

from src.contracts.section_d import Audience, AudienceCategories


class AudienceEngine:
    """
    Computes audience distribution categories.
    Expects optional author metadata from upstream enrichment.
    """

    def compute(
        self,
        author_ids: list[str],
        author_metadata: dict[str, dict] | None = None,
    ) -> Audience:
        if not author_ids or not author_metadata:
            return Audience(
                categories=AudienceCategories(),
                unknown_share=1.0,
                sample_size=len(author_ids),
                confidence=0.0,
            )

        profession_counts: dict[str, int] = {}
        geography_counts: dict[str, int] = {}
        known = 0

        for aid in author_ids:
            meta = author_metadata.get(aid, {})
            if not meta:
                continue
            known += 1
            prof = meta.get("profession", "Other")
            geo = meta.get("geography", "Unknown")
            profession_counts[prof] = profession_counts.get(prof, 0) + 1
            geography_counts[geo] = geography_counts.get(geo, 0) + 1

        total = len(author_ids)
        unknown_share = 1.0 - (known / total) if total > 0 else 1.0

        def normalize(counts: dict[str, int]) -> dict[str, float]:
            s = sum(counts.values())
            if s == 0:
                return {}
            return {k: round(v / s, 2) for k, v in counts.items()}

        confidence = round(known / total, 2) if total > 0 else 0.0

        return Audience(
            categories=AudienceCategories(
                profession=normalize(profession_counts),
                geography=normalize(geography_counts),
            ),
            unknown_share=round(unknown_share, 2),
            sample_size=total,
            confidence=confidence,
        )
