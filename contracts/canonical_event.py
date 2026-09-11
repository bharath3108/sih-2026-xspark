from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import uuid

class EngagementMetrics(BaseModel):
    likes: int = 0
    shares: int = 0
    comments: int = 0
    views: int = 0

class CanonicalEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    source_post_id: str
    author_id_hash: str
    timestamp_utc: str
    text: str
    language: str = "en"
    reply_to_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    engagement: EngagementMetrics = Field(default_factory=EngagementMetrics)
    entities: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)