from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.db.database import get_db
from backend.db.models import CanonicalEventModel
from ingestion.adapters.replay_adapter import ReplayAdapter
from ingestion.adapters.live_adapter import LiveAdapter
from ingestion.normalization.normalizer import normalize_raw_post

router = APIRouter(prefix="/api/ingestion", tags=["Ingestion"])

@router.get("/health")
def ingestion_health():
    return {"status": "ok", "file_found": True}

@router.post("/run-replay")
def run_replay_ingestion(db: Session = Depends(get_db)):
    adapter = ReplayAdapter()
    raw_posts = adapter.fetch_posts()
    
    count = 0
    for post in raw_posts:
        normalized = normalize_raw_post(post)
        # Convert Pydantic object to dictionary using model_dump() or dict()
        event_dict = normalized.model_dump() if hasattr(normalized, 'model_dump') else normalized.dict()
        
        db_event = CanonicalEventModel(**event_dict)
        db.merge(db_event)
        count += 1
        
    db.commit()
    return {"status": "success", "events_ingested": count, "mode": "replay"}

@router.post("/run-live")
def run_live_ingestion(db: Session = Depends(get_db)):
    adapter = LiveAdapter()
    raw_posts = adapter.fetch_live_posts()
    
    if not raw_posts:
        raise HTTPException(status_code=502, detail="Failed to fetch live feed")
        
    count = 0
    for post in raw_posts:
        normalized = normalize_raw_post(post)
        # Convert Pydantic object to dictionary
        event_dict = normalized.model_dump() if hasattr(normalized, 'model_dump') else normalized.dict()
        
        db_event = CanonicalEventModel(**event_dict)
        db.merge(db_event)
        count += 1
        
    db.commit()
    return {"status": "success", "events_ingested": count, "mode": "live_reddit"}