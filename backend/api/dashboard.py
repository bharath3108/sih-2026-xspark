"""Person 5's API composition layer.

Serves the dashboard-facing endpoints from the team's published JSON
contracts (see backend/services/data_access.py for the per-contract read/
swap point). This module composes and shapes data for the UI; it never
imports another person's internal analysis code — sentiment models, topic
clustering, graph algorithms, etc. all stay on their owning module's side of
the JSON contract.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services import data_access, report_generator

router = APIRouter(prefix="/api", tags=["Dashboard"])


# ---------- Overview ----------


@router.get("/overview")
def get_overview():
    events = data_access.get_canonical_events()
    nlp_outputs = data_access.get_nlp_outputs()
    topics = data_access.get_topics()
    network = data_access.get_network()

    sentiment_counts: dict[str, int] = {}
    for o in nlp_outputs:
        label = o["sentiment"]["label"]
        sentiment_counts[label] = sentiment_counts.get(label, 0) + 1

    top_narratives = sorted(topics, key=lambda t: t["metrics"]["trend_score"], reverse=True)[:5]
    anomalies = [
        {
            "topic_id": t["topic_id"],
            "name": t["name"],
            "trend_score": t["metrics"]["trend_score"],
            "reason": "trend_score above anomaly threshold",
        }
        for t in topics
        if t["metrics"]["trend_score"] >= 0.85
    ]

    return {
        "volume": len(events),
        "sentiment_distribution": sentiment_counts,
        "top_narratives": [
            {"topic_id": t["topic_id"], "name": t["name"], "trend_score": t["metrics"]["trend_score"]}
            for t in top_narratives
        ],
        "active_communities": len(network["communities"]),
        "anomalies": anomalies,
    }


# ---------- Timeline ----------


@router.get("/timeline")
def get_timeline(topic_id: str | None = Query(default=None)):
    topics = data_access.get_topics()
    if topic_id:
        topic = data_access.get_topic_by_id(topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail=f"Unknown topic_id '{topic_id}'")
        selected = [topic]
    else:
        selected = topics

    return {
        "series": [
            {
                "topic_id": t["topic_id"],
                "name": t["name"],
                "points": t["timeline"],
            }
            for t in selected
        ]
    }


# ---------- Topics ----------


@router.get("/topics")
def list_topics():
    return {"topics": data_access.get_topics()}


@router.get("/topics/{topic_id}")
def get_topic(topic_id: str):
    topic = data_access.get_topic_by_id(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail=f"Unknown topic_id '{topic_id}'")

    evidence = [
        data_access.get_event_by_id(eid)
        for eid in topic["evidence_event_ids"]
    ]
    nlp = [
        data_access.get_nlp_output_by_event_id(eid)
        for eid in topic["evidence_event_ids"]
    ]
    return {
        **topic,
        "evidence_events": [e for e in evidence if e is not None],
        "nlp_outputs": [n for n in nlp if n is not None],
    }


# ---------- Sentiment ----------


@router.get("/sentiment")
def get_sentiment(topic_id: str | None = Query(default=None)):
    nlp_outputs = data_access.get_nlp_outputs()

    if topic_id:
        topic = data_access.get_topic_by_id(topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail=f"Unknown topic_id '{topic_id}'")
        relevant_ids = set(topic["evidence_event_ids"])
        nlp_outputs = [o for o in nlp_outputs if o["event_id"] in relevant_ids]

    if not nlp_outputs:
        return {"topic_id": topic_id, "sample_size": 0, "sentiment": {}, "emotion": {}, "stance": {}}

    def _distribution(key: str, sub_key: str = "label") -> dict[str, int]:
        counts: dict[str, int] = {}
        for o in nlp_outputs:
            value = (o.get(key) or {}).get(sub_key)
            if value:
                counts[value] = counts.get(value, 0) + 1
        return counts

    return {
        "topic_id": topic_id,
        "sample_size": len(nlp_outputs),
        "sentiment": _distribution("sentiment"),
        "emotion": _distribution("emotion"),
        "stance": _distribution("stance"),
    }


# ---------- Audience ----------


@router.get("/audience")
def get_audience(topic_id: str | None = Query(default=None)):
    if topic_id:
        topic = data_access.get_topic_by_id(topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail=f"Unknown topic_id '{topic_id}'")
        return topic["audience"]

    topics = data_access.get_topics()
    if not topics:
        return {"categories": {}, "unknown_share": 1.0, "sample_size": 0, "confidence": 0.0}

    total_sample = sum(t["audience"]["sample_size"] for t in topics)
    if total_sample == 0:
        return {"categories": {}, "unknown_share": 1.0, "sample_size": 0, "confidence": 0.0}

    categories: dict[str, float] = {}
    weighted_unknown = 0.0
    weighted_confidence = 0.0
    for t in topics:
        weight = t["audience"]["sample_size"] / total_sample
        for cat, share in t["audience"]["categories"].items():
            categories[cat] = categories.get(cat, 0.0) + share * weight
        weighted_unknown += t["audience"]["unknown_share"] * weight
        weighted_confidence += t["audience"]["confidence"] * weight

    return {
        "categories": {k: round(v, 3) for k, v in categories.items()},
        "unknown_share": round(weighted_unknown, 3),
        "sample_size": total_sample,
        "confidence": round(weighted_confidence, 3),
    }


# ---------- Network ----------


@router.get("/network")
def get_network():
    network = data_access.get_network()
    topology = data_access.get_network_topology()
    return {**network, "topology": topology}


@router.get("/network/communities")
def get_network_communities():
    network = data_access.get_network()
    topology = data_access.get_network_topology()
    nodes_by_community: dict[str, list[str]] = {}
    for node in topology["nodes"]:
        nodes_by_community.setdefault(node["community_id"], []).append(node["id"])

    return {
        "communities": [
            {**c, "members": nodes_by_community.get(c["community_id"], [])}
            for c in network["communities"]
        ]
    }


# ---------- Events (evidence) ----------


@router.get("/events/{event_id}")
def get_event(event_id: str):
    event = data_access.get_event_by_id(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Unknown event_id '{event_id}'")
    nlp = data_access.get_nlp_output_by_event_id(event_id)
    return {**event, "nlp": nlp}


# ---------- Investigations ----------


class InvestigationRequest(BaseModel):
    topic_id: str
    start: str | None = None
    end: str | None = None


@router.post("/investigations")
def create_investigation(payload: InvestigationRequest):
    try:
        return report_generator.compose_investigation(payload.topic_id, payload.start, payload.end)
    except report_generator.InvestigationNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------- Reports ----------


class ReportRequest(BaseModel):
    investigation: dict | None = None
    topic_id: str | None = None
    start: str | None = None
    end: str | None = None


@router.post("/reports")
def create_report(payload: ReportRequest):
    if payload.investigation:
        investigation = payload.investigation
    elif payload.topic_id:
        try:
            investigation = report_generator.compose_investigation(
                payload.topic_id, payload.start, payload.end
            )
        except report_generator.InvestigationNotFound as e:
            raise HTTPException(status_code=404, detail=str(e))
    else:
        raise HTTPException(
            status_code=422, detail="Provide either 'investigation' or 'topic_id'"
        )

    return report_generator.generate_report(investigation)


# ---------- Health (dashboard status only; unified /api/health lives in main.py) ----------


@router.get("/dashboard/health")
def dashboard_health():
    status = {}
    for name, loader in (
        ("canonical_events", data_access.get_canonical_events),
        ("nlp_outputs", data_access.get_nlp_outputs),
        ("topics", data_access.get_topics),
        ("network", data_access.get_network),
    ):
        try:
            loader()
            status[name] = "ok"
        except Exception as e:  # noqa: BLE001 - surfaced to health payload, not raised
            status[name] = f"error: {e}"

    return {
        "status": "ok" if all(v == "ok" for v in status.values()) else "degraded",
        "contracts": status,
        "checked_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
