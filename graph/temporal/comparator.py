from graph.construction.builder import build_interaction_graph
from graph.communities.detector import detect_communities
from graph.metrics.centrality import compute_centrality_scores

def compare_network_windows(baseline_events: list[dict], current_events: list[dict]) -> dict:
    """
    Compares baseline network metrics against current window to detect 
    node growth, new key influencers, and community shifts over time.
    """
    G_base, _ = build_interaction_graph(baseline_events)
    G_curr, _ = build_interaction_graph(current_events)

    base_nodes = set(G_base.nodes())
    curr_nodes = set(G_curr.nodes())

    new_nodes = list(curr_nodes - base_nodes)
    node_growth_rate = round((len(curr_nodes) - len(base_nodes)) / max(len(base_nodes), 1), 2)
    edge_growth_rate = round((G_curr.number_of_edges() - G_base.number_of_edges()) / max(G_base.number_of_edges(), 1), 2)

    base_centrality = compute_centrality_scores(G_base)
    curr_centrality = compute_centrality_scores(G_curr)

    # Identify newly emerged key influencers
    emerging_key_nodes = list(set(curr_centrality["top_betweenness"]) - set(base_centrality["top_betweenness"]))

    return {
        "baseline_metrics": {
            "nodes": G_base.number_of_nodes(),
            "edges": G_base.number_of_edges()
        },
        "current_metrics": {
            "nodes": G_curr.number_of_nodes(),
            "edges": G_curr.number_of_edges()
        },
        "growth": {
            "node_growth_rate": node_growth_rate,
            "edge_growth_rate": edge_growth_rate,
            "new_node_count": len(new_nodes)
        },
        "emerging_key_nodes": emerging_key_nodes,
        "current_communities": detect_communities(G_curr)
    }