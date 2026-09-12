"""Tests for the Section D demographics pillar (language/profession/geography).

Covers: aggregation correctness, minimum-sample-size enforcement, static-source
loading + missing-field handling, the live-source stub, worker cadence (mocked
clock, no sleeping), Redis-down fallback, and the standalone audience API.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import audience as audience_api
from src.config import PipelineConfig
from src.contracts.nlp_input import IngestedEvent, Platform
from src.engines.demographics import DemographicsEngine
from src.services.author_metadata import (
    LiveAuthorMetadataSource,
    StaticAuthorMetadataSource,
    build_author_metadata_source,
)
from src.storage.redis_state import InMemoryRedis, RedisStateStore
from src.storage.timeseries_store import TimeSeriesStore
from src.workers.demographics_worker import DemographicsWorker


def _event(event_id: str, author_id: str, topic_id: str, ts: datetime) -> IngestedEvent:
    return IngestedEvent(
        event_id=event_id,
        timestamp=ts,
        platform=Platform.X,
        author_id=author_id,
        likes=0,
        shares=0,
        comments=0,
        raw_text=None,
        vector=[0.0],
        topic_id=topic_id,
    )


class TestDemographicsEngine:
    def test_aggregation_correctness(self):
        engine = DemographicsEngine(PipelineConfig(demographics_min_sample_size=20, demographics_target_sample_size=50))
        metadata = {
            f"author-{i}": {"profession": "Software/Tech" if i % 2 == 0 else "Finance"}
            for i in range(20)
        }
        result = engine.compute(metadata)
        profession = result.profession
        assert profession.sample_size == 20
        assert profession.unknown_share == 0.0
        assert profession.confidence == pytest.approx(20 / 50)
        by_value = {e.value: e for e in profession.distribution}
        assert by_value["Software/Tech"].count == 10
        assert by_value["Finance"].count == 10
        assert by_value["Software/Tech"].share == pytest.approx(0.5)

    def test_minimum_sample_size_enforced_per_category(self):
        """One category with >=20 authors reports a real distribution while
        another category on the same topic with <20 reports unknown_share=1.0."""
        engine = DemographicsEngine(PipelineConfig(demographics_min_sample_size=20, demographics_target_sample_size=50))
        metadata = {}
        for i in range(25):
            entry = {"profession": "Software/Tech" if i % 2 == 0 else "Crypto/Web3"}
            if i < 5:
                entry["language"] = "en"
            metadata[f"author-{i}"] = entry

        result = engine.compute(metadata)

        assert result.profession.sample_size == 25
        assert result.profession.unknown_share == 0.0
        assert result.profession.distribution

        assert result.language.sample_size == 5
        assert result.language.unknown_share == 1.0
        assert result.language.distribution == []

        assert result.geography.sample_size == 0
        assert result.geography.unknown_share == 1.0

    def test_missing_author_metadata_does_not_crash(self):
        engine = DemographicsEngine(PipelineConfig(demographics_min_sample_size=1, demographics_target_sample_size=10))
        metadata = {
            "author-known": {"geography": "US"},
            "author-unmapped": {},  # present in topic but no metadata found
        }
        result = engine.compute(metadata)
        assert result.geography.sample_size == 1
        assert result.geography.unknown_share == pytest.approx(0.5)


class TestStaticAuthorMetadataSource:
    def test_loads_fixture_and_handles_missing_authors(self, tmp_path: Path):
        fixture = tmp_path / "author_metadata.json"
        fixture.write_text(
            json.dumps({"author-1": {"profession": "Software/Tech", "geography": "US"}}),
            encoding="utf-8",
        )
        source = StaticAuthorMetadataSource(path=fixture)
        result = source.get_metadata(["author-1", "author-missing"])
        assert result == {"author-1": {"profession": "Software/Tech", "geography": "US"}}
        assert "author-missing" not in result

    def test_missing_file_degrades_to_empty(self, tmp_path: Path):
        source = StaticAuthorMetadataSource(path=tmp_path / "does_not_exist.json")
        assert source.get_metadata(["author-1"]) == {}


class TestLiveAuthorMetadataSource:
    def test_callable_and_empty_when_unwired(self):
        source = LiveAuthorMetadataSource(url=None)
        assert source.get_metadata(["author-1"]) == {}

    def test_raises_when_url_set_but_unimplemented(self):
        source = LiveAuthorMetadataSource(url="https://person1.example/authors")
        with pytest.raises(NotImplementedError):
            source.get_metadata(["author-1"])

    def test_config_switch_selects_implementation(self):
        static_cfg = PipelineConfig(author_metadata_source="static")
        live_cfg = PipelineConfig(author_metadata_source="live")
        assert isinstance(build_author_metadata_source(static_cfg), StaticAuthorMetadataSource)
        assert isinstance(build_author_metadata_source(live_cfg), LiveAuthorMetadataSource)


class TestDemographicsWorkerCadence:
    def test_due_uses_mocked_clock_without_sleeping(self, tmp_path: Path):
        config = PipelineConfig(
            demographics_interval_minutes=10, duckdb_path=str(tmp_path / "cadence.duckdb")
        )
        current = {"t": datetime(2026, 1, 1, tzinfo=timezone.utc)}
        worker = DemographicsWorker(
            state=RedisStateStore(redis_client=InMemoryRedis(), config=config),
            timeseries_store=TimeSeriesStore(config),
            author_metadata_source=StaticAuthorMetadataSource(path="does-not-exist.json"),
            config=config,
            clock=lambda: current["t"],
        )
        assert worker.due() is True
        worker._last_run = current["t"]
        assert worker.due() is False
        current["t"] += timedelta(minutes=9)
        assert worker.due(current["t"]) is False
        current["t"] += timedelta(minutes=2)
        assert worker.due(current["t"]) is True
        worker.close()


class TestDemographicsWorkerRun:
    @pytest.fixture
    def worker(self, tmp_path: Path):
        config = PipelineConfig(
            duckdb_path=str(tmp_path / "test.duckdb"),
            demographics_min_sample_size=2,
            demographics_target_sample_size=10,
        )
        fixture_path = tmp_path / "authors.json"
        fixture_path.write_text(
            json.dumps(
                {
                    "author-0": {"profession": "Software/Tech", "geography": "US"},
                    "author-1": {"profession": "Software/Tech", "geography": "US"},
                    "author-2": {"profession": "Finance"},
                }
            ),
            encoding="utf-8",
        )
        state = RedisStateStore(redis_client=InMemoryRedis(), config=config)
        timeseries_store = TimeSeriesStore(config)
        w = DemographicsWorker(
            state=state,
            timeseries_store=timeseries_store,
            author_metadata_source=StaticAuthorMetadataSource(path=fixture_path, config=config),
            config=config,
        )
        ts = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)
        w.state.set_centroid("topic-x", np.zeros(4, dtype=np.float32), count=3)
        for i in range(3):
            event = _event(f"evt-{i}", f"author-{i}", "topic-x", ts + timedelta(minutes=i))
            timeseries_store.insert_event(event, topic_id="topic-x")
        yield w
        w.close()

    def test_run_once_writes_redis_and_duckdb(self, worker: DemographicsWorker):
        snapshots = worker.run_once(now=datetime(2026, 9, 12, 10, 10, tzinfo=timezone.utc))
        assert len(snapshots) == 1
        assert snapshots[0].topic_id == "topic-x"
        assert snapshots[0].categories.profession.sample_size == 3

        cached = worker.state.get_audience_snapshot("topic-x")
        assert cached is not None
        assert cached["topic_id"] == "topic-x"

        history = worker.timeseries_store.get_audience_snapshots("topic-x")
        assert len(history) == 1
        assert history[0]["categories"]["profession"]["sample_size"] == 3

    def test_redis_down_fallback_still_succeeds(self, tmp_path: Path):
        """In-memory Redis fallback (same pattern as active_centroids elsewhere)
        means the worker degrades the same way rather than failing."""
        config = PipelineConfig(
            duckdb_path=str(tmp_path / "fallback.duckdb"),
            demographics_min_sample_size=1,
            demographics_target_sample_size=5,
        )
        state = RedisStateStore(redis_client=InMemoryRedis(), config=config)
        timeseries_store = TimeSeriesStore(config)
        worker = DemographicsWorker(
            state=state,
            timeseries_store=timeseries_store,
            author_metadata_source=StaticAuthorMetadataSource(path="missing.json", config=config),
            config=config,
        )
        ts = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)
        worker.state.set_centroid("topic-y", np.zeros(4, dtype=np.float32), count=1)
        timeseries_store.insert_event(_event("evt-0", "author-0", "topic-y", ts), topic_id="topic-y")

        snapshots = worker.run_once()
        assert len(snapshots) == 1
        assert worker.state.get_audience_snapshot("topic-y") is not None
        worker.close()


@pytest.fixture
def api_client():
    app = FastAPI()
    app.include_router(audience_api.router)
    client = TestClient(app)
    yield client
    audience_api.set_demographics_worker(None)  # type: ignore[arg-type]


class TestAudienceAPIContract:
    def _worker_with_one_topic(self, tmp_path: Path) -> DemographicsWorker:
        config = PipelineConfig(
            duckdb_path=str(tmp_path / "api.duckdb"),
            demographics_min_sample_size=1,
            demographics_target_sample_size=5,
        )
        state = RedisStateStore(redis_client=InMemoryRedis(), config=config)
        timeseries_store = TimeSeriesStore(config)
        worker = DemographicsWorker(
            state=state,
            timeseries_store=timeseries_store,
            author_metadata_source=StaticAuthorMetadataSource(path="missing.json", config=config),
            config=config,
        )
        ts = datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc)
        worker.state.set_centroid("topic-api", np.zeros(4, dtype=np.float32), count=1)
        timeseries_store.insert_event(_event("evt-0", "author-0", "topic-api", ts), topic_id="topic-api")
        return worker

    def test_list_audience_shape(self, api_client: TestClient, tmp_path: Path):
        worker = self._worker_with_one_topic(tmp_path)
        worker.run_once(now=datetime(2026, 9, 12, 9, 10, tzinfo=timezone.utc))
        audience_api.set_demographics_worker(worker)

        resp = api_client.get("/api/v1/audience")
        assert resp.status_code == 200
        body = resp.json()
        assert "topics" in body
        assert body["topics"][0]["topic_id"] == "topic-api"
        assert "categories" in body["topics"][0]
        worker.close()

    def test_topic_current_snapshot_shape(self, api_client: TestClient, tmp_path: Path):
        worker = self._worker_with_one_topic(tmp_path)
        worker.run_once(now=datetime(2026, 9, 12, 9, 10, tzinfo=timezone.utc))
        audience_api.set_demographics_worker(worker)

        resp = api_client.get("/api/v1/audience/topic-api")
        assert resp.status_code == 200
        body = resp.json()
        assert body["topic_id"] == "topic-api"
        assert "as_of" in body
        for category in ("language", "profession", "geography"):
            assert category in body["categories"]
            cat = body["categories"][category]
            assert {"distribution", "sample_size", "confidence", "unknown_share"} <= cat.keys()
        worker.close()

    def test_topic_history_range_shape(self, api_client: TestClient, tmp_path: Path):
        worker = self._worker_with_one_topic(tmp_path)
        worker.run_once(now=datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc))
        worker.run_once(now=datetime(2026, 9, 12, 9, 15, tzinfo=timezone.utc))
        audience_api.set_demographics_worker(worker)

        resp = api_client.get(
            "/api/v1/audience/topic-api",
            params={"from": "2026-09-12T00:00:00Z", "to": "2026-09-13T00:00:00Z"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["topic_id"] == "topic-api"
        assert "window" in body
        assert len(body["history"]) == 2
        worker.close()

    def test_unknown_topic_returns_404(self, api_client: TestClient, tmp_path: Path):
        worker = self._worker_with_one_topic(tmp_path)
        audience_api.set_demographics_worker(worker)
        resp = api_client.get("/api/v1/audience/does-not-exist")
        assert resp.status_code == 404
        worker.close()
