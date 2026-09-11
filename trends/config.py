from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    RUN_MODE: str = "fixture"  # only fixture mode for MVP

    FIXTURE_EVENTS_PATH: str = "data/fixtures/canonical_events.sample.jsonl"
    FIXTURE_NLP_PATH: str = "data/fixtures/nlp_outputs.sample.jsonl"
    FIXTURE_EMBEDDINGS_PATH: str = "data/fixtures/embeddings.sample.jsonl"

    # clustering
    CLUSTER_METHOD: str = "kmeans"  # kmeans | hdbscan
    KMEANS_K: int = 8
    MIN_CLUSTER_SIZE: int = 10

    # stable topic mapping (in-memory MVP)
    TOPIC_MATCH_THRESHOLD: float = 0.82

    # trend buckets
    BUCKET_MINUTES: int = 60

    # audience thresholds
    MIN_SAMPLE_SIZE: int = 20

    class Config:
        env_file = ".env"


settings = Settings()