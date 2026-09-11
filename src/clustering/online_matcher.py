"""Step 2a: Online Nearest-Centroid Matching (Streaming Phase)."""

from __future__ import annotations

import numpy as np

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.contracts.nlp_input import IngestedEvent
from src.storage.timeseries_store import TimeSeriesStore
from src.storage.vector_store import VectorStore
from src.utils.vectors import find_best_centroid, to_array


class OnlineCentroidMatcher:
    """
    Computes cosine similarity between incoming vector v_i and active centroids.
    If max Sim >= 0.80: assign to topic_id_k and update centroid.
    Otherwise route to unclustered buffer.
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

    def match(self, event: IngestedEvent) -> tuple[str | None, bool]:
        """
        Returns (topic_id, assigned).
        assigned=True if matched to existing topic, False if routed to buffer.
        """
        vector = to_array(event.vector)
        centroids = self.vector_store.get_active_centroids()

        if not centroids:
            return None, False

        best_id, best_sim = find_best_centroid(vector, centroids)

        if best_sim >= self.config.cosine_similarity_threshold:
            self.vector_store.update_active_centroid(best_id, vector)
            event.topic_id = best_id
            self.timeseries_store.assign_topic(event.event_id, best_id)
            return best_id, True

        return None, False
