"""
tests/unit/test_auto_index_runner_and_adaptive_gates.py — Unit Tests for Self-Sustaining Maintenance & Adaptive Gates.
"""

import ast
import tempfile
from pathlib import Path
import pytest

from vazus_core.maintenance.auto_index_runner import (
    SpecSynchronizer,
    AutoIndexRunner,
    run_maintenance,
)
from vazus_core.verification.concordia_jury import (
    AdaptiveComplexityGate,
    ChangeComplexity,
)
from vazus_core.memory.mem0_memory_engine import Mem0Engine


def test_spec_synchronizer_generates_valid_spec(tmp_path: Path):
    """Verifies that SpecSynchronizer correctly extracts AST symbols and writes SPEC.md."""
    sample_module = tmp_path / "sample_service.py"
    sample_module.write_text(
        '''
"""Sample service module docstring."""

class OrderProcessor:
    """Processes financial orders."""
    def submit_order(self, order_id: str) -> bool:
        return True

def calculate_fee(amount: float) -> float:
    """Calculates flat fee."""
    return amount * 0.02
''',
        encoding="utf-8"
    )

    syncer = SpecSynchronizer(root_dir=tmp_path)
    spec_md = syncer.generate_spec_markdown(tmp_path)

    assert "OrderProcessor" in spec_md
    assert "submit_order" in spec_md
    assert "calculate_fee" in spec_md
    assert "Responsibilities & Boundaries" in spec_md

    synced = syncer.sync_component_spec(tmp_path)
    assert synced is True
    spec_file = tmp_path / "SPEC.md"
    assert spec_file.exists()
    assert "OrderProcessor" in spec_file.read_text(encoding="utf-8")


def test_auto_index_runner_execution():
    """Verifies that AutoIndexRunner runs cleanly without throwing unhandled exceptions."""
    runner = AutoIndexRunner()
    res = runner.run(paths=None, force_reindex=False)
    assert res["status"] == "OK"
    assert isinstance(res["synced_components"], list)
    assert "memory" in res["synced_components"] or "maintenance" in res["synced_components"]


def test_adaptive_complexity_gate_classification():
    """Verifies that AdaptiveComplexityGate properly segregates TRIVIAL, STANDARD, and CRITICAL changes."""
    # Trivial changes: docstrings, comments, constants
    trivial_code = '# Just a comment\nMAX_RETRIES = 5\n'
    assert AdaptiveComplexityGate.classify(trivial_code) == ChangeComplexity.TRIVIAL

    # Standard changes: normal functions
    standard_code = 'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
    assert AdaptiveComplexityGate.classify(standard_code) == ChangeComplexity.STANDARD

    # Critical changes: security, schemas, subprocess, contracts
    critical_contract = 'def divide(a: int, b: int) -> int:\n    """\n    :requires: b > 0\n    :ensures: result >= 0\n    """\n    return a // b\n'
    assert AdaptiveComplexityGate.classify(critical_contract) == ChangeComplexity.CRITICAL

    critical_security = 'import subprocess\nsubprocess.run(["ls"])\n'
    assert AdaptiveComplexityGate.classify(critical_security) == ChangeComplexity.CRITICAL


def test_mem0_adaptive_weights():
    """Verifies that Mem0Engine dynamically adjusts dense vs lexical weights based on query type."""
    engine = Mem0Engine()

    # Code/symbol query -> higher lexical weight
    code_dense, code_lex = engine._compute_adaptive_weights("AutoIndexRunner.run_maintenance()")
    assert code_lex > code_dense

    # Natural language query -> higher dense weight
    nl_dense, nl_lex = engine._compute_adaptive_weights("как работает распределение памяти?")
    assert nl_dense > nl_lex
