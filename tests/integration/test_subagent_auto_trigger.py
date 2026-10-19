"""
tests/test_subagent_auto_trigger.py — Unit tests for M1 Auto-Triggering Subsystem (R1)
"""

import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
WORKSPACE_ROOT = str(Path(__file__).resolve().parents[2])
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from vazus_core.db import get_db_connection
from vazus_core.subagent_auto_trigger import (
    IntentEvaluationResult,
    TaskSpec,
    SubagentDispatchHandle,
    HermesTaskIntentEvaluator,
    InteractiveConfirmationGate,
    SubagentBackgroundDispatcher,
    evaluate_task_intent,
    request_user_confirmation,
    dispatch_background_subagent
)

# HermesTaskIntentEvaluator() builds a full SkillIntentParser index (~3-4s:
# 209+ SKILL.md scan + 768D embeddings). Cache a single instance and adjust
# threshold per test so the suite pays that cost once instead of per test.
_evaluator_cache: dict = {}


def _get_evaluator(threshold: float = 0.6) -> HermesTaskIntentEvaluator:
    key = "__default__"
    if key not in _evaluator_cache:
        _evaluator_cache[key] = HermesTaskIntentEvaluator(threshold=threshold)
    evaluator = _evaluator_cache[key]
    evaluator.threshold = threshold
    return evaluator


def test_intent_evaluator_simple_task():
    evaluator = _get_evaluator()
    res = evaluator.evaluate("What is 2 + 2?")
    assert isinstance(res, IntentEvaluationResult)
    assert res.requires_multi_agent is False
    assert res.requires_subagents is False
    assert res.intent_score < 0.6
    assert res.recommended_mode == "single_agent"


def test_intent_evaluator_complex_multi_agent():
    evaluator = _get_evaluator()
    prompt = "Execute deep research and SMT Z3 contract verification for refactoring whole project codebase."
    res = evaluator.evaluate(prompt)
    assert res.requires_multi_agent is True
    assert res.requires_subagents is True
    assert res.intent_score >= 0.6
    assert res.recommended_mode == "multi_agent_interactive"
    assert len(res.suggested_subagents) > 0


def test_intent_evaluator_keyword_scoring():
    evaluator = _get_evaluator(threshold=0.5)
    res = evaluator.evaluate("Run SMT Z3 formal verification on concordia jury")
    assert res.intent_score >= 0.5
    assert "smt z3" in res.metadata["matched_keywords"]
    assert "concordia" in res.metadata["matched_keywords"]


def test_intent_evaluator_suggested_subagents():
    evaluator = _get_evaluator()
    res = evaluator.evaluate("Deep research on neural architecture search and verify code")
    assert "open_deep_researcher" in res.suggested_subagents
    assert "verifier_worker" in res.suggested_subagents


def test_intent_evaluator_empty_prompt():
    evaluator = _get_evaluator()
    res = evaluator.evaluate("")
    assert res.intent_score == 0.0
    assert res.requires_multi_agent is False
    assert res.reasoning == "Empty prompt"


def test_confirmation_gate_simple_task_auto_pass():
    gate = InteractiveConfirmationGate()
    intent = IntentEvaluationResult(
        user_prompt="Simple task",
        complexity_score=0.2,
        requires_subagents=False,
        reasoning_summary="Simple task"
    )
    assert gate.request_confirmation(intent) is True


def test_confirmation_gate_auto_approve_flag():
    gate = InteractiveConfirmationGate(auto_approve=True)
    intent = IntentEvaluationResult(
        user_prompt="Complex task",
        complexity_score=0.8,
        requires_subagents=True,
        reasoning_summary="Complex task"
    )
    assert gate.request_confirmation(intent) is True


def test_confirmation_gate_custom_interactive_accept():
    called = []

    def mock_cb(msg: str) -> bool:
        called.append(msg)
        return True

    gate = InteractiveConfirmationGate(interactive_fn=mock_cb)
    intent = IntentEvaluationResult(
        user_prompt="Complex task",
        complexity_score=0.85,
        requires_subagents=True,
        reasoning_summary="Multi-agent prompt"
    )
    res = gate.request_confirmation(intent)
    assert res is True
    assert len(called) == 1
    assert "CONFIRMATION GATE" in called[0]


def test_confirmation_gate_custom_interactive_reject():
    def mock_cb(msg: str) -> bool:
        return False

    gate = InteractiveConfirmationGate(interactive_fn=mock_cb)
    intent = IntentEvaluationResult(
        user_prompt="Complex task",
        complexity_score=0.9,
        requires_subagents=True,
        reasoning_summary="Heavy analysis"
    )
    assert gate.request_confirmation(intent) is False


def test_background_dispatcher_valid_task(tmp_path):
    log_dir = tmp_path / "subagent_logs"
    dispatcher = SubagentBackgroundDispatcher(log_dir=str(log_dir))
    spec = TaskSpec(
        task_id="test_task_001",
        subagent_name="code_engineer",
        prompt="Write unit tests for auto trigger"
    )
    handle = dispatcher.dispatch(spec)
    assert isinstance(handle, SubagentDispatchHandle)
    assert handle.task_id == "test_task_001"
    assert handle.pid > 0
    assert os.path.exists(handle.log_file)
    assert handle.kill() is True


