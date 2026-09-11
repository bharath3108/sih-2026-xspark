import json
from typing import Any, Dict, Iterator


def iter_jsonl(path: str) -> Iterator[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def load_index_by_event_id(path: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for obj in iter_jsonl(path):
        eid = obj.get("event_id")
        if eid:
            out[eid] = obj
    return out


def load_embeddings_by_ref(path: str) -> Dict[str, list[float]]:
    """
    Each line:
    {"embedding_ref":"vec-001","vector":[...]}
    """
    out: Dict[str, list[float]] = {}
    for obj in iter_jsonl(path):
        ref = obj.get("embedding_ref")
        vec = obj.get("vector")
        if ref and isinstance(vec, list):
            out[ref] = vec
    return out