"""Regression tests for Person 2's ml/ module: the adapter's platform
mapping (previously collapsed instagram/other onto Platform.X) and the
stance-without-a-target contract (must report unknown, not a guess)."""
import uuid
from datetime import datetime, timezone

import pytest

from ml.mainml import SocialMediaEventRequest, Engagement, Metadata, process_social_event
from ml.adapterml import NLPAdapter
from src.contracts.nlp_input import Platform


def _request(**overrides):
    defaults = dict(
        event_id=uuid.uuid4(),
        source="x",
        source_post_id="post-1",
        author_id_hash="hash-1",
        timestamp_utc=datetime.now(timezone.utc),
        text="a plain test message",
        engagement=Engagement(likes=0, shares=0, comments=0, views=0),
        metadata=Metadata(source_version="1.0.0", collected_at_utc=datetime.now(timezone.utc)),
    )
    defaults.update(overrides)
    return SocialMediaEventRequest(**defaults)


@pytest.mark.parametrize(
    "source,expected",
    [
        ("x", Platform.X),
        ("telegram", Platform.TELEGRAM),
        ("reddit", Platform.REDDIT),
        ("instagram", Platform.INSTAGRAM),
        ("other", Platform.OTHER),
    ],
)
def test_platform_mapping_does_not_collapse_to_x(source, expected):
    req = _request(source=source)
    resp = process_social_event(req)
    contract = NLPAdapter.social_media_event_to_nlp_contract(req, resp)
    assert contract.platform == expected


def test_platform_reverse_mapping_round_trips():
    for source in ("x", "telegram", "reddit", "instagram", "other"):
        req = _request(source=source)
        resp = process_social_event(req)
        contract = NLPAdapter.social_media_event_to_nlp_contract(req, resp)
        reversed_req = NLPAdapter.nlp_contract_to_social_media_event(contract)
        assert reversed_req.source == source


def test_stance_without_target_is_unknown():
    req = _request(target_topic=None, text="I really support this a lot")
    resp = process_social_event(req)
    assert resp.stance.label == "unknown"
    assert resp.stance.confidence == 0.0