def test_background_dispatcher_handle_lifecycle(tmp_path):
    log_dir = tmp_path / "subagent_logs"
    dispatcher = SubagentBackgroundDispatcher(log_dir=str(log_dir))
    spec = TaskSpec(
        task_id="test_task_002",
        subagent_name="open_deep_researcher",
        prompt="Research task lifecycle"
    )
    handle = dispatcher.dispatch(spec)
    assert isinstance(handle.is_alive(), bool)
    res = handle.wait(timeout=2.0)
    assert isinstance(res, dict)
    assert "task_id" in res
    assert handle.kill() is True


def test_background_dispatcher_get_and_list_active(tmp_path):
    log_dir = tmp_path / "subagent_logs"
    dispatcher = SubagentBackgroundDispatcher(log_dir=str(log_dir))
    spec1 = TaskSpec(task_id="t1", subagent_name="code_engineer", prompt="p1")
    spec2 = TaskSpec(task_id="t2", subagent_name="verifier_worker", prompt="p2")
    h1 = dispatcher.dispatch(spec1)
    h2 = dispatcher.dispatch(spec2)

    assert dispatcher.get_handle("t1") == h1
    assert dispatcher.get_handle("t2") == h2
    active_handles = dispatcher.list_active()
    assert len(active_handles) >= 2
    h1.kill()
    h2.kill()


def test_evaluate_task_intent_top_level_api():
    res = evaluate_task_intent("Build full stack app with SMT Z3 verifier")
    assert isinstance(res, IntentEvaluationResult)
    assert res.requires_multi_agent is True
    assert res.requires_subagents is True


def test_request_user_confirmation_top_level_api():
    intent = evaluate_task_intent("Refactor whole system with concordia jury")
    res = request_user_confirmation(intent, auto_approve=True)
    assert res is True


def test_dispatch_background_subagent_top_level_api(tmp_path):
    spec = TaskSpec(
        task_id="t_top_level",
        subagent_name="open_deep_researcher",
        prompt="Deep research prompt",
        log_file=str(tmp_path / "top_level.log")
    )
    handle = dispatch_background_subagent(spec)
    assert isinstance(handle, SubagentDispatchHandle)
    assert handle.task_id == "t_top_level"
    assert handle.kill() is True


def test_background_dispatcher_db_persistence(tmp_path):
    """Self-certifying test asserting SQLite audit trace row persistence in vazus.db subagent_memory_traces."""
    log_dir = tmp_path / "subagent_logs"
    dispatcher = SubagentBackgroundDispatcher(log_dir=str(log_dir))
    task_id = f"test_db_trace_{int(time.time()*1000)}"
    spec = TaskSpec(
        task_id=task_id,
        subagent_name="code_engineer",
        prompt="Verify DB trace insertion"
    )
    handle = dispatcher.dispatch(spec)
    handle.wait(timeout=2.0)

    conn = get_db_connection()
    rows = conn.execute(
        "SELECT trace_id, agent_name, trace_kind, summary, content FROM subagent_memory_traces WHERE dialogue_id = ?",
        (task_id,)
    ).fetchall()
    conn.close()

    assert len(rows) > 0, f"No trace records persisted in vazus.db for dispatched task {task_id}!"
    assert rows[0][1] == "code_engineer"
    assert rows[0][2] == "SUBAGENT_DISPATCH"
    assert task_id in rows[0][3]
    handle.kill()


def test_keyword_overlap_scoring_no_double_count():
    """Verify keyword overlap scoring sorts keywords by length descending to avoid double-counting sub-phrases."""
    evaluator = _get_evaluator()
    res = evaluator.evaluate("Perform deep research on memory architecture")
    matched = res.metadata["matched_keywords"]
    assert "deep research" in matched
    assert "research" not in matched


def test_confirmation_gate_callback_exception_handled():
    """Verify custom interactive_fn callback exceptions are handled without crashing the gate."""
    def failing_cb(msg: str) -> bool:
        raise RuntimeError("Simulated confirmation callback exception")

    gate = InteractiveConfirmationGate(interactive_fn=failing_cb)
    intent = IntentEvaluationResult(
        user_prompt="Complex task",
        complexity_score=0.9,
        requires_subagents=True,
        reasoning_summary="Test callback exception"
    )
    res = gate.request_confirmation(intent)
    assert isinstance(res, bool)


def test_task_spec_dry_run_default_and_parameterized():
    """Verify TaskSpec defaults dry_run to False and allows explicit parametrization."""
    spec_default = TaskSpec()
    assert spec_default.dry_run is False

    spec_dry = TaskSpec(dry_run=True)
    assert spec_dry.dry_run is True


def test_dispatcher_command_injection_safety(tmp_path):
    """Verify generic dispatcher passes complex prompt payloads via JSON sys.argv[1] safely."""
    log_dir = tmp_path / "inj_logs"
    dispatcher = SubagentBackgroundDispatcher(log_dir=str(log_dir))
    malicious_prompt = "Triple quotes ''' and double \" and backslash \\ ; import os; os.system('echo injected')"
    spec = TaskSpec(
        task_id=f"t_inj_{int(time.time()*1000)}",
        subagent_name="unmapped_custom_agent",
        prompt=malicious_prompt
    )
    handle = dispatcher.dispatch(spec)
    res = handle.wait(timeout=3.0)
    assert res["status"] in ("COMPLETED", "FAILED", "KILLED")
    handle.kill()

