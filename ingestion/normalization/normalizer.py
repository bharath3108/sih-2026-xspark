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
    entities = extract_entities(raw.get("text", ""))
    
    return CanonicalEvent(
        source=raw.get("source", "unknown"),
        source_post_id=str(raw.get("id")),
        author_id_hash=author_hash,
        timestamp_utc=raw.get("timestamp_utc", datetime.utcnow().isoformat()),
        text=raw.get("text", ""),
        language=raw.get("language", "en"),
        reply_to_id=raw.get("reply_to_id"),
        engagement=EngagementMetrics(
            likes=raw.get("engagement", {}).get("likes", 0),
            shares=raw.get("engagement", {}).get("shares", 0),
            comments=raw.get("engagement", {}).get("comments", 0),
            views=raw.get("engagement", {}).get("views", 0)
        ),
        entities=entities,
        metadata={"collected_at_utc": datetime.utcnow().isoformat()}
    )