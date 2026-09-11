from fastapi import APIRouter
from pydantic import BaseModel
from graph.construction.builder import build_graph_from_events
from graph.metrics.bridge import detect_bridge_nodes
from graph.metrics.centrality import compute_centrality_with_roles
from graph.propagation.tracker import analyze_propagation_cascade

router = APIRouter(prefix="/api/network", tags=["Network Analysis"])

class NetworkRequest(BaseModel):
    events: list[dict]

@router.post("")
def analyze_network(payload: NetworkRequest):
    G = build_graph_from_events(payload.events)
    
    # 1. Detect bridges
    bridge_nodes = detect_bridge_nodes(G)
    
    # 2. Compute centralities and assign structural roles
    classified_nodes = compute_centrality_with_roles(G, bridge_nodes=bridge_nodes)
    
    # 3. Analyze propagation
    cascade_info = analyze_propagation_cascade(G)
    
    # Extract evidence event IDs
    evidence_ids = [e.get("event_id") for e in payload.events if e.get("event_id")]

    return {
        "graph_metrics": {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "density": round(nx.density(G), 4) if G.number_of_nodes() > 0 else 0
        },
        "classified_nodes": classified_nodes,
        "key_bridge_nodes": bridge_nodes,
        "propagation": cascade_info,
        "evidence_event_ids": evidence_ids
    }