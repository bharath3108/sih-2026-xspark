"""Cross-dimensional investigation composition + report text generation.

Person 5 owns this composition: it reads outputs already published by
Persons 2-4 (via backend.services.data_access) and assembles them into the
Investigation contract. It never invents a metric, sentiment, or confidence
value that another module didn't already produce.

Report narrative text has two backends behind one function signature:
- template (default): deterministic string built from the composed finding.
- groq: same finding, sent to the Groq API for a written explanation.
Switching requires no caller changes — set GROQ_API_KEY and it activates.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx

from backend.services import data_access

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class InvestigationNotFound(Exception):
    pass


def _aggregate_nlp(evidence_event_ids: list[str]) -> dict:
    outputs = [
        o for o in data_access.get_nlp_outputs() if o["event_id"] in evidence_event_ids
    ]
    if not outputs:
        return {
            "dominant_sentiment": "unknown",
            "average_sentiment_confidence": 0.0,
            "dominant_emotion": "unknown",
        }

    sentiment_counts: dict[str, int] = {}
    emotion_counts: dict[str, int] = {}
    confidence_sum = 0.0
    for o in outputs:
        sentiment_counts[o["sentiment"]["label"]] = (
            sentiment_counts.get(o["sentiment"]["label"], 0) + 1
        )
        confidence_sum += o["sentiment"]["confidence"]
        emotion = (o.get("emotion") or {}).get("label")
        if emotion:
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

    dominant_sentiment = max(sentiment_counts, key=sentiment_counts.get)
    dominant_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "unknown"

    return {
        "dominant_sentiment": dominant_sentiment,
        "average_sentiment_confidence": round(confidence_sum / len(outputs), 3),
        "dominant_emotion": dominant_emotion,
    }


def _network_slice_for_nodes(key_nodes: list[str]) -> dict:
    network = data_access.get_network()
    relevant_communities = [
        c
        for c in network["communities"]
        if any(n in key_nodes for n in c["central_nodes"])
    ]
    return {
        "communities": relevant_communities or network["communities"],
        "propagation_depth": network["propagation"]["depth"],
        "key_nodes": network["propagation"]["key_nodes"],
    }


def compose_investigation(topic_id: str, start: str | None = None, end: str | None = None) -> dict:
    topic = data_access.get_topic_by_id(topic_id)
    if topic is None:
        raise InvestigationNotFound(f"No topic found for topic_id={topic_id}")

    evidence_event_ids = topic["evidence_event_ids"]
    nlp_summary = _aggregate_nlp(evidence_event_ids)
    network_slice = _network_slice_for_nodes(
        data_access.get_network()["propagation"]["key_nodes"]
    )

    claims = _build_claims(topic, nlp_summary)

    return {
        "investigation_id": f"inv-{uuid.uuid4().hex[:12]}",
        "query": {
            "topic_id": topic_id,
            "start": start or topic["window"]["start"],
            "end": end or topic["window"]["end"],
        },
        "finding": {
            "narrative": {
                "topic_id": topic["topic_id"],
                "name": topic["name"],
                "trend_score": topic["metrics"]["trend_score"],
                "novelty": topic["metrics"]["novelty"],
                "cross_community_spread": topic["metrics"]["cross_community_spread"],
            },
            "nlp": nlp_summary,
            "audience": topic["audience"],
            "network": network_slice,
        },
        "claims": claims,
        "models": [
            {"name": "cardiffnlp/twitter-roberta-base-sentiment", "version": "1.0"},
            {"name": "investigation-composer", "version": "0.1"},
        ],
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _build_claims(topic: dict, nlp_summary: dict) -> list[dict]:
    claims = []
    metrics = topic["metrics"]
    evidence = topic["evidence_event_ids"]

    if metrics["trend_score"] >= 0.6:
        claims.append(
            {
                "claim": (
                    f"'{topic['name']}' shows a strong trend score of "
                    f"{metrics['trend_score']} driven by volume and engagement growth"
                ),
                "confidence": min(0.95, metrics["trend_score"]),
                "evidence_event_ids": evidence[:3],
            }
        )

    if nlp_summary["dominant_sentiment"] != "unknown":
        claims.append(
            {
                "claim": (
                    f"Discussion sentiment is predominantly {nlp_summary['dominant_sentiment']} "
                    f"(avg confidence {nlp_summary['average_sentiment_confidence']})"
                ),
                "confidence": nlp_summary["average_sentiment_confidence"],
                "evidence_event_ids": evidence[:3],
            }
        )

    if metrics["cross_community_spread"] >= 0.5:
        claims.append(
            {
                "claim": "Narrative has spread across multiple distinct communities, not confined to one cluster",
                "confidence": metrics["cross_community_spread"],
                "evidence_event_ids": evidence,
            }
        )

    return claims


def _template_narrative(investigation: dict) -> str:
    finding = investigation["finding"]
    narrative = finding["narrative"]
    nlp = finding["nlp"]
    audience = finding["audience"]
    network = finding["network"]

    lines = [
        f"Narrative '{narrative['name']}' (topic {narrative['topic_id']}) reached a trend "
        f"score of {narrative['trend_score']} with novelty {narrative['novelty']} and "
        f"cross-community spread of {narrative['cross_community_spread']}.",
        f"Sentiment is predominantly {nlp['dominant_sentiment']} "
        f"(confidence {nlp['average_sentiment_confidence']}), with {nlp['dominant_emotion']} "
        "as the leading emotion.",
        f"Audience is estimated across {len(audience['categories'])} categories from a sample "
        f"of {audience['sample_size']} authors (confidence {audience['confidence']}, "
        f"{audience['unknown_share']} unknown share) — an aggregate estimate, not an identity claim.",
        f"Propagation reached a depth of {network['propagation_depth']} through key nodes "
        f"{', '.join(network['key_nodes'])} across {len(network['communities'])} community/communities.",
    ]
    if investigation["claims"]:
        lines.append("Key claims:")
        lines.extend(
            f"- {c['claim']} (confidence {c['confidence']})" for c in investigation["claims"]
        )
    return "\n".join(lines)


def _groq_narrative(investigation: dict) -> str:
    prompt = (
        "You are writing a concise, evidence-grounded investigation summary for an "
        "analyst dashboard. Use only the facts given below — do not invent numbers. "
        f"Data: {investigation['finding']}\nClaims: {investigation['claims']}\n"
        "Write 3-5 sentences."
    )
    resp = httpx.post(
        GROQ_API_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def generate_report(investigation: dict) -> dict:
    """Returns a report with narrative text plus an audit record of the
    inputs and models used. Uses Groq when GROQ_API_KEY is set, otherwise a
    deterministic template — same output shape either way."""
    if GROQ_API_KEY:
        try:
            narrative_text = _groq_narrative(investigation)
            generated_by = {"mode": "groq", "model": GROQ_MODEL}
        except httpx.HTTPError:
            narrative_text = _template_narrative(investigation)
            generated_by = {"mode": "template", "model": "template-report-composer", "fallback_reason": "groq_request_failed"}
    else:
        narrative_text = _template_narrative(investigation)
        generated_by = {"mode": "template", "model": "template-report-composer"}

    return {
        "report_id": f"rpt-{uuid.uuid4().hex[:12]}",
        "investigation_id": investigation["investigation_id"],
        "narrative_text": narrative_text,
        "generated_by": generated_by,
        "audit": {
            "inputs": {
                "topic_id": investigation["query"]["topic_id"],
                "window": {
                    "start": investigation["query"]["start"],
                    "end": investigation["query"]["end"],
                },
                "evidence_event_ids": sorted(
                    {
                        eid
                        for claim in investigation["claims"]
                        for eid in claim["evidence_event_ids"]
                    }
                ),
            },
            "models": investigation["models"]
            + [{"name": generated_by["model"], "version": generated_by["mode"]}],
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }
