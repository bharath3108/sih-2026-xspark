"""Generates a large synthetic dataset shaped like the raw-post format
ingestion/normalization/normalizer.py expects (same shape every adapter's
fetch() returns), so it can be dropped straight through ReplayAdapter ->
/api/ingestion/run-replay and exercise every dashboard feature at once:

- Reply chains (root -> direct replies -> nested sub-replies), always
  written parent-before-child, so backend/api/ingestion.py's
  `_resolve_parent_event_id` can always resolve them -- giving
  graph/construction/builder.py real author->author edges (centrality,
  communities, bridge nodes, cascades).
- 8 distinct topics, each with its own disjoint author community (so
  graph/communities/detector.py's greedy-modularity pass has real separate
  clusters to find), a per-topic hub author, and only a handful of
  deliberately sparse cross-topic "bridge" replies (enough for bridge-node
  detection without merging every community into one).
- A coordinated/bot cluster per topic (near-duplicate replies, tight time
  window) -- a coordinated-behavior-shaped signal.
- One topic (the first) additionally gets a large, tightly-clustered volume
  spike on top of its normal thread -- meant to push its trend_score over
  the dashboard's anomaly threshold (backend/api/dashboard.py flags
  trend_score >= 0.85) so "anomalies flagged" has something real to show
  instead of always reading zero.
- Sentiment/negation vocabulary drawn from ml/mainml.py's
  _POSITIVE_WORDS/_NEGATIVE_WORDS/_NEGATION_WORDS lexicon fallback, so
  sentiment/emotion/stance stay varied even when transformer models aren't
  loaded.
- A companion data/fixtures/author_metadata.json entry (profession,
  geography, age_group) for every synthetic author, merged with whatever
  entries already exist there, so src/engines/audience.py's demographic
  breakdown has real data for every author actually used here (previously
  the fixture only covered a handful of unrelated demo author ids).
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 42
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "data" / "replay" / "synthetic_1000.json"
AUTHOR_METADATA_PATH = REPO_ROOT / "data" / "fixtures" / "author_metadata.json"

SOURCES = ["x", "telegram", "reddit", "instagram", "bluesky"]

TOPICS = {
    "elections": {"hashtag": "#Elections2026", "hub": "elections_hub"},
    "climate_policy": {"hashtag": "#ClimateAction", "hub": "climate_hub"},
    "tech_layoffs": {"hashtag": "#TechLayoffs", "hub": "tech_hub"},
    "cricket_worldcup": {"hashtag": "#WorldCup2026", "hub": "cricket_hub"},
    "public_health": {"hashtag": "#PublicHealth", "hub": "health_hub"},
    "stock_market": {"hashtag": "#MarketCrash", "hub": "market_hub"},
    "ai_regulation": {"hashtag": "#AIRegulation", "hub": "ai_hub"},
    "farmer_protests": {"hashtag": "#FarmerProtests", "hub": "farmer_hub"},
}

# The first topic gets the extra viral burst engineered to trip the
# dashboard's trend_score >= 0.85 anomaly threshold.
ANOMALY_TOPIC = next(iter(TOPICS))

# Drawn from ml/mainml.py's fallback lexicon so the sentiment/emotion/stance
# fallback path (no transformer models loaded) produces real variety instead
# of defaulting every record to "neutral".
POSITIVE_WORDS = ["good", "great", "love", "happy", "excellent", "amazing", "support", "win", "best", "hope", "proud", "thanks"]
NEGATIVE_WORDS = ["bad", "hate", "terrible", "angry", "worst", "fail", "failed", "sad", "awful", "scam", "afraid", "wrong"]
NEGATION_WORDS = ["not", "never", "against", "oppose", "reject"]

PROFESSIONS = ["Software/Tech", "Finance", "Crypto/Web3", "Healthcare", "Education", "Government", "Media/Journalism", "Student", "Other"]
GEOGRAPHIES = ["US", "EU", "APAC", "LATAM", "MEA", "IN"]
AGE_GROUPS = ["18-24", "25-34", "35-44", "45-54", "55+"]
LANGUAGES = ["en", "en", "en", "hi", "es"]

ROOT_TEMPLATES = [
    "Breaking update on {hashtag}: officials confirm major developments today.",
    "Thread: everything you need to know about {hashtag} right now.",
    "New report on {hashtag} just dropped -- here's the summary.",
    "Live coverage of {hashtag} continues as the situation unfolds.",
    "Analysis: what {hashtag} means for the next few months.",
    "Opinion: the real story behind {hashtag} that nobody is talking about.",
    "Explainer: how we got here with {hashtag}.",
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

ANOMALY_BURST_TEMPLATES = [
    "URGENT: {hashtag} is exploding right now, everyone is talking about it!",
    "This {hashtag} update just went completely viral, unreal reach.",
    "Can't believe how fast {hashtag} is spreading across every platform.",
    "{hashtag} is the only thing anyone is posting about right now.",
]


def make_entities_text(template: str, hashtag: str, mention: str | None = None, **kwargs) -> str:
    text = template.format(hashtag=hashtag, **kwargs)
    if mention:
        text = f"{text} @{mention}"
    return text


def build_dataset(seed: int = SEED) -> tuple[list[dict], dict[str, dict]]:
    rng = random.Random(seed)
    posts: list[dict] = []
    author_metadata: dict[str, dict] = {}
    counter = 0
    base_time = datetime(2026, 9, 2, 8, 0, 0, tzinfo=timezone.utc)

    def next_id(source: str, topic: str) -> str:
        nonlocal counter
        counter += 1
        return f"{source}_{topic}_{counter:05d}"

    def register_author(author_id: str) -> None:
        if author_id in author_metadata:
            return
        author_metadata[author_id] = {
            "language": rng.choice(LANGUAGES),
            "profession": rng.choice(PROFESSIONS),
            "geography": rng.choice(GEOGRAPHIES),
            "age_group": rng.choice(AGE_GROUPS),
        }

    topic_names = list(TOPICS.keys())

    # Bridge authors: only a handful of cross-topic links (not one per
    # adjacent pair) so most topics stay their own distinct community for
    # greedy_modularity_communities, while a couple still demonstrate real
    # cross-community bridge-node detection.
    bridged_pairs = [(topic_names[i], topic_names[i + 1]) for i in range(0, len(topic_names) - 1, 2)]
    bridge_authors = {pair: f"bridge_{i:02d}" for i, pair in enumerate(bridged_pairs)}
    for author in bridge_authors.values():
        register_author(author)

    for topic, cfg in TOPICS.items():
        hashtag = cfg["hashtag"]
        hub = cfg["hub"]
        register_author(hub)
        community_authors = [f"{topic}_user_{i:03d}" for i in range(50)]
        for a in community_authors:
            register_author(a)
        bot_authors = [f"{topic}_bot_{i:02d}" for i in range(10)]
        for a in bot_authors:
            register_author(a)

        topic_start = base_time + timedelta(days=topic_names.index(topic))
        n_roots = 7

        for root_i in range(n_roots):
            root_time = topic_start + timedelta(hours=root_i * 4, minutes=rng.randint(0, 40))
            root_source = SOURCES[root_i % len(SOURCES)]
            root_author = hub if root_i == 0 else rng.choice(community_authors)
            root_text = make_entities_text(rng.choice(ROOT_TEMPLATES), hashtag)
            root_id = next_id(root_source, topic)

            if root_i == 0:
                likes, shares, views = rng.randint(2000, 6000), rng.randint(400, 900), rng.randint(20000, 60000)
                n_direct_replies = 70
            else:
                likes, shares, views = rng.randint(20, 400), rng.randint(2, 60), rng.randint(500, 5000)
                n_direct_replies = rng.randint(18, 32)

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

            if root_i == 0:
                # Coordinated/bot cluster: near-duplicate replies from
                # several bot authors within a tight ~2-minute window.
                bot_window_start = root_time + timedelta(minutes=30)
                for bi, bot_author in enumerate(bot_authors):
                    bot_time = bot_window_start + timedelta(seconds=bi * 12)
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

                # Bridge author (only for topics that start one of the
                # sparse bridged pairs above).
                pair = next((p for p in bridge_authors if p[0] == topic), None)
                if pair:
                    bridge_author = bridge_authors[pair]
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

                if topic == ANOMALY_TOPIC:
                    # Engineered anomaly: a large, tightly-clustered burst of
                    # near-duplicate high-engagement posts from many distinct
                    # authors within a ~10-minute window on top of this
                    # topic's normal thread -- meant to push its computed
                    # volume acceleration/engagement/spread high enough to
                    # clear the dashboard's trend_score >= 0.85 threshold.
                    burst_authors = [f"{topic}_burst_{i:03d}" for i in range(120)]
                    for a in burst_authors:
                        register_author(a)
                    burst_start = root_time + timedelta(minutes=5)
                    for bi, burst_author in enumerate(burst_authors):
                        burst_time = burst_start + timedelta(seconds=bi * 5)
                        burst_source = rng.choice(SOURCES)
                        burst_text = make_entities_text(rng.choice(ANOMALY_BURST_TEMPLATES), hashtag)
                        burst_id = next_id(burst_source, topic)
                        posts.append({
                            "id": burst_id,
                            "source": burst_source,
                            "author_id": burst_author,
                            "timestamp_utc": burst_time.isoformat(),
                            "text": burst_text,
                            "language": "en",
                            "reply_to_id": root_id,
                            "engagement": {
                                "likes": rng.randint(500, 4000),
                                "shares": rng.randint(100, 900),
                                "comments": rng.randint(0, 20),
                                "views": rng.randint(5000, 40000),
                            },
                        })

    return posts, author_metadata


def main() -> None:
    posts, author_metadata = build_dataset()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(posts, indent=2), encoding="utf-8")

    AUTHOR_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, dict] = {}
    if AUTHOR_METADATA_PATH.exists():
        existing = json.loads(AUTHOR_METADATA_PATH.read_text(encoding="utf-8"))
    merged = {**existing, **author_metadata}
    AUTHOR_METADATA_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")

    print(f"Wrote {len(posts)} synthetic posts to {OUTPUT_PATH}")
    print(f"Wrote metadata for {len(author_metadata)} authors ({len(merged)} total) to {AUTHOR_METADATA_PATH}")


if __name__ == "__main__":
    main()
