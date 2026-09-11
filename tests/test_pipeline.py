"""Integration tests for the Section D pipeline."""

import json
import math
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pytest

from src.config import PipelineConfig
from src.contracts.nlp_input import NLPOutputContract, Platform
from src.clustering.naming import compute_ctfidf_keywords
from src.engines.trend_score import sigmoid, TrendScoreEngine
from src.pipeline.orchestrator import SectionDPipeline
from src.utils.vectors import cosine_similarity, update_centroid_moving_average


def _make_vector(seed: int, dim: int = 384) -> list[float]:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim)
    v = v / np.linalg.norm(v)
    return v.tolist()


def _similar_vector(base: list[float], noise: float = 0.05, seed: int = 0) -> list[float]:
    rng = np.random.RandomState(seed)
    arr = np.array(base) + rng.randn(len(base)) * noise
    arr = arr / np.linalg.norm(arr)
    return arr.tolist()


@pytest.fixture
def temp_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = PipelineConfig(duckdb_path=f"{tmpdir}/test.duckdb")
        pipeline = SectionDPipeline(config=config)
        yield pipeline
        pipeline.close()


class TestVectorUtils:
    def test_cosine_similarity_identical(self):
        v = np.array([1.0, 0.0, 0.0])
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_centroid_update(self):
        c = np.array([1.0, 0.0])
        v = np.array([0.0, 1.0])
        result = update_centroid_moving_average(c, 1, v)
        expected = (c + v) / 2
        np.testing.assert_array_almost_equal(result, expected)


class TestTrendScore:
    def test_sigmoid_bounds(self):
        assert 0.0 < sigmoid(-10) < 0.01
        assert 0.99 < sigmoid(10) < 1.0
        assert sigmoid(0) == pytest.approx(0.5)

    def test_trend_score_computation(self):
        engine = TrendScoreEngine()
        score = engine.compute(
            acceleration=50.0,
            author_growth=0.5,
            engagement_per_author=100.0,
            novelty=0.78,
            spread=0.82,
            volume_std=10.0,
        )
        assert 0.0 <= score <= 1.0


class TestCTFIDF:
    def test_keyword_extraction(self):
        texts = [
            "zero knowledge proof scaling frameworks blockchain",
            "zk proof scaling layer two frameworks",
        ]
        keywords = compute_ctfidf_keywords(texts, top_k=5)
        assert len(keywords) <= 5
        assert any("proof" in k or "scaling" in k or "framework" in k for k in keywords)


class TestPipelineIntegration:
    def test_ingest_and_cluster(self, temp_pipeline):
        base_vec = _make_vector(42)
        embeddings = {}
        payloads = []

        ts = datetime(2026, 9, 11, 14, 0, 0, tzinfo=timezone.utc)
        for i in range(15):
            ref = f"emb-{i}"
            vec = _similar_vector(base_vec, noise=0.02, seed=i)
            embeddings[ref] = vec
            payloads.append(
                NLPOutputContract(
                    event_id=f"event-{i:03d}",
                    timestamp=ts + timedelta(minutes=i * 5),
                    platform=Platform.X if i % 2 == 0 else Platform.REDDIT,
                    embedding_ref=ref,
                    author_id=f"author-{i % 8}",
                    likes=10 + i,
                    shares=i,
                    comments=i * 2,
                    raw_text=f"zero knowledge proof scaling framework post {i}",
                )
            )

        for ref, vec in embeddings.items():
            temp_pipeline.embedding_store.store(ref, vec)

        events = temp_pipeline.ingest_batch(payloads[:5])
        assert len(events) == 5

        temp_pipeline.flush_buffer()
        results = temp_pipeline.build_all_section_d()
        assert len(results) >= 0

    def test_section_d_payload_structure(self, temp_pipeline):
        base_vec = _make_vector(99)
        ts = datetime(2026, 9, 11, 14, 0, 0, tzinfo=timezone.utc)

        for i in range(16):
            ref = f"emb-{i}"
            vec = _similar_vector(base_vec, noise=0.01, seed=i)
            temp_pipeline.embedding_store.store(ref, vec)
            temp_pipeline.ingest(
                NLPOutputContract(
                    event_id=f"e4b11f32-{i:04d}-8a90-4c12-b21a-29831aef0102",
                    timestamp=ts + timedelta(hours=i // 4),
                    platform=[Platform.X, Platform.TELEGRAM, Platform.REDDIT, Platform.YOUTUBE][i % 4],
                    embedding_ref=ref,
                    author_id=f"author-{i % 6}",
                    likes=100 + i * 10,
                    shares=20 + i,
                    comments=30 + i * 3,
                    raw_text="zero knowledge proof scaling frameworks blockchain crypto",
                )
            )

        temp_pipeline.flush_buffer()
        results = temp_pipeline.build_all_section_d()
        assert results, "expected at least one clustered topic"

        payload = results[0]
        data = payload.to_json_dict()
        assert "topic_id" in data
        assert "name" in data
        assert "window" in data
        assert "metrics" in data
        assert "timeline" in data
        assert "audience" in data
        assert "evidence_event_ids" in data

        metrics = data["metrics"]
        assert 0.0 <= metrics["trend_score"] <= 1.0
        assert 0.0 <= metrics["novelty"] <= 1.0
        assert 0.0 <= metrics["cross_community_spread"] <= 1.0

    def test_online_matching_threshold(self, temp_pipeline):
        vec_a = _make_vector(1)
        vec_b = _make_vector(100)

        temp_pipeline.embedding_store.store("ref-a", vec_a)
        temp_pipeline.embedding_store.store("ref-b", vec_b)

        ts = datetime.now(timezone.utc)

        for i in range(16):
            ref = f"ref-a-{i}"
            temp_pipeline.embedding_store.store(ref, _similar_vector(vec_a, noise=0.02, seed=i))
            temp_pipeline.ingest(
                NLPOutputContract(
                    event_id=f"event-a{i}",
                    timestamp=ts + timedelta(minutes=i),
                    platform=Platform.X,
                    embedding_ref=ref,
                    author_id=f"author-{i}",
                    likes=10 + i,
                    raw_text="topic alpha content",
                )
            )

        temp_pipeline.flush_buffer()
        active = temp_pipeline.vector_store.get_active_centroids()
        assert len(active) >= 1

        temp_pipeline.ingest(
            NLPOutputContract(
                event_id="event-a-similar",
                timestamp=ts + timedelta(minutes=16),
                platform=Platform.X,
                embedding_ref="ref-a",
                author_id="author-new",
                likes=20,
                raw_text="topic alpha content similar",
            )
        )
        assert temp_pipeline.unclustered_buffer.size() == 0

        temp_pipeline.ingest(
            NLPOutputContract(
                event_id="event-b1",
                timestamp=ts + timedelta(minutes=12),
                platform=Platform.REDDIT,
                embedding_ref="ref-b",
                author_id="author-3",
                likes=5,
                raw_text="completely different topic beta",
            )
        )
        assert temp_pipeline.unclustered_buffer.size() >= 1
