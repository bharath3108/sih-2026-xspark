"""Background scheduler for 10-minute HDBSCAN buffer flushes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler

if TYPE_CHECKING:
    from src.pipeline.orchestrator import SectionDPipeline

logger = logging.getLogger(__name__)


class BufferFlushScheduler:
    """Runs HDBSCAN batch clustering every 10 minutes."""

    def __init__(self, pipeline: "SectionDPipeline"):
        self.pipeline = pipeline
        self.scheduler = BackgroundScheduler()
        interval_minutes = int(
            pipeline.config.buffer_flush_interval.total_seconds() / 60
        )
        self.scheduler.add_job(
            self._flush,
            "interval",
            minutes=interval_minutes,
            id="hdbscan_buffer_flush",
        )

    def _flush(self) -> None:
        new_topics = self.pipeline.flush_buffer()
        if new_topics:
            logger.info("HDBSCAN created topics: %s", new_topics)

    def start(self) -> None:
        self.scheduler.start()

    def stop(self) -> None:
        self.scheduler.shutdown(wait=False)
