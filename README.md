# XSpark — Processing Engine

Lightweight processing engine for Section D (Person 3) of the SIH investigator pipeline. Ingests Person 2 NLP events, matches/upserts centroids in Redis, reclusters with HDBSCAN, computes trend/lifecycle signals, stores time-series snapshots in DuckDB and exposes a small FastAPI delivery surface for dashboards and investigation.

Tech stack

- Python (core processing, workers, API) — 68.3%
- TypeScript (dashboard) — 30.4%
- CSS / JS (frontend styles & small runtime pieces)

Architecture

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

Quick start — run locally

Prereqs: Python 3.10+, pip, optional Docker for Redis/Qdrant

```bash
pip install -r requirements.txt
# Optional: start Redis (+ Qdrant if you use Person 2 vector fetch)
docker compose up -d
# demo ingestion + api
python scripts/run_demo.py
python scripts/run_api.py     # http://127.0.0.1:8000/docs
# tests
python -m pytest tests/ -v
```

APIs (use for the dashboard and integration)

- POST /api/v1/events — ingest one NLP contract (development stand-in for the broker)
- POST /api/v1/workers/hdbscan — run buffer clustering immediately
- GET /api/v1/topics — list active topics
- GET /api/v1/topics/{topic_id} — topic payload for Section D
- GET /api/v1/audience — audience snapshot for all active topics
- GET /api/v1/audience/{topic_id} — audience snapshot for one topic; add `?from=&to=` for DuckDB history

Workers (run these for continuous processing)

- python -m src.workers.stream_consumer — Redis Stream consumer `person2:nlp_events`
- python -m src.workers.hdbscan_worker — HDBSCAN loop (default every 10 minutes)
- python -m src.workers.demographics_worker — periodic audience aggregation (default 10m)

What is implemented now

- Redis-based online centroid store (`active_centroids`), topic counts and event-to-topic mapping
- Unclustered buffer (Redis list) + cosine similarity online matching (threshold 0.80) and moving-average centroid update
- HDBSCAN reclustering (min_cluster_size=10, cluster_selection_epsilon=0.2, min batch 15)
- Novelty, Shannon entropy spread, sigmoid trend scoring
- Lifecycle detection (first_appearance → acceleration → peak → decline)
- Evidence selection (closest-to-centroid + highest engagement)
- DuckDB time-series events + audience snapshots
- FastAPI delivery service with in-memory Redis fallback when Redis is unavailable
- Audience demographics aggregation with gating (language/profession/geography), snapshotting in Redis and history in DuckDB

Wire later (external/system integration)

These interfaces are currently stubs. They must be provided by Person 2 / infra when wiring into the larger system:

- Person 2 vector DB (Qdrant / PgVector) — configure `person2_qdrant_url` in `src/config.py` and ensure `embedding_ref` and 384-dim vectors (`all-MiniLM-L6-v2`)
- Person 2 event stream — Redis Stream `person2:nlp_events` or Kafka `person2.nlp.output` (see `src/workers/stream_consumer.py` and config)
- Author metadata service (live) — configure `author_metadata_source` in `src/config.py` to `live` and set the `author_metadata_live_url` for Person 1 / infra
- Component E graph (author interactions) for Louvain (`src/component_e/network.py`)
- Optional: Swap DuckDB for TimescaleDB/Postgres via `src/storage/timeseries_store.py` if the infra standardizes on Postgres
- Auth / rate limiting — recommend putting a gateway in front of `/api/v1/*` (see `src/api/main.py`)

Configuration notes

- `author_metadata_source: "static" | "live"` in `src/config.py` toggles between the local static fixture (`data/fixtures/author_metadata.json`) and a live lookup. When live is unset or returns missing fields, the system uses a conservative `unknown_share = 1.0` fallback for that category. Below `demographics_min_sample_size` (default 20) a category reports `unknown_share = 1.0` instead of an unreliable distribution.
- `person2_qdrant_url` in `src/config.py` switches vector fetch between the local store and Person 2's vector DB.

Frontend / Dashboard (Person 5)

See `frontend/README.md` for the Next.js + TypeScript dashboard. The dashboard talks to the lightweight composition API in `backend/dashboard.py` and expects the JSON contracts published by this repository's API — it does not import internal Python modules.

Contributing

If you're wiring Person 2 or Person 1 systems, please update the corresponding config keys and add integration tests under `tests/integration/`.

License

MIT (see LICENSE)
