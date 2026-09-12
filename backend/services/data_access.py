"""Single point where the dashboard composition layer reads each contract.

Today every loader reads the checked-in fixtures under data/fixtures/. Each
function is the one place to swap in a real HTTP call to that person's
service later (set the matching env var below) — route/view code in
backend/api/dashboard.py never talks to fixtures or other services directly.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import httpx

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures"

PERSON1_API_BASE = os.getenv("PERSON1_API_BASE")  # canonical events
PERSON2_API_BASE = os.getenv("PERSON2_API_BASE")  # NLP outputs
PERSON3_API_BASE = os.getenv("PERSON3_API_BASE")  # topics/trends/audience
PERSON4_API_BASE = os.getenv("PERSON4_API_BASE")  # network/graph


def _load_fixture(filename: str) -> dict | list:
    with open(FIXTURES_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def get_canonical_events() -> list[dict]:
    if PERSON1_API_BASE:
        resp = httpx.get(f"{PERSON1_API_BASE}/events", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    return _load_fixture("canonical_events.json")


@lru_cache(maxsize=1)
def get_nlp_outputs() -> list[dict]:
    if PERSON2_API_BASE:
        resp = httpx.get(f"{PERSON2_API_BASE}/nlp-outputs", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    return _load_fixture("nlp_outputs.json")


@lru_cache(maxsize=1)
def get_topics() -> list[dict]:
    if PERSON3_API_BASE:
        resp = httpx.get(f"{PERSON3_API_BASE}/topics", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    return _load_fixture("topics.json")


@lru_cache(maxsize=1)
def get_network() -> dict:
    if PERSON4_API_BASE:
        resp = httpx.get(f"{PERSON4_API_BASE}/network", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    return _load_fixture("network_output.json")


@lru_cache(maxsize=1)
def get_network_topology() -> dict:
    """Node/edge list for the visual graph. Not yet part of Person 4's
    published contract (which only exposes summary metrics + community
    membership) — this is a Person-5 fixture standing in until a real
    topology export exists, kept separate so it's obvious what's contractual
    vs. a visualization aid."""
    if PERSON4_API_BASE:
        resp = httpx.get(f"{PERSON4_API_BASE}/network/topology", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    return _load_fixture("network_edges.json")


def get_event_by_id(event_id: str) -> dict | None:
    return next((e for e in get_canonical_events() if e["event_id"] == event_id), None)


def get_nlp_output_by_event_id(event_id: str) -> dict | None:
    return next((n for n in get_nlp_outputs() if n["event_id"] == event_id), None)


def get_topic_by_id(topic_id: str) -> dict | None:
    return next((t for t in get_topics() if t["topic_id"] == topic_id), None)


def clear_cache() -> None:
    """Used by tests so each test sees fresh fixture reads."""
    get_canonical_events.cache_clear()
    get_nlp_outputs.cache_clear()
    get_topics.cache_clear()
    get_network.cache_clear()
    get_network_topology.cache_clear()
