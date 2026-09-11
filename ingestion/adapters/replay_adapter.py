import json
import os
from typing import List, Dict, Any
from ingestion.adapters.base import SourceAdapter
from ingestion.normalization.normalizer import normalize_raw_post
from contracts.canonical_event import CanonicalEvent

class ReplayAdapter(SourceAdapter):
    def __init__(self, filepath: str = "data/replay/sample_raw_posts.json"):
        self.filepath = filepath

    def source_name(self) -> str:
        return "replay_file"

    def health_check(self) -> Dict[str, Any]:
        exists = os.path.exists(self.filepath)
        return {"status": "ok" if exists else "error", "file_found": exists}

    def fetch(self, query: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        if not os.path.exists(self.filepath):
            return []
        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data[:limit]

    def normalize(self, raw_post: Dict[str, Any]) -> CanonicalEvent:
        return normalize_raw_post(raw_post)