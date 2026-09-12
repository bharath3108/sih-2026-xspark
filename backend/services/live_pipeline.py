"""Best-effort in-process bridge from newly-ingested events into Person 3's
SectionDPipeline (topics/trends/audience).

SectionDPipeline needs Redis + Qdrant, which may not be running. Per the
project's own rule ("the dashboard must remain usable when a source or
model is unavailable"), a missing/unreachable pipeline degrades silently —
callers get None/no-op instead of a crash, and backend/services/data_access.py
falls back to the checked-in fixtures whenever this has nothing to offer.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_pipeline = None
_unavailable = False


def get_pipeline():
    global _pipeline, _unavailable
    if _pipeline is not None or _unavailable:
        return _pipeline
    try:
        from src.pipeline.orchestrator import SectionDPipeline

        pipeline = SectionDPipeline()
        pipeline.connect_external_stores()
        _pipeline = pipeline
    except Exception as e:
        logger.warning("Live SectionDPipeline unavailable (Redis/Qdrant not reachable?): %s", e)
        _unavailable = True
    return _pipeline


def ingest_nlp_output(nlp_contract) -> None:
    pipeline = get_pipeline()
    if pipeline is None:
        return
    try:
        pipeline.ingest(nlp_contract)
    except Exception as e:
        logger.warning("Live pipeline ingest failed for event %s: %s", getattr(nlp_contract, "event_id", "?"), e)


def get_live_topics() -> list[dict]:
    pipeline = get_pipeline()
    if pipeline is None:
        return []
    try:
        return [p.to_json_dict() for p in pipeline.build_all_section_d()]
    except Exception as e:
        logger.warning("Live topic build failed: %s", e)
        return []
