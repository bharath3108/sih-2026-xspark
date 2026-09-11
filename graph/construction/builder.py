import networkx as nx

def build_interaction_graph(events: list[dict]) -> tuple[nx.DiGraph, list[str]]:
    """
    Extracts directed interaction edges (author -> target/parent) from canonical events.
    """
    G = nx.DiGraph()
    evidence_ids = []

    for event in events:
        author = event.get("author_id_hash")
        event_id = event.get("event_id")
        
        if event_id:
            evidence_ids.append(event_id)
        if not author:
            continue

        G.add_node(author)

        # Connect to replied author or parent event
        parent_author = event.get("parent_author_id_hash")
        parent_id = event.get("reply_to_id") or event.get("parent_event_id")

        if parent_author:
            G.add_edge(author, parent_author, event_id=event_id)
        elif parent_id:
            G.add_node(parent_id)
            G.add_edge(author, parent_id, event_id=event_id)

    return G, evidence_ids