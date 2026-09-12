# Person 3 — Section D Processing Engine

Stream ingest from Person 2 → Redis centroid matching → HDBSCAN recovery →
trend/lifecycle state machine → FastAPI JSON delivery.

```
Person 2 NLP + Vector DB
        │  (event stream)
        ▼
Stream Consumer (Redis Streams / FastAPI POST)
        ▼
Online Centroid Matcher  ──sim ≥ 0.80──► Active centroids (Redis)
        │ sim < 0.80
        ▼
Unclustered buffer (Redis list)
        │ every 10 min
        ▼
HDBSCAN worker ──► new topic_ids in Redis
        ▼
Trend + lifecycle (DuckDB time series)
        ▼
GET /api/v1/topics/{topic_id}
```

## Run locally

```bash
pip install -r requirements.txt
docker compose up -d          # Redis + Qdrant (optional)
python scripts/run_demo.py
python scripts/run_api.py     # http://127.0.0.1:8000/docs
python -m pytest tests/ -v
```

**API**

- `POST /api/v1/events` — ingest one NLP contract (dev stand-in for the broker)
- `POST /api/v1/workers/hdbscan` — run buffer clustering now
- `GET /api/v1/topics` — all active topics
- `GET /api/v1/topics/{topic_id}` — Section D payload
- `GET /api/v1/audience` — current audience (language/profession/geography) snapshot for all active topics
- `GET /api/v1/audience/{topic_id}` — current snapshot for one topic; add `?from=&to=` for DuckDB time-series history

**Workers**

- `python -m src.workers.stream_consumer` — Redis Stream `person2:nlp_events`
- `python -m src.workers.hdbscan_worker` — HDBSCAN every 10 minutes
- `python -m src.workers.demographics_worker` — audience aggregation every `demographics_interval_minutes` (default 10)

## What is implemented now

- Redis hashes: `active_centroids`, `topic_counts`, `event_topic_map`
- Redis list: `unclustered_buffer`
- Cosine threshold 0.80 + moving-average centroid update
- HDBSCAN (`min_cluster_size=10`, `cluster_selection_epsilon=0.2`, min batch 15)
- Novelty, Shannon entropy spread, sigmoid trend score
- Lifecycle: first_appearance / acceleration / peak / decline
- Evidence: closest-to-centroid + highest engagement
- DuckDB time-series events
- FastAPI delivery service
- In-memory Redis fallback when Redis is down
- Audience demographics: periodic aggregation of language/profession/geography per topic
  (`src/workers/demographics_worker.py`), minimum-sample-size gating, Redis `audience_current:{topic_id}`
  snapshot + DuckDB `audience_snapshots` history, standalone `/api/v1/audience` API

## Wire later (Person 2 / E / infra)

These interfaces exist as stubs. Do not pretend they are live.

| Dependency | Where | What Person 2 / infra must provide |
|---|---|---|
| **Person 2 Qdrant / Pgvector** | `src/person2/vector_client.py` `QdrantPerson2VectorClient` | Collection URL, API key, payload field `embedding_ref`, 384-dim vectors (`all-MiniLM-L6-v2`) |
| **Person 2 event stream** | `src/workers/stream_consumer.py` | Redis Stream `person2:nlp_events` **or** Kafka `person2.nlp.output` (`config.kafka_bootstrap_servers`) |
| **NLP contract** | `src/contracts/nlp_input.py` | Confirm nested `sentiment.label` and `metrics.engagement` vs flat likes/shares/comments |
| **Component E graph** | `src/component_e/network.py` | Author interaction API/file for Louvain `H_network` (`config.component_e_api_url`) |
| **Local LLM names** | `src/clustering/naming.py` | Llama-3-8B (or compatible) HTTP endpoint; until then c-TF-IDF keywords are the headline |
| **TimescaleDB** | `src/storage/timeseries_store.py` | Swap DuckDB for Timescale if the team standardizes on Postgres |
| **Audience metadata (live)** | `src/services/author_metadata.py` `LiveAuthorMetadataSource` | Person 1 / infra live author-metadata endpoint or DB, keyed by `author_id`, returning `{language?, profession?, geography?}` |
| **Auth / rate limits** | `src/api/main.py` | Gateway auth in front of `/api/v1/topics` |

Set `person2_qdrant_url` in `src/config.py` (or env later) to switch vector fetch from the local store to Person 2's DB.

Set `author_metadata_source: "static" | "live"` in `src/config.py` to switch the demographics
worker's author-metadata lookup between `StaticAuthorMetadataSource` (reads the local fixture at
`author_metadata_static_path`, default `data/fixtures/author_metadata.json`) and
`LiveAuthorMetadataSource` (calls `author_metadata_live_url`, currently unset/unimplemented — it
returns empty metadata until a URL is configured, then raises `NotImplementedError` until the
live call is wired). No call-site changes are needed when the live source becomes real; the
original `SectionDPipeline(author_metadata=...)` stub referenced here previously is superseded by
this dual-mode source, used by `src/workers/demographics_worker.py` and the `/api/v1/audience`
API. Missing authors/fields degrade to `unknown_share = 1.0` for that category only — never
fabricated, never blocking the other two signals. Below `demographics_min_sample_size` (default
20) distinct known authors, a category reports `unknown_share = 1.0` instead of a real
distribution; `demographics_target_sample_size` (default 50) controls how quickly `confidence`
climbs to 1.0 with sample size. No author_id-to-category mapping is ever returned or logged —
only aggregate counts/shares.
