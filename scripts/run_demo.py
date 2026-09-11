"""End-to-end demo: ingest clustered posts and print a Section D payload."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import PipelineConfig
from src.contracts.nlp_input import NLPOutputContract, Platform
from src.pipeline.orchestrator import SectionDPipeline


PLATFORMS = [Platform.X, Platform.TELEGRAM, Platform.REDDIT, Platform.YOUTUBE]
TEXTS = [
    "zero knowledge proof scaling frameworks on layer two rollups",
    "zk proof scaling solutions boosting ethereum throughput",
    "new zk scaling framework for production mainnet deployments",
    "zero knowledge proofs cutting verification costs at scale",
    "rollup teams adopting zk proof scaling frameworks this quarter",
]


def _vector(seed: int, dim: int = 384) -> list[float]:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim)
    return (v / np.linalg.norm(v)).tolist()


def _near(base: list[float], seed: int, noise: float = 0.015) -> list[float]:
    rng = np.random.RandomState(seed)
    arr = np.array(base) + rng.randn(len(base)) * noise
    return (arr / np.linalg.norm(arr)).tolist()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = PipelineConfig(duckdb_path=f"{tmpdir}/demo.duckdb")
        metadata = {
            f"author-{i}": {
                "profession": ["Software/Tech", "Crypto/Web3", "Other"][i % 3],
                "geography": ["US", "EU", "APAC"][i % 3],
            }
            for i in range(24)
        }
        pipeline = SectionDPipeline(config=config, author_metadata=metadata)
        base = _vector(7)
        start = datetime(2026, 9, 11, 14, 0, 0, tzinfo=timezone.utc)

        for i in range(24):
            ref = f"emb-zk-{i:03d}"
            pipeline.embedding_store.store(ref, _near(base, seed=100 + i))
            hour = i // 8
            pipeline.ingest(
                NLPOutputContract(
                    event_id=f"event-{i:03d}",
                    timestamp=start + timedelta(hours=hour, minutes=i % 8 * 7),
                    platform=PLATFORMS[i % 4],
                    embedding_ref=ref,
                    author_id=f"author-{i % 18}",
                    likes=80 + i * 12,
                    shares=10 + i * 3,
                    comments=5 + i * 2,
                    raw_text=TEXTS[i % len(TEXTS)],
                )
            )

        new_topics = pipeline.flush_buffer()
        payloads = pipeline.build_all_section_d()
        out_dir = ROOT / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "section_d.json"
        data = [p.to_json_dict() for p in payloads]
        out_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        print(f"HDBSCAN topics: {new_topics}")
        print(f"Wrote {len(payloads)} payload(s) to {out_path}")
        if payloads:
            print(json.dumps(payloads[0].to_json_dict(), indent=2, default=str))
        pipeline.close()


if __name__ == "__main__":
    main()
