import networkx as nx

def classify_node_role(
    node: str,
    in_deg: int,
    out_deg: int,
    betweenness: float,
    is_bridge: bool = False,
    max_in_deg: int = 1,
    max_out_deg: int = 1
) -> str:
    """
    Categorizes a node into a human-readable structural role based on topology.
    """
    # Normalized thresholds relative to graph max
    norm_in = in_deg / max(max_in_deg, 1)
    norm_out = out_deg / max(max_out_deg, 1)
    
    # 1. Bridge Node Priority
    if is_bridge:
        return "Cross-Community Narrative Bridge"

    # 2. Spammer / Automated Bot pattern: Heavy output, zero engagement back
    if out_deg >= 5 and in_deg == 0:
        return "Potential Spammer / High-Volume Broadcaster"
    
    # 3. Mega-Influencer: Heavy incoming engagement, low outbound spam
    if norm_in > 0.3 and norm_out < 0.2:
        return "Mega-Influencer / Focal Account"

    # 4. Gatekeeper / Information Broker: High betweenness centrality
    if betweenness > 0.1:
        return "Information Gatekeeper / Bottleneck"

    # 5. Core Hub: High inbound AND outbound engagement
    if norm_in > 0.2 and norm_out > 0.2:
        return "Active Network Hub"

    return "Standard Participant"


def compute_centrality_with_roles(G: nx.DiGraph, bridge_nodes: list[str] = None) -> list[dict]:
    """
    Calculates centrality metrics and attaches structural roles to all nodes in the graph.
    """
    if G.number_of_nodes() == 0:
        return []

    bridge_set = set(bridge_nodes or [])

    # Calculate raw metrics
    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())
    betweenness = nx.betweenness_centrality(G, k=min(G.number_of_nodes(), 100)) # k-sampling for speed

    max_in = max(in_degrees.values()) if in_degrees else 1
    max_out = max(out_degrees.values()) if out_degrees else 1

    nodes_summary = []
    for node in G.nodes():
        in_deg = in_degrees.get(node, 0)
        out_deg = out_degrees.get(node, 0)
        b_score = betweenness.get(node, 0.0)
        is_b = node in bridge_set

        role = classify_node_role(
            node=node,
            in_deg=in_deg,
            out_deg=out_deg,
            betweenness=b_score,
            is_bridge=is_b,
            max_in_deg=max_in,
            max_out_deg=max_out
        )

        nodes_summary.append({
            "node_id": node,
            "in_degree": in_deg,
            "out_degree": out_deg,
            "betweenness_centrality": round(b_score, 4),
            "is_bridge": is_b,
            "structural_role": role
        })

    # Sort nodes by influence (in_degree + betweenness)
    nodes_summary.sort(key=lambda x: (x["in_degree"], x["betweenness_centrality"]), reverse=True)
    return nodes_summary