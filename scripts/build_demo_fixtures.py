"""Build a larger, contract-shaped fixture set for the hosted demo.

data/fixtures is the team's versioned contract fixture set — small, curated and
pinned by the test suite, so it must not grow. This script composes a *second*
directory, data/fixtures_demo, that keeps those curated records verbatim and
layers the 2.3k-event replay corpus (data/replay/synthetic_1000.json) on top,
so the deployed dashboard has realistic volume.

Point a deployment at it with FIXTURES_DIR=data/fixtures_demo.

    python -m scripts.build_demo_fixtures

Everything is derived deterministically from the replay corpus (ids are seeded
hashes), so re-running produces byte-identical output.

The replay author ids encode the structure this dataset was generated with —
`<topic>_hub`, `<topic>_bot_NN`, `<topic>_user_NNN` — and that is what drives
audience categories, community assignment and node roles here, rather than any
invented attribute.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "data" / "fixtures"
REPLAY = REPO_ROOT / "data" / "replay" / "synthetic_1000.json"
OUT = REPO_ROOT / "data" / "fixtures_demo"

# CanonicalEvent.source is a closed enum in the contract; the replay corpus also
# contains "bluesky", which maps onto the contract's catch-all.
SOURCE_MAP = {"x": "x", "telegram": "telegram", "reddit": "reddit", "instagram": "instagram"}

TOPIC_LABELS = {
    "elections": "Election integrity claims",
    "climate": "Climate action backlash",
    "tech": "Tech layoffs narrative",
    "cricket": "World Cup 2026 chatter",
    "public": "Public health guidance dispute",
    "stock": "Market crash speculation",
    "ai": "AI regulation debate",
    "farmer": "Farmer protest coverage",
}

NS = uuid.UUID("6f1b7a54-0000-4000-8000-000000000000")


def _seed(key: str) -> int:
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


def _event_id(replay_id: str) -> str:
    return str(uuid.uuid5(NS, replay_id))


def _author_hash(author_id: str) -> str:
    return hashlib.sha256(author_id.encode()).hexdigest()[:16]


def _iso_z(ts: str) -> str:
    return datetime.fromisoformat(ts).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _author_kind(author_id: str) -> str:
    if author_id.endswith("_hub"):
        return "amplifier_account"
    if re.search(r"_bot_\d+$", author_id):
        return "automated_account"
    return "organic_user"


def _topic_key(replay_id: str) -> str:
    return replay_id.split("_")[1]


def _sentiment(text: str, author_id: str, replay_id: str) -> tuple[str, float]:
    """Heuristic label for demo fixtures — not a model output.

    Coordinated accounts in this corpus push conspiratorial framings, so the
    label leans on the template phrasing first and the author kind second.
    """
    lowered = text.lower()
    if "real story behind" in lowered or "nobody is talking about" in lowered:
        return "negative", 0.72 + (_seed(replay_id) % 18) / 100
    if "breaking update" in lowered or "officials confirm" in lowered:
        base = "negative" if _author_kind(author_id) == "automated_account" else "neutral"
        return base, 0.61 + (_seed(replay_id) % 24) / 100
    if "everything you need to know" in lowered or "here's the summary" in lowered:
        return "neutral", 0.66 + (_seed(replay_id) % 20) / 100
    if "explainer" in lowered or "analysis" in lowered:
        return ("neutral", 0.70) if _seed(replay_id) % 3 else ("positive", 0.64)
    roll = _seed(replay_id) % 100
    if roll < 30:
        return "negative", 0.58 + (roll % 20) / 100
    if roll < 55:
        return "positive", 0.60 + (roll % 18) / 100
    return "neutral", 0.62 + (roll % 22) / 100


EMOTIONS = {"negative": "anger", "positive": "optimism", "neutral": "neutral"}
STANCES = {"negative": "oppose", "positive": "support", "neutral": "neutral"}


def build() -> None:
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    curated_events = json.loads((FIXTURES / "canonical_events.json").read_text(encoding="utf-8"))
    curated_nlp = json.loads((FIXTURES / "nlp_outputs.json").read_text(encoding="utf-8"))
    curated_topics = json.loads((FIXTURES / "topics.json").read_text(encoding="utf-8"))
    curated_net = json.loads((FIXTURES / "network_output.json").read_text(encoding="utf-8"))
    curated_edges = json.loads((FIXTURES / "network_edges.json").read_text(encoding="utf-8"))

    events = list(curated_events)
    nlp_outputs = list(curated_nlp)
    by_topic: dict[str, list[dict]] = defaultdict(list)

    # Topic ids continue after the curated ones so existing references hold.
    topic_keys = sorted(TOPIC_LABELS)
    topic_id_for = {k: f"topic-{i + 3:03d}" for i, k in enumerate(topic_keys)}

    for row in replay:
        rid = row["id"]
        tkey = _topic_key(rid)
        if tkey not in TOPIC_LABELS:
            continue
        tid = topic_id_for[tkey]
        eid = _event_id(rid)
        author = row["author_id"]
        ts = _iso_z(row["timestamp_utc"])
        label, conf = _sentiment(row["text"], author, rid)

        events.append(
            {
                "event_id": eid,
                "source": SOURCE_MAP.get(row["source"], "other"),
                "source_post_id": rid,
                "author_id_hash": _author_hash(author),
                "timestamp_utc": ts,
                "text": row["text"],
                "language": row.get("language") or "en",
                "reply_to_id": _event_id(row["reply_to_id"]) if row.get("reply_to_id") else None,
                "parent_event_id": None,
                "engagement": row["engagement"],
                "entities": sorted(set(re.findall(r"#(\w+)", row["text"]))),
                "metadata": {"source_version": f"{row['source']}-replay-v1", "collected_at_utc": ts},
            }
        )

        nlp_outputs.append(
            {
                "event_id": eid,
                "language": {"label": row.get("language") or "en", "confidence": 0.97},
                "sentiment": {"label": label, "confidence": round(conf, 2)},
                "emotion": {"label": EMOTIONS[label], "confidence": round(conf - 0.08, 2)},
                "stance": {"target": tid, "label": STANCES[label], "confidence": round(conf - 0.05, 2)},
                "embedding_ref": None,
                "evidence": [{"type": "source_event", "event_id": eid}],
                "model": {"name": "synthetic-replay-heuristic", "version": "0.1"},
            }
        )

        by_topic[tkey].append({"event": events[-1], "sentiment": label, "author": author})

    topics = list(curated_topics)
    community_for_topic = {k: f"c{i + 3}" for i, k in enumerate(topic_keys)}

    for tkey in topic_keys:
        rows = by_topic[tkey]
        tid = topic_id_for[tkey]
        evs = [r["event"] for r in rows]
        authors = {e["author_id_hash"] for e in evs}
        engagement = sum(
            e["engagement"]["likes"] + e["engagement"]["shares"] + e["engagement"]["comments"] for e in evs
        )

        buckets: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            hour = r["event"]["timestamp_utc"][:13] + ":00:00Z"
            buckets[hour].append(r)

        timeline = []
        for hour in sorted(buckets):
            brs = buckets[hour]
            score = sum(1 if r["sentiment"] == "positive" else -1 if r["sentiment"] == "negative" else 0 for r in brs)
            timeline.append(
                {
                    "bucket_start": hour,
                    "volume": len(brs),
                    "unique_authors": len({r["event"]["author_id_hash"] for r in brs}),
                    "engagement": sum(
                        r["event"]["engagement"]["likes"] + r["event"]["engagement"]["shares"] for r in brs
                    ),
                    "avg_sentiment": round(score / len(brs), 2),
                }
            )

        volumes = [b["volume"] for b in timeline] or [0]
        mean_v = sum(volumes) / len(volumes)
        trend = min(0.99, round((max(volumes) / mean_v) / 6, 2)) if mean_v else 0.0

        # Audience is the composition of the *authors* behind a narrative, so
        # count each author once rather than once per post.
        kinds = Counter(_author_kind(name) for name in {r["author"] for r in rows})
        total_k = sum(kinds.values())
        categories = {k: round(v / total_k, 2) for k, v in kinds.most_common() if round(v / total_k, 2) > 0}
        # Leave a residual share unattributed rather than forcing the split to 1.
        unknown = round(max(0.0, 1 - sum(categories.values())), 2)

        topics.append(
            {
                "topic_id": tid,
                "name": TOPIC_LABELS[tkey],
                "window": {
                    "start": min(e["timestamp_utc"] for e in evs),
                    "end": max(e["timestamp_utc"] for e in evs),
                },
                "metrics": {
                    "volume": len(evs),
                    "unique_authors": len(authors),
                    "engagement": engagement,
                    "trend_score": trend,
                    "novelty": round(min(0.95, len(authors) / max(1, len(evs)) + 0.2), 2),
                    "cross_community_spread": round(min(0.95, 0.3 + (_seed(tkey) % 50) / 100), 2),
                },
                "timeline": timeline,
                "audience": {
                    "categories": categories,
                    "unknown_share": unknown,
                    "sample_size": len(authors),
                    "confidence": round(min(0.92, 0.45 + len(authors) / 400), 2),
                },
                "evidence_event_ids": [e["event_id"] for e in evs[:6]],
            }
        )

    # ---- network -----------------------------------------------------------
    # The corpus carries real reply chains (~2.2k of them), so the graph is the
    # actual author-to-author reply structure rather than a synthesised one.
    activity = Counter()
    author_topic: dict[str, str] = {}
    author_name: dict[str, str] = {}
    for tkey, rows in by_topic.items():
        for r in rows:
            h = r["event"]["author_id_hash"]
            activity[h] += 1
            author_topic.setdefault(h, tkey)
            author_name.setdefault(h, r["author"])

    replay_by_id = {row["id"]: row for row in replay}
    reply_pairs: Counter[tuple[str, str]] = Counter()
    for row in replay:
        parent = replay_by_id.get(row.get("reply_to_id") or "")
        if not parent or parent["author_id"] == row["author_id"]:
            continue
        src, tgt = _author_hash(row["author_id"]), _author_hash(parent["author_id"])
        if src in author_topic and tgt in author_topic:
            reply_pairs[(src, tgt)] += 1

    in_degree = Counter()
    for (_, tgt), w in reply_pairs.items():
        in_degree[tgt] += w

    # Cap the rendered topology so the graph view stays legible and fast. Keep
    # every seed and automated account — the coordinated cluster is the whole
    # point of the view — then fill with the most replied-to organic accounts.
    per_community: dict[str, list[str]] = defaultdict(list)
    for h, _ in sorted(activity.items(), key=lambda kv: (-in_degree[kv[0]], -kv[1])):
        per_community[author_topic[h]].append(h)

    keep: list[str] = []
    for tkey in topic_keys:
        members = per_community[tkey]
        seeds = [h for h in members if author_name[h].endswith("_hub")]
        bots = [h for h in members if re.search(r"_bot_\d+$", author_name[h])]
        rest = [h for h in members if h not in set(seeds) | set(bots)]
        keep.extend(seeds + bots[:10] + rest[:15])
    kept = set(keep)

    nodes = list(curated_edges["nodes"])
    edges = list(curated_edges["edges"])
    max_in = max(in_degree.values()) if in_degree else 1
    # "Amplifier" is reserved for the top decile by inbound replies, so the
    # label means something rather than applying to almost every node.
    amplifier_floor = sorted(in_degree.values(), reverse=True)[: max(1, len(in_degree) // 10)][-1] if in_degree else 0

    def _role(h: str) -> str:
        name = author_name[h]
        if name.endswith("_hub"):
            return "seed"
        if re.search(r"_bot_\d+$", name):
            return "automated"
        if in_degree[h] >= max(2, amplifier_floor):
            return "amplifier"
        return "participant"

    for h in keep:
        nodes.append(
            {
                "id": h,
                "community_id": community_for_topic[author_topic[h]],
                "centrality": round(min(0.98, in_degree[h] / max_in) if max_in else 0.0, 2),
                "role": _role(h),
            }
        )

    for (src, tgt), w in reply_pairs.items():
        if src in kept and tgt in kept:
            edges.append({"source": src, "target": tgt, "weight": w, "type": "reply"})

    cross = sum(
        1
        for (src, tgt) in reply_pairs
        if src in kept and tgt in kept and author_topic[src] != author_topic[tgt]
    )
    kept_edges = sum(1 for (src, tgt) in reply_pairs if src in kept and tgt in kept)

    communities = list(curated_net["communities"])
    for tkey in topic_keys:
        members = [h for h in keep if author_topic[h] == tkey]
        communities.append(
            {
                "community_id": community_for_topic[tkey],
                "size": len(per_community[tkey]),
                "central_nodes": sorted(members, key=lambda h: -in_degree[h])[:3],
            }
        )

    # Longest reply chain actually present in the corpus.
    depth_cache: dict[str, int] = {}

    def _depth(rid: str, seen: frozenset[str] = frozenset()) -> int:
        if rid in depth_cache:
            return depth_cache[rid]
        row = replay_by_id.get(rid)
        parent = row.get("reply_to_id") if row else None
        d = 1 if not parent or parent in seen else 1 + _depth(parent, seen | {rid})
        depth_cache[rid] = d
        return d

    max_depth = max((_depth(rid) for rid in replay_by_id), default=1)

    key_nodes = [h for h, _ in in_degree.most_common(5) if h in kept]

    n, e = len(nodes), len(edges)
    network_output = {
        "window": {
            "start": min(ev["timestamp_utc"] for ev in events),
            "end": max(ev["timestamp_utc"] for ev in events),
        },
        "graph_metrics": {"nodes": n, "edges": e, "density": round(e / (n * (n - 1)) if n > 1 else 0, 4)},
        "communities": communities,
        "propagation": {
            "depth": max_depth,
            "cross_community_rate": round(cross / kept_edges, 2) if kept_edges else 0.0,
            "key_nodes": key_nodes,
        },
        "evidence_event_ids": curated_net["evidence_event_ids"],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    _write(OUT / "canonical_events.json", events)
    _write(OUT / "nlp_outputs.json", nlp_outputs)
    _write(OUT / "topics.json", topics)
    _write(OUT / "network_output.json", network_output)
    _write(OUT / "network_edges.json", {"nodes": nodes, "edges": edges})
    for passthrough in ("investigation.json", "author_metadata.json"):
        shutil.copyfile(FIXTURES / passthrough, OUT / passthrough)

    print(f"events        {len(events):>6}")
    print(f"nlp_outputs   {len(nlp_outputs):>6}")
    print(f"topics        {len(topics):>6}")
    print(f"communities   {len(communities):>6}")
    print(f"topology      {n} nodes / {e} edges")
    print(f"written to    {OUT.relative_to(REPO_ROOT)}")


def _write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
