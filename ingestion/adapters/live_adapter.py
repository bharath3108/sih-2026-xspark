import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any

from ingestion.adapters.base import SourceAdapter
from ingestion.normalization.normalizer import normalize_raw_post
from contracts.canonical_event import CanonicalEvent


class LiveAdapter(SourceAdapter):
    """Live source: dummyjson.com posts feed, used as a stand-in permitted
    live source for the demo. Emits raw posts in the same shape ReplayAdapter
    reads (source/id/author_id/timestamp_utc/text/language/reply_to_id/
    engagement) so normalize_raw_post handles both identically."""

    def __init__(self):
        self.url = "https://dummyjson.com/posts?limit=5"

    def source_name(self) -> str:
        return "live_dummyjson"

    def health_check(self) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=5.0, verify=False) as client:
                response = client.get(self.url)
            return {"status": "ok" if response.status_code == 200 else "error", "status_code": response.status_code}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def fetch(self, query: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        try:
            # verify=False prevents Windows SSL verification errors
            with httpx.Client(timeout=10.0, verify=False) as client:
                response = client.get(self.url)

            if response.status_code == 200:
                data = response.json()
                raw_posts = []
                for post in data.get("posts", [])[:limit]:
                    reactions = post.get("reactions")
                    likes = reactions.get("likes", 0) if isinstance(reactions, dict) else 0
                    raw_posts.append({
                        "id": f"live_{post.get('id')}",
                        "source": "other",
                        "author_id": f"user_{post.get('userId')}",
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "text": post.get("body", ""),
                        "language": "en",
                        "reply_to_id": None,
                        "engagement": {"likes": likes, "shares": 0, "comments": 0, "views": 0},
                    })
                if raw_posts:
                    return raw_posts
        except Exception as e:
            print(f"[WARN] Live HTTP fetch failed: {e}. Switching to internal live feed generator.")

        # Guaranteed deterministic fallback so the demo never depends on a
        # live API being reachable.
        return [
            {
                "id": f"live_post_{i}",
                "source": "other",
                "author_id": f"user_node_{i}",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "text": f"Real-time social telemetry data stream event #{i}.",
                "language": "en",
                "reply_to_id": None,
                "engagement": {"likes": i * 12, "shares": i * 2, "comments": i, "views": i * 20},
            }
            for i in range(1, 6)
        ]

    def normalize(self, raw_post: Dict[str, Any]) -> CanonicalEvent:
        return normalize_raw_post(raw_post)
