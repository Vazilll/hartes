"""
tests/test_precommit_gate.py — Verification suite for Pre-Commit Quality Gate & Anti-Reward Hacking.
"""

import sys
import ast
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
