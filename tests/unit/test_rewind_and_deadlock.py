import json

import pytest

from vazus_core.engine.global_j_workspace import GlobalJWorkspace
from vazus_core.engine.skill_state_runtime import SkillStateRuntime


def _resp(patch):
    return json.dumps({"action": "x", "state_patch": patch})


def test_rewind_restores_earlier_state():
    rt = SkillStateRuntime("s", "p", {"n": 0})
    for i in (1, 2, 3):
        rt.process_llm_response(_resp({"n": i}))
    assert rt.rewind(2) == {"n": 1}
    assert rt.step_count == 1
    with pytest.raises(ValueError):
        rt.rewind(5)


def test_rewind_checkpoint_is_deep_copy():
    rt = SkillStateRuntime("s", "p", {"e": {"b": 1}})
    rt.process_llm_response(_resp({"n": 1}))
    rt.state["e"]["b"] = 99  # nested dict is shared with the pre-step state unless deep-copied
    assert rt.rewind(1) == {"e": {"b": 1}}


def test_break_deadlock_inhibits_repeated_concept():
    ws = GlobalJWorkspace()
    for _ in range(3):
        ws.broadcast_concept("c1", "retry_same_fix", 0.8, "coder")
    assert ws.break_deadlock() == "c1"
    assert ws.active_concepts["c1"].activation_strength == pytest.approx(0.4)
    assert ws.break_deadlock() is None  # marker entry reset the window


def test_no_deadlock_when_progressing():
    ws = GlobalJWorkspace()
    for i, label in enumerate(("plan", "code", "verify")):
        ws.broadcast_concept(f"c{i}", label, 0.8, "agent")
    assert ws.break_deadlock() is None
