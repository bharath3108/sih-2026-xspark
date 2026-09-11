import json
import jsonschema
import pytest

def test_canonical_events_fixture():
    with open("contracts/v1/canonical_event.schema.json") as f:
        schema = json.load(f)

    with open("data/fixtures/v1/canonical_events.jsonl") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                jsonschema.validate(instance=item, schema=schema)
