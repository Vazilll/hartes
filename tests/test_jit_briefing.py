import pytest
from vazus_core.hooks.pre_invocation_hook import generate_executive_briefing
from vazus_core.workers.handoff_generator import check_and_generate_handoff

def test_jit_executive_briefing_content():
    briefing = generate_executive_briefing()
    assert isinstance(briefing, str)
    assert "15.10.2026" in briefing or "МИРЭА" in briefing
    assert "HUD" in briefing or "Vazus" in briefing

def test_handoff_generator_thresholds():
    # Below threshold (e.g. 5 turns)
    normal = check_and_generate_handoff(turn_index=5, messages=[])
    assert normal["should_handoff"] is False

    # Above threshold (e.g. 22 turns)
    bloated = check_and_generate_handoff(turn_index=22, messages=[{"role": "user", "content": "test request"}])
    assert bloated["should_handoff"] is True
    assert "handoff_briefing" in bloated
