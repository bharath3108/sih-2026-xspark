import networkx as nx


def build_interaction_graph(events: list[dict]) -> tuple[nx.DiGraph, list[str]]:
    """
    Extracts directed interaction edges (replying author -> original author)
    from canonical events.

    Canonical events only carry reply_to_id / parent_event_id — the parent
    EVENT's id, not its author — so parent authorship is resolved via an
    event_id -> author_id_hash map built from this same batch. A reply whose
    parent isn't present in the batch is skipped rather than wiring an edge
    to a raw event id, which would otherwise mix event ids and author hashes
    together as if they were the same kind of node.
    """
    G = nx.DiGraph()
    evidence_ids = []

    event_id_to_author = {
        event["event_id"]: event["author_id_hash"]
        for event in events
        if event.get("event_id") and event.get("author_id_hash")
    }

    for event in events:
        author = event.get("author_id_hash")
        event_id = event.get("event_id")

        if event_id:
            evidence_ids.append(event_id)
        if not author:
            continue

        G.add_node(author)

        # parent_event_id is the resolved internal event id; reply_to_id is
        # the raw platform post reference (e.g. "x_1001") and only usable
        # here if a caller has already put a real event id in it directly.
        parent_event_id = event.get("parent_event_id") or event.get("reply_to_id")
        parent_author = event_id_to_author.get(parent_event_id) if parent_event_id else None

        if parent_author and parent_author != author:
            G.add_edge(author, parent_author, event_id=event_id)

    return G, evidence_ids
