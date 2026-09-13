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

        pipeline = SectionDPipeline(author_metadata=_load_author_metadata())
        pipeline.connect_external_stores()
        _pipeline = pipeline
    except Exception as e:
        logger.warning("Live SectionDPipeline unavailable (Redis/Qdrant not reachable?): %s", e)
        _unavailable = True
    return _pipeline


def _load_author_metadata() -> dict:
    """SectionDPipeline takes its whole author_metadata dict once, up front
    at construction time (see scripts/run_demo.py) rather than looking
    authors up lazily as events stream in, so this reads the entire static
    fixture eagerly instead of the per-author-id lookup
    StaticAuthorMetadataSource.get_metadata() is shaped for -- we don't know
    which author ids will show up until events actually arrive."""
    import json

    from src.config import DEFAULT_CONFIG

    path = DEFAULT_CONFIG.author_metadata_static_path
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not load author metadata fixture %s: %s", path, e)
        return {}


def ingest_nlp_output(nlp_contract, embedding_vector: list[float] | None = None) -> None:
    pipeline = get_pipeline()
    if pipeline is None:
        return
    try:
        _ensure_embedding_stored(pipeline, nlp_contract, embedding_vector)
        pipeline.ingest(nlp_contract)
    except Exception as e:
        logger.warning("Live pipeline ingest failed for event %s: %s", getattr(nlp_contract, "event_id", "?"), e)


def _ensure_embedding_stored(pipeline, nlp_contract, embedding_vector: list[float] | None) -> None:
    """SectionDPipeline.ingest() resolves nlp_contract.embedding_ref through
    its own EmbeddingStore (src/storage/embedding_store.py), which is a
    separate store from the Qdrant collection ml/mainml.py writes to
    (different collection, and keyed by an `embedding_ref` payload field
    mainml.py's points never set) -- so a ref computed by mainml.py is never
    actually resolvable here. Storing the caller-supplied vector (the real
    one ml/mainml.py already computed -- a real transformer embedding when
    its models are loaded, its own lexicon fallback otherwise) under that
    ref closes that gap without changing either module's public contract;
    only when the caller has none do we recompute our own fallback from
    raw_text, so real embeddings are never discarded in favor of a cruder
    hash-based stand-in."""
    ref = getattr(nlp_contract, "embedding_ref", None)
    if not ref:
        return
    try:
        pipeline.embedding_store.fetch(ref)
        return
    except KeyError:
        pass
    if embedding_vector:
        pipeline.embedding_store.store(ref, embedding_vector)
        return
    text = getattr(nlp_contract, "raw_text", None)
    if not text:
        return
    from ml.mainml import fallback_embedding

    pipeline.embedding_store.store(ref, fallback_embedding(text))


def get_live_topics() -> list[dict]:
    pipeline = get_pipeline()
    if pipeline is None:
        return []
    try:
        return [p.to_json_dict() for p in pipeline.build_all_section_d()]
    except Exception:
        logger.exception("Live topic build failed")
        return []
