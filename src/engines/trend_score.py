"""Novelty helpers plus the bounded trend-score formula."""

from __future__ import annotations

import math
from typing import List

import numpy as np

from src.config import PipelineConfig, DEFAULT_CONFIG


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


class TrendMetricEngine:
    def calculate_novelty(
        self, current_centroid: np.ndarray, historical_centroids: List[np.ndarray]
    ) -> float:
        if not historical_centroids:
            return 1.0
        max_sim = 0.0
        c_norm = np.linalg.norm(current_centroid)
        if c_norm == 0:
            return 1.0
        for h_vec in historical_centroids:
            h_norm = np.linalg.norm(h_vec)
            if h_norm == 0:
                continue
            sim = float(np.dot(current_centroid, h_vec) / (c_norm * h_norm))
            if sim > max_sim:
                max_sim = sim
        return float(max(0.0, 1.0 - max_sim))

    def calculate_entropy(self, distribution: List[float]) -> float:
        if not distribution or sum(distribution) == 0:
            return 0.0
        total = sum(distribution)
        probs = [p / total for p in distribution if p > 0]
        k = len(distribution)
        if k <= 1:
            return 0.0
        entropy = -sum(p * math.log2(p) for p in probs)
        return float(entropy / math.log2(k))

    def compute_trend_score(
        self,
        vol_accel: float,
        author_growth: float,
        engagement_rate: float,
        novelty: float,
        spread: float,
    ) -> float:
        w1, w2, w3, w4, w5 = 0.30, 0.25, 0.15, 0.15, 0.15
        norm_engagement = math.log10(1 + engagement_rate)
        raw_score = (
            w1 * vol_accel
            + w2 * author_growth
            + w3 * norm_engagement
            + w4 * novelty
            + w5 * spread
        )
        return round(sigmoid(raw_score), 4)


class TrendScoreEngine:
    def __init__(self, config: PipelineConfig = DEFAULT_CONFIG):
        self.config = config
        self.metrics = TrendMetricEngine()

    def compute(
        self,
        acceleration: float,
        author_growth: float,
        engagement_per_author: float,
        novelty: float,
        spread: float,
        volume_std: float = 1.0,
    ) -> float:
        a_tilde = acceleration / max(volume_std, 1.0)
        return self.metrics.compute_trend_score(
            vol_accel=a_tilde,
            author_growth=author_growth,
            engagement_rate=engagement_per_author,
            novelty=novelty,
            spread=spread,
        )
