"""
Unit tests for Sandboxed LocalREPL Engine and Self-Healing Code Execution (Milestone M1).
"""

import pytest
from vazus_core.repl_engine import LocalREPL, eval_and_heal


def test_local_repl_basic_execution():
    """Verify LocalREPL executes python code, stores locals, and captures stdout."""
    repl = LocalREPL()
    try:
        code = "a = 10\nb = 20\nres = a + b\nprint(f'SUM: {res}')"
        result = repl.execute_code(code)
        assert result.status == "SUCCESS"
        assert "SUM: 30" in result.stdout
        assert result.locals["res"] == 30
        assert result.locals["a"] == 10
    finally:
        repl.cleanup()


def test_local_repl_sandbox_restrictions():
    """Verify restricted system modules cannot be imported inside sandboxed LocalREPL."""
    repl = LocalREPL()
    try:
        code = "import subprocess"
        result = repl.execute_code(code)
        assert result.status in ("ERROR", "BLOCKED")
        assert any(kw in result.stderr for kw in ["ImportError", "REPLSandboxSecurityError", "restricted"])
    finally:
        repl.cleanup()


def test_eval_and_heal_clean_code():
    """Verify eval_and_heal returns clean result without healing for valid code."""
    code = "x = 5\ny = 15\nresult = x * y\nprint('RESULT:', result)"
    result = eval_and_heal(code)
    assert result.status == "SUCCESS"
    assert result.healed is False
    assert "RESULT: 75" in result.stdout


def test_eval_and_heal_stray_syntax_parenthesis():
    """Verify self-healing fixes stray trailing closing parenthesis 's)' or ')' syntax error."""
    broken_code = """
def calc_product(a: int, b: int) -> int:
    return a * b
s)
print("Product:", calc_product(6, 7))
"""
    result = eval_and_heal(broken_code)
    assert result.healed is True
    assert result.status == "HEALED"
    assert "Product: 42" in result.stdout
    assert "calc_product" in result.healed_code


def test_eval_and_heal_missing_colon():
    """Verify self-healing repairs missing colons in function and control flow headers."""
    broken_code = """
def double_val(x)
    return x * 2

print("Double:", double_val(21))
"""
    result = eval_and_heal(broken_code)
    assert result.healed is True
    assert result.status == "HEALED"
    assert "Double: 42" in result.stdout


def test_eval_and_heal_missing_import():
    """Verify self-healing injects missing standard library imports on NameError."""
    broken_code = """
val = math.sqrt(144)
print("Square root:", val)
"""
    result = eval_and_heal(broken_code)
    assert result.healed is True
    assert result.status == "HEALED"
    assert "Square root: 12.0" in result.stdout


def test_eval_and_heal_unfixable_error():
    """Verify unfixable syntax error returns status FAILED with original error details."""
    broken_code = "??? $$$ ### Invalid Token Chaos !!!"
    result = eval_and_heal(broken_code)
    assert result.healed is False
    assert result.status == "FAILED"
    assert result.original_error is not None
