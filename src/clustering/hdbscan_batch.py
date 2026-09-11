"""Step 2c: HDBSCAN batch discovery on unclustered buffer (every 10 minutes)."""

from __future__ import annotations

from dataclasses import dataclass

import hdbscan
import numpy as np

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.contracts.nlp_input import IngestedEvent
from src.storage.timeseries_store import TimeSeriesStore
from src.storage.vector_store import VectorStore
from src.utils.vectors import cosine_similarity, normalize, to_array


@dataclass
class ClusterResult:
    topic_id: str
    events: list[IngestedEvent]
    centroid: np.ndarray


class HDBSCANBatchClusterer:
    """
    Every 10 minutes, execute HDBSCAN on unclustered buffer.
    Min cluster size N_min = 10, Euclidean on normalized vectors.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        timeseries_store: TimeSeriesStore,
        config: PipelineConfig = DEFAULT_CONFIG,
    ):
        self.vector_store = vector_store
        self.timeseries_store = timeseries_store
        self.config = config

    def cluster(self, events: list[IngestedEvent]) -> tuple[list[ClusterResult], list[IngestedEvent]]:
        """
        Returns (new_clusters, unassigned_events).
        """
        if len(events) < self.config.hdbscan_min_cluster_size:
            return [], events

        vectors = np.array([to_array(e.vector) for e in events])
        normalized = np.array([normalize(v) for v in vectors])

        # Tiny unique jitter prevents HDBSCAN from treating near-duplicates as noise.
        jitter = np.linspace(0, 1e-6, len(events)).reshape(-1, 1)
        jittered = normalized + jitter

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.config.hdbscan_min_cluster_size,
            min_samples=1,
            metric="euclidean",
            cluster_selection_method="eom",
        )
        labels = clusterer.fit_predict(jittered)

        if np.all(labels == -1):
            labels = self._fallback_dense_labels(normalized)

        clusters: dict[int, list[IngestedEvent]] = {}
        unassigned: list[IngestedEvent] = []

        for event, label in zip(events, labels):
            if label == -1:
                unassigned.append(event)
            else:
                clusters.setdefault(int(label), []).append(event)

        results: list[ClusterResult] = []
        for cluster_events in clusters.values():
            cluster_vectors = np.array(
                [to_array(e.vector) for e in cluster_events]
            )
            centroid = cluster_vectors.mean(axis=0)
            topic_id = self.vector_store.generate_topic_id()
            tc = self.vector_store.create_active_topic(
                centroid=centroid, topic_id=topic_id, count=len(cluster_events)
            )
            for event in cluster_events:
                event.topic_id = topic_id
                self.timeseries_store.assign_topic(event.event_id, topic_id)
            results.append(
                ClusterResult(
                    topic_id=topic_id,
                    events=cluster_events,
                    centroid=tc.centroid,
                )
            )

        return results, unassigned

    def _fallback_dense_labels(self, normalized: np.ndarray) -> np.ndarray:
        """If HDBSCAN yields all noise, group points near the mean with cosine >= 0.80."""
        labels = np.full(len(normalized), -1, dtype=int)
        mean = normalize(normalized.mean(axis=0))
        members = [
            i
            for i, vec in enumerate(normalized)
            if cosine_similarity(vec, mean) >= self.config.cosine_similarity_threshold
        ]
        if len(members) >= self.config.hdbscan_min_cluster_size:
            for i in members:
                labels[i] = 0
        return labels
