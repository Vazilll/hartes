"""
Unit and End-to-End Integration Tests for SelfHealingREPLManager & RollbackGuardrail (Milestone M1 / R1).
Tests closed-loop LocalREPL iterative repair, Concordia 3-Agent Jury consensus,
SMT Z3 contract verification, test command validation, and automatic RollbackGuardrail file restoration.
"""

import sys
import tempfile
from pathlib import Path
import pytest

from vazus_core.self_healing_repl import SelfHealingREPLManager
from vazus_core.safety_guardrail import RollbackGuardrail, SMTZ3Verifier
from vazus_core.concordia_jury import ConcordiaJury
from vazus_core.supergraph_master_orchestrator import SuperGraphMasterOrchestrator


def test_self_healing_repl_manager_init():
    """Verify SelfHealingREPLManager initializes with default and custom parameters."""
    manager = SelfHealingREPLManager(effort_level="high", consensus_threshold=0.66, min_quorum=3)
    assert manager.jury is not None
    assert manager.verifier is not None
    assert manager.consensus_threshold == 0.66
    assert manager.min_quorum == 3


def test_run_self_healing_repair_clean_success():
    """Verify end-to-end self-healing repair succeeds on valid proposal with passing votes, SMT, and tests."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".py") as tmp:
        tmp.write("def initial_func(): return 'original'\n")
        tmp_path = Path(tmp.name)

    try:
        manager = SelfHealingREPLManager()
        clean_proposal = '''
def add_positive(a: int, b: int) -> int:
    """
    :requires: a >= 0 and b >= 0
    :ensures: result >= 0
    """
    return a + b
'''
        agent_votes = [
            {"agent": "Planner", "verdict": "PASS"},
            {"agent": "RLM_Coder", "verdict": "PASS"},
            {"agent": "Verifier", "verdict": "PASS"},
        ]
        test_cmd = [sys.executable, "-c", "import sys; sys.exit(0)"]

        result = manager.run_self_healing_repair(
            target_file=tmp_path,
            code_proposal=clean_proposal,
            agent_votes=agent_votes,
            test_cmd=test_cmd,
            max_iterations=3,
        )

        assert result["repaired"] is True
        assert result["status"] in ("SUCCESS", "HEALED")
        assert result["jury_verdict"]["approved"] is True
        assert result["smt_verified"] is True
        assert result["rollback_executed"] is False
        assert "add_positive" in tmp_path.read_text(encoding="utf-8")
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_run_self_healing_repair_stray_syntax_auto_healed():
    """Verify SelfHealingREPLManager automatically heals stray syntax errors (stray 's)') without rollback."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".py") as tmp:
        tmp.write("def dummy(): return 'old'\n")
        tmp_path = Path(tmp.name)

    try:
        manager = SelfHealingREPLManager()
        broken_proposal = '''
def compute_total(a: int, b: int) -> int:
    return a + b
s)
'''
        test_cmd = [sys.executable, "-c", "import sys; sys.exit(0)"]

        result = manager.run_self_healing_repair(
            target_file=tmp_path,
            code_proposal=broken_proposal,
            test_cmd=test_cmd,
            max_iterations=3,
        )

        assert result["repaired"] is True
        assert result["status"] == "HEALED"
        assert result["healed"] is True
        assert "s)" not in tmp_path.read_text(encoding="utf-8")
        assert "compute_total" in tmp_path.read_text(encoding="utf-8")
        assert result["rollback_executed"] is False
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_run_self_healing_repair_concordia_jury_rejection_rollback():
    """Verify automatic RollbackGuardrail restoration when Concordia Jury rejects proposal (< 66% consensus)."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".py") as tmp:
        tmp.write("def original_code(): return 100\n")
        tmp_path = Path(tmp.name)

    try:
        manager = SelfHealingREPLManager(consensus_threshold=0.66, min_quorum=3)
        proposal = "def mutated_code(): return 200\n"
        failing_votes = [
            {"agent": "Planner", "verdict": "FAIL"},
            {"agent": "RLM_Coder", "verdict": "FAIL"},
            {"agent": "Verifier", "verdict": "PASS"},
        ]  # 1/3 = 33% < 66%

        result = manager.run_self_healing_repair(
            target_file=tmp_path,
            code_proposal=proposal,
            agent_votes=failing_votes,
        )

        assert result["repaired"] is False
        assert result["jury_verdict"]["approved"] is False
        assert result["rollback_executed"] is True
        assert tmp_path.read_text(encoding="utf-8") == "def original_code(): return 100\n"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_run_self_healing_repair_smt_contract_violation_rollback():
    """Verify automatic RollbackGuardrail restoration when SMT Z3 contract is violated."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".py") as tmp:
        tmp.write("def safe_func(x: int) -> int: return abs(x)\n")
        tmp_path = Path(tmp.name)

    try:
        manager = SelfHealingREPLManager()
        # Proposal violates post-condition: returns negative value for positive input
        violating_proposal = '''
def safe_func(x: int) -> int:
    """
    :requires: x >= 0
    :ensures: result >= 0
    """
    return -x - 1
'''
        agent_votes = [
            {"agent": "Planner", "verdict": "PASS"},
            {"agent": "RLM_Coder", "verdict": "PASS"},
            {"agent": "Verifier", "verdict": "PASS"},
        ]

        result = manager.run_self_healing_repair(
            target_file=tmp_path,
            code_proposal=violating_proposal,
            agent_votes=agent_votes,
        )

        assert result["repaired"] is False
        assert result["smt_verified"] is False
        assert result["rollback_executed"] is True
        assert tmp_path.read_text(encoding="utf-8") == "def safe_func(x: int) -> int: return abs(x)\n"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_run_self_healing_repair_test_command_failure_rollback():
    """Verify automatic RollbackGuardrail restoration when external test command fails (exit code != 0)."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".py") as tmp:
        tmp.write("def stable(): return True\n")
        tmp_path = Path(tmp.name)

    try:
        manager = SelfHealingREPLManager()
        proposal = "def stable(): return False\n"
        agent_votes = [
            {"agent": "Planner", "verdict": "PASS"},
            {"agent": "RLM_Coder", "verdict": "PASS"},
            {"agent": "Verifier", "verdict": "PASS"},
        ]
        failing_test_cmd = [sys.executable, "-c", "import sys; sys.exit(1)"]

        result = manager.run_self_healing_repair(
            target_file=tmp_path,
            code_proposal=proposal,
            agent_votes=agent_votes,
            test_cmd=failing_test_cmd,
        )

        assert result["repaired"] is False
        assert result["test_passed"] is False
        assert result["rollback_executed"] is True
        assert tmp_path.read_text(encoding="utf-8") == "def stable(): return True\n"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_run_self_healing_repair_unfixable_code_rollback():
    """Verify unfixable syntax errors trigger rollback and return status FAILED."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".py") as tmp:
        tmp.write("def valid(): pass\n")
        tmp_path = Path(tmp.name)

    try:
        manager = SelfHealingREPLManager()
        unfixable_proposal = "??? $$$ ### Invalid Token Syntax !!!"

        result = manager.run_self_healing_repair(
            target_file=tmp_path,
            code_proposal=unfixable_proposal,
        )

        assert result["repaired"] is False
        assert result["status"] == "FAILED"
        assert result["rollback_executed"] is True
        assert tmp_path.read_text(encoding="utf-8") == "def valid(): pass\n"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_master_orchestrator_r1_hook_integration():
    """Verify SuperGraphMasterOrchestrator.orchestrate_r1_self_healing_repl hook execution."""
    orchestrator = SuperGraphMasterOrchestrator()
    res = orchestrator.orchestrate_r1_self_healing_repl()
    assert isinstance(res, dict)
    assert res.get("status") in ("SUCCESS", "HEALED", "SYSTEM_R1_SELF_HEALED")
    assert res.get("repaired") is True
    assert "jury_verdict" in res
    assert "smt_status" in res
