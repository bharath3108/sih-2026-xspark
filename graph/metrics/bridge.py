import networkx as nx

def detect_bridge_nodes(G: nx.DiGraph, communities: list[dict]) -> list[dict]:
    """
    Identifies nodes that connect two or more distinct communities 
    and calculates their inter-community connection strength.
    """
    if not communities or G.number_of_edges() == 0:
        return []

    # Map each node to its assigned community ID (full membership, not just
    # the top-3 "central_nodes" sample -- see detector.py's "members" field).
    node_comm_map = {}
    for comm in communities:
        comm_id = comm.get("community_id")
        for node in comm.get("members", comm.get("central_nodes", [])):
            node_comm_map[node] = comm_id

    bridge_scores = {}

    for u, v in G.edges():
        comm_u = node_comm_map.get(u)
        comm_v = node_comm_map.get(v)

        # Check if edge crosses two known, distinct communities
        if comm_u and comm_v and comm_u != comm_v:
            bridge_scores[u] = bridge_scores.get(u, 0) + 1
            bridge_scores[v] = bridge_scores.get(v, 0) + 1

    sorted_bridges = sorted(bridge_scores.items(), key=lambda x: x[1], reverse=True)

    return [
        {
            "node_hash": node,
            "cross_edges": score,
            "community_id": node_comm_map.get(node, "unknown")
        }
        for node, score in sorted_bridges[:5]
    ]