"""
tests/test_subagent_bridges.py — Verification suite for RLM, Research Bridges, and Darwinian Evolver.
"""

import sys
from pathlib import Path

sys.path.insert(0, "C:/vazus")

from vazus_core.subagent_rlm_bridge import RLMCodeEngineerBridge
from vazus_core.subagent_research_bridge import OpenDeepResearchBridge
from vazus_core.evolution.darwinian_evolver import evaluate_fitness


def test_rlm_code_engineer_repl():
    bridge = RLMCodeEngineerBridge()
    res = bridge.execute_in_repl("a = 5\nb = 10\nres = a * b\nprint('Done')")

    assert res["status"] == "SUCCESS"
    assert "Done" in res["stdout"]
    assert res["duration_ms"] >= 0


def test_rlm_code_engineer_ast_pruning():
    bridge = RLMCodeEngineerBridge()
    code = """
def sample_function(x: int, y: int) -> int:
    '''This is a sample docstring.'''
    step_one = x + 10
    step_two = y * 20
    return step_one + step_two
"""
    prune_res = bridge.prune_code_context(code)
    assert prune_res["reduction_pct"] > 0
    assert "def sample_function" in prune_res["pruned_code"]


def test_research_bridge_decomposition_and_persistence(tmp_path):
    bridge = OpenDeepResearchBridge()
    subqueries = bridge.decompose_query("SMT Z3 Invariant Verification")

    assert len(subqueries) >= 3
    assert any("SMT Z3" in sq for sq in subqueries)

    report_res = bridge.persist_research_report(
        title="Test_SMT_Report",
        summary="SMT Z3 provides formal proofs for loop invariants.",
        findings=["Found 100% sound proof", "CEGAR minimizes counterexamples"],
        sources=["https://z3prover.github.io"]
    )
    assert report_res["status"] == "PERSISTED"
    assert report_res["findings_count"] == 2


def test_darwinian_evolver_fitness(tmp_path):
    valid_file = tmp_path / "valid_chrom.py"
    valid_file.write_text("def valid_fn(): return 42\n", encoding="utf-8")

    fitness = evaluate_fitness(str(valid_file))
    assert fitness == 1.0


def test_rlm_subagent_bridge_antigravity_default():
    from vazus_core.workers.subagent_rlm_bridge import RLMSubagentBridge
    bridge = RLMSubagentBridge()
    assert bridge.backend == "antigravity"
    res = bridge.run_subagent_task(
        prompt="Verify prime numbers under 20",
        dry_run=True
    )
    assert res["status"] == "SUCCESS"
    assert res["subagent"] == "rlm_code_engineer"
    assert res["mode"] == "dry_run_verification"

