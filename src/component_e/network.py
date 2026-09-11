"""Component E: Author interaction network for spread calculation."""

from __future__ import annotations

import json
import math
from pathlib import Path

import networkx as nx

try:
    import community as community_louvain
except ImportError:
    community_louvain = None


class AuthorInteractionNetwork:
    """
    Pulls author interaction network graph from Component E.
    Applies Louvain modularity to identify communities.
    """

    def __init__(self, graph_path: str | None = None):
        self.graph = nx.Graph()
        if graph_path:
            self.load_from_file(graph_path)

    def load_from_file(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.load_from_dict(data)

    def load_from_dict(self, data: dict) -> None:
        self.graph.clear()
        for edge in data.get("edges", []):
            self.graph.add_edge(
                edge["source"],
                edge["target"],
                weight=edge.get("weight", 1.0),
            )

    def add_edge(self, author_a: str, author_b: str, weight: float = 1.0) -> None:
        if self.graph.has_edge(author_a, author_b):
            self.graph[author_a][author_b]["weight"] += weight
        else:
            self.graph.add_edge(author_a, author_b, weight=weight)

    def build_from_cooccurrence(self, author_ids: list[str]) -> None:
        """Build edges from authors appearing in the same topic."""
        unique = list(set(author_ids))
        for i, a in enumerate(unique):
            for b in unique[i + 1 :]:
                self.add_edge(a, b)

    def get_communities(self) -> dict[str, int]:
        if self.graph.number_of_nodes() == 0:
            return {}
        if community_louvain is None:
            return {node: 0 for node in self.graph.nodes()}
        return community_louvain.best_partition(self.graph)

    def compute_network_entropy(self, author_ids: list[str]) -> float:
        """
        H_network = -1/log2(M) * sum(q_m * log2(q_m))
        where q_m is proportion of unique authors in community m.
        """
        if not author_ids:
            return 0.0

        communities = self.get_communities()
        author_set = set(author_ids)
        community_counts: dict[int, int] = {}

        for author in author_set:
            comm = communities.get(author, -1)
            if comm == -1:
                continue
            community_counts[comm] = community_counts.get(comm, 0) + 1

        if not community_counts:
            return 0.0

        total = sum(community_counts.values())
        m = len(community_counts)
        if m <= 1:
            return 0.0

        entropy = 0.0
        for count in community_counts.values():
            q = count / total
            if q > 0:
                entropy -= q * math.log2(q)

        return entropy / math.log2(m)
