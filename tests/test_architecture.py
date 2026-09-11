"""Architecture tests: Redis clustering, lifecycle, FastAPI delivery."""

import tempfile
from datetime import datetime, timedelta, timezone

import numpy as np
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.config import PipelineConfig
from src.contracts.nlp_input import NLPOutputContract, Platform
from src.engines.lifecycle import TopicLifecycleTracker, LifecycleStage
from src.engines.trend_score import TrendMetricEngine
from src.pipeline.orchestrator import SectionDPipeline
from src.storage.redis_state import InMemoryRedis, RedisStateStore
from src.clustering.streaming import DynamicTopicClusterer


def _vec(seed: int) -> list[float]:
    rng = np.random.RandomState(seed)
    v = rng.randn(384)
    return (v / np.linalg.norm(v)).tolist()


def test_lifecycle_state_machine():
    tracker = TopicLifecycleTracker()
    assert tracker.evaluate_lifecycle_state(12, 0, 0, 0.0, 1.0) == LifecycleStage.FIRST_APPEARANCE
    assert tracker.evaluate_lifecycle_state(80, 40, 10, 0.5, 5.0) == LifecycleStage.ACCELERATION
    assert tracker.evaluate_lifecycle_state(100, 98, 90, 0.0, 8.0) == LifecycleStage.PEAK
    assert tracker.evaluate_lifecycle_state(50, 100, 90, 0.0, 10.0) == LifecycleStage.DECLINE


def test_trend_metric_engine_bounds():
    eng = TrendMetricEngine()
    assert eng.calculate_novelty(np.array([1.0, 0.0]), []) == 1.0
    entropy = eng.calculate_entropy([1.0, 1.0, 1.0, 1.0])
    assert entropy == 1.0
    score = eng.compute_trend_score(1.0, 0.4, 50.0, 0.8, 0.7)
    assert 0.0 <= score <= 1.0


def test_redis_online_then_hdbscan():
    state = RedisStateStore(redis_client=InMemoryRedis())
    clusterer = DynamicTopicClusterer(state)
    base = np.array(_vec(3), dtype=np.float32)
    for i in range(16):
        noise = np.random.RandomState(i).randn(384).astype(np.float32) * 0.01
        v = base + noise
        v = v / np.linalg.norm(v)
        assert clusterer.assign_or_buffer(f"e{i}", v.tolist()) == "buffered"
    created = clusterer.run_hdbscan_on_buffer()
    assert created
    near = (base + np.random.RandomState(99).randn(384).astype(np.float32) * 0.01)
    near = near / np.linalg.norm(near)
    assigned = clusterer.assign_or_buffer("e-new", near.tolist())
    assert assigned == created[0]


def test_fastapi_topic_endpoint():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = PipelineConfig(duckdb_path=f"{tmpdir}/api.duckdb")
        pipeline = SectionDPipeline(config=config, redis_client=InMemoryRedis())
        base = _vec(9)
        ts = datetime(2026, 9, 11, 14, 0, tzinfo=timezone.utc)
        rng = np.random.RandomState(1)
        for i in range(16):
            v = np.array(base) + rng.randn(384) * 0.01
            v = v / np.linalg.norm(v)
            pipeline.embedding_store.store(f"r{i}", v.tolist())
            pipeline.ingest(
                NLPOutputContract(
                    event_id=f"evt-{i}",
                    timestamp=ts + timedelta(minutes=i),
                    platform=Platform.X,
                    embedding_ref=f"r{i}",
                    author_id=f"a{i}",
                    likes=10,
                    raw_text="zero knowledge proof scaling frameworks",
                )
            )
        pipeline.flush_buffer()
        app = create_app(pipeline, start_scheduler=False)
        client = TestClient(app)
        listed = client.get("/api/v1/topics").json()
        assert listed["topics"]
        topic_id = listed["topics"][0]["topic_id"]
        data = client.get(f"/api/v1/topics/{topic_id}").json()
        assert data["topic_id"] == topic_id
        assert "metrics" in data
        assert "evidence_event_ids" in data
        assert data["timeline"][0]["bucket"]
        pipeline.close()
