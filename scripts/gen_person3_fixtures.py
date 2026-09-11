import json, random, uuid
from datetime import datetime, timedelta, timezone

random.seed(42)

OUT_EVENTS = "data/fixtures/canonical_events.sample.jsonl"
OUT_NLP = "data/fixtures/nlp_outputs.sample.jsonl"
OUT_EMB = "data/fixtures/embeddings.sample.jsonl"

DIM = 32
N_EVENTS = 240
N_AUTHORS = 80

topics = [
    ("exam", ["exam results", "jee cutoff", "neet counselling", "semester results", "college admissions"]),
    ("election", ["election rally", "government policy", "parliament debate", "minister statement", "public issue"]),
    ("cricket", ["cricket match", "ipl team", "century scored", "toss update", "match highlights"]),
]

base = []
for _ in topics:
    base.append([random.uniform(-1, 1) for _ in range(DIM)])

def add_noise(v, noise=0.15):
    return [x + random.gauss(0, noise) for x in v]

now = datetime.now(timezone.utc)
start = now - timedelta(hours=24)
authors = [f"hash{idx:03d}" for idx in range(N_AUTHORS)]

with open(OUT_EVENTS, "w", encoding="utf-8") as f_ev, \
     open(OUT_NLP, "w", encoding="utf-8") as f_nlp, \
     open(OUT_EMB, "w", encoding="utf-8") as f_emb:

    for i in range(N_EVENTS):
        topic_idx = i % len(topics)
        phrase = random.choice(topics[topic_idx][1])

        t = start + timedelta(minutes=(24 * 60) * (i / N_EVENTS))
        eid = str(uuid.uuid4())
        author = random.choice(authors)

        text = f"{phrase} in Delhi" if random.random() < 0.25 else phrase
        emb_ref = f"vec-{i:05d}"

        event = {
            "event_id": eid,
            "source": "x",
            "source_post_id": str(100000 + i),
            "author_id_hash": author,
            "timestamp_utc": t.isoformat().replace("+00:00", "Z"),
            "text": text,
            "language": "en",
            "reply_to_id": None,
            "parent_event_id": None,
            "engagement": {"likes": random.randint(0, 50), "shares": random.randint(0, 20),
                           "comments": random.randint(0, 15), "views": random.randint(10, 200)},
            "entities": [],
            "metadata": {"source_version": "fixture-v1", "collected_at_utc": now.isoformat().replace("+00:00", "Z")},
        }

        nlp = {
            "event_id": eid,
            "language": {"label": "en", "confidence": 0.98},
            "sentiment": {"label": random.choice(["positive","neutral","negative"]), "confidence": 0.75},
            "emotion": {"label": random.choice(["joy","anger","fear","sadness","neutral"]), "confidence": 0.65},
            "stance": {"target": None, "label": "unknown", "confidence": 0.0},
            "embedding_ref": emb_ref,
            "evidence": [{"type": "source_event", "event_id": eid}],
            "model": {"name": "fixture", "version": "0.1"},
        }

        vec = add_noise(base[topic_idx])
        emb = {"embedding_ref": emb_ref, "vector": vec}

        f_ev.write(json.dumps(event) + "\n")
        f_nlp.write(json.dumps(nlp) + "\n")
        f_emb.write(json.dumps(emb) + "\n")

print("Fixtures generated.")