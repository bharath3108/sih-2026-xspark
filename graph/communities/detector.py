import networkx as nx
from networkx.algorithms.community import greedy_modularity_communities
def detect_communities(G: nx.DiGraph) -> list[dict]:
    """
    Detects sub-communities using greedy modularity optimization.
    """
    if G.number_of_nodes() < 2:
        return []

    undirected_G = G.to_undirected()
    communities = list(greedy_modularity_communities(undirected_G))
    deg_centrality = nx.degree_centrality(G)

    result = []
    for i, comm in enumerate(communities):
        comm_nodes = list(comm)
        comm_nodes_sorted = sorted(comm_nodes, key=lambda n: deg_centrality.get(n, 0), reverse=True)
        
        result.append({
            "community_id": f"c{i+1}",
            "size": len(comm_nodes),
            # "central_nodes" is a short representative sample for the
            # published Network Contract; "members" is the full membership
            # and is what cross-community-edge math (bridge.py, engine.py)
            # must use — treating the truncated sample as full membership
            # was the bug that made cross_community_rate/bridge detection
            # blind to most of the graph.
            "central_nodes": comm_nodes_sorted[:3],
            "members": comm_nodes_sorted
        })

    return result