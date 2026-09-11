"""Redis (or in-memory) state store for active centroids and the unclustered buffer."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import numpy as np

from src.config import PipelineConfig, DEFAULT_CONFIG

ACTIVE_CENTROIDS = "active_centroids"
TOPIC_COUNTS = "topic_counts"
TOPIC_NAMES = "topic_names"
EVENT_TOPIC_MAP = "event_topic_map"
UNCLUSTERED_BUFFER = "unclustered_buffer"
TOPIC_ID_SEQ = "topic_id_seq"
EVENT_CACHE_PREFIX = "event:cache:"


class InMemoryRedis:
    """Drop-in subset of Redis used when Redis is not running."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, bytes | str | int]] = defaultdict(dict)
        self._lists: dict[str, list[bytes]] = defaultdict(list)
        self._kv: dict[str, bytes | str | int] = {}

    def hgetall(self, key: str) -> dict[bytes, bytes]:
        return {
            k.encode() if isinstance(k, str) else k: (
                v if isinstance(v, bytes) else str(v).encode()
            )
            for k, v in self._hashes[key].items()
        }

    def hget(self, key: str, field: str) -> bytes | None:
        val = self._hashes[key].get(field)
        if val is None:
            return None
        return val if isinstance(val, bytes) else str(val).encode()

    def hset(self, key: str, field: str, value: Any) -> None:
        if isinstance(value, str):
            value = value.encode()
        self._hashes[key][field] = value

    def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        current = int(self._hashes[key].get(field, 0) or 0)
        current += amount
        self._hashes[key][field] = str(current).encode()
        return current

    def rpush(self, key: str, value: str | bytes) -> int:
        data = value.encode() if isinstance(value, str) else value
        self._lists[key].append(data)
        return len(self._lists[key])

    def lrange(self, key: str, start: int, end: int) -> list[bytes]:
        seq = self._lists[key]
        if end == -1:
            return seq[start:]
        return seq[start : end + 1]

    def lindex(self, key: str, index: int) -> bytes | None:
        seq = self._lists[key]
        try:
            return seq[index]
        except IndexError:
            return None

    def lset(self, key: str, index: int, value: str | bytes) -> None:
        data = value.encode() if isinstance(value, str) else value
        self._lists[key][index] = data

    def delete(self, *keys: str) -> int:
        n = 0
        for key in keys:
            if key in self._hashes:
                del self._hashes[key]
                n += 1
            if key in self._lists:
                del self._lists[key]
                n += 1
            if key in self._kv:
                del self._kv[key]
                n += 1
        return n

    def incr(self, key: str) -> int:
        val = int(self._kv.get(key, 0) or 0) + 1
        self._kv[key] = val
        return val

    def set(self, key: str, value: str | bytes) -> None:
        self._kv[key] = value.encode() if isinstance(value, str) else value

    def get(self, key: str) -> bytes | None:
        val = self._kv.get(key)
        if val is None:
            return None
        return val if isinstance(val, bytes) else str(val).encode()

    def xadd(self, name: str, fields: dict) -> str:
        payload = json.dumps(fields)
        self.rpush(name, payload)
        return str(len(self._lists[name]))

    def xreadgroup(self, *args: Any, **kwargs: Any) -> list:
        return []

    def xgroup_create(self, *args: Any, **kwargs: Any) -> None:
        return None


def connect_redis(config: PipelineConfig = DEFAULT_CONFIG) -> Any:
    try:
        import redis

        client = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=0,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        return client
    except Exception:
        return InMemoryRedis()


class RedisStateStore:
    """Active topic cluster state + unclustered buffer (Redis hashes/lists)."""

    def __init__(self, redis_client: Any | None = None, config: PipelineConfig = DEFAULT_CONFIG):
        self.config = config
        self.redis = redis_client if redis_client is not None else connect_redis(config)

    def get_active_centroids(self) -> dict[str, np.ndarray]:
        raw = self.redis.hgetall(ACTIVE_CENTROIDS)
        centroids: dict[str, np.ndarray] = {}
        for topic_id_b, centroid_b in raw.items():
            topic_id = topic_id_b.decode() if isinstance(topic_id_b, bytes) else str(topic_id_b)
            buf = centroid_b if isinstance(centroid_b, bytes) else bytes(centroid_b)
            centroids[topic_id] = np.frombuffer(buf, dtype=np.float32).copy()
        return centroids

    def set_centroid(self, topic_id: str, centroid: np.ndarray, count: int | None = None) -> None:
        self.redis.hset(ACTIVE_CENTROIDS, topic_id, centroid.astype(np.float32).tobytes())
        if count is not None:
            self.redis.hset(TOPIC_COUNTS, topic_id, str(count))

    def get_count(self, topic_id: str) -> int:
        raw = self.redis.hget(TOPIC_COUNTS, topic_id)
        if raw is None:
            return 0
        return int(raw.decode() if isinstance(raw, bytes) else raw)

    def incr_count(self, topic_id: str, amount: int = 1) -> int:
        return int(self.redis.hincrby(TOPIC_COUNTS, topic_id, amount))

    def next_topic_id(self) -> str:
        seq = int(self.redis.incr(TOPIC_ID_SEQ))
        return f"topic-{seq}"

    def map_event(self, event_id: str, topic_id: str) -> None:
        self.redis.hset(EVENT_TOPIC_MAP, event_id, topic_id)

    def get_event_topic(self, event_id: str) -> str | None:
        raw = self.redis.hget(EVENT_TOPIC_MAP, event_id)
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, bytes) else str(raw)

    def set_topic_name(self, topic_id: str, name: str) -> None:
        self.redis.hset(TOPIC_NAMES, topic_id, name)

    def get_topic_name(self, topic_id: str) -> str:
        raw = self.redis.hget(TOPIC_NAMES, topic_id)
        if raw is None:
            return ""
        return raw.decode() if isinstance(raw, bytes) else str(raw)

    def cache_event(self, event_id: str, payload: dict) -> None:
        self.redis.set(f"{EVENT_CACHE_PREFIX}{event_id}", json.dumps(payload, default=str))

    def get_cached_event(self, event_id: str) -> dict | None:
        raw = self.redis.get(f"{EVENT_CACHE_PREFIX}{event_id}")
        if raw is None:
            return None
        text = raw.decode() if isinstance(raw, bytes) else str(raw)
        return json.loads(text)

    def push_unclustered(self, record: dict) -> None:
        self.redis.rpush(UNCLUSTERED_BUFFER, json.dumps(record, default=str))

    def get_unclustered(self) -> list[dict]:
        raw = self.redis.lrange(UNCLUSTERED_BUFFER, 0, -1)
        items = []
        for item in raw:
            text = item.decode() if isinstance(item, bytes) else str(item)
            items.append(json.loads(text))
        return items

    def replace_unclustered(self, records: list[dict]) -> None:
        self.redis.delete(UNCLUSTERED_BUFFER)
        for rec in records:
            self.push_unclustered(rec)

    def unclustered_size(self) -> int:
        return len(self.get_unclustered())

    def clear_unclustered(self) -> None:
        self.redis.delete(UNCLUSTERED_BUFFER)
