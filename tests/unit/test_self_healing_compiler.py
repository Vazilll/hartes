"""
Unit tests for SelfHealingCompiler (RLEF / RLPF).
"""

import pytest
from pathlib import Path
from vazus_core.engine.self_healing_compiler import SelfHealingCompiler


def test_self_healing_compiler_performance_measurement():
    compiler = SelfHealingCompiler()
    target = Path("C:/vazus/vazus_core/verification/ast_pruner.py")
    perf = compiler._measure_performance(target)

    assert "ast_nodes" in perf
    assert perf["ast_nodes"] > 10
    assert "parse_latency_us" in perf
    assert perf["parse_latency_us"] > 0
    assert "peak_memory_kb" in perf


def test_self_healing_compiler_extract_code():
    compiler = SelfHealingCompiler()
    raw = "Here is the fix:\n```python\ndef add(a, b):\n    return a + b\n```\nDone."
    extracted = compiler._extract_code(raw)
    assert extracted == "def add(a, b):\n    return a + b"
