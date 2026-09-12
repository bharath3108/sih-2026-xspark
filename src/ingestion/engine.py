"""Stream consumer: Person 2 events -> vector fetch -> Redis event cache."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.contracts.nlp_input import IngestedEvent, NLPOutputContract, Platform
from src.person2.vector_client import Person2VectorDB, build_person2_vector_client
from src.storage.embedding_store import EmbeddingStore
from src.storage.redis_state import RedisStateStore
from src.storage.timeseries_store import TimeSeriesStore


@dataclass
class IngestionBuffer:
    events: list[IngestedEvent] = field(default_factory=list)

    def append(self, event: IngestedEvent) -> None:
        self.events.append(event)

    def drain(self) -> list[IngestedEvent]:
        batch = self.events.copy()
        self.events.clear()
        return batch

    def size(self) -> int:
        return len(self.events)


class StreamIngestionWorker:
    """
    Reads NLP Output Contract objects from a broker payload, fetches the
    384-dim vector from Person 2's Vector DB via embedding_ref, and caches
    metadata in Redis for rapid state lookups.
    """

    def __init__(
        self,
        redis_state: RedisStateStore,
        vector_db_client: Person2VectorDB,
        timeseries_store: TimeSeriesStore | None = None,
        config: PipelineConfig = DEFAULT_CONFIG,
    ):
        self.state = redis_state
        self.vector_db = vector_db_client
        self.timeseries_store = timeseries_store
        self.config = config
        self.redis_client = redis_state.redis

    def process_incoming_event(self, event_json: str) -> dict[str, Any]:
        """Parse contract, fetch vector, format record, cache in Redis."""
        event = json.loads(event_json) if isinstance(event_json, str) else event_json
        event_id = event["event_id"]
        embedding_ref = event.get("embedding_ref")

        vector = None
        if embedding_ref:
            vector = self.vector_db.get_vector_by_key(embedding_ref)

        metrics = event.get("metrics") or {}
        engagement = metrics.get("engagement")
        if engagement is None:
            engagement = (
                int(event.get("likes", 0))
                + int(event.get("shares", 0))
                + int(event.get("comments", 0))
            )

        sentiment = event.get("sentiment") or {}
        payload = {
            "event_id": event_id,
            "timestamp": event.get("timestamp"),
            "author_id": event.get("author_id"),
            "platform": event.get("platform"),
            "sentiment_label": sentiment.get("label") if isinstance(sentiment, dict) else sentiment,
            "sentiment_score": sentiment.get("score") if isinstance(sentiment, dict) else None,
            "vector": vector,
            "engagement": engagement,
            "likes": event.get("likes", metrics.get("likes", 0)),
            "shares": event.get("shares", metrics.get("shares", 0)),
            "comments": event.get("comments", metrics.get("comments", 0)),
            "raw_text": event.get("raw_text"),
            "embedding_ref": embedding_ref,
        }
        self.state.cache_event(event_id, payload)
        return payload

    def to_ingested_event(self, payload: dict[str, Any]) -> IngestedEvent | None:
        vector = payload.get("vector")
        if not vector:
            return None
        ts = payload.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        platform = payload.get("platform") or "X"
        if isinstance(platform, str):
            platform = Platform(platform)
        return IngestedEvent(
            event_id=payload["event_id"],
            timestamp=ts,
            platform=platform,
            author_id=str(payload.get("author_id") or "unknown"),
            likes=int(payload.get("likes") or 0),
            shares=int(payload.get("shares") or 0),
            comments=int(payload.get("comments") or 0),
            raw_text=payload.get("raw_text"),
            vector=list(vector),
            sentiment_label=payload.get("sentiment_label"),
            sentiment_score=payload.get("sentiment_score"),
        )


class IngestionEngine:
    """Typed ingest path used by the orchestrator and tests."""

    def __init__(
        self,
        embedding_store: EmbeddingStore,
        timeseries_store: TimeSeriesStore,
        config: PipelineConfig = DEFAULT_CONFIG,
        redis_state: RedisStateStore | None = None,
        vector_db: Person2VectorDB | None = None,
    ):
        self.embedding_store = embedding_store
        self.timeseries_store = timeseries_store
        self.config = config
        self.state = redis_state or RedisStateStore(config=config)
        self.worker = StreamIngestionWorker(
            redis_state=self.state,
            vector_db_client=vector_db
            or build_person2_vector_client(config, local_store=embedding_store),
            timeseries_store=timeseries_store,
            config=config,
        )
        self.buffer = IngestionBuffer()

    def ingest(self, payload: NLPOutputContract) -> IngestedEvent:
        raw = payload.model_dump(mode="json")
        record = self.worker.process_incoming_event(json.dumps(raw))
        event = self.worker.to_ingested_event(record)
        if event is None:
            raise KeyError(f"embedding_ref not found: {payload.embedding_ref}")
        self.buffer.append(event)
        self.timeseries_store.insert_event(event, topic_id=None)
        return event

    def ingest_batch(self, payloads: list[NLPOutputContract]) -> list[IngestedEvent]:
        return [self.ingest(p) for p in payloads]
