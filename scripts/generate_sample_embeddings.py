"""Generate sample embeddings for example NLP payloads."""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    rng = np.random.RandomState(42)
    base = rng.randn(384)
    base = base / np.linalg.norm(base)

    embeddings = {}
    for i in range(1, 16):
        noise = rng.randn(384) * 0.02
        vec = base + noise
        vec = vec / np.linalg.norm(vec)
        embeddings[f"emb-zk-{i:03d}"] = vec.tolist()

    for i in range(1, 4):
        embeddings[f"emb-zk-00{i}"] = embeddings[f"emb-zk-00{i}"]

    out = ROOT / "examples" / "sample_embeddings.json"
    out.write_text(json.dumps(embeddings, indent=2), encoding="utf-8")
    print(f"Wrote {len(embeddings)} embeddings to {out}")


if __name__ == "__main__":
    main()
