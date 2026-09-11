import networkx as nx

def build_interaction_graph(canonical_events: list[dict]) -> nx.DiGraph:
    """
    Extracts directed interaction edges from Person 1's canonical events.
    """
    graph = nx.DiGraph()
    for event in canonical_events:
        author = event.get("author_id_hash")
        if not author:
            continue
        
        graph.add_node(author)
        
        parent_id = event.get("parent_event_id") or event.get("reply_to_id")
        if parent_id:
            graph.add_edge(author, parent_id)
            
    return graph