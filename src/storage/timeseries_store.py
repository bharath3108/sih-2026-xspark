"""Time-series store for raw event associations (DuckDB)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.contracts.nlp_input import IngestedEvent


def _utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class TimeSeriesStore:
    """Stores event associations indexed by (topic_id, timestamp, platform, author_id)."""

    def __init__(self, config: PipelineConfig = DEFAULT_CONFIG):
        self.config = config
        Path(config.duckdb_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(config.duckdb_path)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id VARCHAR PRIMARY KEY,
                topic_id VARCHAR,
                timestamp TIMESTAMP,
                platform VARCHAR,
                author_id VARCHAR,
                likes INTEGER,
                shares INTEGER,
                comments INTEGER,
                raw_text VARCHAR
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_topic_ts
            ON events (topic_id, timestamp)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_author
            ON events (author_id)
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS audience_snapshots (
                topic_id VARCHAR,
                timestamp TIMESTAMP,
                payload VARCHAR
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audience_snapshots_topic_ts
            ON audience_snapshots (topic_id, timestamp)
        """)

    def insert_event(self, event: IngestedEvent, topic_id: str | None = None) -> None:
        tid = topic_id or event.topic_id
        self._conn.execute(
            """
            INSERT OR REPLACE INTO events
            (event_id, topic_id, timestamp, platform, author_id, likes, shares, comments, raw_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event.event_id,
                tid,
                event.timestamp if isinstance(event.timestamp, str) else _utc_naive(event.timestamp),
                event.platform.value,
                event.author_id,
                event.likes,
                event.shares,
                event.comments,
                event.raw_text,
            ],
        )

    def assign_topic(self, event_id: str, topic_id: str) -> None:
        self._conn.execute(
            "UPDATE events SET topic_id = ? WHERE event_id = ?",
            [topic_id, event_id],
        )

    def get_events_for_topic(
        self, topic_id: str, start: datetime | None = None, end: datetime | None = None
    ) -> list[dict]:
        query = "SELECT * FROM events WHERE topic_id = ?"
        params: list = [topic_id]
        if start is not None:
            query += " AND timestamp >= ?"
            params.append(_utc_naive(start))
        if end is not None:
            query += " AND timestamp <= ?"
            params.append(_utc_naive(end))
        query += " ORDER BY timestamp"
        rows = self._conn.execute(query, params).fetchall()
        cols = [d[0] for d in self._conn.description]
        records = [dict(zip(cols, row)) for row in rows]
        for rec in records:
            rec["timestamp"] = _aware(rec["timestamp"])
        return records

    def get_topic_author_ids(self, topic_id: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT author_id FROM events WHERE topic_id = ?",
            [topic_id],
        ).fetchall()
        return [r[0] for r in rows]

    def get_platform_distribution(self, topic_id: str) -> dict[str, int]:
        rows = self._conn.execute(
            """
            SELECT platform, COUNT(*) as cnt
            FROM events WHERE topic_id = ?
            GROUP BY platform
            """,
            [topic_id],
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    def get_bucket_stats(
        self, topic_id: str, bucket_start: datetime, bucket_end: datetime
    ) -> dict:
        row = self._conn.execute(
            """
            SELECT
                COUNT(*) as volume,
                COUNT(DISTINCT author_id) as authors,
                COALESCE(SUM(likes + shares + comments), 0) as engagement
            FROM events
            WHERE topic_id = ?
              AND timestamp >= ?
              AND timestamp < ?
            """,
            [topic_id, _utc_naive(bucket_start), _utc_naive(bucket_end)],
        ).fetchone()
        return {
            "volume": row[0],
            "authors": row[1],
            "engagement": row[2],
        }

    def get_all_bucket_starts(self, topic_id: str) -> list[datetime]:
        rows = self._conn.execute(
            """
            SELECT DISTINCT date_trunc('hour', timestamp) as bucket
            FROM events WHERE topic_id = ?
            ORDER BY bucket
            """,
            [topic_id],
        ).fetchall()
        return [_aware(r[0]) for r in rows]

    def insert_audience_snapshot(self, topic_id: str, timestamp: datetime, payload: dict) -> None:
        self._conn.execute(
            "INSERT INTO audience_snapshots (topic_id, timestamp, payload) VALUES (?, ?, ?)",
            [topic_id, _utc_naive(timestamp), json.dumps(payload, default=str)],
        )

    def get_audience_snapshots(
        self, topic_id: str, start: datetime | None = None, end: datetime | None = None
    ) -> list[dict]:
        query = "SELECT timestamp, payload FROM audience_snapshots WHERE topic_id = ?"
        params: list = [topic_id]
        if start is not None:
            query += " AND timestamp >= ?"
            params.append(_utc_naive(start))
        if end is not None:
            query += " AND timestamp <= ?"
            params.append(_utc_naive(end))
        query += " ORDER BY timestamp"
        rows = self._conn.execute(query, params).fetchall()
        records = []
        for ts, payload_json in rows:
            payload = json.loads(payload_json)
            payload["as_of"] = _aware(ts).isoformat()
            records.append(payload)
        return records

    def close(self) -> None:
        self._conn.close()
