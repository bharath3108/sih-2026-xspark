"""Step 3: Historical Storage & Novelty Engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.storage.vector_store import VectorStore
from src.utils.vectors import cosine_similarity, to_array


class NoveltyEngine:
    """
    Novelty = 1.0 - max(cosine_sim(C_new, C_h)) over 30-day historical window.
    N ≈ 1.0: completely novel; N ≤ 0.20: recycled discussion.
    """

    def __init__(
        self, vector_store: VectorStore, config: PipelineConfig = DEFAULT_CONFIG
    ):
        self.vector_store = vector_store
        self.config = config

    def compute(self, centroid: np.ndarray | list[float]) -> float:
        vec = to_array(centroid)
        cutoff = datetime.now(timezone.utc) - self.config.historical_window
        historical = self.vector_store.get_historical_centroids(cutoff=cutoff)

        if not historical:
            return 1.0

        max_sim = max(cosine_similarity(vec, h) for h in historical)
        return float(min(1.0, max(0.0, 1.0 - max_sim)))

    def archive_expired_active(self) -> None:
        cutoff = datetime.now(timezone.utc) - self.config.active_window
        self.vector_store.prune_active(cutoff)
