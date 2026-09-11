"""Person 2 Vector DB client — fetch 384-dim vectors by embedding_ref."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.storage.embedding_store import EmbeddingStore


class Person2VectorDB(Protocol):
    def get_vector_by_key(self, embedding_ref: str) -> list[float] | None:
        ...


class LocalPerson2VectorClient:
    """Local stand-in until Person 2's Qdrant/Pgvector endpoint is wired."""

    def __init__(self, store: EmbeddingStore | None = None, config: PipelineConfig = DEFAULT_CONFIG):
        self.store = store or EmbeddingStore(config)
        self.config = config

    def get_vector_by_key(self, embedding_ref: str) -> list[float] | None:
        try:
            return self.store.fetch(embedding_ref).tolist()
        except KeyError:
            return None


class QdrantPerson2VectorClient:
    """
    WIRE LATER: Point this at Person 2's Qdrant collection.

    Required from Person 2:
      - host/URL and API key (if any)
      - collection name
      - payload field that stores embedding_ref
    """

    def __init__(self, url: str, collection: str):
        self.url = url
        self.collection = collection
        self._client = None

    def connect(self) -> None:
        from qdrant_client import QdrantClient

        self._client = QdrantClient(url=self.url)

    def get_vector_by_key(self, embedding_ref: str) -> list[float] | None:
        if self._client is None:
            try:
                self.connect()
            except Exception:
                return None
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        results, _ = self._client.scroll(
            collection_name=self.collection,
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
        if not results:
            return None
        vec = results[0].vector
        if isinstance(vec, dict):
            vec = next(iter(vec.values()))
        return np.asarray(vec, dtype=np.float32).tolist()


def build_person2_vector_client(
    config: PipelineConfig = DEFAULT_CONFIG,
    local_store: EmbeddingStore | None = None,
) -> Person2VectorDB:
    if config.person2_qdrant_url:
        return QdrantPerson2VectorClient(
            url=config.person2_qdrant_url,
            collection=config.person2_qdrant_collection,
        )
    return LocalPerson2VectorClient(store=local_store, config=config)
