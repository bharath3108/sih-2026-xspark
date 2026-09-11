"""Pipeline configuration constants matching the Section D specification."""

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class PipelineConfig:
    # Embedding
    embedding_dim: int = 384
    embedding_model: str = "all-MiniLM-L6-v2"

    # Online clustering
    cosine_similarity_threshold: float = 0.80

    # HDBSCAN buffer
    hdbscan_min_cluster_size: int = 10
    hdbscan_min_batch: int = 15
    hdbscan_cluster_selection_epsilon: float = 0.2
    buffer_flush_interval: timedelta = timedelta(minutes=10)
    buffer_expiration: timedelta = timedelta(hours=6)

    # Rolling windows
    active_window: timedelta = timedelta(hours=48)
    historical_window: timedelta = timedelta(days=30)

    # Spread engine
    spread_alpha: float = 0.5
    supported_platforms: tuple[str, ...] = ("X", "Telegram", "Reddit", "YouTube")

    # Lifecycle
    bucket_size: timedelta = timedelta(hours=1)
    lifecycle_min_volume: int = 10
    first_appearance_max_hours: int = 2
    author_growth_threshold: float = 0.25
    peak_velocity_ratio: float = 0.10
    decline_drop_ratio: float = 0.15
    decline_consecutive_buckets: int = 2

    # Trend score weights
    w_acceleration: float = 0.30
    w_author_growth: float = 0.25
    w_engagement: float = 0.15
    w_novelty: float = 0.15
    w_spread: float = 0.15

    # Naming
    ctfidf_top_k: int = 5
    llm_prompt_template: str = (
        "Summarize these keywords into a 3 to 5 word topic headline: {keywords}"
    )

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    active_centroids_collection: str = "active_topic_centroids"
    historical_centroids_collection: str = "historical_topic_centroids"
    embeddings_collection: str = "post_embeddings"

    # DuckDB
    duckdb_path: str = "data/timeseries.duckdb"

    # Redis (active centroids, unclustered buffer, stream)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_stream_key: str = "person2:nlp_events"
    redis_consumer_group: str = "section-d-workers"
    redis_consumer_name: str = "worker-1"

    # Person 2 Vector DB — WIRE LATER: real Qdrant/Pgvector URL from Person 2
    person2_qdrant_url: str | None = None
    person2_qdrant_collection: str = "nlp_embeddings"
    person2_pgvector_dsn: str | None = None

    # Kafka — WIRE LATER: Person 2 event stream
    kafka_bootstrap_servers: str | None = None
    kafka_topic: str = "person2.nlp.output"

    # Component E
    component_e_graph_path: str | None = None
    component_e_api_url: str | None = None


DEFAULT_CONFIG = PipelineConfig()
