"""Redis Stream / Kafka consumer for Person 2 NLP events."""

from __future__ import annotations

import json
import logging
import time

from src.config import DEFAULT_CONFIG, PipelineConfig
from src.pipeline.orchestrator import SectionDPipeline

logger = logging.getLogger(__name__)


class StreamConsumerService:
    """
    Production: XREADGROUP on Redis Stream `person2:nlp_events`.
    WIRE LATER: swap consume_forever() to Kafka consumer using
    config.kafka_bootstrap_servers / config.kafka_topic.
    """

    def __init__(self, pipeline: SectionDPipeline, config: PipelineConfig = DEFAULT_CONFIG):
        self.pipeline = pipeline
        self.config = config
        self.redis = pipeline.state.redis

    def ensure_group(self) -> None:
        try:
            self.redis.xgroup_create(
                self.config.redis_stream_key,
                self.config.redis_consumer_group,
                id="0",
                mkstream=True,
            )
        except Exception:
            pass

    def handle_message(self, fields: dict) -> None:
        payload = fields.get("payload") or fields.get(b"payload")
        if isinstance(payload, bytes):
            payload = payload.decode()
        if payload is None:
            payload = json.dumps(
                { (k.decode() if isinstance(k, bytes) else k): (
                    v.decode() if isinstance(v, bytes) else v
                ) for k, v in fields.items() }
            )
        self.pipeline.ingest_stream_json(payload)

    def consume_forever(self, poll_seconds: float = 1.0) -> None:
        self.ensure_group()
        logger.info("Listening on Redis stream %s", self.config.redis_stream_key)
        while True:
            try:
                resp = self.redis.xreadgroup(
                    groupname=self.config.redis_consumer_group,
                    consumername=self.config.redis_consumer_name,
                    streams={self.config.redis_stream_key: ">"},
                    count=50,
                    block=int(poll_seconds * 1000),
                )
            except Exception as exc:
                logger.warning("Stream read failed (%s); retrying", exc)
                time.sleep(poll_seconds)
                continue
            if not resp:
                continue
            for _stream, messages in resp:
                for msg_id, fields in messages:
                    try:
                        self.handle_message(fields)
                    except Exception:
                        logger.exception("Failed to process %s", msg_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    pipeline = SectionDPipeline()
    pipeline.connect_external_stores()
    StreamConsumerService(pipeline).consume_forever()


if __name__ == "__main__":
    main()
