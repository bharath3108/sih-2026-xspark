"""Step 2b: Unclustered buffer for posts below similarity threshold."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.contracts.nlp_input import IngestedEvent


@dataclass
class BufferedEvent:
    event: IngestedEvent
    buffered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class UnclusteredBuffer:
    """Holds events with Sim < 0.80 until HDBSCAN batch or expiration."""

    def __init__(self, config: PipelineConfig = DEFAULT_CONFIG):
        self.config = config
        self._buffer: list[BufferedEvent] = []

    def push(self, event: IngestedEvent) -> None:
        self._buffer.append(BufferedEvent(event=event))

    def get_events(self) -> list[IngestedEvent]:
        return [be.event for be in self._buffer]

    def size(self) -> int:
        return len(self._buffer)

    def expire_stale(self) -> list[IngestedEvent]:
        """Remove points older than 6 hours."""
        cutoff = datetime.now(timezone.utc) - self.config.buffer_expiration
        kept: list[BufferedEvent] = []
        expired: list[IngestedEvent] = []
        for be in self._buffer:
            if be.buffered_at < cutoff:
                expired.append(be.event)
            else:
                kept.append(be)
        self._buffer = kept
        return expired

    def remove_events(self, event_ids: set[str]) -> None:
        self._buffer = [
            be for be in self._buffer if be.event.event_id not in event_ids
        ]

    def clear(self) -> None:
        self._buffer.clear()
