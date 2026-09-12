"""Demographics cron worker — every `config.demographics_interval_minutes`
(default 10) on the topics/trends pipeline's active topic set.

For every active topic (Redis `active_centroids`) it resolves the topic's
current author set (via TimeSeriesStore, which the topics pipeline keeps in
sync with Redis `event_topic_map` as events are assigned), resolves author
metadata through the configured AuthorMetadataSource, aggregates a
language/profession/geography distribution, and:

  - writes the current snapshot to Redis (`audience_current:{topic_id}`),
    mirroring the `active_centroids` pattern, so the API can serve "now" cheaply
  - appends the same snapshot to DuckDB (`audience_snapshots`) for history

This is strictly a periodic batch job — no per-event demographic computation
happens anywhere in this module. It only reads from the topics/trends
pipeline's storage (Redis active_centroids + TimeSeriesStore); it never
mutates clustering/trend state.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.contracts.demographics import AudienceSnapshot
from src.engines.demographics import DemographicsEngine
from src.services.author_metadata import AuthorMetadataSource, build_author_metadata_source
from src.storage.redis_state import RedisStateStore
from src.storage.timeseries_store import TimeSeriesStore

logger = logging.getLogger(__name__)


class DemographicsWorker:
    def __init__(
        self,
        state: RedisStateStore | None = None,
        timeseries_store: TimeSeriesStore | None = None,
        author_metadata_source: AuthorMetadataSource | None = None,
        config: PipelineConfig = DEFAULT_CONFIG,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.config = config
        self.state = state if state is not None else RedisStateStore(config=config)
        self.timeseries_store = timeseries_store if timeseries_store is not None else TimeSeriesStore(config)
        self.author_metadata_source = author_metadata_source or build_author_metadata_source(config)
        self.demographics_engine = DemographicsEngine(config)
        self._clock = clock
        self._last_run: datetime | None = None

    def active_topic_ids(self) -> list[str]:
        return list(self.state.get_active_centroids().keys())

    def due(self, now: datetime | None = None) -> bool:
        """True if `demographics_interval_minutes` have elapsed since the last
        run (or this worker has never run). Takes an explicit `now` so tests
        can drive cadence without sleeping."""
        now = now if now is not None else self._clock()
        if self._last_run is None:
            return True
        elapsed = now - self._last_run
        return elapsed >= timedelta(minutes=self.config.demographics_interval_minutes)

    def compute_topic_snapshot(self, topic_id: str, now: datetime | None = None) -> AudienceSnapshot:
        now = now if now is not None else self._clock()
        author_ids = self.timeseries_store.get_topic_author_ids(topic_id)
        known_metadata = self.author_metadata_source.get_metadata(author_ids)
        full_metadata = {aid: known_metadata.get(aid, {}) for aid in author_ids}
        categories = self.demographics_engine.compute(full_metadata)
        return AudienceSnapshot(topic_id=topic_id, as_of=now, categories=categories)

    def run_once(self, now: datetime | None = None) -> list[AudienceSnapshot]:
        now = now if now is not None else self._clock()
        snapshots = []
        for topic_id in self.active_topic_ids():
            snapshot = self.compute_topic_snapshot(topic_id, now)
            self._persist(snapshot)
            snapshots.append(snapshot)
        self._last_run = now
        logger.info("Demographics worker updated %d topic(s)", len(snapshots))
        return snapshots

    def _persist(self, snapshot: AudienceSnapshot) -> None:
        data = snapshot.to_json_dict()
        self.state.set_audience_snapshot(snapshot.topic_id, data)
        self.timeseries_store.insert_audience_snapshot(snapshot.topic_id, snapshot.as_of, data)

    def run_forever(self, sleep_fn: Callable[[float], None] = time.sleep, poll_seconds: int = 30) -> None:
        logger.info(
            "Demographics worker running every %s minute(s)",
            self.config.demographics_interval_minutes,
        )
        while True:
            if self.due():
                self.run_once()
            sleep_fn(poll_seconds)

    def close(self) -> None:
        self.timeseries_store.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    worker = DemographicsWorker()
    try:
        worker.run_forever()
    except KeyboardInterrupt:
        worker.close()


if __name__ == "__main__":
    main()
