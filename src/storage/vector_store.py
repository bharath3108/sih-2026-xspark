"""Vector database for active and historical topic centroids."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from src.config import PipelineConfig, DEFAULT_CONFIG


@dataclass
class TopicCentroid:
    topic_id: str
    centroid: np.ndarray
    count: int = 0
    name: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class VectorStore:
    """Manages active (48h) and historical (30-day) topic centroids."""

    def __init__(self, config: PipelineConfig = DEFAULT_CONFIG):
        self.config = config
        self._active: dict[str, TopicCentroid] = {}
        self._historical: dict[str, list[TopicCentroid]] = {}
        self._next_topic_num = 1
        self._qdrant = None

    def connect_qdrant(self) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self._qdrant = QdrantClient(
                host=self.config.qdrant_host,
                port=self.config.qdrant_port,
                timeout=2,
            )
            for collection in (
                self.config.active_centroids_collection,
                self.config.historical_centroids_collection,
            ):
                collections = {
                    c.name for c in self._qdrant.get_collections().collections
                }
                if collection not in collections:
                    self._qdrant.create_collection(
                        collection_name=collection,
                        vectors_config=VectorParams(
                            size=self.config.embedding_dim, distance=Distance.COSINE
                        ),
                    )
        except Exception:
            self._qdrant = None

    def generate_topic_id(self) -> str:
        topic_id = f"topic-{self._next_topic_num}"
        self._next_topic_num += 1
        return topic_id

    def get_active_centroids(self) -> dict[str, np.ndarray]:
        return {tid: tc.centroid for tid, tc in self._active.items()}

    def get_active_topic(self, topic_id: str) -> TopicCentroid | None:
        return self._active.get(topic_id)

    def create_active_topic(
        self,
        centroid: np.ndarray,
        name: str = "",
        topic_id: str | None = None,
        count: int = 1,
    ) -> TopicCentroid:
        tid = topic_id or self.generate_topic_id()
        now = datetime.now(timezone.utc)
        tc = TopicCentroid(
            topic_id=tid,
            centroid=centroid.copy(),
            count=max(1, count),
            name=name,
            created_at=now,
        )
        self._active[tid] = tc
        self._sync_active_to_qdrant(tc)
        return tc

    def update_active_centroid(
        self, topic_id: str, new_vector: np.ndarray
    ) -> TopicCentroid:
        tc = self._active[topic_id]
        tc.centroid = (tc.count * tc.centroid + new_vector) / (tc.count + 1)
        tc.count += 1
        tc.updated_at = datetime.now(timezone.utc)
        self._sync_active_to_qdrant(tc)
        return tc

    def set_topic_name(self, topic_id: str, name: str) -> None:
        if topic_id in self._active:
            self._active[topic_id].name = name

    def archive_topic(self, topic_id: str) -> None:
        if topic_id not in self._active:
            return
        tc = self._active.pop(topic_id)
        day_key = tc.updated_at.strftime("%Y-%m-%d")
        self._historical.setdefault(day_key, []).append(tc)
        self._sync_historical_to_qdrant(tc, day_key)

    def get_historical_centroids(
        self, cutoff: datetime | None = None
    ) -> list[np.ndarray]:
        centroids: list[np.ndarray] = []
        for day_key, topics in self._historical.items():
            for tc in topics:
                if cutoff is None or tc.updated_at >= cutoff:
                    centroids.append(tc.centroid)
        return centroids

    def prune_active(self, cutoff: datetime) -> None:
        expired = [
            tid for tid, tc in self._active.items() if tc.updated_at < cutoff
        ]
        for tid in expired:
            self.archive_topic(tid)

    def _sync_active_to_qdrant(self, tc: TopicCentroid) -> None:
        if self._qdrant is None:
            return
        from qdrant_client.models import PointStruct

        self._qdrant.upsert(
            collection_name=self.config.active_centroids_collection,
            points=[
                PointStruct(
                    id=hash(tc.topic_id) & 0x7FFFFFFFFFFFFFFF,
                    vector=tc.centroid.tolist(),
                    payload={
                        "topic_id": tc.topic_id,
                        "count": tc.count,
                        "name": tc.name,
                    },
                )
            ],
        )

    def _sync_historical_to_qdrant(self, tc: TopicCentroid, day_key: str) -> None:
        if self._qdrant is None:
            return
        from qdrant_client.models import PointStruct

        self._qdrant.upsert(
            collection_name=self.config.historical_centroids_collection,
            points=[
                PointStruct(
                    id=hash(f"{tc.topic_id}:{day_key}") & 0x7FFFFFFFFFFFFFFF,
                    vector=tc.centroid.tolist(),
                    payload={
                        "topic_id": tc.topic_id,
                        "partition_day": day_key,
                        "name": tc.name,
                    },
                )
            ],
        )
