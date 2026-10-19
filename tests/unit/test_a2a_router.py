"""Tests for Google Agent-to-Agent (A2A) Protocol Router in Vazus."""

import pytest
from vazus_core.a2a_router import A2AContext, A2AIntent, A2AMessage, A2ARouter


def test_a2a_message_creation_and_serialization():
    msg = A2AMessage.create(
        sender="antigravity_master",
        recipient="harnet_oracle",
        intent=A2AIntent.VERIFICATION,
        payload={"candidate_code": "def test(): pass"},
    )
    assert msg.sender == "antigravity_master"
    assert msg.intent == A2AIntent.VERIFICATION
    assert msg.context.depth == 0

    json_str = msg.to_json()
    assert "antigravity_master" in json_str

    # Test deserialization
    import json
    data = json.loads(json_str)
    reconstructed = A2AMessage.from_dict(data)
    assert reconstructed.message_id == msg.message_id
    assert reconstructed.intent == A2AIntent.VERIFICATION


def test_a2a_router_depth_limit():
    router = A2ARouter()
    deep_ctx = A2AContext(depth=9, max_depth=8)
    msg = A2AMessage.create(
        sender="agent_a",
        recipient="agent_b",
        intent=A2AIntent.HANDOFF,
        payload={},
        context=deep_ctx,
    )
    res = router.route_message(msg)
    assert res["status"] == "REJECTED_MAX_DEPTH"


def test_a2a_router_circular_loop_detection():
    router = A2ARouter()
    ctx = A2AContext()

    msg1 = A2AMessage.create(sender="agent_a", recipient="agent_b", intent=A2AIntent.HANDOFF, payload={}, context=ctx)
    msg2 = A2AMessage.create(sender="agent_b", recipient="agent_a", intent=A2AIntent.HANDOFF, payload={}, context=ctx)
    msg3 = A2AMessage.create(sender="agent_a", recipient="agent_b", intent=A2AIntent.HANDOFF, payload={}, context=ctx)

    assert router.route_message(msg1)["status"] == "ROUTED"
    assert router.route_message(msg2)["status"] == "ROUTED"
    res3 = router.route_message(msg3)
    assert res3["status"] == "REJECTED_CIRCULAR_LOOP"
