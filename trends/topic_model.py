from dataclasses import dataclass
from typing import Dict, List
import numpy as np

from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

from .config import settings
from .store import JoinedEvent


@dataclass
class TopicCluster:
    cluster_label: int
    event_ids: List[str]
    centroid: np.ndarray
    name: str
    keywords: List[str]


def _extract_keywords(texts: List[str], top_n: int = 8) -> List[str]:
    if not texts:
        return []
    v = TfidfVectorizer(max_features=3000, ngram_range=(1, 2), stop_words="english")
    X = v.fit_transform(texts)
    scores = np.asarray(X.mean(axis=0)).ravel()
    idx = np.argsort(scores)[::-1][:top_n]
    vocab = np.array(v.get_feature_names_out())
    return vocab[idx].tolist()


def _name_from_keywords(keywords: List[str]) -> str:
    return " / ".join(keywords[:3]) if keywords else "unknown narrative"


def cluster_topics(joined: List[JoinedEvent]) -> List[TopicCluster]:
    rows = [e for e in joined if e.vector is not None and e.text.strip()]
    if len(rows) < settings.MIN_CLUSTER_SIZE:
        return []

    X = np.stack([e.vector for e in rows], axis=0)

    if settings.CLUSTER_METHOD == "hdbscan":
        import hdbscan
        labels = hdbscan.HDBSCAN(min_cluster_size=settings.MIN_CLUSTER_SIZE).fit_predict(X)
    else:
        k = min(settings.KMEANS_K, max(2, len(rows) // settings.MIN_CLUSTER_SIZE))
        labels = KMeans(n_clusters=k, random_state=42, n_init="auto").fit_predict(X)

    clusters: Dict[int, List[int]] = {}
    for i, lab in enumerate(labels):
        if lab == -1:
            continue
        clusters.setdefault(int(lab), []).append(i)

    out: List[TopicCluster] = []
    for lab, idxs in clusters.items():
        centroid = X[idxs].mean(axis=0)
        texts = [rows[i].text for i in idxs]
        keywords = _extract_keywords(texts)
        out.append(
            TopicCluster(
                cluster_label=lab,
                event_ids=[rows[i].event_id for i in idxs],
                centroid=centroid,
                name=_name_from_keywords(keywords),
                keywords=keywords,
            )
        )
    return out


class TopicRegistry:
    """MVP: in-memory stable mapping across one run. Later: persist in Postgres."""
    def __init__(self) -> None:
        self.topic_id_to_centroid: Dict[str, np.ndarray] = {}
        self._counter = 1

    def match_or_create(self, centroid: np.ndarray) -> str:
        if not self.topic_id_to_centroid:
            tid = self._new_id()
            self.topic_id_to_centroid[tid] = centroid
            return tid

        best_tid, best_sim = None, -1.0
        for tid, c in self.topic_id_to_centroid.items():
            sim = float(cosine_similarity(centroid.reshape(1, -1), c.reshape(1, -1))[0, 0])
            if sim > best_sim:
                best_tid, best_sim = tid, sim

        if best_tid and best_sim >= settings.TOPIC_MATCH_THRESHOLD:
            self.topic_id_to_centroid[best_tid] = 0.8 * self.topic_id_to_centroid[best_tid] + 0.2 * centroid
            return best_tid

        tid = self._new_id()
        self.topic_id_to_centroid[tid] = centroid
        return tid

    def _new_id(self) -> str:
        tid = f"topic-{self._counter:03d}"
        self._counter += 1
        return tid