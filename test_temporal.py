import json
from graph.temporal.comparator import compare_network_windows

baseline = [
    {"event_id": "b1", "author_id_hash": "user_a", "parent_author_id_hash": None, "reply_to_id": None},
    {"event_id": "b2", "author_id_hash": "user_b", "parent_author_id_hash": "user_a", "reply_to_id": "b1"}
]

current = [
    {"event_id": "c1", "author_id_hash": "user_a", "parent_author_id_hash": None, "reply_to_id": None},
    {"event_id": "c2", "author_id_hash": "user_b", "parent_author_id_hash": "user_a", "reply_to_id": "c1"},
    {"event_id": "c3", "author_id_hash": "user_c", "parent_author_id_hash": "user_b", "reply_to_id": "c2"},
    {"event_id": "c4", "author_id_hash": "user_d", "parent_author_id_hash": "user_c", "reply_to_id": "c3"}
]

res = compare_network_windows(baseline, current)
print(json.dumps(res, indent=2))