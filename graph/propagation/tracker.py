import networkx as nx

def calculate_cascade_metrics(G: nx.DiGraph) -> dict:
    """
    Traces interaction cascades across the network to measure exact depth 
    and narrative reach per root originator.
    """
    if G.number_of_nodes() == 0:
        return {"max_depth": 0, "cascade_count": 0, "top_cascades": []}

    # Root originators are nodes with 0 in-degree (started a thread/narrative)
    roots = [node for node, in_deg in G.in_degree() if in_deg == 0]
    
    cascades = []
    max_depth = 0

    for root in roots:
        # Single-source shortest path gives exact tree depth and reach without cycle crashes
        lengths = nx.single_source_shortest_path_length(G, root)
        if lengths:
            depth = max(lengths.values())
            reach = len(lengths)
            if depth > max_depth:
                max_depth = depth
            if reach > 1:  # Only track cascades that actually propagated
                cascades.append({
                    "root_node": root,
                    "depth": depth,
                    "reach": reach
                })

    cascades.sort(key=lambda x: x["reach"], reverse=True)

    return {
        "max_depth": max_depth if max_depth > 0 else (1 if G.number_of_nodes() > 0 else 0),
        "cascade_count": len(cascades),
        "top_cascades": cascades[:3]
    }