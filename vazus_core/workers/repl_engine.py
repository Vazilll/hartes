"""
vazus_core.repl_engine ? Sandboxed REPL Engine with Self-Healing Code Evaluation Loop.
Provides LocalREPL execution and automated error recovery for Vazus SuperGraph OS v4.0.
"""

import ast
import copy
import io
import logging
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("LocalREPL")


@dataclass
class REPLResult:
    """Structured execution result returned by LocalREPL."""
    stdout: str
    stderr: str
    locals: Dict[str, Any]
    execution_time: float
    healed: bool = False
    healed_code: Optional[str] = None
    status: str = "SUCCESS"
    final_answer: Optional[str] = None
    original_error: Optional[str] = None
    rlm_calls: List[Any] = field(default_factory=list)
    result: Any = None

    @property
    def is_ready(self) -> bool:
        if self.status == "EMPTY_CODE":
            return False
        return self.status in ("SUCCESS", "HEALED")

    @property
    def variables(self) -> Dict[str, Any]:
        return self.locals

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "execution_time": self.execution_time,
            "healed": self.healed,
            "healed_code": self.healed_code,
            "status": self.status,
            "final_answer": self.final_answer,
            "original_error": self.original_error,
        }


class _AnswerDict(dict):
    """REPL-visible dict where setting ``answer['ready'] = True`` signals completion."""

    def __init__(self, on_ready=None):
        super().__init__()
        super().__setitem__("content", "")
        super().__setitem__("ready", False)
        self._on_ready = on_ready

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if key == "ready" and value and self._on_ready is not None:
            try:
                self._on_ready(self.get("content", ""))
            except Exception as exc:
                logger.debug("on_ready callback failed: %s", exc)


class REPLSandboxSecurityError(Exception):
    """Raised when code violates REPL sandbox security policies."""
    pass


FORBIDDEN_ATTRIBUTES = {
    "__subclasses__",
    "__mro__",
    "__bases__",
    "__base__",
    "__subclasshook__",
    "__globals__",
    "__code__",
    "__closure__",
    "__dict__",
    "__builtins__",
    "__import__",
    "__getattribute__",
    "func_globals",
    "gi_frame",
    "cr_frame",
}

FORBIDDEN_MODULES = {
    "importlib",
    "ctypes",
    "sys",
    "os",
    "subprocess",
    "pty",
    "builtins",
    "socket",
    "shutil",
    "signal",
    "multiprocessing",
    "pickle",
    "marshal",
    "inspect",
    "platform",
    "gc",
}

FORBIDDEN_BUILTINS = {
    "eval",
    "exec",
    "compile",
    "globals",
    "locals",
}


