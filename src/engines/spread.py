"""Step 4: Multi-Dimensional Spread Engine."""

from __future__ import annotations

import math

from src.component_e.network import AuthorInteractionNetwork
from src.config import PipelineConfig, DEFAULT_CONFIG
from src.storage.timeseries_store import TimeSeriesStore


class SpreadEngine:
    """
    cross_community_spread = α * H_platform + (1 - α) * H_network
    where α = 0.5
    """

    def __init__(
        self,
        timeseries_store: TimeSeriesStore,
        network: AuthorInteractionNetwork,
        config: PipelineConfig = DEFAULT_CONFIG,
    ):
        self.timeseries_store = timeseries_store
        self.network = network
        self.config = config

    def compute_platform_entropy(self, topic_id: str) -> float:
        """
        H_platform = -1/log2(K) * sum(p_k * log2(p_k))
        K = 4 supported platforms.
        """
        distribution = self.timeseries_store.get_platform_distribution(topic_id)
        k = len(self.config.supported_platforms)

        total = sum(distribution.values())
        if total == 0:
            return 0.0

        entropy = 0.0
        for platform in self.config.supported_platforms:
            count = distribution.get(platform, 0)
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        return entropy / math.log2(k)

    def compute_network_entropy(self, topic_id: str) -> float:
        author_ids = self.timeseries_store.get_topic_author_ids(topic_id)
        return self.network.compute_network_entropy(author_ids)

    def compute(self, topic_id: str) -> float:
        h_platform = self.compute_platform_entropy(topic_id)
        h_network = self.compute_network_entropy(topic_id)
        alpha = self.config.spread_alpha
        spread = alpha * h_platform + (1 - alpha) * h_network
        return float(min(1.0, max(0.0, spread)))
