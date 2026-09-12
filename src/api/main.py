"""Final JSON delivery service (FastAPI)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from src.api.audience import router as audience_router
from src.contracts.nlp_input import NLPOutputContract
from src.pipeline.orchestrator import SectionDPipeline
from src.pipeline.scheduler import BufferFlushScheduler

_pipeline: SectionDPipeline | None = None
_scheduler: BufferFlushScheduler | None = None


def get_pipeline() -> SectionDPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = SectionDPipeline()
        _pipeline.connect_external_stores()
    return _pipeline


def create_app(pipeline: SectionDPipeline | None = None, start_scheduler: bool = True) -> FastAPI:
    app = FastAPI(title="Section D Real-Time Trend Engine")
    if pipeline is not None:
        global _pipeline
        _pipeline = pipeline

    app.include_router(audience_router)

    if start_scheduler:

        @app.on_event("startup")
        def _start_hdbscan_cron() -> None:
            global _scheduler
            pipe = get_pipeline()
            _scheduler = BufferFlushScheduler(pipe)
            _scheduler.start()

        @app.on_event("shutdown")
        def _stop() -> None:
            global _scheduler
            if _scheduler:
                _scheduler.stop()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/topics")
    def list_topics() -> dict[str, Any]:
        pipe = get_pipeline()
        payloads = [p.to_json_dict() for p in pipe.build_all_section_d()]
        return {"topics": payloads}

    @app.get("/api/v1/topics/{topic_id}")
    def get_topic_analytics(topic_id: str) -> dict[str, Any]:
        pipe = get_pipeline()
        payload = pipe.build_section_d(topic_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Unknown topic_id: {topic_id}")
        data = payload.to_json_dict()
        data["timeline"] = [
            {
                "bucket": item["bucket_start"],
                "bucket_start": item["bucket_start"],
                "volume": item["volume"],
                "unique_authors": item["unique_authors"],
                "engagement": item["engagement"],
                "avg_sentiment": item["avg_sentiment"],
                "status": item["status"],
            }
            for item in data.get("timeline", [])
        ]
        return data

    @app.post("/api/v1/events")
    def ingest_event(event: NLPOutputContract) -> dict[str, Any]:
        """Dev ingest until Kafka/Redis Streams from Person 2 is wired."""
        pipe = get_pipeline()
        ingested = pipe.ingest(event)
        return {
            "event_id": ingested.event_id,
            "topic_id": ingested.topic_id,
            "status": ingested.topic_id or "buffered",
        }

    @app.post("/api/v1/workers/hdbscan")
    def run_hdbscan() -> dict[str, Any]:
        pipe = get_pipeline()
        created = pipe.flush_buffer()
        return {"new_topics": created}

    return app


app = create_app()
