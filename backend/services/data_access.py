"""Single point where the dashboard composition layer reads each contract.

Each loader tries, in order: (1) an HTTP call to that person's own service if
its PERSON*_API_BASE env var is set, (2) real data already computed
in-process (DB rows from ingestion, or Person 3/4's live pipeline/graph
engine), (3) the checked-in fixture under data/fixtures/ as a last resort so
the dashboard never breaks. Route/view code in backend/api/dashboard.py never
talks to fixtures or other services directly -- this module is the one place
to swap in a real HTTP call to that person's service later.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import httpx

from backend.services import live_pipeline

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Defaults to the team's versioned contract fixtures. FIXTURES_DIR lets a
# deployment point at a different contract-shaped directory (the hosted demo
# uses data/fixtures_demo) without touching the fixtures the test suite and
# every other module are pinned to.
FIXTURES_DIR = Path(os.getenv("FIXTURES_DIR") or _REPO_ROOT / "data" / "fixtures")
if not FIXTURES_DIR.is_absolute():
    FIXTURES_DIR = _REPO_ROOT / FIXTURES_DIR

PERSON1_API_BASE = os.getenv("PERSON1_API_BASE")  # canonical events
PERSON2_API_BASE = os.getenv("PERSON2_API_BASE")  # NLP outputs
PERSON3_API_BASE = os.getenv("PERSON3_API_BASE")  # topics/trends/audience
PERSON4_API_BASE = os.getenv("PERSON4_API_BASE")  # network/graph


def _load_fixture(filename: str) -> dict | list:
    with open(FIXTURES_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _db_session():
    try:
        from backend.db.database import SessionLocal

        return SessionLocal()
    except Exception as e:
        logger.warning("DB unavailable: %s", e)
        return None


def _canonical_row_to_dict(row) -> dict:
    ts = row.timestamp_utc
    return {
        "event_id": row.event_id,
        "source": row.source,
        "source_post_id": row.source_post_id,
        "author_id_hash": row.author_id_hash,
        "timestamp_utc": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
        "text": row.text,
        "language": row.language or "en",
        "reply_to_id": row.reply_to_id,
        "parent_event_id": row.parent_event_id,
        "engagement": row.engagement or {"likes": 0, "shares": 0, "comments": 0, "views": 0},
        "entities": row.entities or [],
        "metadata": row.event_metadata or {"source_version": "1.0.0", "collected_at_utc": ts.isoformat() if hasattr(ts, "isoformat") else str(ts)},
    }


def _get_live_canonical_events() -> list[dict]:
    db = _db_session()
    if db is None:
        return []
    try:
        from backend.db.models import CanonicalEventModel

        rows = db.query(CanonicalEventModel).all()
        return [_canonical_row_to_dict(r) for r in rows]
    except Exception as e:
        logger.warning("Live canonical event read failed: %s", e)
        return []
    finally:
        db.close()


def _nlp_row_to_dict(row) -> dict:
    return {
        "event_id": row.event_id,
        "language": row.language or {"label": "en", "confidence": 0.0},
        "sentiment": row.sentiment or {"label": "neutral", "confidence": 0.0},
        "emotion": row.emotion,
        "stance": row.stance or {"target": None, "label": "unknown", "confidence": 0.0},
        "embedding_ref": row.embedding_ref,
        "evidence": row.evidence or [],
        "model": row.model or {"name": "unknown", "version": "unknown"},
    }


def _get_live_nlp_outputs() -> list[dict]:
    db = _db_session()
    if db is None:
        return []
    try:
        from backend.db.models import NLPOutputModel

        rows = db.query(NLPOutputModel).all()
        return [_nlp_row_to_dict(r) for r in rows]
    except Exception as e:
        logger.warning("Live NLP output read failed: %s", e)
        return []
    finally:
        db.close()


def _infer_window(events: list[dict]) -> tuple[str, str]:
    timestamps = sorted(e["timestamp_utc"] for e in events if e.get("timestamp_utc"))
    if timestamps:
        return timestamps[0], timestamps[-1]
    now = datetime.now(timezone.utc).isoformat()
    return now, now


@lru_cache(maxsize=1)
def get_canonical_events() -> list[dict]:
    if PERSON1_API_BASE:
        resp = httpx.get(f"{PERSON1_API_BASE}/events", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    live = _get_live_canonical_events()
    return live if live else _load_fixture("canonical_events.json")


@lru_cache(maxsize=1)
def get_nlp_outputs() -> list[dict]:
    if PERSON2_API_BASE:
        resp = httpx.get(f"{PERSON2_API_BASE}/nlp-outputs", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    live = _get_live_nlp_outputs()
    return live if live else _load_fixture("nlp_outputs.json")


@lru_cache(maxsize=1)
def get_topics() -> list[dict]:
    if PERSON3_API_BASE:
        resp = httpx.get(f"{PERSON3_API_BASE}/topics", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    live = live_pipeline.get_live_topics()
    return live if live else _load_fixture("topics.json")


@lru_cache(maxsize=1)
def get_network() -> dict:
    if PERSON4_API_BASE:
        resp = httpx.get(f"{PERSON4_API_BASE}/network", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    events = get_canonical_events()
    live_events = _get_live_canonical_events()
    if not live_events:
        return _load_fixture("network_output.json")
    try:
        from graph.engine import analyze_network

        start, end = _infer_window(live_events)
        return analyze_network(live_events, start, end)
    except Exception as e:
        logger.warning("Live network analysis failed: %s", e)
        return _load_fixture("network_output.json")


@lru_cache(maxsize=1)
def get_network_topology() -> dict:
    """Node/edge list for the visual graph. Not yet part of Person 4's
    published contract (which only exposes summary metrics + community
    membership) — this is a Person-5 fixture standing in until real events
    exist, kept separate so it's obvious what's contractual vs. a
    visualization aid."""
    if PERSON4_API_BASE:
        resp = httpx.get(f"{PERSON4_API_BASE}/network/topology", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    live_events = _get_live_canonical_events()
    if not live_events:
        return _load_fixture("network_edges.json")
    try:
        from graph.engine import build_network_topology

        return build_network_topology(live_events)
    except Exception as e:
        logger.warning("Live network topology build failed: %s", e)
        return _load_fixture("network_edges.json")


def get_event_by_id(event_id: str) -> dict | None:
    return next((e for e in get_canonical_events() if e["event_id"] == event_id), None)


def get_nlp_output_by_event_id(event_id: str) -> dict | None:
    return next((n for n in get_nlp_outputs() if n["event_id"] == event_id), None)


def get_topic_by_id(topic_id: str) -> dict | None:
    return next((t for t in get_topics() if t["topic_id"] == topic_id), None)


def clear_cache() -> None:
    """Used by tests, and by ingestion after writing new rows, so each
    caller sees fresh reads instead of the first-call cache forever."""
    get_canonical_events.cache_clear()
    get_nlp_outputs.cache_clear()
    get_topics.cache_clear()
    get_network.cache_clear()
    get_network_topology.cache_clear()
