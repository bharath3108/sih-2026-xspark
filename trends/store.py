from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from dateutil import parser as dtparser
import numpy as np

from .config import settings
from .fixtures import iter_jsonl, load_index_by_event_id, load_embeddings_by_ref


@dataclass
class JoinedEvent:
    event_id: str
    timestamp_utc: str
    text: str
    author_id_hash: str
    engagement: Dict[str, int]
    nlp: Dict[str, Any]
    vector: Optional[np.ndarray]


class FixtureStore:
    def __init__(self) -> None:
        self.events = list(iter_jsonl(settings.FIXTURE_EVENTS_PATH))
        self.nlp_by_event = load_index_by_event_id(settings.FIXTURE_NLP_PATH)
        self.emb_by_ref = load_embeddings_by_ref(settings.FIXTURE_EMBEDDINGS_PATH)

    def query_joined_events(self, start_iso: str, end_iso: str) -> List[JoinedEvent]:
        start = dtparser.isoparse(start_iso)
        end = dtparser.isoparse(end_iso)

        out: List[JoinedEvent] = []
        for ev in self.events:
            ts = dtparser.isoparse(ev["timestamp_utc"])
            if ts < start or ts >= end:
                continue

            nlp = self.nlp_by_event.get(ev["event_id"], {})
            ref = nlp.get("embedding_ref")
            vec = self.emb_by_ref.get(ref) if ref else None

            out.append(
                JoinedEvent(
                    event_id=ev["event_id"],
                    timestamp_utc=ev["timestamp_utc"],
                    text=ev.get("text") or "",
                    author_id_hash=ev.get("author_id_hash") or "unknown",
                    engagement=ev.get("engagement") or {},
                    nlp=nlp,
                    vector=np.array(vec, dtype=np.float32) if vec is not None else None,
                )
            )
        return out


def get_store() -> FixtureStore:
    return FixtureStore()