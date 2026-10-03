"""
tests/unit/test_subprocess_repl.py — Unit tests for ZeroTrustSubprocessREPL.
"""

import pytest
from vazus_core.workers.subprocess_repl import ZeroTrustSubprocessREPL, SubprocessREPLResult


def test_subprocess_repl_basic_execution():
    repl = ZeroTrustSubprocessREPL(timeout_seconds=5.0, require_kernel_sandbox=False)
    res = repl.execute_code("a = 10\nb = 20\nc = a + b\nprint('Total:', c)")
    assert isinstance(res, SubprocessREPLResult)
    assert res.status == "SUCCESS"
    assert "Total: 30" in res.stdout
    assert res.locals.get("c") == 30


def test_subprocess_repl_with_context():
    repl = ZeroTrustSubprocessREPL(timeout_seconds=5.0, require_kernel_sandbox=False)
    res = repl.execute_code("result = base_val * 2", context={"base_val": 21})
    assert res.status == "SUCCESS"
    assert res.locals.get("result") == 42


def test_subprocess_repl_syntax_error():
    repl = ZeroTrustSubprocessREPL(timeout_seconds=5.0, require_kernel_sandbox=False)
    res = repl.execute_code("def broken(: pass")
    assert res.status == "ERROR"
    assert "SyntaxError" in res.stderr
