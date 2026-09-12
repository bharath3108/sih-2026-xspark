from sqlalchemy import Column, String, DateTime, JSON, Text
from backend.db.database import Base
from datetime import datetime

class CanonicalEventModel(Base):
    __tablename__ = "canonical_events"

    event_id = Column(String, primary_key=True, index=True)
    source = Column(String, index=True, nullable=False)
    source_post_id = Column(String, index=True, nullable=False)
    author_id_hash = Column(String, index=True, nullable=False)
    timestamp_utc = Column(DateTime, index=True, nullable=False)
    text = Column(Text, nullable=False)
    language = Column(String, default="en")
    reply_to_id = Column(String, nullable=True)
    parent_event_id = Column(String, nullable=True)
    engagement = Column(JSON, default={})
    entities = Column(JSON, default=[])
    event_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)


class NLPOutputModel(Base):
    """Person 2's NLP Output Contract, persisted per ingested event so the
    dashboard can read real sentiment/emotion/stance instead of only the
    static nlp_outputs.json fixture. Mirrors backend/schemas/contracts.py's
    NLPOutput shape."""

    __tablename__ = "nlp_outputs"

    event_id = Column(String, primary_key=True, index=True)
    language = Column(JSON, default={})
    sentiment = Column(JSON, default={})
    emotion = Column(JSON, nullable=True)
    stance = Column(JSON, default={})
    embedding_ref = Column(String, nullable=True)
    evidence = Column(JSON, default=[])
    model = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)