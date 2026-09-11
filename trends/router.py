from fastapi import APIRouter, Query
from .pipeline import build_topics
from .store import get_store
from .audience import compute_audience

router = APIRouter(tags=["trends"])

@router.get("/api/topics")
def api_topics(start: str = Query(...), end: str = Query(...)):
    return build_topics(start, end)

@router.get("/api/audience")
def api_audience(start: str = Query(...), end: str = Query(...)):
    store = get_store()
    events = store.query_joined_events(start, end)
    return {
        "window": {"start": start, "end": end},
        "audience": compute_audience(events)
    }