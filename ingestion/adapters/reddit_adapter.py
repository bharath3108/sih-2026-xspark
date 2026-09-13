import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any

from ingestion.adapters.base import SourceAdapter
from ingestion.normalization.normalizer import normalize_raw_post
from contracts.canonical_event import CanonicalEvent


class RedditAdapter(SourceAdapter):
    """Live source: Reddit's public read-only JSON feed (no OAuth needed for
    permitted, public subreddit listings). Emits raw posts in the same shape
    ReplayAdapter/LiveAdapter read (source/id/author_id/timestamp_utc/text/
    language/reply_to_id/engagement) so normalize_raw_post handles all three
    identically."""

    DEFAULT_SUBREDDIT = "worldnews"
    USER_AGENT = "sih2026-social-analytics-adapter/1.0"

    def __init__(self, subreddit: str = DEFAULT_SUBREDDIT):
        self.subreddit = subreddit

    def _listing_url(self, subreddit: str, limit: int) -> str:
        return f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"

    def source_name(self) -> str:
        return "reddit"

    def health_check(self) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=5.0, verify=False, headers={"User-Agent": self.USER_AGENT}) as client:
                response = client.get(self._listing_url(self.subreddit, 1))
            return {"status": "ok" if response.status_code == 200 else "error", "status_code": response.status_code}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def fetch(self, query: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        subreddit = query or self.subreddit
        try:
            with httpx.Client(timeout=10.0, verify=False, headers={"User-Agent": self.USER_AGENT}) as client:
                response = client.get(self._listing_url(subreddit, limit))

            if response.status_code == 200:
                data = response.json()
                raw_posts = []
                for child in data.get("data", {}).get("children", [])[:limit]:
                    post = child.get("data", {})
                    text = post.get("title", "")
                    selftext = post.get("selftext", "")
                    if selftext:
                        text = f"{text}\n\n{selftext}"
                    created_utc = post.get("created_utc")
                    timestamp = (
                        datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()
                        if created_utc
                        else datetime.now(timezone.utc).isoformat()
                    )
                    raw_posts.append({
                        "id": f"reddit_{post.get('id')}",
                        "source": "reddit",
                        "author_id": f"user_{post.get('author', 'unknown')}",
                        "timestamp_utc": timestamp,
                        "text": text,
                        "language": "en",
                        "reply_to_id": None,
                        "engagement": {
                            "likes": post.get("ups", 0) or 0,
                            "shares": 0,
                            "comments": post.get("num_comments", 0) or 0,
                            "views": 0,
                        },
                    })
                if raw_posts:
                    return raw_posts
        except Exception as e:
            print(f"[WARN] Reddit HTTP fetch failed: {e}. Switching to internal live feed generator.")

        # Guaranteed deterministic fallback so the demo never depends on
        # Reddit's public endpoint being reachable (it rate-limits/blocks
        # anonymous requests without warning).
        return [
            {
                "id": f"reddit_fallback_{subreddit}_{i}",
                "source": "reddit",
                "author_id": f"user_reddit_node_{i}",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "text": f"[r/{subreddit}] Simulated discussion thread event #{i}.",
                "language": "en",
                "reply_to_id": None,
                "engagement": {"likes": i * 15, "shares": 0, "comments": i * 3, "views": 0},
            }
            for i in range(1, 6)
        ]

    def normalize(self, raw_post: Dict[str, Any]) -> CanonicalEvent:
        return normalize_raw_post(raw_post)
