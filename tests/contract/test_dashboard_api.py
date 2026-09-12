"""Integration tests for Person 5's composition API.

Uses a standalone FastAPI app that mounts only backend.api.dashboard —
deliberately not main.py, since main.py wires up Person 1's Postgres engine
at import time and this suite should run without a live database.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import dashboard
from backend.schemas.contracts import Investigation, ModelInfo, NetworkOutput, Topic
from backend.services import data_access


@pytest.fixture(autouse=True)
def _clear_cache():
    data_access.clear_cache()
    yield
    data_access.clear_cache()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(dashboard.router)
    return TestClient(app)


def test_overview_shape(client):
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert "volume" in body
    assert "sentiment_distribution" in body
    assert "top_narratives" in body
    assert "active_communities" in body


def test_timeline_all_topics(client):
    resp = client.get("/api/timeline")
    assert resp.status_code == 200
    assert len(resp.json()["series"]) >= 2


def test_timeline_unknown_topic_404(client):
    resp = client.get("/api/timeline", params={"topic_id": "does-not-exist"})
    assert resp.status_code == 404


def test_list_topics_matches_contract(client):
    resp = client.get("/api/topics")
    assert resp.status_code == 200
    for t in resp.json()["topics"]:
        Topic.model_validate(t)


def test_topic_drilldown_includes_evidence(client):
    resp = client.get("/api/topics/topic-002")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["evidence_events"]) == len(body["evidence_event_ids"])
    assert len(body["nlp_outputs"]) == len(body["evidence_event_ids"])


def test_sentiment_scoped_to_topic(client):
    resp = client.get("/api/sentiment", params={"topic_id": "topic-002"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_size"] == 4
    assert body["sentiment"].get("negative", 0) >= 2


def test_audience_overall_aggregates_across_topics(client):
    resp = client.get("/api/audience")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_size"] == 7  # 4 + 3 across the two fixture topics
    assert 0.0 <= body["confidence"] <= 1.0


def test_network_matches_contract_plus_topology(client):
    resp = client.get("/api/network")
    assert resp.status_code == 200
    body = resp.json()
    NetworkOutput.model_validate({k: v for k, v in body.items() if k != "topology"})
    assert "nodes" in body["topology"]
    assert "edges" in body["topology"]


def test_network_communities_include_members(client):
    resp = client.get("/api/network/communities")
    assert resp.status_code == 200
    for c in resp.json()["communities"]:
        assert "members" in c and len(c["members"]) > 0


def test_event_lookup_merges_nlp(client):
    resp = client.get("/api/events/e4b11f32-8a90-4c12-b21a-29831aef0101")
    assert resp.status_code == 200
    body = resp.json()
    assert body["nlp"]["sentiment"]["label"] == "positive"


def test_event_lookup_404(client):
    resp = client.get("/api/events/does-not-exist")
    assert resp.status_code == 404


def test_create_investigation_matches_contract(client):
    resp = client.post("/api/investigations", json={"topic_id": "topic-002"})
    assert resp.status_code == 200
    body = resp.json()
    Investigation.model_validate(body)
    assert len(body["claims"]) > 0
    for claim in body["claims"]:
        assert len(claim["evidence_event_ids"]) > 0


def test_create_investigation_unknown_topic_404(client):
    resp = client.post("/api/investigations", json={"topic_id": "does-not-exist"})
    assert resp.status_code == 404


def test_create_report_models_are_well_formed(client):
    resp = client.post("/api/reports", json={"topic_id": "topic-002"})
    assert resp.status_code == 200
    for model in resp.json()["audit"]["models"]:
        ModelInfo.model_validate(model)


def test_create_report_from_topic_id(client):
    resp = client.post("/api/reports", json={"topic_id": "topic-002"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["narrative_text"]
    assert body["generated_by"]["mode"] == "template"  # no GROQ_API_KEY in test env
    assert body["audit"]["inputs"]["evidence_event_ids"]


def test_create_report_from_investigation_object(client):
    investigation = client.post("/api/investigations", json={"topic_id": "topic-001"}).json()
    resp = client.post("/api/reports", json={"investigation": investigation})
    assert resp.status_code == 200
    assert resp.json()["investigation_id"] == investigation["investigation_id"]


def test_create_report_requires_input(client):
    resp = client.post("/api/reports", json={})
    assert resp.status_code == 422


def test_dashboard_health(client):
    resp = client.get("/api/dashboard/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
