"""Step 5: Chronological Tracking & Lifecycle Engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.contracts.section_d import TimelineBucket
from src.storage.timeseries_store import TimeSeriesStore


def _utc(dt: datetime) -> datetime:
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class LifecycleStage(str, Enum):
    FIRST_APPEARANCE = "first_appearance"
    ACCELERATION = "acceleration"
    PEAK = "peak"
    DECLINE = "decline"


LifecyclePhase = LifecycleStage


class TopicLifecycleTracker:
    """1-hour bucket state machine for first_appearance / acceleration / peak / decline."""

    def __init__(self, config: PipelineConfig = DEFAULT_CONFIG):
        self.config = config

    def evaluate_lifecycle_state(
        self,
        current_volume: int,
        prev_volume: int,
        prev_prev_volume: int,
        author_growth_rate: float,
        age_in_hours: float,
    ) -> LifecycleStage:
        velocity = current_volume - prev_volume
        acceleration = velocity - (prev_volume - prev_prev_volume)

        if (
            age_in_hours <= self.config.first_appearance_max_hours
            and current_volume >= self.config.lifecycle_min_volume
        ):
            return LifecycleStage.FIRST_APPEARANCE

        if (
            velocity > 0
            and acceleration > 0
            and author_growth_rate > self.config.author_growth_threshold
        ):
            return LifecycleStage.ACCELERATION

        if (
            prev_volume > 0
            and abs(velocity) <= (self.config.peak_velocity_ratio * max(1, current_volume))
            and current_volume >= prev_volume
        ):
            return LifecycleStage.PEAK

        if velocity < 0 and prev_volume > 0:
            drop = prev_volume - current_volume
            if drop > (self.config.decline_drop_ratio * prev_volume):
                return LifecycleStage.DECLINE

        return LifecycleStage.ACCELERATION


class LifecycleEngine:
    """
    Partitions events into 1-hour buckets and classifies lifecycle phases.
    """

    def __init__(
        self,
        timeseries_store: TimeSeriesStore,
        config: PipelineConfig = DEFAULT_CONFIG,
    ):
        self.timeseries_store = timeseries_store
        self.config = config
        self.tracker = TopicLifecycleTracker(config)

    def _bucket_end(self, bucket_start: datetime) -> datetime:
        return bucket_start + self.config.bucket_size

    def compute_buckets(self, topic_id: str) -> list[dict]:
        bucket_starts = self.timeseries_store.get_all_bucket_starts(topic_id)
        if not bucket_starts:
            return []

        buckets: list[dict] = []
        for bs in bucket_starts:
            be = self._bucket_end(bs)
            stats = self.timeseries_store.get_bucket_stats(topic_id, bs, be)
            buckets.append(
                {
                    "bucket_start": bs,
                    "volume": stats["volume"],
                    "authors": stats["authors"],
                    "engagement": stats["engagement"],
                }
            )
        return buckets

    def _volume_velocity(self, buckets: list[dict], idx: int) -> float:
        if idx == 0:
            return float(buckets[idx]["volume"])
        return buckets[idx]["volume"] - buckets[idx - 1]["volume"]

    def _volume_acceleration(self, buckets: list[dict], idx: int) -> float:
        v_curr = self._volume_velocity(buckets, idx)
        v_prev = self._volume_velocity(buckets, idx - 1) if idx > 0 else 0.0
        return v_curr - v_prev

    def _author_growth(self, buckets: list[dict], idx: int) -> float:
        if idx == 0:
            return 0.0
        prev = max(1, buckets[idx - 1]["authors"])
        return (buckets[idx]["authors"] - buckets[idx - 1]["authors"]) / prev

    def classify_phase(
        self, buckets: list[dict], idx: int, topic_created: datetime
    ) -> LifecyclePhase:
        b = buckets[idx]
        g_a = self._author_growth(buckets, idx)
        prev_volume = buckets[idx - 1]["volume"] if idx > 0 else 0
        prev_prev_volume = buckets[idx - 2]["volume"] if idx > 1 else prev_volume
        bucket_time = _utc(b["bucket_start"])
        origin = _utc(topic_created)
        lifetime_hours = (bucket_time - origin).total_seconds() / 3600
        return self.tracker.evaluate_lifecycle_state(
            current_volume=b["volume"],
            prev_volume=prev_volume,
            prev_prev_volume=prev_prev_volume,
            author_growth_rate=g_a,
            age_in_hours=lifetime_hours,
        )

    def build_timeline(
        self, topic_id: str, topic_created: datetime
    ) -> list[TimelineBucket]:
        buckets = self.compute_buckets(topic_id)
        timeline: list[TimelineBucket] = []

        for idx, b in enumerate(buckets):
            phase = self.classify_phase(buckets, idx, topic_created)
            bs = _utc(b["bucket_start"])
            timeline.append(
                TimelineBucket(
                    bucket_start=bs,
                    volume=b["volume"],
                    authors=b["authors"],
                    status=phase.value,
                )
            )
        return timeline

    def get_latest_metrics(self, topic_id: str) -> dict:
        buckets = self.compute_buckets(topic_id)
        if not buckets:
            return {
                "volume": 0,
                "authors": 0,
                "engagement": 0,
                "acceleration": 0.0,
                "author_growth": 0.0,
                "volume_std": 1.0,
            }

        total_volume = sum(b["volume"] for b in buckets)
        total_engagement = sum(b["engagement"] for b in buckets)
        all_authors = self.timeseries_store.get_topic_author_ids(topic_id)

        idx = len(buckets) - 1
        volumes = [b["volume"] for b in buckets]
        vol_std = (
            (sum((v - sum(volumes) / len(volumes)) ** 2 for v in volumes) / len(volumes))
            ** 0.5
            if len(volumes) > 1
            else 1.0
        )

        return {
            "volume": total_volume,
            "authors": len(all_authors),
            "engagement": total_engagement,
            "acceleration": self._volume_acceleration(buckets, idx),
            "author_growth": self._author_growth(buckets, idx),
            "volume_std": max(vol_std, 1.0),
            "engagement_per_author": total_engagement / max(1, len(all_authors)),
        }
