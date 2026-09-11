"""Embedding store — resolves embedding_ref to 384-dim vectors from Person 2."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.config import PipelineConfig, DEFAULT_CONFIG


class EmbeddingStore:
    """Stores and retrieves post embeddings keyed by embedding_ref."""

    def __init__(self, config: PipelineConfig = DEFAULT_CONFIG):
        self.config = config
        self._local: dict[str, np.ndarray] = {}
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
            collections = {c.name for c in self._qdrant.get_collections().collections}
            if self.config.embeddings_collection not in collections:
                self._qdrant.create_collection(
                    collection_name=self.config.embeddings_collection,
                    vectors_config=VectorParams(
                        size=self.config.embedding_dim, distance=Distance.COSINE
                    ),
                )
        except Exception:
            self._qdrant = None

    def store(self, embedding_ref: str, vector: list[float] | np.ndarray) -> None:
        arr = np.asarray(vector, dtype=np.float64)
        if arr.shape[0] != self.config.embedding_dim:
            raise ValueError(
                f"Expected {self.config.embedding_dim}-dim vector, got {arr.shape[0]}"
            )
        self._local[embedding_ref] = arr
        if self._qdrant is not None:
            from qdrant_client.models import PointStruct

            self._qdrant.upsert(
                collection_name=self.config.embeddings_collection,
                points=[
                    PointStruct(
                        id=hash(embedding_ref) & 0x7FFFFFFFFFFFFFFF,
                        vector=arr.tolist(),
                        payload={"embedding_ref": embedding_ref},
                    )
                ],
            )

    def fetch(self, embedding_ref: str) -> np.ndarray:
        if embedding_ref in self._local:
            return self._local[embedding_ref]

        if self._qdrant is not None:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            results, _ = self._qdrant.scroll(
                collection_name=self.config.embeddings_collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="embedding_ref",
                            match=MatchValue(value=embedding_ref),
                        )
                    ]
                ),
                limit=1,
                with_vectors=True,
            )
            if results:
                vec = np.asarray(results[0].vector, dtype=np.float64)
                self._local[embedding_ref] = vec
                return vec

        raise KeyError(f"embedding_ref not found: {embedding_ref}")

    def load_from_json(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for ref, vector in data.items():
            self.store(ref, vector)
