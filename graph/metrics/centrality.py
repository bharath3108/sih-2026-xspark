import networkx as nx

def compute_centrality_scores(G: nx.DiGraph, top_n: int = 5) -> dict:
    """
    Calculates degree and betweenness centrality for key node identification.
    """
    if G.number_of_nodes() == 0:
        return {"top_degree": [], "top_betweenness": []}

    deg_centrality = nx.degree_centrality(G)
    bet_centrality = nx.betweenness_centrality(G)

    sorted_deg = sorted(deg_centrality.items(), key=lambda x: x[1], reverse=True)[:top_n]
    sorted_bet = sorted(bet_centrality.items(), key=lambda x: x[1], reverse=True)[:top_n]

    return {
        "top_degree": [node for node, _ in sorted_deg],
        "top_betweenness": [node for node, _ in sorted_bet],
    }