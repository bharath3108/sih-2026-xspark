import json
from graph.engine import analyze_network

# Mock canonical event data from Person 1
sample_events = [
    {"event_id": "evt-1", "author_id_hash": "user_a", "parent_author_id_hash": None, "reply_to_id": None},
    {"event_id": "evt-2", "author_id_hash": "user_b", "parent_author_id_hash": "user_a", "reply_to_id": "evt-1"},
    {"event_id": "evt-3", "author_id_hash": "user_c", "parent_author_id_hash": "user_a", "reply_to_id": "evt-1"},
    {"event_id": "evt-4", "author_id_hash": "user_d", "parent_author_id_hash": "user_b", "reply_to_id": "evt-2"},
]

output = analyze_network(
    events=sample_events, 
    start_time="2026-09-11T00:00:00Z", 
    end_time="2026-09-11T12:00:00Z"
)

print(json.dumps(output, indent=2))