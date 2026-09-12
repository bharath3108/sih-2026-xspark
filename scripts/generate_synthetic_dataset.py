"""Generates a ~1000-record synthetic dataset shaped like the raw-post
format ingestion/normalization/normalizer.py expects (same shape every
adapter's fetch() returns), so it can be dropped straight through
ReplayAdapter -> /api/ingestion/run-replay and exercise every downstream
feature in one shot:

- Reply chains (root -> direct replies -> nested sub-replies), always
  written parent-before-child, so backend/api/ingestion.py's
  `_resolve_parent_event_id` (which looks up the parent by source_post_id
  within the same ingest transaction) can always resolve them. This is what
  gives graph/construction/builder.py real author->author edges to build a
  network from (centrality, communities, bridge nodes, cascades).
- Distinct per-topic "communities" of authors, a per-topic hub author with
  disproportionate reply volume (centrality/hub testing), and a couple of
  "bridge" authors who also reply into a different topic's thread
  (cross-community edges for bridge-node detection).
- A small coordinated/bot cluster per topic: several bot authors posting
  near-duplicate amplification replies to the same root within a tight
  time window (coordinated-behavior-shaped data).
- Sentiment/negation vocabulary drawn straight from ml/mainml.py's
  _POSITIVE_WORDS/_NEGATIVE_WORDS/_NEGATION_WORDS so the lexicon fallback
  (used whenever the transformer models aren't loaded) produces varied,
  non-trivial sentiment/emotion/stance labels -- not just "neutral" for
  everything.
- Wide engagement spread (viral roots vs. quiet replies) and timestamps
  spread over the last ~10 days, for timeline/novelty/spread-style views.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 42
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "replay" / "synthetic_1000.json"

SOURCES = ["x", "telegram", "reddit", "instagram", "bluesky"]

TOPICS = {
    "elections": {
        "hashtag": "#Elections2026",
        "hub": "elections_hub",
    },
    "climate_policy": {
        "hashtag": "#ClimateAction",
        "hub": "climate_hub",
    },
    "tech_layoffs": {
        "hashtag": "#TechLayoffs",
        "hub": "tech_hub",
    },
    "cricket_worldcup": {
        "hashtag": "#WorldCup2026",
        "hub": "cricket_hub",
    },
    "public_health": {
        "hashtag": "#PublicHealth",
        "hub": "health_hub",
    },
}

# Drawn from ml/mainml.py's fallback lexicon so the sentiment/emotion/stance
# fallback path (no transformer models loaded) produces real variety instead
# of defaulting every record to "neutral".
POSITIVE_WORDS = ["good", "great", "love", "happy", "excellent", "amazing", "support", "win", "best", "hope", "proud", "thanks"]
NEGATIVE_WORDS = ["bad", "hate", "terrible", "angry", "worst", "fail", "failed", "sad", "awful", "scam", "afraid", "wrong"]
NEGATION_WORDS = ["not", "never", "against", "oppose", "reject"]

ROOT_TEMPLATES = [
    "Breaking update on {hashtag}: officials confirm major developments today.",
    "Thread: everything you need to know about {hashtag} right now.",
    "New report on {hashtag} just dropped -- here's the summary.",
    "Live coverage of {hashtag} continues as the situation unfolds.",
    "Analysis: what {hashtag} means for the next few months.",
    "Opinion: the real story behind {hashtag} that nobody is talking about.",
]

POSITIVE_REPLY_TEMPLATES = [
    "This is {pos} news for {hashtag}, feeling really {pos2} about it.",
    "Honestly {pos}, I {pos3} where this is heading with {hashtag}.",
    "{pos} to see progress here, big {pos2} moment for {hashtag}.",
]

NEGATIVE_REPLY_TEMPLATES = [
    "This is {neg} for {hashtag}, I'm genuinely {neg2} about it.",
    "Feels like a {neg} outcome, I {negation} this direction on {hashtag}.",
    "{neg} handling of {hashtag}, this whole thing was {neg2}.",
]

NEUTRAL_REPLY_TEMPLATES = [
    "Following the updates on {hashtag} closely, waiting for more details.",
    "Does anyone have a timeline for how {hashtag} plays out?",
    "Here's a fact-check thread on the claims around {hashtag}.",
]

BOT_REPLY_TEMPLATES = [
    "{hashtag} is trending, share this now!!",
    "{hashtag} is trending, spread the word!!",
    "{hashtag} is trending, repost everywhere!!",
]


def make_entities_text(template: str, hashtag: str, mention: str | None = None, **kwargs) -> str:
    text = template.format(hashtag=hashtag, **kwargs)
    if mention:
        text = f"{text} @{mention}"
    return text


def build_dataset(seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    posts: list[dict] = []
    counter = 0
    base_time = datetime(2026, 9, 2, 8, 0, 0, tzinfo=timezone.utc)

    def next_id(source: str, topic: str) -> str:
        nonlocal counter
        counter += 1
        return f"{source}_{topic}_{counter:05d}"

    topic_names = list(TOPICS.keys())

    # Bridge authors: each pair of adjacent topics shares one author who
    # replies into both, producing cross-community edges for bridge-node
    # detection in graph/metrics/bridge.py.
    bridge_authors = {
        (topic_names[i], topic_names[(i + 1) % len(topic_names)]): f"bridge_{i:02d}"
        for i in range(len(topic_names))
    }

    for topic, cfg in TOPICS.items():
        hashtag = cfg["hashtag"]
        hub = cfg["hub"]
        community_authors = [f"{topic}_user_{i:03d}" for i in range(40)]
        bot_authors = [f"{topic}_bot_{i:02d}" for i in range(8)]

        topic_start = base_time + timedelta(days=topic_names.index(topic))
        n_roots = 6

        for root_i in range(n_roots):
            root_time = topic_start + timedelta(hours=root_i * 5, minutes=rng.randint(0, 40))
            root_source = SOURCES[root_i % len(SOURCES)]
            root_author = hub if root_i == 0 else rng.choice(community_authors)
            root_text = make_entities_text(rng.choice(ROOT_TEMPLATES), hashtag)
            root_id = next_id(root_source, topic)

            # Root 0 is the designated "viral hub" thread; later roots get
            # normal-range engagement.
            if root_i == 0:
                likes, shares, views = rng.randint(2000, 6000), rng.randint(400, 900), rng.randint(20000, 60000)
                n_direct_replies = 60
            else:
                likes, shares, views = rng.randint(20, 400), rng.randint(2, 60), rng.randint(500, 5000)
                n_direct_replies = rng.randint(15, 30)

            posts.append({
                "id": root_id,
                "source": root_source,
                "author_id": root_author,
                "timestamp_utc": root_time.isoformat(),
                "text": root_text,
                "language": "en",
                "reply_to_id": None,
                "engagement": {"likes": likes, "shares": shares, "comments": n_direct_replies, "views": views},
            })

            direct_reply_ids: list[str] = []
            for reply_i in range(n_direct_replies):
                reply_time = root_time + timedelta(minutes=rng.randint(2, 600))
                reply_source = rng.choice(SOURCES)
                reply_author = rng.choice(community_authors)
                sentiment_bucket = rng.choices(["pos", "neg", "neutral"], weights=[0.4, 0.35, 0.25])[0]

                if sentiment_bucket == "pos":
                    text = make_entities_text(
                        rng.choice(POSITIVE_REPLY_TEMPLATES), hashtag,
                        pos=rng.choice(POSITIVE_WORDS), pos2=rng.choice(POSITIVE_WORDS), pos3=rng.choice(POSITIVE_WORDS),
                    )
                elif sentiment_bucket == "neg":
                    text = make_entities_text(
                        rng.choice(NEGATIVE_REPLY_TEMPLATES), hashtag,
                        neg=rng.choice(NEGATIVE_WORDS), neg2=rng.choice(NEGATIVE_WORDS), negation=rng.choice(NEGATION_WORDS),
                    )
                else:
                    text = make_entities_text(rng.choice(NEUTRAL_REPLY_TEMPLATES), hashtag)

                reply_id = next_id(reply_source, topic)
                direct_reply_ids.append(reply_id)
                posts.append({
                    "id": reply_id,
                    "source": reply_source,
                    "author_id": reply_author,
                    "timestamp_utc": reply_time.isoformat(),
                    "text": text,
                    "language": "en",
                    "reply_to_id": root_id,
                    "engagement": {
                        "likes": rng.randint(0, 80),
                        "shares": rng.randint(0, 15),
                        "comments": rng.randint(0, 5),
                        "views": rng.randint(50, 2000),
                    },
                })

                # ~15% of direct replies get one nested sub-reply, giving the
                # cascade tracker real depth-3 chains instead of a flat star.
                if rng.random() < 0.15:
                    sub_time = reply_time + timedelta(minutes=rng.randint(2, 200))
                    sub_source = rng.choice(SOURCES)
                    sub_author = rng.choice(community_authors)
                    sub_text = make_entities_text(rng.choice(NEUTRAL_REPLY_TEMPLATES), hashtag)
                    sub_id = next_id(sub_source, topic)
                    posts.append({
                        "id": sub_id,
                        "source": sub_source,
                        "author_id": sub_author,
                        "timestamp_utc": sub_time.isoformat(),
                        "text": sub_text,
                        "language": "en",
                        "reply_to_id": reply_id,
                        "engagement": {
                            "likes": rng.randint(0, 20),
                            "shares": rng.randint(0, 3),
                            "comments": 0,
                            "views": rng.randint(20, 400),
                        },
                    })

            # Coordinated/bot cluster: several bot authors all reply to this
            # topic's root-0 (the viral hub) with near-duplicate text within
            # a tight ~2-minute window -- a shape a coordinated-behavior
            # detector should flag (many low-diversity accounts, one target,
            # near-simultaneous posting).
            if root_i == 0:
                bot_window_start = root_time + timedelta(minutes=30)
                for bi, bot_author in enumerate(bot_authors):
                    bot_time = bot_window_start + timedelta(seconds=bi * 15)
                    bot_text = make_entities_text(rng.choice(BOT_REPLY_TEMPLATES), hashtag)
                    bot_id = next_id("other", topic)
                    posts.append({
                        "id": bot_id,
                        "source": "other",
                        "author_id": bot_author,
                        "timestamp_utc": bot_time.isoformat(),
                        "text": bot_text,
                        "language": "en",
                        "reply_to_id": root_id,
                        "engagement": {"likes": rng.randint(0, 3), "shares": rng.randint(0, 2), "comments": 0, "views": rng.randint(10, 100)},
                    })

                # Bridge author: replies here too, plus into the *next*
                # topic's root-0 below, so the two communities share an edge.
                bridge_key = (topic, topic_names[(topic_names.index(topic) + 1) % len(topic_names)])
                bridge_author = bridge_authors[bridge_key]
                bridge_time = root_time + timedelta(minutes=45)
                bridge_text = make_entities_text(rng.choice(NEUTRAL_REPLY_TEMPLATES), hashtag)
                bridge_id = next_id("x", topic)
                posts.append({
                    "id": bridge_id,
                    "source": "x",
                    "author_id": bridge_author,
                    "timestamp_utc": bridge_time.isoformat(),
                    "text": bridge_text,
                    "language": "en",
                    "reply_to_id": root_id,
                    "engagement": {"likes": rng.randint(5, 50), "shares": rng.randint(0, 10), "comments": 0, "views": rng.randint(100, 1000)},
                })

    return posts


def main() -> None:
    posts = build_dataset()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(posts, indent=2), encoding="utf-8")
    print(f"Wrote {len(posts)} synthetic posts to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
