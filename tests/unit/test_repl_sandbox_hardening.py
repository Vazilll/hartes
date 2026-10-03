"""
Unit tests for Sandboxed LocalREPL AST Sandboxing and Escape Prevention (Requirement R2).
"""

import pytest
from vazus_core.repl_engine import LocalREPL


def test_v01_subclasses_exploit_blocked():
    """Verify V-01 subclass gadget chain traversal is blocked."""
    repl = LocalREPL()
    try:
        # 1. Direct object.__subclasses__() access
        r1 = repl.execute_code("object.__subclasses__()")
        assert r1.status in ("BLOCKED", "REJECTED")
        assert r1.status != "SUCCESS"
        assert "REPLSandboxSecurityError" in r1.stderr or "forbidden attribute" in r1.stderr

        # 2. Traversal via type(chr).__mro__[1].__subclasses__()
        r2 = repl.execute_code("type(chr).__mro__[1].__subclasses__()")
        assert r2.status in ("BLOCKED", "REJECTED")
        assert r2.status != "SUCCESS"
        assert "REPLSandboxSecurityError" in r2.stderr or "forbidden attribute" in r2.stderr

        # 3. Access to __mro__, __bases__, __globals__
        r3 = repl.execute_code("str.__mro__")
        assert r3.status != "SUCCESS"

        r4 = repl.execute_code("int.__bases__")
        assert r4.status != "SUCCESS"
    finally:
        repl.cleanup()


def test_v03_import_exploits_blocked():
    """Verify V-03 importlib and ctypes module loading gadgets are blocked."""
    repl = LocalREPL()
    try:
        # 1. import importlib
        r1 = repl.execute_code("import importlib")
        assert r1.status in ("BLOCKED", "REJECTED")
        assert r1.status != "SUCCESS"
        assert "REPLSandboxSecurityError" in r1.stderr or "restricted" in r1.stderr

        # 2. import ctypes
        r2 = repl.execute_code("import ctypes")
        assert r2.status in ("BLOCKED", "REJECTED")
        assert r2.status != "SUCCESS"
        assert "REPLSandboxSecurityError" in r2.stderr or "restricted" in r2.stderr

        # 3. import sys and import os
        r3 = repl.execute_code("import sys")
        assert r3.status != "SUCCESS"

        r4 = repl.execute_code("import os")
        assert r4.status != "SUCCESS"

        # 4. from importlib import import_module
        r5 = repl.execute_code("from importlib import import_module")
        assert r5.status != "SUCCESS"

        # 5. Dynamic __import__('importlib')
        r6 = repl.execute_code("__import__('importlib')")
        assert r6.status != "SUCCESS"

        # 6. Dynamic __import__('ctypes')
        r7 = repl.execute_code("__import__('ctypes')")
        assert r7.status != "SUCCESS"
    finally:
        repl.cleanup()


def test_forbidden_builtins_blocked():
    """Verify forbidden builtins (eval, exec, compile, globals, locals) are blocked."""
    repl = LocalREPL()
    try:
        r1 = repl.execute_code("eval('1 + 1')")
        assert r1.status != "SUCCESS"

        r2 = repl.execute_code("exec('a = 1')")
        assert r2.status != "SUCCESS"

        r3 = repl.execute_code("compile('a = 1', '', 'exec')")
        assert r3.status != "SUCCESS"

        r4 = repl.execute_code("g = globals()")
        assert r4.status != "SUCCESS"

        r5 = repl.execute_code("l = locals()")
        assert r5.status != "SUCCESS"
    finally:
        repl.cleanup()


def test_dynamic_attribute_getattr_blocked():
    """Verify dynamic getattr attempts accessing forbidden attributes are blocked."""
    repl = LocalREPL()
    try:
        r1 = repl.execute_code("getattr(object, '__subclasses__')")
        assert r1.status != "SUCCESS"

        r2 = repl.execute_code("getattr(object, '__sub' + 'classes__')")
        assert r2.status != "SUCCESS"
    finally:
        repl.cleanup()


def test_legitimate_code_executes_successfully():
    """Verify legitimate code and allowed standard library modules execute successfully."""
    repl = LocalREPL()
    try:
        # 1. Basic math and variable assignment
        r1 = repl.execute_code("a = 15\nb = 27\nres = a + b\nprint(f'SUM: {res}')")
        assert r1.status == "SUCCESS"
        assert "SUM: 42" in r1.stdout
        assert r1.locals["res"] == 42

        # 2. Data manipulation
        r2 = repl.execute_code("items = [3, 1, 4, 1, 5, 9]\nsorted_items = sorted(items)")
        assert r2.status == "SUCCESS"
        assert r2.locals["sorted_items"] == [1, 1, 3, 4, 5, 9]

        # 3. Allowed standard library: math
        r3 = repl.execute_code("import math\nval = math.sqrt(256)")
        assert r3.status == "SUCCESS"
        assert r3.locals["val"] == 16.0

        # 4. Allowed standard library: json
        r4 = repl.execute_code('''import json\ndata = json.loads('{"status": "ok"}')''')
        assert r4.status == "SUCCESS"
        assert r4.locals["data"]["status"] == "ok"
    finally:
        repl.cleanup()
