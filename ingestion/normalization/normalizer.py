import hashlib
import re
from datetime import datetime
from contracts.canonical_event import CanonicalEvent, EngagementMetrics

def hash_author_id(raw_author_id: str) -> str:
    return hashlib.sha256(raw_author_id.encode('utf-8')).hexdigest()[:16]

def extract_entities(text: str) -> list[str]:
    hashtags = re.findall(r"#\w+", text)
    mentions = re.findall(r"@\w+", text)
    return list(set(hashtags + mentions))

def normalize_raw_post(raw: dict) -> CanonicalEvent:
    author_hash = hash_author_id(str(raw.get("author_id", "anonymous")))
    entities = extract_entities(raw.get("text", "") or "")
    # "engagement" may be absent OR explicitly null in a malformed upstream
    # record — `raw.get("engagement", {})` only covers the absent case.
    engagement = raw.get("engagement") or {}

    return CanonicalEvent(
        source=raw.get("source") or "other",
        source_post_id=str(raw.get("id")),
        author_id_hash=author_hash,
        timestamp_utc=raw.get("timestamp_utc", datetime.utcnow().isoformat()),
        text=raw.get("text", ""),
        language=raw.get("language", "en"),
        reply_to_id=raw.get("reply_to_id"),
        engagement=EngagementMetrics(
            likes=engagement.get("likes", 0),
            shares=engagement.get("shares", 0),
            comments=engagement.get("comments", 0),
            views=engagement.get("views", 0)
        ),
        entities=entities,
        metadata={
            "source_version": raw.get("source_version", "1.0.0"),
            "collected_at_utc": datetime.utcnow().isoformat()
        }
    )