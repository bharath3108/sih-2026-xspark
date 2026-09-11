from fastapi import APIRouter
from graph.engine import analyze_network
from graph.temporal.comparator import compare_network_windows
from graph.db import fetch_canonical_events_from_db

router = APIRouter(prefix="/api/network", tags=["Network Graph"])

@router.post("")
def get_network_metrics(payload: dict):
    """
    Returns full network metrics. Accepts either raw 'events' array 
    or 'start'/'end' timestamps to fetch directly from PostgreSQL.
    """
    events = payload.get("events", [])
    start = payload.get("start", "2026-09-11T00:00:00Z")
    end = payload.get("end", "2026-09-11T12:00:00Z")

    # If no explicit events are passed, query Person 1's database
    if not events:
        events = fetch_canonical_events_from_db(start, end)

    return analyze_network(events, start, end)

@router.post("/communities")
def get_network_communities(payload: dict):
    """Returns community breakdown specifically for the network explorer view."""
    res = get_network_metrics(payload)
    return {"communities": res.get("communities", [])}

@router.post("/temporal")
def compare_temporal_windows(payload: dict):
    """Compares baseline event window against current event window."""
    baseline_events = payload.get("baseline_events", [])
    current_events = payload.get("current_events", [])
    return compare_network_windows(baseline_events, current_events)