"""
tests/test_precommit_gate.py — Verification suite for Pre-Commit Quality Gate & Anti-Reward Hacking.
"""

import sys
from pathlib import Path

sys.path.insert(0, "C:/vazus")

from vazus_core.verification.precommit_gate import (
    run_gate_1_ast_and_security,
    find_targeted_tests,
)


def test_gate_1_clean_files(tmp_path):
    clean_file = tmp_path / "valid_module.py"
    clean_file.write_text("""
def calculate_metrics(values: list[float]) -> float:
    return sum(values) / max(1, len(values))
""", encoding="utf-8")

    ok, errors = run_gate_1_ast_and_security([clean_file])
    assert ok is True
    assert len(errors) == 0


def test_gate_1_detects_prohibited_calls(tmp_path):
    bad_file = tmp_path / "bad_worker.py"
    bad_file.write_text("""
import os
import subprocess

def run_dangerous():
    os.system("echo dangerous")
    subprocess.run(["dir"], shell=True)
""", encoding="utf-8")

    ok, errors = run_gate_1_ast_and_security([bad_file])
    assert ok is False
    assert any("os.system" in e for e in errors)
    assert any("shell=True" in e for e in errors)


def test_gate_1_detects_reward_hacking(tmp_path):
    dummy_test = tmp_path / "test_fake.py"
    dummy_test.write_text("""
def test_something():
    pass

def test_tautological():
    assert True
""", encoding="utf-8")

    ok, errors = run_gate_1_ast_and_security([dummy_test])
    assert ok is False
    assert any("Empty dummy test" in e for e in errors)
    assert any("Tautological assertion" in e for e in errors)


def test_find_targeted_tests():
    staged = [Path("C:/vazus/vazus_core/memory/mem0_memory_engine.py")]
    tests = find_targeted_tests(staged)
    assert isinstance(tests, list)


def test_gate_3_blocks_contract_violation(tmp_path):
    """Gate-3 must block a module whose implementation violates its formal contract."""
    from vazus_core.verification.precommit_gate import run_gate_3_smt_z3_contracts

    bad_file = tmp_path / "violating_module.py"
    bad_file.write_text("""\ndef faulty(x: int) -> int:
    \"\"\"
    :requires: x > 0
    :ensures: result > x + 5
    \"\"\"
    return x + 1
""", encoding="utf-8")

    ok, errors = run_gate_3_smt_z3_contracts([bad_file])
    assert ok is False
    assert any("SAT" in e for e in errors)


def test_gate_3_passes_clean_module(tmp_path):
    """Gate-3 must pass a module without formal contracts (NO_CONTRACTS, no fabricated UNSAT)."""
    from vazus_core.verification.precommit_gate import run_gate_3_smt_z3_contracts

    clean_file = tmp_path / "clean_module.py"
    clean_file.write_text("""\ndef add(x: int, y: int) -> int:
    return x + y
""", encoding="utf-8")

    ok, errors = run_gate_3_smt_z3_contracts([clean_file])
    assert ok is True


def test_programmatic_precommit_result_structure():
    """Verify GateResult and PrecommitResult dataclasses and to_dict serialization."""
    from vazus_core.verification.precommit_gate import GateResult, PrecommitResult

    gr = GateResult(gate_id=1, name="AST Syntax", passed=True, duration_ms=12.5)
    assert gr.gate_id == 1
    assert gr.passed is True
    assert gr.errors == []

    pr = PrecommitResult(
        all_passed=True,
        gate_results={1: gr},
        target_files=[Path("C:/vazus/valid.py")],
        total_duration_ms=50.0,
    )
    assert pr.all_passed is True
    d = pr.to_dict()
    assert d["all_passed"] is True
    assert 1 in d["gate_results"]
    assert d["gate_results"][1]["name"] == "AST Syntax"


def test_run_precommit_gate_empty_target_files():
    """run_precommit_gate with empty target list should immediately return all_passed=True."""
    from vazus_core.verification.precommit_gate import run_precommit_gate

    res = run_precommit_gate(target_files=[])
    assert res.all_passed is True
    assert len(res.gate_results) == 0
    assert len(res.target_files) == 0


def test_run_precommit_gate_failing_file(tmp_path):
    """run_precommit_gate should catch violations and return all_passed=False without sys.exit."""
    from vazus_core.verification.precommit_gate import run_precommit_gate

    bad_file = tmp_path / "syntax_error.py"
    bad_file.write_text("def broken_syntax(:\n    pass\n", encoding="utf-8")

    res = run_precommit_gate(target_files=[bad_file])
    assert res.all_passed is False
    assert 1 in res.gate_results
    assert res.gate_results[1].passed is False
    assert len(res.gate_results[1].errors) > 0


def test_run_precommit_gate_clean_file():
    """run_precommit_gate should pass clean modules through all stages."""
    from vazus_core.verification.precommit_gate import run_precommit_gate

    clean_file = Path("C:/vazus/vazus_core/verification/smt_z3_verifier.py")
    res = run_precommit_gate(target_files=[clean_file])
    assert res.all_passed is True
    assert 1 in res.gate_results
    assert res.gate_results[1].passed is True
    assert res.gate_results[2].passed is True
    assert res.gate_results[3].passed is True
    assert res.gate_results[4].passed is True
    assert res.gate_results[5].passed is True
    assert res.gate_results[6].passed is True


def test_cli_pixel_visualizer_import_and_fallback():
    """Verify CLIPixelVisualizer can be imported from root bridge and renders cleanly."""
    from vazus_core.cli_pixel_visualizer import CLIPixelVisualizer, cli_visualizer
    assert CLIPixelVisualizer is not None
    assert cli_visualizer is not None
    art = CLIPixelVisualizer.render_terminal_graph()
    assert isinstance(art, str)
    assert len(art) > 0

