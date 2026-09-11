"""HDBSCAN cron worker — every 10 minutes on the Redis unclustered buffer."""

from __future__ import annotations

import logging
import time

from src.config import DEFAULT_CONFIG
from src.pipeline.orchestrator import SectionDPipeline
from src.pipeline.scheduler import BufferFlushScheduler

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    pipeline = SectionDPipeline()
    pipeline.connect_external_stores()
    scheduler = BufferFlushScheduler(pipeline)
    scheduler.start()
    logger.info("HDBSCAN worker running every %s", DEFAULT_CONFIG.buffer_flush_interval)
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.stop()
        pipeline.close()


if __name__ == "__main__":
    main()
