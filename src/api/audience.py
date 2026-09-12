"""Standalone audience/demographics delivery API — separate from
`/api/v1/topics`. Purely a read path: it never triggers aggregation itself,
it only serves what `DemographicsWorker` has already written to Redis/DuckDB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.contracts.demographics import AudienceCategories, AudienceSnapshot
from src.workers.demographics_worker import DemographicsWorker

router = APIRouter(prefix="/api/v1/audience", tags=["audience"])

_worker: DemographicsWorker | None = None


def get_demographics_worker() -> DemographicsWorker:
    global _worker
    if _worker is None:
        _worker = DemographicsWorker()
    return _worker


def set_demographics_worker(worker: DemographicsWorker) -> None:
    global _worker
    _worker = worker


def _empty_snapshot(topic_id: str) -> dict[str, Any]:
    return AudienceSnapshot(
        topic_id=topic_id, as_of=datetime.now(timezone.utc), categories=AudienceCategories()
    ).to_json_dict()


@router.get("")
def list_audience() -> dict[str, Any]:
    worker = get_demographics_worker()
    snapshots = []
    for topic_id in worker.active_topic_ids():
        cached = worker.state.get_audience_snapshot(topic_id)
        snapshots.append(cached if cached is not None else _empty_snapshot(topic_id))
    return {"topics": snapshots}


@router.get("/{topic_id}")
def get_audience(
    topic_id: str,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
) -> dict[str, Any]:
    worker = get_demographics_worker()

    if from_ is not None or to is not None:
        rows = worker.timeseries_store.get_audience_snapshots(topic_id, start=from_, end=to)
        return {
            "topic_id": topic_id,
            "window": {
                "start": from_.isoformat() if from_ else (rows[0]["as_of"] if rows else None),
                "end": to.isoformat() if to else (rows[-1]["as_of"] if rows else None),
            },
            "history": rows,
        }

    cached = worker.state.get_audience_snapshot(topic_id)
    if cached is not None:
        return cached
    if topic_id in worker.active_topic_ids():
        return _empty_snapshot(topic_id)
    raise HTTPException(status_code=404, detail=f"Unknown topic_id: {topic_id}")
