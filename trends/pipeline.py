from typing import List, Dict
from dateutil import parser as dtparser
from datetime import timedelta

from .config import settings
from .store import get_store, JoinedEvent
from .topic_model import cluster_topics, TopicRegistry
from .trend_score import bucketize, cross_spread_proxy, novelty, trend_score
from .audience import compute_audience


def build_topics(start_iso: str, end_iso: str) -> List[Dict]:
    store = get_store()
    joined = store.query_joined_events(start_iso, end_iso)

    # baseline window for novelty
    start_dt = dtparser.isoparse(start_iso)
    end_dt = dtparser.isoparse(end_iso)
    dur = end_dt - start_dt
    baseline = store.query_joined_events((start_dt - dur).isoformat(), start_iso)

    clusters = cluster_topics(joined)
    reg = TopicRegistry()

    outputs: List[Dict] = []
    for cl in clusters:
        topic_id = reg.match_or_create(cl.centroid)

        topic_event_ids = set(cl.event_ids)
        topic_events = [e for e in joined if e.event_id in topic_event_ids]

        baseline_count = sum(1 for e in baseline if e.event_id in topic_event_ids)  # MVP simplification

        timeline_stats = bucketize(topic_events, bucket_minutes=settings.BUCKET_MINUTES)
        nov = novelty(len(topic_events), baseline_count)
        spread = cross_spread_proxy(topic_events)
        tscore = trend_score(timeline_stats, novelty_score=nov, spread=spread)

        authors = {e.author_id_hash for e in topic_events}
        engagement = sum(
            int((e.engagement or {}).get("likes", 0)
                + (e.engagement or {}).get("shares", 0)
                + (e.engagement or {}).get("comments", 0)
                + (e.engagement or {}).get("views", 0))
            for e in topic_events
        )

        out = {
            "topic_id": topic_id,
            "name": cl.name,
            "window": {"start": start_iso, "end": end_iso},
            "metrics": {
                "volume": len(topic_events),
                "unique_authors": len(authors),
                "engagement": int(engagement),
                "trend_score": float(tscore),
                "novelty": float(nov),
                "cross_community_spread": float(spread),
            },
            "timeline": [
                {
                    "bucket_start": b.start,
                    "bucket_end": b.end,
                    "volume": b.volume,
                    "unique_authors": b.unique_authors,
                    "engagement": b.engagement,
                }
                for b in timeline_stats
            ],
            "audience": compute_audience(topic_events),
            "evidence_event_ids": cl.event_ids[:15],
        }
        outputs.append(out)

    return outputs