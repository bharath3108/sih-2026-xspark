"""Tier 1 online centroid matcher + Tier 2 HDBSCAN buffer worker (Redis)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import hdbscan
import numpy as np

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.storage.redis_state import RedisStateStore
from src.utils.vectors import cosine_similarity, normalize


class DynamicTopicClusterer:
    """
    Incoming Event --> Cosine Sim >= 0.80?
                          |-- YES --> Assign topic_id & moving-average centroid
                          +-- NO  --> Redis unclustered buffer
                                          v (every 10 min)
                                    HDBSCAN -> new topic centroids
    """

    def __init__(
        self,
        redis_state: RedisStateStore,
        similarity_threshold: float | None = None,
        config: PipelineConfig = DEFAULT_CONFIG,
    ):
        self.state = redis_state
        self.redis = redis_state.redis
        self.config = config
        self.threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else config.cosine_similarity_threshold
        )

    def cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        return cosine_similarity(vec_a, vec_b)

    def assign_or_buffer(self, event_id: str, vector: list[float], extra: dict | None = None) -> str:
        if not vector:
            return "unassigned"

        vec = np.array(vector, dtype=np.float32)
        active_topics = self.state.get_active_centroids()

        best_topic_id = None
        highest_sim = -1.0
        for topic_id, centroid in active_topics.items():
            sim = self.cosine_similarity(vec, centroid)
            if sim > highest_sim:
                highest_sim = sim
                best_topic_id = topic_id

        if highest_sim >= self.threshold and best_topic_id:
            self._update_centroid(best_topic_id, vec)
            self.state.map_event(event_id, best_topic_id)
            return best_topic_id

        record = {"event_id": event_id, "vector": vector, "buffered_at": datetime.now(timezone.utc).isoformat()}
        if extra:
            record.update(extra)
        self.state.push_unclustered(record)
        return "buffered"

    def _update_centroid(self, topic_id: str, new_vec: np.ndarray) -> None:
        count = max(self.state.get_count(topic_id), 1)
        centroids = self.state.get_active_centroids()
        old = centroids.get(topic_id)
        if old is not None and old.size:
            updated = (old.astype(np.float32) * count + new_vec) / (count + 1)
        else:
            updated = new_vec
        self.state.set_centroid(topic_id, updated.astype(np.float32), count=count + 1)

    def run_hdbscan_on_buffer(self) -> list[str]:
        """Periodic (cron / every 10 min) spawn of new topics from the buffer."""
        events = self.state.get_unclustered()
        usable = [e for e in events if e.get("vector")]
        if len(usable) < self.config.hdbscan_min_batch:
            return []

        vectors = np.array([e["vector"] for e in usable], dtype=np.float32)
        event_ids = [e["event_id"] for e in usable]
        normalized = np.array([normalize(v) for v in vectors])
        jitter = np.linspace(0, 1e-6, len(usable)).reshape(-1, 1)
        jittered = normalized + jitter

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.config.hdbscan_min_cluster_size,
            min_samples=1,
            metric="euclidean",
            cluster_selection_epsilon=self.config.hdbscan_cluster_selection_epsilon,
        )
        labels = clusterer.fit_predict(jittered)
        if np.all(labels == -1):
            labels = self._fallback_dense_labels(normalized)

        new_topics: list[str] = []
        assigned_ids: set[str] = set()
        remaining: list[dict] = []

        for cluster_id in set(labels.tolist()):
            if cluster_id == -1:
                continue
            idxs = np.where(labels == cluster_id)[0]
            cluster_vecs = vectors[idxs]
            centroid = np.mean(cluster_vecs, axis=0).astype(np.float32)
            new_topic_id = self.state.next_topic_id()
            self.state.set_centroid(new_topic_id, centroid, count=len(idxs))
            for idx in idxs:
                eid = event_ids[idx]
                self.state.map_event(eid, new_topic_id)
                assigned_ids.add(eid)
            new_topics.append(new_topic_id)

        for rec in events:
            if rec.get("event_id") not in assigned_ids:
                remaining.append(rec)
        self.state.replace_unclustered(remaining)
        return new_topics

    def _fallback_dense_labels(self, normalized: np.ndarray) -> np.ndarray:
        labels = np.full(len(normalized), -1, dtype=int)
        mean = normalize(normalized.mean(axis=0))
        members = [
            i
            for i, vec in enumerate(normalized)
            if cosine_similarity(vec, mean) >= self.threshold
        ]
        if len(members) >= self.config.hdbscan_min_cluster_size:
            for i in members:
                labels[i] = 0
        return labels
