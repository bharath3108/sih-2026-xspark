"""Step 7: Traceability & Representative Evidence Engine."""

from __future__ import annotations

import numpy as np

from src.contracts.nlp_input import IngestedEvent, Platform
from src.storage.timeseries_store import TimeSeriesStore
from src.utils.vectors import cosine_distance, to_array


class EvidenceEngine:
    """
    Selects medoid (highest semantic centrality) and virality catalyst
    for evidence_event_ids output.
    """

    def __init__(self, timeseries_store: TimeSeriesStore):
        self.timeseries_store = timeseries_store

    def select_closest_to_centroid(
        self, centroid: np.ndarray, events: list[IngestedEvent]
    ) -> str | None:
        if not events:
            return None
        best_id = None
        min_dist = float("inf")
        c = np.asarray(centroid, dtype=np.float64)
        for event in events:
            dist = float(np.linalg.norm(c - to_array(event.vector)))
            if dist < min_dist:
                min_dist = dist
                best_id = event.event_id
        return best_id

    def select_medoid(self, events: list[IngestedEvent]) -> str | None:
        if not events:
            return None
        if len(events) == 1:
            return events[0].event_id

        vectors = [to_array(e.vector) for e in events]
        best_idx = 0
        best_total_dist = float("inf")

        for i, vi in enumerate(vectors):
            total_dist = sum(cosine_distance(vi, vj) for j, vj in enumerate(vectors))
            if total_dist < best_total_dist:
                best_total_dist = total_dist
                best_idx = i

        return events[best_idx].event_id

    def select_virality_catalyst(
        self,
        events: list[IngestedEvent],
        acceleration_start: str | None = None,
        acceleration_end: str | None = None,
    ) -> str | None:
        if not events:
            return None

        candidates = events
        if acceleration_start and acceleration_end:
            from datetime import datetime

            start = datetime.fromisoformat(acceleration_start.replace("Z", "+00:00"))
            end = datetime.fromisoformat(acceleration_end.replace("Z", "+00:00"))
            window_events = [
                e for e in events if start <= e.timestamp.replace(tzinfo=start.tzinfo) <= end
            ]
            if window_events:
                candidates = window_events

        best = max(candidates, key=lambda e: e.engagement)
        return best.event_id

    def select_evidence(
        self,
        events: list[IngestedEvent],
        acceleration_window: tuple[str, str] | None = None,
    ) -> list[str]:
        medoid_id = self.select_medoid(events)
        viral_id = None
        if acceleration_window:
            viral_id = self.select_virality_catalyst(
                events, acceleration_window[0], acceleration_window[1]
            )
        else:
            viral_id = self.select_virality_catalyst(events)

        ids: list[str] = []
        if medoid_id:
            ids.append(medoid_id)
        if viral_id and viral_id != medoid_id:
            ids.append(viral_id)
        elif viral_id and viral_id not in ids:
            ids.append(viral_id)
        return ids

    def select_from_topic(
        self,
        topic_id: str,
        event_vectors: dict[str, list[float]],
    ) -> list[str]:
        rows = self.timeseries_store.get_events_for_topic(topic_id)
        events: list[IngestedEvent] = []
        for row in rows:
            vec = event_vectors.get(row["event_id"])
            if vec is None:
                continue
            platform = row["platform"]
            if isinstance(platform, str):
                platform = Platform(platform)
            events.append(
                IngestedEvent(
                    event_id=row["event_id"],
                    timestamp=row["timestamp"],
                    platform=platform,
                    author_id=row["author_id"],
                    likes=row["likes"],
                    shares=row["shares"],
                    comments=row["comments"],
                    raw_text=row.get("raw_text"),
                    vector=vec,
                    topic_id=topic_id,
                )
            )
        return self.select_evidence(events)
