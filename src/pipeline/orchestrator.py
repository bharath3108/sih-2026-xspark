"""Main pipeline: Redis stream clustering + DuckDB metrics + Section D JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.clustering.naming import NarrativeNameGenerator
from src.clustering.streaming import DynamicTopicClusterer
from src.component_e.network import AuthorInteractionNetwork
from src.config import PipelineConfig, DEFAULT_CONFIG
from src.contracts.nlp_input import IngestedEvent, NLPOutputContract, Platform
from src.contracts.section_d import SectionDPayload, TimeWindow, TopicMetrics
from src.engines.audience import AudienceEngine
from src.engines.evidence import EvidenceEngine
from src.engines.lifecycle import LifecycleEngine
from src.engines.novelty import NoveltyEngine
from src.engines.spread import SpreadEngine
from src.engines.trend_score import TrendScoreEngine
from src.ingestion.engine import IngestionEngine
from src.person2.vector_client import build_person2_vector_client
from src.storage.embedding_store import EmbeddingStore
from src.storage.redis_state import RedisStateStore, connect_redis
from src.storage.timeseries_store import TimeSeriesStore
from src.storage.vector_store import VectorStore


class SectionDPipeline:
    """
    Person 3 processing engine:
      Stream ingest -> online centroid match (Redis) -> unclustered buffer
      -> HDBSCAN every 10m -> trend/lifecycle -> Section D JSON API
    """

    def __init__(
        self,
        config: PipelineConfig = DEFAULT_CONFIG,
        llm_endpoint: str | None = None,
        author_metadata: dict[str, dict] | None = None,
        redis_client=None,
    ):
        self.config = config
        self.author_metadata = author_metadata or {}

        self.embedding_store = EmbeddingStore(config)
        self.vector_store = VectorStore(config)
        self.timeseries_store = TimeSeriesStore(config)
        self.network = AuthorInteractionNetwork(config.component_e_graph_path)

        self.state = RedisStateStore(
            redis_client=redis_client if redis_client is not None else connect_redis(config),
            config=config,
        )
        self.person2_vectors = build_person2_vector_client(
            config, local_store=self.embedding_store
        )

        self.ingestion = IngestionEngine(
            self.embedding_store,
            self.timeseries_store,
            config,
            redis_state=self.state,
            vector_db=self.person2_vectors,
        )
        self.clusterer = DynamicTopicClusterer(self.state, config=config)
        self.unclustered_buffer = _BufferFacade(self.state)
        self.name_generator = NarrativeNameGenerator(config, llm_endpoint)

        self.novelty_engine = NoveltyEngine(self.vector_store, config)
        self.spread_engine = SpreadEngine(self.timeseries_store, self.network, config)
        self.lifecycle_engine = LifecycleEngine(self.timeseries_store, config)
        self.trend_engine = TrendScoreEngine(config)
        self.evidence_engine = EvidenceEngine(self.timeseries_store)
        self.audience_engine = AudienceEngine()

        self._event_vectors: dict[str, list[float]] = {}
        self._topic_events: dict[str, list[IngestedEvent]] = {}

    def connect_external_stores(self) -> None:
        self.embedding_store.connect_qdrant()
        self.vector_store.connect_qdrant()

    def ingest(self, payload: NLPOutputContract) -> IngestedEvent:
        event = self.ingestion.ingest(payload)
        self._event_vectors[event.event_id] = event.vector
        return self._process_event(event)

    def ingest_batch(self, payloads: list[NLPOutputContract]) -> list[IngestedEvent]:
        return [self.ingest(p) for p in payloads]

    def ingest_stream_json(self, event_json: str) -> IngestedEvent | None:
        record = self.ingestion.worker.process_incoming_event(event_json)
        event = self.ingestion.worker.to_ingested_event(record)
        if event is None:
            return None
        self.timeseries_store.insert_event(event, topic_id=None)
        self._event_vectors[event.event_id] = event.vector
        return self._process_event(event)

    def _process_event(self, event: IngestedEvent) -> IngestedEvent:
        extra = {
            "timestamp": event.timestamp.isoformat(),
            "author_id": event.author_id,
            "platform": event.platform.value,
            "raw_text": event.raw_text,
            "likes": event.likes,
            "shares": event.shares,
            "comments": event.comments,
        }
        result = self.clusterer.assign_or_buffer(event.event_id, event.vector, extra=extra)
        if result not in ("buffered", "unassigned"):
            event.topic_id = result
            self.timeseries_store.assign_topic(event.event_id, result)
            self._track_event(result, event)
            self._mirror_centroid(result)
            author_ids = self.timeseries_store.get_topic_author_ids(result)
            self.network.build_from_cooccurrence(author_ids)
        return event

    def _track_event(self, topic_id: str, event: IngestedEvent) -> None:
        self._topic_events.setdefault(topic_id, []).append(event)

    def _mirror_centroid(self, topic_id: str) -> None:
        centroids = self.state.get_active_centroids()
        centroid = centroids.get(topic_id)
        if centroid is None:
            return
        count = self.state.get_count(topic_id)
        name = self.state.get_topic_name(topic_id)
        existing = self.vector_store.get_active_topic(topic_id)
        if existing is None:
            self.vector_store.create_active_topic(
                centroid=centroid.astype(float),
                name=name,
                topic_id=topic_id,
                count=count or 1,
            )
        else:
            existing.centroid = centroid.astype(float)
            existing.count = count
            existing.name = name or existing.name

    def flush_buffer(self) -> list[str]:
        new_topic_ids = self.clusterer.run_hdbscan_on_buffer()
        for topic_id in new_topic_ids:
            self._hydrate_topic_events(topic_id)
            events = self._topic_events.get(topic_id, [])
            if events:
                name = self.name_generator.generate_from_events(events)
                self.state.set_topic_name(topic_id, name)
                self.vector_store.set_topic_name(topic_id, name)
            self._mirror_centroid(topic_id)
            author_ids = [e.author_id for e in events]
            self.network.build_from_cooccurrence(author_ids)
        self.novelty_engine.archive_expired_active()
        return new_topic_ids

    def _hydrate_topic_events(self, topic_id: str) -> None:
        raw_map = self.state.redis.hgetall("event_topic_map")
        for eid_b, tid_b in raw_map.items():
            eid = eid_b.decode() if isinstance(eid_b, bytes) else str(eid_b)
            tid = tid_b.decode() if isinstance(tid_b, bytes) else str(tid_b)
            if tid == topic_id:
                self.timeseries_store.assign_topic(eid, topic_id)

        known = {e.event_id for e in self._topic_events.get(topic_id, [])}
        for row in self.timeseries_store.get_events_for_topic(topic_id):
            eid = row["event_id"]
            if eid in known:
                continue
            vec = self._event_vectors.get(eid)
            cached = self.state.get_cached_event(eid)
            if vec is None and cached and cached.get("vector"):
                vec = cached["vector"]
            if vec is None:
                continue
            platform = row["platform"]
            if isinstance(platform, str):
                platform = Platform(platform)
            self._track_event(
                topic_id,
                IngestedEvent(
                    event_id=eid,
                    timestamp=row["timestamp"],
                    platform=platform,
                    author_id=row["author_id"],
                    likes=row["likes"],
                    shares=row["shares"],
                    comments=row["comments"],
                    raw_text=row.get("raw_text"),
                    vector=vec,
                    topic_id=topic_id,
                ),
            )

    def build_section_d(self, topic_id: str) -> SectionDPayload | None:
        centroids = self.state.get_active_centroids()
        centroid = centroids.get(topic_id)
        if centroid is None:
            tc = self.vector_store.get_active_topic(topic_id)
            if tc is None:
                return None
            centroid = tc.centroid
            name = tc.name
            created = tc.created_at
            updated = tc.updated_at
        else:
            self._mirror_centroid(topic_id)
            tc = self.vector_store.get_active_topic(topic_id)
            name = self.state.get_topic_name(topic_id) or (tc.name if tc else "")
            created = tc.created_at if tc else datetime.now(timezone.utc)
            updated = tc.updated_at if tc else created

        self._hydrate_topic_events(topic_id)
        events = self._topic_events.get(topic_id, [])

        lifecycle_metrics = self.lifecycle_engine.get_latest_metrics(topic_id)
        origin = created
        if events:
            origin = min(events, key=lambda e: e.timestamp).timestamp
        timeline = self.lifecycle_engine.build_timeline(topic_id, origin)

        novelty = self.novelty_engine.compute(centroid)
        spread = self.spread_engine.compute(topic_id)
        trend_score = self.trend_engine.compute(
            acceleration=lifecycle_metrics["acceleration"],
            author_growth=lifecycle_metrics["author_growth"],
            engagement_per_author=lifecycle_metrics["engagement_per_author"],
            novelty=novelty,
            spread=spread,
            volume_std=lifecycle_metrics["volume_std"],
        )

        closest = self.evidence_engine.select_closest_to_centroid(centroid, events)
        evidence_ids = self.evidence_engine.select_evidence(events)
        if closest and closest not in evidence_ids:
            evidence_ids = [closest] + evidence_ids
        evidence_ids = evidence_ids[:2]

        author_ids = self.timeseries_store.get_topic_author_ids(topic_id)
        audience = self.audience_engine.compute(author_ids, self.author_metadata)

        window_start, window_end = created, updated
        if events:
            timestamps = [e.timestamp for e in events]
            window_start, window_end = min(timestamps), max(timestamps)

        return SectionDPayload(
            topic_id=topic_id,
            name=name or "Untitled Topic",
            window=TimeWindow(start=window_start, end=window_end),
            metrics=TopicMetrics(
                volume=lifecycle_metrics["volume"],
                unique_authors=lifecycle_metrics["authors"],
                engagement=lifecycle_metrics["engagement"],
                trend_score=round(trend_score, 2),
                novelty=round(novelty, 2),
                cross_community_spread=round(spread, 2),
            ),
            timeline=timeline,
            audience=audience,
            evidence_event_ids=evidence_ids,
        )

    def list_topic_ids(self) -> list[str]:
        ids = list(self.state.get_active_centroids().keys())
        if not ids:
            ids = list(self.vector_store.get_active_centroids().keys())
        return ids

    def build_all_section_d(self) -> list[SectionDPayload]:
        payloads: list[SectionDPayload] = []
        for topic_id in self.list_topic_ids():
            payload = self.build_section_d(topic_id)
            if payload:
                payloads.append(payload)
        return payloads

    def export_section_d_json(self, topic_id: str, path: str | Path) -> dict:
        payload = self.build_section_d(topic_id)
        if payload is None:
            raise ValueError(f"Topic not found: {topic_id}")
        data = payload.to_json_dict()
        Path(path).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return data

    def close(self) -> None:
        self.timeseries_store.close()


class _BufferFacade:
    def __init__(self, state: RedisStateStore):
        self._state = state

    def size(self) -> int:
        return self._state.unclustered_size()

    def get_events(self) -> list:
        return self._state.get_unclustered()


def _tokenize_list(text: str) -> list[str]:
    import re

    return re.findall(r"[a-zA-Z]{3,}", text.lower())
