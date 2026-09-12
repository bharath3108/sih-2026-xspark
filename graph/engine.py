import networkx as nx
from graph.construction.builder import build_interaction_graph
from graph.metrics.centrality import compute_centrality_scores, compute_centrality_with_roles
from graph.communities.detector import detect_communities
from graph.propagation.tracker import calculate_cascade_metrics
from graph.metrics.bridge import detect_bridge_nodes

MAX_NODES_LIMIT = 2000

def analyze_network(events: list[dict], start_time: str, end_time: str) -> dict:
    """
    Executes complete network graph pipeline including communities,
    centrality, propagation cascades, and cross-community bridge nodes.
    """
    G, evidence_ids = build_interaction_graph(events)
    
    if G.number_of_nodes() > MAX_NODES_LIMIT:
        top_nodes = sorted(G.degree, key=lambda x: x[1], reverse=True)[:MAX_NODES_LIMIT]
        G = G.subgraph([n for n, _ in top_nodes]).copy()

    num_nodes = G.number_of_nodes()
    num_edges = G.number_of_edges()
    density = round(nx.density(G), 6) if num_nodes > 0 else 0.0

    centrality = compute_centrality_scores(G)
    communities = detect_communities(G)
    cascade_data = calculate_cascade_metrics(G)
    bridge_nodes = detect_bridge_nodes(G, communities)

    # Calculate cross-community spread rate
    cross_community_rate = 0.0
    if communities and num_edges > 0:
        node_comm_map = {}
        for comm in communities:
            for node in comm.get("members", comm.get("central_nodes", [])):
                node_comm_map[node] = comm["community_id"]
        
        cross_edges = sum(1 for u, v in G.edges() if node_comm_map.get(u) != node_comm_map.get(v))
        cross_community_rate = round(cross_edges / num_edges, 2)

    return {
        "window": {"start": start_time, "end": end_time},
        "graph_metrics": {
            "nodes": num_nodes,
            "edges": num_edges,
            "density": density
        },
        "communities": communities,
        "bridge_nodes": bridge_nodes,
        "propagation": {
            "depth": cascade_data["max_depth"],
            "cross_community_rate": cross_community_rate,
            "cascade_count": cascade_data["cascade_count"],
            "key_nodes": centrality["top_betweenness"][:3]
        },
        "evidence_event_ids": evidence_ids[:10]
    }


def build_network_topology(events: list[dict]) -> dict:
    """Node/edge list for the visual graph -- not part of the published
    Network Contract (which only carries summary metrics + community
    membership), but real computed data instead of backend/services/
    data_access.py's network_edges.json stand-in, once real events exist."""
    G, _ = build_interaction_graph(events)

    if G.number_of_nodes() > MAX_NODES_LIMIT:
        top_nodes = sorted(G.degree, key=lambda x: x[1], reverse=True)[:MAX_NODES_LIMIT]
        G = G.subgraph([n for n, _ in top_nodes]).copy()

    communities = detect_communities(G)
    node_comm_map: dict[str, str] = {}
    for comm in communities:
        for node in comm.get("members", comm.get("central_nodes", [])):
            node_comm_map[node] = comm["community_id"]

    bridge_nodes = detect_bridge_nodes(G, communities)
    bridge_hashes = [b["node_hash"] for b in bridge_nodes]
    classified = compute_centrality_with_roles(G, bridge_nodes=bridge_hashes)

    nodes = [
        {
            "id": n["node_id"],
            "community_id": node_comm_map.get(n["node_id"], "unknown"),
            "centrality": n["betweenness_centrality"],
            "role": n["structural_role"],
        }
        for n in classified
    ]
    edges = [
        {"source": u, "target": v, "weight": 1, "type": "reply"}
        for u, v in G.edges()
    ]
    return {"nodes": nodes, "edges": edges}