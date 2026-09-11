from dataclasses import dataclass
from typing import List
from dateutil import parser as dtparser
from datetime import timedelta
import numpy as np

from .store import JoinedEvent


def _engagement_sum(e: JoinedEvent) -> int:
    eng = e.engagement or {}
    return int(eng.get("likes", 0) + eng.get("shares", 0) + eng.get("comments", 0) + eng.get("views", 0))


@dataclass
class BucketStats:
    start: str
    end: str
    volume: int
    unique_authors: int
    engagement: int


def bucketize(events: List[JoinedEvent], bucket_minutes: int) -> List[BucketStats]:
    if not events:
        return []
    events = sorted(events, key=lambda x: x.timestamp_utc)

    start_ts = dtparser.isoparse(events[0].timestamp_utc)
    end_ts = dtparser.isoparse(events[-1].timestamp_utc)

    bucket = timedelta(minutes=bucket_minutes)
    cur = start_ts.replace(minute=(start_ts.minute // bucket_minutes) * bucket_minutes, second=0, microsecond=0)

    out: List[BucketStats] = []
    while cur <= end_ts:
        nxt = cur + bucket
        in_bucket = [e for e in events if cur <= dtparser.isoparse(e.timestamp_utc) < nxt]
        if in_bucket:
            authors = {e.author_id_hash for e in in_bucket}
            out.append(
                BucketStats(
                    start=cur.isoformat(),
                    end=nxt.isoformat(),
                    volume=len(in_bucket),
                    unique_authors=len(authors),
                    engagement=sum(_engagement_sum(e) for e in in_bucket),
                )
            )
        cur = nxt
    return out


def cross_spread_proxy(events: List[JoinedEvent]) -> float:
    if not events:
        return 0.0
    authors = [e.author_id_hash for e in events]
    _, counts = np.unique(authors, return_counts=True)
    p = counts / counts.sum()
    entropy = float(-(p * np.log(p + 1e-12)).sum())
    max_entropy = float(np.log(len(counts) + 1e-12))
    return float(entropy / max_entropy) if max_entropy > 0 else 0.0


def novelty(current_count: int, baseline_count: int) -> float:
    if current_count <= 0:
        return 0.0
    return float(1.0 - (baseline_count / (baseline_count + current_count + 1e-9)))


def _norm(x: float, cap: float = 5.0) -> float:
    if x <= 0:
        return 0.0
    return float(min(1.0, x / cap))


def trend_score(timeline: List[BucketStats], novelty_score: float, spread: float) -> float:
    if len(timeline) < 2:
        return 0.0
    t, p = timeline[-1], timeline[-2]

    v_accel = (t.volume - p.volume) / max(1, p.volume)
    a_growth = (t.unique_authors - p.unique_authors) / max(1, p.unique_authors)
    e_growth = (t.engagement - p.engagement) / max(1, p.engagement)

    score = (
        0.30 * _norm(v_accel) +
        0.20 * _norm(a_growth) +
        0.20 * _norm(e_growth) +
        0.15 * max(0.0, min(1.0, novelty_score)) +
        0.15 * max(0.0, min(1.0, spread))
    )
    return float(max(0.0, min(1.0, score)))