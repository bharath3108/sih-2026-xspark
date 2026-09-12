"""Every checked-in fixture must validate against the contract it claims to
implement — this is the enforcement of the team's "Contract Rule": no one
depends on another person's internal code, only on versioned JSON that
matches these shapes."""

import json
from pathlib import Path

import pytest

from backend.schemas.contracts import (
    CanonicalEvent,
    Investigation,
    NetworkOutput,
    NLPOutput,
    Topic,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures"


def _load(filename: str):
    with open(FIXTURES_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def test_canonical_events_fixture_matches_contract():
    events = _load("canonical_events.json")
    assert len(events) > 0
    for e in events:
        CanonicalEvent.model_validate(e)


def test_nlp_outputs_fixture_matches_contract():
    outputs = _load("nlp_outputs.json")
    assert len(outputs) > 0
    for o in outputs:
        NLPOutput.model_validate(o)


def test_topics_fixture_matches_contract():
    topics = _load("topics.json")
    assert len(topics) > 0
    for t in topics:
        Topic.model_validate(t)


def test_network_fixture_matches_contract():
    network = _load("network_output.json")
    NetworkOutput.model_validate(network)


def test_investigation_fixture_matches_contract():
    investigation = _load("investigation.json")
    Investigation.model_validate(investigation)


def test_nlp_outputs_reference_real_events():
    event_ids = {e["event_id"] for e in _load("canonical_events.json")}
    for o in _load("nlp_outputs.json"):
        assert o["event_id"] in event_ids, f"NLP output references unknown event {o['event_id']}"


def test_topic_evidence_references_real_events():
    event_ids = {e["event_id"] for e in _load("canonical_events.json")}
    for t in _load("topics.json"):
        for eid in t["evidence_event_ids"]:
            assert eid in event_ids, f"Topic {t['topic_id']} references unknown event {eid}"


@pytest.mark.parametrize("topic", _load("topics.json"))
def test_audience_shares_are_plausible(topic):
    audience = topic["audience"]
    assert 0.0 <= audience["unknown_share"] <= 1.0
    assert 0.0 <= audience["confidence"] <= 1.0
    assert audience["sample_size"] >= 0
