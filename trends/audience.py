from collections import Counter
from typing import Dict, List
from dateutil import parser as dtparser
import re

from .config import settings
from .store import JoinedEvent


STATE_HINTS = {
    "delhi": "IN-DL",
    "mumbai": "IN-MH",
    "pune": "IN-MH",
    "bengaluru": "IN-KA",
    "bangalore": "IN-KA",
    "hyderabad": "IN-TG",
    "chennai": "IN-TN",
    "kolkata": "IN-WB",
}

INTEREST_RULES = {
    "politics": {"election", "bjp", "congress", "parliament", "government", "govt", "modi"},
    "student": {"exam", "jee", "neet", "college", "university", "student", "results"},
    "tech": {"ai", "ml", "python", "developer", "coding", "startup", "app"},
    "sports": {"cricket", "football", "match", "ipl", "goal"},
    "finance": {"stocks", "trading", "crypto", "nifty", "sensex", "ipo"},
}


def _per_author_latest(events: List[JoinedEvent]) -> Dict[str, JoinedEvent]:
    best = {}
    for e in events:
        ts = dtparser.isoparse(e.timestamp_utc)
        cur = best.get(e.author_id_hash)
        if cur is None or dtparser.isoparse(cur.timestamp_utc) < ts:
            best[e.author_id_hash] = e
    return best


def compute_audience(events: List[JoinedEvent]) -> Dict:
    author_events = _per_author_latest(events)
    sample_size = len(author_events)

    if sample_size < settings.MIN_SAMPLE_SIZE:
        return {"categories": {}, "unknown_share": 1.0, "sample_size": sample_size, "confidence": 0.0}

    # Language (from NLP)
    lang_labels, lang_confs = [], []
    for e in author_events.values():
        lang = (e.nlp.get("language") or {}).get("label")
        conf = float((e.nlp.get("language") or {}).get("confidence", 0.0))
        if lang:
            lang_labels.append(lang)
            lang_confs.append(conf)

    categories: Dict[str, Dict[str, float]] = {}
    confidences: List[float] = []

    if lang_labels:
        counts = Counter(lang_labels)
        covered = len(lang_labels)
        categories["language"] = {k: v / covered for k, v in counts.items()}
        coverage = covered / sample_size
        avg_conf = sum(lang_confs) / max(1, len(lang_confs))
        confidences.append(0.6 * coverage + 0.4 * avg_conf)
    else:
        confidences.append(0.0)

    # Geo (very best-effort from text)
    geo_found = []
    for e in author_events.values():
        txt = (e.text or "").lower()
        for hint, code in STATE_HINTS.items():
            if hint in txt:
                geo_found.append(code)
                break
    if geo_found:
        counts = Counter(geo_found)
        covered = len(geo_found)
        categories["geo"] = {k: v / covered for k, v in counts.items()}
        coverage = covered / sample_size
        confidences.append(0.6 * coverage + 0.4 * 0.65)
    else:
        confidences.append(0.0)

    # Interests (keyword rules MVP)
    interest_labels = []
    for e in author_events.values():
        txt = re.sub(r"[^a-zA-Z0-9\s]", " ", (e.text or "").lower())
        words = set(txt.split())
        best, best_score = None, 0
        for cat, keys in INTEREST_RULES.items():
            score = len(words.intersection(keys))
            if score > best_score:
                best, best_score = cat, score
        if best and best_score > 0:
            interest_labels.append(best)

    if interest_labels:
        counts = Counter(interest_labels)
        covered = len(interest_labels)
        categories["interests"] = {k: v / covered for k, v in counts.items()}
        coverage = covered / sample_size
        confidences.append(0.6 * coverage + 0.4 * 0.70)
    else:
        confidences.append(0.0)

    overall_conf = sum(confidences) / max(1, len(confidences))
    unknown_share = max(0.0, min(1.0, 1.0 - overall_conf))

    return {
        "categories": categories,
        "unknown_share": float(unknown_share),
        "sample_size": sample_size,
        "confidence": float(max(0.0, min(1.0, overall_conf))),
    }