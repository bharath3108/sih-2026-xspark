"""Vector math utilities for cosine similarity and centroid updates."""

import numpy as np


def to_array(vector: list[float] | np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError("Expected 1-dimensional vector")
    return arr


def normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm == 0 or b_norm == 0:
        return 0.0
    return float(np.dot(a, b) / (a_norm * b_norm))


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    return 1.0 - cosine_similarity(a, b)


def update_centroid_moving_average(
    current_centroid: np.ndarray, count: int, new_vector: np.ndarray
) -> np.ndarray:
    """C_k^(t+1) = (N_k * C_k^(t) + v_i) / (N_k + 1)"""
    return (count * current_centroid + new_vector) / (count + 1)


def find_best_centroid(
    vector: np.ndarray, centroids: dict[str, np.ndarray]
) -> tuple[str | None, float]:
    best_id: str | None = None
    best_sim = -1.0
    for topic_id, centroid in centroids.items():
        sim = cosine_similarity(vector, centroid)
        if sim > best_sim:
            best_sim = sim
            best_id = topic_id
    return best_id, best_sim
