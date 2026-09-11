"""Step 2d: Narrative name generation via c-TF-IDF + lightweight LLM."""

from __future__ import annotations

import math
import re
from collections import Counter

import httpx

from src.config import PipelineConfig, DEFAULT_CONFIG
from src.contracts.nlp_input import IngestedEvent


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z]{3,}", text.lower())


def compute_ctfidf_keywords(
    cluster_texts: list[str],
    all_cluster_texts: list[list[str]] | None = None,
    top_k: int = 5,
) -> list[str]:
    """
    c-TF-IDF: W_{t,c} = tf_{t,c} * log(1 + A / f_t)
    """
    if not cluster_texts:
        return ["untitled", "topic"]

    cluster_tokens = [_tokenize(t) for t in cluster_texts if t]
    if not cluster_tokens:
        return ["untitled", "topic"]

    tf_counter: Counter = Counter()
    for tokens in cluster_tokens:
        tf_counter.update(tokens)

    all_clusters = all_cluster_texts if all_cluster_texts is not None else cluster_tokens
    total_freq: Counter = Counter()
    for ctokens in all_clusters:
        total_freq.update(set(ctokens))

    avg_words = sum(len(t) for t in cluster_tokens) / max(len(cluster_tokens), 1)

    scores: dict[str, float] = {}
    for term, tf in tf_counter.items():
        ft = total_freq.get(term, 1)
        scores[term] = tf * math.log(1 + avg_words / ft)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [term for term, _ in ranked[:top_k]]


class NarrativeNameGenerator:
    """Generates 3-5 word topic headlines from c-TF-IDF keywords."""

    def __init__(
        self,
        config: PipelineConfig = DEFAULT_CONFIG,
        llm_endpoint: str | None = None,
    ):
        self.config = config
        self.llm_endpoint = llm_endpoint

    def generate_from_events(
        self,
        events: list[IngestedEvent],
        all_cluster_texts: list[list[str]] | None = None,
    ) -> str:
        texts = [e.raw_text or "" for e in events]
        keywords = compute_ctfidf_keywords(
            texts,
            all_cluster_texts=all_cluster_texts,
            top_k=self.config.ctfidf_top_k,
        )
        return self.generate_from_keywords(keywords)

    def generate_from_keywords(self, keywords: list[str]) -> str:
        prompt = self.config.llm_prompt_template.format(
            keywords=", ".join(keywords)
        )

        if self.llm_endpoint:
            try:
                return self._call_llm(prompt)
            except Exception:
                pass

        return self._fallback_name(keywords)

    def _call_llm(self, prompt: str) -> str:
        response = httpx.post(
            self.llm_endpoint,
            json={"prompt": prompt, "max_tokens": 20},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        name = data.get("response") or data.get("text") or data.get("content", "")
        return name.strip().strip('"').strip("'")

    def _fallback_name(self, keywords: list[str]) -> str:
        words = keywords[:5]
        if len(words) < 3:
            words.extend(["topic", "discussion"][: 3 - len(words)])
        return " ".join(w.capitalize() for w in words[:5])
