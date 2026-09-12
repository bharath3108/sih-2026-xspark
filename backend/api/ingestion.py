from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import CanonicalEventModel, NLPOutputModel
from backend.services import data_access
from contracts.canonical_event import CanonicalEvent
from ingestion.adapters.replay_adapter import ReplayAdapter
from ingestion.adapters.live_adapter import LiveAdapter
from ingestion.normalization.normalizer import normalize_raw_post

router = APIRouter(prefix="/api/ingestion", tags=["Ingestion"])

_VALID_NLP_SOURCES = {"x", "telegram", "reddit", "instagram", "other"}


@router.get("/health")
def ingestion_health():
    return {"status": "ok", "file_found": True}


def _event_to_db_row(event: CanonicalEvent) -> dict:
    """CanonicalEvent.metadata collides with SQLAlchemy's reserved `metadata`
    attribute on every Base-derived model; the DB column is `event_metadata`.
    timestamp_utc is also a plain ISO string on the contract but a DateTime
    column in the DB, so it needs parsing before construction."""
    data = event.model_dump()
    data["event_metadata"] = data.pop("metadata")
    ts = data["timestamp_utc"]
    if isinstance(ts, str):
        data["timestamp_utc"] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return data


def _resolve_parent_event_id(db: Session, normalized: CanonicalEvent) -> None:
    """reply_to_id, as copied straight from the raw platform post, is a
    source_post_id-style reference (e.g. "x_1001"), not an internal event_id
    -- event_id is a fresh random UUID minted per normalize() call, so the
    graph module (which needs a real parent event_id to build author->author
    edges) could never resolve a reply target without this lookup."""
    if not normalized.reply_to_id or normalized.parent_event_id:
        return
    # A reply can cross platforms (e.g. Telegram replying to an X post), so
    # this must not filter by the replying post's own source.
    parent = (
        db.query(CanonicalEventModel)
        .filter_by(source_post_id=normalized.reply_to_id)
        .first()
    )
    if parent is not None:
        normalized.parent_event_id = parent.event_id


def _run_nlp_analysis(db: Session, event: CanonicalEvent) -> None:
    """Best-effort: run the event through Person 2's analyzer, persist the
    NLP Output Contract, and feed Person 3's live pipeline. ml/mainml.py
    degrades to deterministic local fallbacks on its own if its transformer
    models aren't loaded, so this only fails on a genuine bug -- caught here
    so a Person-2/3 hiccup never blocks ingestion itself."""
    try:
        from ml.mainml import (
            SocialMediaEventRequest,
            Engagement as MlEngagement,
            Metadata as MlMetadata,
            process_social_event,
        )
        from ml.adapterml import NLPAdapter

        ts = event.timestamp_utc
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        source = event.source if event.source in _VALID_NLP_SOURCES else "other"

        request = SocialMediaEventRequest(
            event_id=UUID(event.event_id),
            source=source,
            source_post_id=event.source_post_id,
            author_id_hash=event.author_id_hash,
            timestamp_utc=ts,
            text=event.text,
            language=event.language,
            reply_to_id=event.reply_to_id,
            parent_event_id=UUID(event.parent_event_id) if event.parent_event_id else None,
            engagement=MlEngagement(**event.engagement.model_dump()),
            metadata=MlMetadata(
                source_version=event.metadata.get("source_version", "1.0.0"),
                collected_at_utc=datetime.now(timezone.utc),
            ),
        )
        response = process_social_event(request)

        nlp_row = NLPOutputModel(
            event_id=event.event_id,
            language=response.language.model_dump(),
            sentiment=response.sentiment.model_dump(),
            emotion=response.emotion.model_dump(),
            stance=response.stance.model_dump(),
            embedding_ref=response.embedding_ref,
            evidence=[e.model_dump(mode="json") for e in response.evidence],
            model=response.model.model_dump(),
        )
        db.merge(nlp_row)

        nlp_contract = NLPAdapter.social_media_event_to_nlp_contract(request, response)
        from backend.services import live_pipeline

        live_pipeline.ingest_nlp_output(nlp_contract)
    except Exception as e:
        print(f"[WARN] NLP analysis failed for event {event.event_id}: {e}")


def _ingest_raw_posts(db: Session, raw_posts: list[dict]) -> dict:
    """Normalizes + inserts raw posts, skipping (not crashing on) malformed
    records and deduping by (source, source_post_id) since each normalize()
    call mints a fresh random event_id, so merge()-by-primary-key alone
    would not catch a post ingested twice across separate runs."""
    ingested = 0
    skipped_duplicates = 0
    failed: list[dict] = []

    for post in raw_posts:
        try:
            normalized = normalize_raw_post(post)
            _resolve_parent_event_id(db, normalized)
        except Exception as e:
            failed.append({"post": post, "error": str(e)})
            continue

        existing = (
            db.query(CanonicalEventModel)
            .filter_by(source=normalized.source, source_post_id=normalized.source_post_id)
            .first()
        )
        if existing is not None:
            skipped_duplicates += 1
            continue

        try:
            db_event = CanonicalEventModel(**_event_to_db_row(normalized))
            db.merge(db_event)
            db.flush()
            _run_nlp_analysis(db, normalized)
            ingested += 1
        except Exception as e:
            db.rollback()
            failed.append({"post": post, "error": str(e)})

    db.commit()
    if ingested:
        data_access.clear_cache()
    return {
        "events_ingested": ingested,
        "skipped_duplicates": skipped_duplicates,
        "failed_records": failed,
    }


@router.post("/run-replay")
def run_replay_ingestion(db: Session = Depends(get_db)):
    adapter = ReplayAdapter()
    raw_posts = adapter.fetch()
    result = _ingest_raw_posts(db, raw_posts)
    return {"status": "success", "mode": "replay", **result}


@router.post("/run-live")
def run_live_ingestion(db: Session = Depends(get_db)):
    adapter = LiveAdapter()
    raw_posts = adapter.fetch()

    if not raw_posts:
        raise HTTPException(status_code=502, detail="Failed to fetch live feed")

    result = _ingest_raw_posts(db, raw_posts)
    return {"status": "success", "mode": "live", **result}