class REPLSandboxASTValidator(ast.NodeVisitor):
    """
    AST Visitor to strictly validate code prior to execution in the REPL sandbox.
    Neutralizes gadget chains, restricted imports, and forbidden builtins.
    """

    def validate(self, tree: ast.AST) -> None:
        self.visit(tree)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr in FORBIDDEN_ATTRIBUTES:
            raise REPLSandboxSecurityError(
                f"REPLSandboxSecurityError: Access to forbidden attribute '{node.attr}' is restricted."
            )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            mod_base = alias.name.split('.')[0]
            if mod_base in FORBIDDEN_MODULES or alias.name in FORBIDDEN_MODULES:
                raise REPLSandboxSecurityError(
                    f"REPLSandboxSecurityError: Import of module '{alias.name}' is restricted."
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            mod_base = node.module.split('.')[0]
            if mod_base in FORBIDDEN_MODULES or node.module in FORBIDDEN_MODULES:
                raise REPLSandboxSecurityError(
                    f"REPLSandboxSecurityError: Import from module '{node.module}' is restricted."
                )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if node.id in FORBIDDEN_BUILTINS:
            raise REPLSandboxSecurityError(
                f"REPLSandboxSecurityError: Access to forbidden builtin '{node.id}' is restricted."
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_BUILTINS:
                raise REPLSandboxSecurityError(
                    f"REPLSandboxSecurityError: Call to forbidden builtin '{node.func.id}' is restricted."
                )
            if node.func.id == "__import__":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    mod_name = node.args[0].value
                    mod_base = mod_name.split('.')[0]
                    if mod_base in FORBIDDEN_MODULES or mod_name in FORBIDDEN_MODULES:
                        raise REPLSandboxSecurityError(
                            f"REPLSandboxSecurityError: Dynamic import of module '{mod_name}' is restricted."
                        )
                else:
                    raise REPLSandboxSecurityError(
                        "REPLSandboxSecurityError: Direct call to __import__ is restricted."
                    )
            elif node.func.id == "getattr":
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                    attr_name = node.args[1].value
                    if attr_name in FORBIDDEN_ATTRIBUTES:
                        raise REPLSandboxSecurityError(
                            f"REPLSandboxSecurityError: Dynamic access to forbidden attribute '{attr_name}' is restricted."
                        )
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in FORBIDDEN_ATTRIBUTES:
                raise REPLSandboxSecurityError(
                    f"REPLSandboxSecurityError: Access to forbidden attribute '{node.func.attr}' is restricted."
                )
        self.generic_visit(node)


def _safe_getattr(obj, name, default=...):
    if name in FORBIDDEN_ATTRIBUTES:
        raise REPLSandboxSecurityError(f"REPLSandboxSecurityError: Access to forbidden attribute '{name}' is restricted.")
    if default is ...:
        return getattr(obj, name)
    return getattr(obj, name, default)


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    base_name = name.split('.')[0]
    if base_name in FORBIDDEN_MODULES or name in FORBIDDEN_MODULES:
        raise ImportError(f"REPLSandboxSecurityError: Import of module '{name}' is restricted in sandbox.")
    return __import__(name, globals, locals, fromlist, level)


def _get_safe_builtins() -> Dict[str, Any]:
    """Generates sandboxed Python builtins dictionary for REPL environment."""
    return {
        "abs": abs, "min": min, "max": max, "sum": sum, "len": len, "range": range,
        "enumerate": enumerate, "zip": zip, "map": map, "filter": filter, "sorted": sorted,
        "reversed": reversed, "list": list, "dict": dict, "set": set, "tuple": tuple,
        "str": str, "int": int, "float": float, "bool": bool, "type": type, "isinstance": isinstance,
        "issubclass": issubclass, "print": print, "round": round, "any": any, "all": all,
        "pow": pow, "divmod": divmod, "chr": chr, "ord": ord, "hex": hex, "bin": bin,
        "oct": oct, "repr": repr, "ascii": ascii, "format": format, "hash": hash, "id": id,
        "iter": iter, "next": next, "slice": slice, "callable": callable, "hasattr": hasattr,
        "getattr": _safe_getattr, "setattr": setattr, "delattr": delattr, "dir": dir, "vars": vars,
        "bytes": bytes, "bytearray": bytearray, "memoryview": memoryview, "complex": complex,
        "object": object, "super": super, "property": property, "staticmethod": staticmethod,
        "classmethod": classmethod, "__import__": _safe_import, "open": None,
        "Exception": Exception, "BaseException": BaseException, "ValueError": ValueError,
        "TypeError": TypeError, "KeyError": KeyError, "IndexError": IndexError,
        "AttributeError": AttributeError, "FileNotFoundError": FileNotFoundError,
        "PermissionError": PermissionError, "OSError": OSError, "IOError": IOError,
        "RuntimeError": RuntimeError, "NameError": NameError, "ImportError": ImportError,
        "StopIteration": StopIteration, "AssertionError": AssertionError,
        "NotImplementedError": NotImplementedError, "ArithmeticError": ArithmeticError,
        "LookupError": LookupError, "ZeroDivisionError": ZeroDivisionError,
        "IndentationError": IndentationError, "SyntaxError": SyntaxError, "Warning": Warning,
        "input": None, "eval": None, "exec": None, "compile": None, "globals": None,
        "locals": None, "breakpoint": None, "help": None, "exit": None, "quit": None
    }


SAFE_BUILTINS = _get_safe_builtins()
_SAFE_BUILTINS = SAFE_BUILTINS


class LocalREPL:
    """
    Local REPL Sandbox environment with persistent Python namespace and self-healing execution.
    """

    def __init__(
        self,
        context_payload: Optional[Union[dict, list, str]] = None,
        setup_code: Optional[str] = None,
        persistent: bool = True,
        depth: int = 1,
        custom_tools: Optional[Dict[str, Any]] = None,
    ):
        self.persistent = persistent
        self.depth = depth
        self.temp_dir = tempfile.mkdtemp(prefix=f"vazus_repl_{uuid.uuid4().hex[:8]}_")
        self._lock = threading.Lock()
        self.custom_tools = custom_tools or {}
        self.setup()

        if context_payload is not None:
            self.load_context(context_payload)

        if setup_code:
            self.execute_code(setup_code)

    def setup(self):
        """Initializes sandboxed environment globals and locals."""
        self.globals: Dict[str, Any] = {
            "__builtins__": _SAFE_BUILTINS.copy(),
            "__name__": "__main__",
        }
        self.locals: Dict[str, Any] = {}
        self._pending_llm_calls: List[Any] = []
        self._last_final_answer: Optional[str] = None

        temp_dir = self.temp_dir

        def _safe_open(file, mode="r", buffering=-1, *, encoding=None, errors=None, newline=None, closefd=True, opener=None):
            file_str = str(file)
            if not os.path.isabs(file_str):
                target_path = os.path.abspath(os.path.join(temp_dir, file_str))
            else:
                target_path = os.path.abspath(file_str)

            real_target = os.path.realpath(target_path)
            real_temp_dir = os.path.realpath(temp_dir)

            if not (real_target == real_temp_dir or real_target.startswith(real_temp_dir + os.sep)):
                raise PermissionError(f"Access to path '{file_str}' outside REPL sandbox '{temp_dir}' is denied.")

            return open(real_target, mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline, closefd=closefd, opener=opener)

        self.globals["__builtins__"]["open"] = _safe_open
        self.globals["open"] = _safe_open

        self.locals["answer"] = _AnswerDict(on_ready=self._capture_answer)

        for name, value in self.custom_tools.items():
            if callable(value):
                self.globals[name] = value
            else:
                self.locals[name] = value

    def _capture_answer(self, content: Any) -> None:
        self._last_final_answer = str(content)

    def load_context(self, context_payload: Union[dict, list, str]):
        """Load context dictionary or text into local variables."""
        if isinstance(context_payload, str):
            self.locals["context"] = context_payload
        elif isinstance(context_payload, (dict, list)):
            self.locals["context"] = copy.deepcopy(context_payload)

    def execute(self, code: str) -> REPLResult:
        """Alias for execute_code."""
        return self.execute_code(code)

    def _pre_validate_code_security(self, code: str, start_time: float) -> Optional[REPLResult]:
        try:
            tree = ast.parse(code)
            validator = REPLSandboxASTValidator()
            validator.validate(tree)
            return None
        except REPLSandboxSecurityError as sec_err:
            logger.debug("Sandbox security policy violation: %s", sec_err)
            return REPLResult(
                stdout="",
                stderr=str(sec_err),
                locals=self.locals.copy(),
                execution_time=time.perf_counter() - start_time,
                status="BLOCKED",
                final_answer=None,
                original_error=str(sec_err),
                rlm_calls=[],
            )
        except SyntaxError as syn_err:
            logger.debug("AST parse syntax note during validation: %s", syn_err)
            return None

    def _run_exec_sandbox(self, code: str) -> Tuple[str, str, str]:
        stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
        old_stdout, old_stderr = sys.stdout, sys.stderr
        old_cwd = os.getcwd()

        try:
            os.chdir(self.temp_dir)
            sys.stdout, sys.stderr = stdout_buf, stderr_buf

            combined = {**self.globals, **self.locals}
            exec(code, combined, combined)

            for key, value in combined.items():
                if key not in self.globals and not key.startswith("_"):
                    self.locals[key] = value

            return stdout_buf.getvalue(), stderr_buf.getvalue(), "SUCCESS"
        except Exception as e:
            logger.debug("REPL execution caught error: %s", e)
            stdout = stdout_buf.getvalue()
            is_sec = isinstance(e, (REPLSandboxSecurityError, PermissionError)) or "REPLSandboxSecurityError" in str(e)
            stderr = stdout + stderr_buf.getvalue() + ("\nREPLSandboxSecurityError: " + str(e) if is_sec else f"\n{type(e).__name__}: {e}")
            return stdout, stderr, ("BLOCKED" if is_sec else "ERROR")
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
            try:
                os.chdir(old_cwd)
            except Exception as exc:
                logger.debug("os.chdir restore note: %s", exc)

    def execute_code(self, code: str) -> REPLResult:
        """Executes Python code inside sandboxed REPL environment."""
        if not code or not code.strip():
            return REPLResult(
                stdout="",
                stderr="ValueError: Empty code string provided",
                locals=self.locals.copy(),
                execution_time=0.0,
                status="EMPTY_CODE",
                final_answer=None,
                rlm_calls=[],
            )

        start_time = time.perf_counter()

        blocked_result = self._pre_validate_code_security(code, start_time)
        if blocked_result is not None:
            return blocked_result

        self._pending_llm_calls = []
        stdout, stderr, status = self._run_exec_sandbox(code)

        final_ans = self._last_final_answer
        self._last_final_answer = None

        return REPLResult(
            stdout=stdout,
            stderr=stderr,
            locals=self.locals.copy(),
            execution_time=time.perf_counter() - start_time,
            status=status,
            final_answer=final_ans,
            rlm_calls=self._pending_llm_calls.copy(),
        )

    def eval_and_heal(self, code: str) -> REPLResult:
        """
        Executes code in REPL sandbox. Catches syntax/runtime errors and attempts
        automated self-healing repair.
        """
        if not code or not code.strip():
            return REPLResult(
                stdout="",
                stderr="ValueError: Empty code string provided",
                locals={},
                execution_time=0.0,
                status="EMPTY_CODE",
                healed=False,
                original_error="Empty code string provided"
            )

        initial_res = self.execute_code(code)

        if initial_res.status in ("BLOCKED", "REJECTED"):
            return initial_res

        # If execution passed cleanly without errors in stderr or status ERROR
        if initial_res.status == "SUCCESS" and not any(
            err_kw in initial_res.stderr
            for err_kw in ["SyntaxError:", "NameError:", "IndentationError:", "TypeError:", "ZeroDivisionError:", "AttributeError:"]
        ):
            return initial_res

        # Record original error
        orig_err = initial_res.stderr.strip() if initial_res.stderr.strip() else f"Execution status {initial_res.status}"
        logger.warning(f"[Self-Healing REPL] Detected error: {orig_err}. Attempting self-healing repair...")

        healed_code = code
        max_attempts = 3

        for attempt in range(max_attempts):
            healed_code = self._apply_self_healing(healed_code, orig_err)

            # Re-evaluate healed code
            attempt_res = self.execute_code(healed_code)

            if attempt_res.status == "SUCCESS" and not any(
                err_kw in attempt_res.stderr
                for err_kw in ["SyntaxError:", "NameError:", "IndentationError:", "TypeError:", "ZeroDivisionError:", "AttributeError:"]
            ):
                logger.info(f"[Self-Healing REPL] Repair successful on attempt {attempt + 1}!")
                attempt_res.healed = True
                attempt_res.healed_code = healed_code
                attempt_res.status = "HEALED"
                attempt_res.original_error = orig_err
                return attempt_res

            # Update error for next iteration
            orig_err = attempt_res.stderr.strip()

        # Failed to heal after max_attempts
        failed_res = self.execute_code(healed_code)
        failed_res.healed = False
        failed_res.healed_code = healed_code
        failed_res.status = "FAILED"
        failed_res.original_error = orig_err
        return failed_res

    def _apply_self_healing(self, code: str, error_msg: str) -> str:
        """
        Applies genuine AST and regex-based repair heuristics to fix common syntax and runtime errors.
        """
        lines = code.splitlines()
        new_lines = list(lines)

        # 1. Syntax Error Heuristics: Stray unmatched parenthesis/brackets (e.g. `s)` or `)`)
        if "SyntaxError: unmatched ')'" in error_msg or "unmatched ')'" in error_msg:
            m_line = re.search(r"line (\d+)", error_msg)
            if m_line:
                idx = int(m_line.group(1)) - 1
                if 0 <= idx < len(new_lines):
                    line_str = new_lines[idx].strip()
                    if line_str in (")", "s)", "])", "})"):
                        new_lines[idx] = ""
                    else:
                        new_lines[idx] = re.sub(r"s\)$|\)$", "", new_lines[idx])
            else:
                for i, ln in enumerate(new_lines):
                    if ln.strip() in (")", "s)", "])", "})"):
                        new_lines[i] = ""

        # 2. Syntax Error: Missing colons in block statements
        if "SyntaxError" in error_msg or "invalid syntax" in error_msg:
            for i, line in enumerate(new_lines):
                stripped = line.rstrip()
                if re.search(r"^\s*(def |if |elif |else|for |while |class |try|except|finally)", stripped) and not stripped.endswith(":"):
                    new_lines[i] = stripped + ":"

        # 3. NameError: Undefined variables or missing imports
        if "NameError: name " in error_msg:
            m_name = re.search(r"NameError: name '(\w+)' is not defined", error_msg)
            if m_name:
                var_name = m_name.group(1)
                stdlib_modules = {"math", "json", "re", "time", "copy", "uuid", "ast"}
                if var_name in stdlib_modules:
                    new_lines.insert(0, f"import {var_name}")
                else:
                    new_lines.insert(0, f"{var_name} = 0")

        # 4. ZeroDivisionError: Guard against division by zero
        if "ZeroDivisionError" in error_msg:
            for i, line in enumerate(new_lines):
                if "/" in line and "if" not in line:
                    new_lines[i] = re.sub(r"/ (\w+)", r"/ (\1 if \1 != 0 else 1)", new_lines[i])

        # 5. Indentation Error
        if "IndentationError" in error_msg:
            m_line = re.search(r"line (\d+)", error_msg)
            if m_line:
                idx = int(m_line.group(1)) - 1
                if 0 <= idx < len(new_lines):
                    new_lines[idx] = "    " + new_lines[idx].lstrip()

        return "\n".join(new_lines)

    def cleanup(self):
        """Cleanup temporary execution files."""
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as exc:
            logger.debug("shutil.rmtree cleanup error: %s", exc)
        if hasattr(self, "globals"):
            self.globals.clear()
        if hasattr(self, "locals"):
            self.locals.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False


def eval_and_heal(code: str) -> REPLResult:
    """Convenience module-level function for self-healing code evaluation."""
    repl = LocalREPL()
    try:
        return repl.eval_and_heal(code)
    finally:
        repl.cleanup()
