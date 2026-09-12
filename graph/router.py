from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from graph.engine import analyze_network as _analyze_network

router = APIRouter(prefix="/api/network", tags=["Network Analysis"])


class NetworkRequest(BaseModel):
    events: list[dict]
    start: str | None = Field(default=None, description="ISO-8601 window start; defaults to earliest event timestamp")
    end: str | None = Field(default=None, description="ISO-8601 window end; defaults to latest event timestamp")


def _infer_window(events: list[dict], start: str | None, end: str | None) -> tuple[str, str]:
    if start and end:
        return start, end
    timestamps = sorted(e["timestamp_utc"] for e in events if e.get("timestamp_utc"))
    if timestamps:
        return start or timestamps[0], end or timestamps[-1]
    now = datetime.now(timezone.utc).isoformat()
    return start or now, end or now


@router.post("")
def analyze_network(payload: NetworkRequest):
    """
    Delegates to graph.engine.analyze_network, which already builds the
    graph with MAX_NODES_LIMIT sampling and returns the exact Network
    Contract shape (window/graph_metrics/communities/propagation/
    evidence_event_ids) -- this used to reimplement the same pipeline
    inline with broken imports and a different, non-conforming output shape.
    """
    start, end = _infer_window(payload.events, payload.start, payload.end)
    return _analyze_network(payload.events, start, end)
