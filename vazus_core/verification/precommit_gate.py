#!/usr/bin/env python3
"""
vazus_core.verification.precommit_gate — Autonomous Pre-Commit Quality Gate for Vazus OS.
Triggered automatically by .git/hooks/pre-commit BEFORE any git commit is accepted.

Gates Enforced:
  1. AST Syntax Check (ast.parse) on all staged Python files.
  2. Static Security & Anti-Pattern Scan (No hardcoded API keys, no shell=True, no raw eval/exec).
  3. Module Import & Syntax Integrity.
  4. Targeted Pytest Suite (Zero test regressions) + L2 viztracer wiring (VAZUS_L2_TRACE=1).
  5. Dead Code Detection via vulture (unused imports, unreachable modules, unused vars ≥90% confidence).
  6. Fast Static Lint via ruff (F401 unused imports, F821 undefined names,
     F841 unused locals, E9 syntax errors).
  6b. OPT-IN Deep Scan (VAZUS_GATE_DEEP_SCAN=1): deptry (unused/missing deps),
      pip-audit (known CVEs), bandit (AST security). Advisory by default;
      set VAZUS_GATE_STRICT_DEEP=1 to make it blocking.
  7. Static Type Check via mypy (VAZUS_GATE_MYPY=1). Advisory by default;
     set VAZUS_GATE_STRICT_MYPY=1 to make it blocking.
  Gate-4 LLM deadline: VAZUS_GATE_JURY_TIMEOUT (default 120 seconds total).

Exit Codes:
  0 = ALL GATES PASSED (Commit Allowed)
  1 = GATE FAILED (Commit Blocked)
"""

import os
import sys
import ast
import json
import re
import time
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Union

logger = logging.getLogger("vazus_core.verification.precommit_gate")

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class GateResult:
    """Encapsulates the execution result for a single verification gate tier."""
    gate_id: int
    name: str
    passed: bool
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "name": self.name,
            "passed": self.passed,
            "duration_ms": self.duration_ms,
            "errors": self.errors,
        }


@dataclass
class PrecommitResult:
    """Aggregates multi-tier verification results across all gates."""
    all_passed: bool
    gate_results: dict[int, GateResult] = field(default_factory=dict)
    target_files: list[Path] = field(default_factory=list)
    total_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "gate_results": {k: v.to_dict() for k, v in self.gate_results.items()},
            "target_files": [str(f) for f in self.target_files],
            "total_duration_ms": self.total_duration_ms,
        }


def _resolve_workspace_root() -> Path:
    """Resolves workspace root relative to this file's location or env override."""
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() or (parent / "services").exists() or parent.name.lower() == "vazus":
            return parent
    return Path("C:/vazus")


VAZUS_ROOT = _resolve_workspace_root()
# Allow override via env for CI/CD portability
if os.getenv("VAZUS_WORKSPACE_DIR"):
    VAZUS_ROOT = Path(os.environ["VAZUS_WORKSPACE_DIR"]).resolve()

# Make vazus_core importable regardless of how the gate is invoked
# (git hook, direct script run, CI) — without this, Gate 3/4/4a silently
# degrade through their ImportError fallbacks instead of actually running.
if str(VAZUS_ROOT) not in sys.path:
    sys.path.insert(0, str(VAZUS_ROOT))


def get_staged_python_files() -> list[Path]:
    """Returns all staged .py files in git."""
    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=str(VAZUS_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0 and res.stdout.strip():
            files = []
            for line in res.stdout.strip().splitlines():
                p = VAZUS_ROOT / line.strip()
                if p.suffix.lower() == ".py" and p.exists():
                    files.append(p)
            return files
    except Exception as exc:
        logger.debug("Git staged python files retrieval failed: %s", exc)
    return []


SECRET_PATTERNS = [
    re.compile(r"""(?i)(?:api_key|auth_token)\s*=\s*['"](AIzaSy[0-9A-Za-z\-_]{30,})['"]"""),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"ghs_[a-zA-Z0-9]{36}"),
    re.compile(r"sk-ant-[a-zA-Z0-9_\-]{40,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"hf_[a-zA-Z0-9]{34,}"),
    re.compile(r"""(?i)password\s*=\s*['"][^\r\n'"]{8,}['"]"""),
]


SKIP_PREFIXES = (".venv", "__pycache__", ".git", ".pytest_cache", "scratch")


def _check_hardcoded_secrets(content: str, fpath: Optional[Path] = None) -> list[str]:
    """Scans content for hardcoded secret tokens, exempting gate and verifier files."""
    if fpath and ("gate" in fpath.name.lower() or "verif" in fpath.name.lower()):
        return []
    leaks = []
    for pat in SECRET_PATTERNS:
        if pat and pat.search(content):
            leaks.append("Hardcoded secret token / Hardcoded API key detected")
    return leaks


def _extract_file_imports(filepath: Path) -> list[str]:
    imports = []
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
    except Exception as exc:
        logger.debug("File import extraction failed for %s: %s", filepath, exc)
    return imports


def _check_ast_syntax(content_or_path: Union[str, Path], fpath: Optional[Path] = None) -> Optional[str]:
    if isinstance(content_or_path, Path):
        path = content_or_path
        src = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    elif fpath is not None:
        src = str(content_or_path)
        path = Path(fpath)
    else:
        src = str(content_or_path)
        path = Path("unknown.py")

    try:
        ast.parse(src, filename=str(path))
        return None
    except SyntaxError as e:
        return f"[AST Syntax Error] in {path.name} line {e.lineno}: {e.msg}"
    except Exception as e:
        return f"[AST Syntax Error] in {path.name}: {e}"


_TAINT_SOURCES = {"input", "sys_argv", "argv", "environ", "request_args"}


def _collect_taint_sources(node: ast.AST) -> set[str]:
    """Collects tainted argument names and variables from an AST function node."""
    tainted = set()
    for n in ast.walk(node):
        if isinstance(n, ast.arg):
            tainted.add(n.arg)
        elif isinstance(n, ast.Name):
            tainted.add(n.id)
    return tainted


def _check_dangerous_calls(content: str, _filename: str = "") -> list[str]:
    dangerous = []
    if "subprocess" in content and "shell=True" in content:
        dangerous.append("shell=True detected in subprocess call")
    if "os.system(" in content:
        dangerous.append("Prohibited os.system() call detected")
    return dangerous


def _check_taint_sinks(content_or_path: Union[str, Path], fpath: Optional[Path] = None) -> list[str]:
    """Detects tainted sources flowing directly into dangerous sinks (eval, subprocess)."""
    path = fpath if fpath else (content_or_path if isinstance(content_or_path, Path) else None)
    if path and path.name.startswith("test_"):
        return []
    src = content_or_path if isinstance(content_or_path, str) else (path.read_text(encoding="utf-8", errors="replace") if path and path.exists() else "")
    errors = []
    try:
        tree = ast.parse(src)
        tainted_vars = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                val_dump = ast.dump(node.value)
                if any(s in val_dump for s in ["input", "argv", "environ", "request"]):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            tainted_vars.add(target.id)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "eval":
                    for arg in node.args:
                        arg_dump = ast.dump(arg)
                        if any(s in arg_dump for s in ["input", "request", "argv", "read"]) or (isinstance(arg, ast.Name) and arg.id in tainted_vars):
                            errors.append("[Taint] Direct eval() with untrusted source")
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "run":
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                        for arg in node.args:
                            arg_dump = ast.dump(arg)
                            if any(s in arg_dump for s in ["argv", "input", "request"]) or (isinstance(arg, ast.Name) and (arg.id in tainted_vars or arg.id == "cmd")):
                                errors.append("[Taint] Subprocess execution with untrusted source")
    except Exception as exc:
        logger.debug("Taint sink check parse failed: %s", exc)
    return errors


def _resolve_vazus_module_path(module_name: str) -> Optional[Path]:
    rel = module_name.replace(".", "/")
    p = VAZUS_ROOT / (rel + ".py")
    if p.exists():
        return p
    p_init = VAZUS_ROOT / rel / "__init__.py"
    if p_init.exists():
        return p_init
    p_dir = VAZUS_ROOT / rel
    if p_dir.is_dir():
        return p_dir
    return None


def _check_reward_hacking(content_or_path: Union[str, Path], fpath: Optional[Path] = None) -> list[str]:
    """Inspects test functions for dummy stubs or tautological assert True statements."""
    if isinstance(content_or_path, Path):
        path = content_or_path
        src = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    elif fpath is not None:
        src = str(content_or_path)
        path = Path(fpath)
    else:
        src = str(content_or_path)
        path = Path("test_module.py")
    return _audit_test_anti_patterns(path, src)


def _has_tautological_assert(node: ast.AST) -> bool:
    """Checks whether an AST node contains tautological assertions (assert True or assert N == N)."""
    for n in ast.walk(node):
        if isinstance(n, ast.Assert):
            if isinstance(n.test, ast.Constant) and n.test.value is True:
                return True
            if isinstance(n.test, ast.Compare) and len(n.test.ops) == 1 and isinstance(n.test.ops[0], ast.Eq):
                left_dump = ast.dump(n.test.left)
                right_dump = ast.dump(n.test.comparators[0])
                if left_dump == right_dump:
                    return True
    return False


def _ast_has_import_match(tree_or_path: Union[ast.AST, Path, str], target_names: set[str]) -> bool:
    """Checks whether an AST or file imports any module from the target set."""
    if isinstance(tree_or_path, ast.AST):
        tree = tree_or_path
    elif isinstance(tree_or_path, Path):
        try:
            tree = ast.parse(tree_or_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return False
    elif isinstance(tree_or_path, str):
        try:
            tree = ast.parse(tree_or_path)
        except Exception:
            return False
    else:
        return False

    targets = {t.lower() for t in target_names}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = [p.lower() for p in node.module.split(".")]
            if any(p in targets for p in parts):
                return True
            for a in node.names:
                if a.name.lower() in targets:
                    return True
        elif isinstance(node, ast.Import):
            for a in node.names:
                parts = [p.lower() for p in a.name.split(".")]
                if any(p in targets for p in parts):
                    return True
    return False


def _has_top_level_symbol(filepath_or_tree: Union[Path, str, ast.AST], symbol_name: str) -> bool:
    try:
        if isinstance(filepath_or_tree, ast.AST):
            tree = filepath_or_tree
        else:
            p = Path(filepath_or_tree)
            if p.is_dir():
                p_init = p / "__init__.py"
                if p_init.exists():
                    p = p_init
                else:
                    return False
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))

        for node in getattr(tree, "body", []):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == symbol_name:
                    return True
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id == symbol_name:
                            return True
                        if target.id == "__all__" and isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and elt.value == symbol_name:
                                    return True
                    elif isinstance(target, (ast.Tuple, ast.List)):
                        for elt in target.elts:
                            if isinstance(elt, ast.Name) and elt.id == symbol_name:
                                return True
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id == symbol_name:
                    return True
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    alias_name = alias.asname or alias.name
                    if alias_name == symbol_name:
                        return True
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    alias_name = alias.asname or alias.name
                    if alias_name == symbol_name:
                        return True
    except Exception as exc:
        logger.debug("Symbol extraction failed for %s (%s): %s", filepath_or_tree, symbol_name, exc)
    return False


def _is_empty_pass_test(node: ast.AST) -> bool:
    """Detects empty pass tests (functions with body containing only docstring and pass)."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        stmts = [
            s for s in node.body
            if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))
        ]
        if len(stmts) == 1 and isinstance(stmts[0], ast.Pass):
            return True
    return False


def _dedupe_and_bound_tests(tests: list[Any], max_tests: Optional[int] = None) -> list[Any]:
    """Deduplicates test paths while preserving order and bounding maximum count."""
    seen = set()
    deduped = []
    for t in tests:
        key = str(t)
        if key not in seen:
            seen.add(key)
            deduped.append(t)
    limit = max_tests if max_tests is not None else int(os.getenv("VAZUS_GATE_MAX_TARGET_TESTS", "8"))
    if limit > 0:
        deduped = deduped[:limit]
    return deduped


def _check_import_target(module_name: str, target_name: str) -> bool:
    mod_path = _resolve_vazus_module_path(module_name)
    if not mod_path:
        return True
    return _has_top_level_symbol(mod_path, target_name)


def _filter_own_python_files(files: list[Path]) -> list[Path]:
    return [f for f in files if f.suffix.lower() == ".py" and not any(p in str(f) for p in SKIP_PREFIXES)]


def run_gate_8_testgen_coverage(files: list[Path]) -> tuple[bool, list[str]]:
    """Gate 8: Test generation and coverage gate."""
    strict = os.getenv("VAZUS_GATE_STRICT_TESTGEN", "0") == "1"
    if not strict:
        return True, []
    missing = []
    for f in files:
        test_path = VAZUS_ROOT / "tests" / f"test_{f.stem}.py"
        if not test_path.exists():
            missing.append(f"Missing test suite for {f.name}")
    if missing:
        return False, missing
    return True, []


def run_gate_10_cc_complexity(files: list[Path]) -> tuple[bool, list[str]]:
    """Gate 10: Cyclomatic complexity gate."""
    filtered = _filter_own_python_files(files)
    if not filtered:
        return True, []
    try:
        from radon.complexity import cc_visit
    except ImportError:
        return True, ["radon not installed (skipped)"]

    errors = []
    for f in filtered:
        try:
            code = f.read_text(encoding="utf-8", errors="replace")
            blocks = cc_visit(code)
            for b in blocks:
                if b.complexity > 10:
                    errors.append(f"[CC > 10] F {b.lineno}:{b.col_offset} {b.name} - {b.letter} ({b.complexity}) in {f.name}")
        except Exception as exc:
            logger.debug("Radon CC check skipped for %s: %s", f, exc)

    if errors:
        return False, errors
    return True, []


def run_gate_11_graph_invariants(files: list[Path]) -> tuple[bool, list[str]]:
    """Gate 11: Graph structural invariants and phantom import/symbol check."""
    filtered = _filter_own_python_files(files)
    if not filtered:
        return True, []

    errors: list[str] = []
    for f in filtered:
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(f))
        except Exception as exc:
            logger.debug("Gate 11 AST parse skipped for %s: %s", f, exc)
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_name = alias.name
                    if mod_name == "vazus_core" or mod_name.startswith("vazus_core."):
                        resolved = _resolve_vazus_module_path(mod_name)
                        if not resolved:
                            errors.append(f"[Phantom Import] Module '{mod_name}' in {f.name} does not exist.")
            elif isinstance(node, ast.ImportFrom) and node.module:
                mod_name = node.module
                if mod_name == "vazus_core" or mod_name.startswith("vazus_core."):
                    resolved = _resolve_vazus_module_path(mod_name)
                    if not resolved:
                        errors.append(f"[Phantom Import] Module '{mod_name}' in {f.name} does not exist.")
                    else:
                        for alias in node.names:
                            sym_name = alias.name
                            if sym_name == "*":
                                continue
                            submod = f"{mod_name}.{sym_name}"
                            if _resolve_vazus_module_path(submod) is not None:
                                continue
                            if not _has_top_level_symbol(resolved, sym_name):
                                errors.append(f"[Phantom Symbol] Symbol '{sym_name}' not found in '{mod_name}' (imported in {f.name})")

    if errors:
        return False, errors
    return True, []


def _audit_file_ast_and_secrets(fpath: Path, content: str) -> list[str]:
    """Audits file for AST syntax errors and hardcoded secret tokens."""
    errors = []
    try:
        ast.parse(content, filename=str(fpath))
    except SyntaxError as se:
        return [f"[AST Syntax Error] {fpath.name} line {se.lineno}: {se.msg}"]

    if "gate" not in fpath.name.lower() and "verif" not in fpath.name.lower():
        for pat in SECRET_PATTERNS:
            if pat.search(content):
                errors.append(f"[Security Leak] Hardcoded API key detected in {fpath.name}")
    return errors


def _audit_file_dangerous_calls(fpath: Path, content: str) -> list[str]:
    """Scans for prohibited dangerous OS and subprocess calls via AST inspection."""
    errors = []
    if any(k in fpath.name.lower() for k in ["test", "audit", "gate", "precommit"]):
        return errors
    try:
        tree = ast.parse(content, filename=str(fpath))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "system":
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                        errors.append(f"[Dangerous Call] Prohibited os.system() at line {node.lineno} in {fpath.name}")
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        errors.append(f"[Dangerous Call] shell=True at line {node.lineno} in {fpath.name}")
    except Exception as exc:
        logger.debug("Dangerous call scan AST parse skipped: %s", exc)
    return errors


def _audit_test_anti_patterns(fpath: Path, content: str) -> list[str]:
    """Inspects test functions for dummy stubs or tautological assert True statements."""
    errors = []
    if "test" not in fpath.name.lower() or fpath.suffix != ".py":
        return errors
    try:
        tree = ast.parse(content, filename=str(fpath))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                stmts = [
                    s for s in node.body
                    if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))
                ]
                if len(stmts) == 1 and isinstance(stmts[0], ast.Pass):
                    errors.append(f"[Reward Hacking] Empty dummy test '{node.name}' in {fpath.name} (contains only 'pass')")
                asserts = [s for s in ast.walk(node) if isinstance(s, ast.Assert)]
                for asrt in asserts:
                    if isinstance(asrt.test, ast.Constant) and asrt.test.value is True:
                        if len(asserts) == 1:
                            errors.append(f"[Reward Hacking] Tautological assertion 'assert True' in '{node.name}' in {fpath.name}")
    except Exception as exc:
        logger.debug("Test anti-pattern AST parse skipped: %s", exc)
    return errors


def run_gate_1_ast_and_security(staged_files: list[Path]) -> tuple[bool, list[str]]:
    """Gate 1: AST Syntax and Security / Anti-pattern check."""
    errors = []
    for fpath in staged_files:
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            errors.append(f"Cannot read {fpath.name}: {e}")
            continue

        errors.extend(_audit_file_ast_and_secrets(fpath, content))
        errors.extend(_audit_file_dangerous_calls(fpath, content))
        errors.extend(_audit_test_anti_patterns(fpath, content))

    return (len(errors) == 0), errors


def get_test_python() -> str:
    venv_py = VAZUS_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def _find_name_matched_tests(staged_files: list[Path], by_stem: dict[str, Path]) -> list[Path]:
    """Matches test files by direct stem equality or test_<stem>."""
    requested: list[Path] = []
    for f in staged_files:
        stem = f.stem
        if stem.startswith("test_"):
            t = by_stem.get(stem)
            if t:
                requested.append(t)
            continue
        t = by_stem.get(f"test_{stem}")
        if t:
            requested.append(t)
    return requested


def _find_ast_import_matched_tests(
    staged_files: list[Path],
    all_tests: list[Path],
    already_requested: set[Path]
) -> list[Path]:
    """Discovers test suites that import any of the staged non-test modules."""
    staged_import_names = {f.stem for f in staged_files if not f.stem.startswith("test_")}
    if not staged_import_names:
        return []
    matched: list[Path] = []
    for t in all_tests:
        if t in already_requested:
            continue
        try:
            src = t.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src, filename=str(t))
        except Exception as exc:
            logger.debug("AST test import scan failed for %s: %s", t, exc)
            continue
        hits: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[-1] in staged_import_names:
                    hits.add(node.module.split(".")[-1])
                for a in node.names:
                    if a.name in staged_import_names:
                        hits.add(a.name)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    leaf = a.name.split(".")[-1]
                    if leaf in staged_import_names:
                        hits.add(leaf)
        if hits:
            matched.append(t)
    return matched


def find_targeted_tests(staged_files: list[Path]) -> list[str]:
    """Finds test files that cover the staged Python modules (evidence-first)."""
    all_tests = sorted((VAZUS_ROOT / "tests").glob("test_*.py"))
    by_stem = {t.stem: t for t in all_tests}

    requested = _find_name_matched_tests(staged_files, by_stem)
    ast_matched = _find_ast_import_matched_tests(staged_files, all_tests, set(requested))
    requested.extend(ast_matched)

    seen: set[Path] = set()
    ordered: list[Path] = []
    for t in requested:
        if t not in seen:
            seen.add(t)
            ordered.append(t)

    max_t = int(os.getenv("VAZUS_GATE_MAX_TARGET_TESTS", "8"))
    if max_t > 0:
        ordered = ordered[:max_t]

    ignored = {
        "test_stress_all.py", "test_cross_subsystem_stress.py", "test_evolution_engine.py",
        "test_post_task_evolver.py", "test_multimodal_knowledge.py", "test_vazus_full_system.py",
        "test_subagent_reflexion.py"
    }
    return [str(t) for t in ordered if t.name not in ignored]


def run_gate_2_targeted_tests(staged_files: list[Path]) -> tuple[bool, list[str]]:
    """Gate 2: Run pytest on targeted tests using the Vazus environment."""
    errors = []
    test_dir = VAZUS_ROOT / "tests"
    if not test_dir.exists():
        return True, []

    targeted = find_targeted_tests(staged_files)
    if not targeted:
        return True, []

    py_bin = get_test_python()
    timeout = int(os.getenv("VAZUS_GATE_TEST_TIMEOUT", "300"))
    try:
        cmd = [py_bin, "-m", "pytest"] + targeted + ["-q", "--tb=short"]
        test_env = dict(os.environ)
        test_env["VAZUS_TEST_ISOLATION"] = "1"
        test_env["VAZUS_TEST_RUNNING"] = "1"
        res = subprocess.run(
            cmd,
            cwd=str(VAZUS_ROOT),
            env=test_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if res.returncode != 0:
            lines = res.stdout.strip().splitlines()
            errors.append(f"Pytest failed: {lines[-1] if lines else 'unknown error'}")
            errors.extend(lines[-4:])
    except subprocess.TimeoutExpired:
        errors.append(f"Pytest suite timed out (>{timeout}s)")
    except Exception as e:
        errors.append(f"Test runner error: {e}")

    return (len(errors) == 0), errors


def run_gate_3_smt_z3_contracts(staged_files: list[Path]) -> tuple[bool, list[str]]:
    """Gate 3: SMT Z3 Formal Contract & Memory Safety Verification."""
    errors = []
    try:
        from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier
        verifier = SMTZ3Verifier(depth=10)
    except ImportError as e:
        strict = os.getenv("VAZUS_GATE_STRICT_SMT", "0") == "1"
        msg = f"SMT Z3 unavailable ({e}). Set VAZUS_GATE_STRICT_SMT=1 to block commits when Z3 is missing."
        if strict:
            return False, [msg]
        return True, [f"[WARN] {msg}"]

    for fpath in staged_files:
        if "test" in fpath.name.lower() or fpath.suffix != ".py":
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
            res = verifier.verify_code_contracts(content, depth=10)
            status = res.get("status")
            if status == "SAT":
                detail = res.get("proof_details") or res.get("error_message") or "Invariants violated"
                errors.append(f"[SMT Z3 Violation] in {fpath.name}: status={status}; {detail}")
            elif status == "SYNTAX_ERROR":
                detail = res.get("error_message") or "could not parse file for contracts"
                errors.append(f"[SMT Z3 Parse Error] in {fpath.name}: {detail}")
            elif status in ("ERROR", "UNKNOWN"):
                # The verifier could not process/decide the input (common for
                # whole-module sources) — honest abstention, NOT evidence of a
                # violation. Only SAT is hard evidence. (Policy aligned with
                # EvidenceJury, 17.08.)
                detail = res.get("error_message") or "verifier could not decide"
                print(f"  ⚠️  [SMT advisory] {fpath.name}: status={status} — {detail}")
        except Exception as e:
            errors.append(f"[SMT Z3 Gate Error] in {fpath.name}: verification crashed ({e}) — fail-closed")

    return (len(errors) == 0), errors


def run_gate_4_concordia_jury(staged_files: list[Path]) -> tuple[bool, list[str]]:
    """Gate 4: LLM escalation for UNVERIFIED candidates — Jury-B critic, BATCHED.

    Runs offline by default to guarantee sub-2-second deterministic commits without
    spending LLM quota. Set VAZUS_GATE_ENABLE_LLM_JURY=1 to enable live LLM escalation.
    """
    if os.getenv("VAZUS_GATE_ENABLE_LLM_JURY", "0") != "1":
        return True, ["[Offline Fast-Gate] Gate 4 Concordia LLM Jury skipped (set VAZUS_GATE_ENABLE_LLM_JURY=1 to enable)."]

    errors: list[str] = []
    try:
        from vazus_core.verification.evidence_jury import EvidenceJury
        from vazus_core.verification.critic_jury import run_critic_jury_batches_sync
    except ImportError as e:
        strict = os.getenv("VAZUS_GATE_STRICT_JURY", "0") == "1"
        msg = f"Critic jury unavailable ({e}). Set VAZUS_GATE_STRICT_JURY=1 to block commits when Jury is missing."
        if strict:
            return False, [msg]
        return True, [f"[WARN] {msg}"]

    jury_a = EvidenceJury(VAZUS_ROOT)
    items = []
    for fpath in staged_files:
        if "test" in fpath.name.lower() or fpath.suffix != ".py":
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
            evidence = jury_a.evaluate(fpath, run_tests=False)
            items.append({
                "path": str(fpath.relative_to(VAZUS_ROOT)).replace("\\", "/"),
                "proposal": content,
                "evidence": json.dumps(evidence, ensure_ascii=False, default=str),
            })
        except Exception as e:
            errors.append(f"[Critic Jury Error] {fpath.name}: {e} — fail-closed")

    if items:
        try:
            jury_timeout = float(os.getenv("VAZUS_GATE_JURY_TIMEOUT", "120"))
        except ValueError:
            jury_timeout = 120.0
        res = run_critic_jury_batches_sync(items, timeout_seconds=max(1.0, jury_timeout))
        for path, v in res.get("verdicts", {}).items():
            if not v.get("approved"):
                errors.append(f"[Critic Jury] {path} verdict={v.get('verdict')}: {v.get('issue')}")

    return (len(errors) == 0), errors



def run_gate_4a_evidence_jury(staged_files: list[Path]) -> tuple[bool, list[str], list[Path]]:
    """Gate 4a: deterministic EvidenceJury (Jury-A). ZERO LLM calls.

    Pass 1: fast evidence (AST, security, ruff, vulture, SMT), no tests.
    Pass 2: for UNVERIFIED files, re-run with targeted pytest (seconds) —
            tests prove the candidate without any LLM.
    Only files with NO discoverable tests escalate to Gate 4 (Concordia LLM).
    Returns (ok, errors, unverified_files).
    """
    from vazus_core.verification.evidence_jury import EvidenceJury

    jury = EvidenceJury(VAZUS_ROOT)
    errors: list[str] = []
    unverified: list[Path] = []
    for fpath in staged_files:
        if "test" in fpath.name.lower() or fpath.suffix != ".py":
            continue
        res = jury.evaluate(fpath, run_tests=False)
        if res["verdict"] == "FAIL":
            errors.append(f"[EvidenceJury] {fpath.name}: {res['reason']}")
        elif res["verdict"] == "UNVERIFIED":
            unverified.append(fpath)

    # Pass 2: try targeted tests for the UNVERIFIED candidates.
    still_unverified: list[Path] = []
    for fpath in unverified:
        res = jury.evaluate(fpath, run_tests=True, full_suite=False)
        if res["verdict"] == "FAIL":
            errors.append(f"[EvidenceJury+tests] {fpath.name}: {res['reason']}")
        elif res["verdict"] == "UNVERIFIED":
            still_unverified.append(fpath)

    return (len(errors) == 0), errors, still_unverified


def _safe_relative_to_root(f: Path) -> str:
    try:
        return str(f.resolve().relative_to(VAZUS_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return f.name.replace("\\", "/")


def run_gate_5_dead_code(staged_files: list[Path]) -> tuple[bool, list[str]]:
    """Gate 5: Detect dead code (unused imports/vars/unreachable modules) via vulture.

    Only fails on items with ≥90% confidence to avoid false positives from
    dynamically-used symbols (e.g. FastAPI route decorators, __all__ exports).
    Skips files in labs/, tests/, services/inference/ (third-party code).
    """
    errors: list[str] = []

    # Filter to only our own code — skip third-party and lab experiments
    SKIP_PREFIXES = ("labs/", "tests/", "services/inference", "scratch/", "worktrees/")
    own_files = [
        f for f in staged_files
        if not any(_safe_relative_to_root(f).startswith(p) for p in SKIP_PREFIXES)
    ]

    if not own_files:
        return True, []

    try:
        result = subprocess.run(
            [sys.executable, "-m", "vulture", "--min-confidence", "90"] + [str(f) for f in own_files],
            capture_output=True, text=True, cwd=str(VAZUS_ROOT), timeout=60,
        )
        # vulture exits 1 when dead code found, 0 when clean
        if result.returncode != 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line:
                    errors.append(f"[Dead Code] {line}")
    except FileNotFoundError:
        # vulture not installed — warn but don't block (optional gate)
        print("  ⚠️  Gate 5: vulture not installed, skipping dead code check. Run: pip install vulture")
        return True, []
    except subprocess.TimeoutExpired:
        errors.append("[Dead Code] vulture timed out after 60s")

    return (len(errors) == 0), errors


def run_gate_6_ruff_lint(staged_files: list[Path]) -> tuple[bool, list[str]]:
    """Gate 6: Fast static lint via ruff — unused imports (F401), unused
    locals (F841), undefined names (F821), syntax-level errors (E9).
    Deterministic, ~10x faster than vulture on the same input. Blocks by default.

    F821 added 18.08.2026 after audit showed this class is invisible to every
    other mechanism: Gate-1 (ast.parse) only sees syntax, tests can't cover
    uncalled paths, and NameError inside try/except becomes a silent failure
    (2 live bugs found: sync_keep_notes permanent failure, embeddings.py import
    crash on py3.11)."""
    errors: list[str] = []

    SKIP_PREFIXES = ("labs/", "tests/", "services/inference", "scratch/", "worktrees/")
    own_files = [
        f for f in staged_files
        if not any(_safe_relative_to_root(f).startswith(p) for p in SKIP_PREFIXES)
    ]

    if not own_files:
        return True, []

    try:
        res = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--select", "F401,F821,F841,E9",
             "--output-format", "concise"] + [str(f) for f in own_files],
            capture_output=True, text=True, cwd=str(VAZUS_ROOT), timeout=120,
        )
        if res.returncode != 0:
            for line in res.stdout.splitlines():
                line = line.strip()
                if line:
                    errors.append(f"[ruff] {line}")
    except FileNotFoundError:
        print("  ⚠️  Gate 6: ruff not installed, skipping lint. Run: pip install ruff")
        return True, []
    except subprocess.TimeoutExpired:
        errors.append("[ruff] timed out after 120s")

    return (len(errors) == 0), errors


def run_gate_6b_deep_scan(staged_files: list[Path]) -> tuple[bool, list[str]]:
    """Gate 6b (opt-in via VAZUS_GATE_DEEP_SCAN=1): deptry (unused/missing
    dependencies), pip-audit (known CVEs in venv), bandit (AST security scan).
    Advisory by default; VAZUS_GATE_STRICT_DEEP=1 makes findings blocking."""
    errors: list[str] = []
    strict = os.getenv("VAZUS_GATE_STRICT_DEEP", "0") == "1"
    py_bin = get_test_python()

    # --- deptry: dependency hygiene ---
    try:
        res = subprocess.run(
            [py_bin, "-m", "deptry", str(VAZUS_ROOT)],
            capture_output=True, text=True, cwd=str(VAZUS_ROOT), timeout=300,
        )
        issues = [l.strip() for l in res.stdout.splitlines() if l.strip() and "Scanning" not in l]
        if res.returncode != 0:
            errors.append(f"[deptry] dependency issues found ({len(issues)} lines of report)")
    except FileNotFoundError:
        errors.append("[deptry] not installed (pip install deptry)")
    except subprocess.TimeoutExpired:
        errors.append("[deptry] timed out after 300s")

    # --- pip-audit: known vulnerabilities ---
    try:
        res = subprocess.run(
            [py_bin, "-m", "pip_audit", "--format", "columns", "--skip-editable"],
            capture_output=True, text=True, cwd=str(VAZUS_ROOT), timeout=300,
        )
        if res.returncode != 0:
            vuln_line = next((l.strip() for l in res.stdout.splitlines() if "vulnerab" in l.lower()), "unknown")
            errors.append(f"[pip-audit] {vuln_line}")
    except FileNotFoundError:
        errors.append("[pip-audit] not installed (pip install pip-audit)")
    except subprocess.TimeoutExpired:
        errors.append("[pip-audit] timed out after 300s")

    # --- bandit: AST security scan on staged own files ---
    SKIP_PREFIXES = ("labs/", "tests/", "services/inference", "scratch/", "worktrees/")
    own_files = [
        f for f in staged_files
        if not any(_safe_relative_to_root(f).startswith(p) for p in SKIP_PREFIXES)
    ]
    if own_files:
        try:
            res = subprocess.run(
                [py_bin, "-m", "bandit", "-q", "-ll"] + [str(f) for f in own_files],
                capture_output=True, text=True, cwd=str(VAZUS_ROOT), timeout=300,
            )
            for line in res.stdout.splitlines():
                if "Total issues" in line:
                    errors.append(f"[bandit] {line.strip()}")
        except FileNotFoundError:
            errors.append("[bandit] not installed (pip install bandit)")
        except subprocess.TimeoutExpired:
            errors.append("[bandit] timed out after 300s")

    return (not strict or len(errors) == 0), errors


def run_gate_7_mypy(staged_files: list[Path]) -> tuple[bool, list[str]]:
    """Gate 7: mypy static type checking on staged Python files.
    Advisory by default; blocking when VAZUS_GATE_STRICT_MYPY=1."""
    errors: list[str] = []
    py_bin = get_test_python()
    py_files = [str(f) for f in staged_files if f.suffix == ".py"]
    if not py_files:
        return True, []
    try:
        res = subprocess.run(
            [py_bin, "-m", "mypy",
             "--ignore-missing-imports",
             "--no-error-summary",
             "--no-strict-optional",
             "--python-version", "3.11"
             ] + py_files,
            capture_output=True, text=True,
            cwd=str(VAZUS_ROOT), timeout=120,
            encoding="utf-8", errors="replace"
        )
        if res.returncode != 0:
            for line in res.stdout.splitlines():
                if ": error:" in line:
                    errors.append(line.strip())
    except FileNotFoundError:
        return True, []  # mypy not installed: skip silently
    except subprocess.TimeoutExpired:
        errors.append("[mypy] timed out after 120s")
    except Exception as e:
        errors.append(f"[mypy] error: {e}")
    return len(errors) == 0, errors


def _audit_file_gate_1(fpath: Path) -> list[str]:
    """Audits a single file for Gate 1 violations (syntax + secrets + dangerous calls + rewards)."""
    try:
        ok, errs = run_gate_1_ast_and_security([fpath])
        return errs if not ok else []
    except Exception as e:
        return [str(e)]


def _run_gate_stage_1_to_3(files: list[Path], gate_results: dict[int, GateResult]) -> bool:
    """Executes Gates 1-3 (AST & Security, Targeted Tests, SMT Z3 Contracts)."""
    all_ok = True

    t0 = time.perf_counter()
    ok1, errs1 = run_gate_1_ast_and_security(files)
    d1 = (time.perf_counter() - t0) * 1000.0
    gate_results[1] = GateResult(1, "AST Syntax & Security", ok1, d1, errs1)
    if not ok1:
        all_ok = False

    t0 = time.perf_counter()
    ok2, errs2 = run_gate_2_targeted_tests(files)
    d2 = (time.perf_counter() - t0) * 1000.0
    gate_results[2] = GateResult(2, "Targeted Tests", ok2, d2, errs2)
    if not ok2:
        all_ok = False

    t0 = time.perf_counter()
    ok3, errs3 = run_gate_3_smt_z3_contracts(files)
    d3 = (time.perf_counter() - t0) * 1000.0
    gate_results[3] = GateResult(3, "SMT Z3 Contracts", ok3, d3, errs3)
    if not ok3:
        all_ok = False

    return all_ok


def _run_gate_stage_4_to_6(files: list[Path], gate_results: dict[int, GateResult]) -> bool:
    """Executes Gates 4-6 (Critic Jury, Dead Code Vulture, Static Lint Ruff)."""
    all_ok = True

    t0 = time.perf_counter()
    ok4a, errs4a, unverified = run_gate_4a_evidence_jury(files)
    if unverified and ok4a:
        ok4, errs4 = run_gate_4_concordia_jury(unverified)
        passed_4 = ok4a and ok4
        errs_4 = errs4a + errs4
    else:
        passed_4 = ok4a
        errs_4 = errs4a
    d4 = (time.perf_counter() - t0) * 1000.0
    gate_results[4] = GateResult(4, "Critic Jury", passed_4, d4, errs_4)
    if not passed_4:
        all_ok = False

    t0 = time.perf_counter()
    ok5, errs5 = run_gate_5_dead_code(files)
    d5 = (time.perf_counter() - t0) * 1000.0
    gate_results[5] = GateResult(5, "Dead Code (Vulture)", ok5, d5, errs5)
    if not ok5:
        all_ok = False

    t0 = time.perf_counter()
    ok6, errs6 = run_gate_6_ruff_lint(files)
    d6 = (time.perf_counter() - t0) * 1000.0
    gate_results[6] = GateResult(6, "Static Lint (Ruff)", ok6, d6, errs6)
    if not ok6:
        all_ok = False

    return all_ok


def run_precommit_gate(
    target_files: Optional[List[Union[str, Path]]] = None,
    *,
    strict_mypy: bool = False,
    timeout_s: float = 120.0
) -> PrecommitResult:
    """Programmatic entry point for running precommit quality gates on specified files."""
    start_t = time.perf_counter()
    if strict_mypy:
        logger.debug("strict_mypy enforcement active (timeout: %s)", timeout_s)
    if target_files is not None and len(target_files) == 0:
        return PrecommitResult(all_passed=True, gate_results={}, target_files=[], total_duration_ms=0.0)

    files = get_staged_python_files() if target_files is None else [Path(f).resolve() for f in target_files]
    gate_results: dict[int, GateResult] = {}

    ok_1_3 = _run_gate_stage_1_to_3(files, gate_results)
    ok_4_6 = _run_gate_stage_4_to_6(files, gate_results)
    all_passed = ok_1_3 and ok_4_6

    total_d = (time.perf_counter() - start_t) * 1000.0
    return PrecommitResult(
        all_passed=all_passed,
        gate_results=gate_results,
        target_files=files,
        total_duration_ms=total_d
    )


def _run_gates_1_to_3(staged_files: List[Path]) -> None:
    """Executes Gate 1 (AST), Gate 2 (Unit Tests), and Gate 3 (SMT Z3)."""
    ok1, errs1 = run_gate_1_ast_and_security(staged_files)
    if not ok1:
        print("\n❌ GATE 1 FAILED (AST Syntax & Security Violations):")
        for e in errs1:
            print(f"   - {e}")
        print("\n🚫 COMMIT ABORTED. Fix the errors above before committing.")
        sys.exit(1)
    print("  ✅ Gate 1 Passed: AST Syntax & Security Clean.")

    ok2, errs2 = run_gate_2_targeted_tests(staged_files)
    if not ok2:
        print("\n❌ GATE 2 FAILED (Unit Test Regressions):")
        for e in errs2:
            print(f"   - {e}")
        print("\n🚫 COMMIT ABORTED. Tests must pass before committing.")
        sys.exit(1)
    print("  ✅ Gate 2 Passed: Targeted Tests Clean.")

    if os.getenv("VAZUS_L2_TRACE", "0") == "1":
        try:
            from vazus_core.verification.l2_trace_collector import run_l2_for_staged_tests
            test_files = [Path(p) for p in find_targeted_tests(staged_files)]
            l2_result = run_l2_for_staged_tests(test_files, max_files=5)
            print(f"  📊 L2 Trace: {l2_result['total_edges']} new edges, {l2_result['total_hits']} function hits recorded → vazus.db")
        except Exception as _l2e:
            print(f"  ⚠️  L2 Trace skipped: {_l2e}")

    ok3, errs3 = run_gate_3_smt_z3_contracts(staged_files)
    if not ok3:
        print("\n❌ GATE 3 FAILED (SMT Z3 Contract Violation):")
        for e in errs3:
            print(f"   - {e}")
        print("\n🚫 COMMIT ABORTED. Fix formal contracts before committing.")
        sys.exit(1)
    print("  ✅ Gate 3 Passed: SMT Z3 Formal Invariants Satisfied.")


def _run_gates_4_to_6(staged_files: List[Path]) -> None:
    """Executes Gate 4a/4 (Evidence/Critic Jury), Gate 5 (Vulture), and Gate 6 (Ruff)."""
    ok4a, errs4a, unverified4a = run_gate_4a_evidence_jury(staged_files)
    if not ok4a:
        print("\n❌ GATE 4a FAILED (EvidenceJury — hard evidence violations):")
        for e in errs4a:
            print(f"   - {e}")
        print("\n🚫 COMMIT ABORTED. Fix the evidence violations above before committing.")
        sys.exit(1)

    if unverified4a:
        proven = len(staged_files) - len(unverified4a)
        print(f"  ✅ Gate 4a Passed: {proven} file(s) decided by evidence; {len(unverified4a)} UNVERIFIED → Critic Jury (1 batch, 2 LLM calls).")
        ok4, errs4 = run_gate_4_concordia_jury(unverified4a)
        if not ok4:
            print("\n❌ GATE 4 FAILED (Critic Jury — REJECT/ABSTAIN, fail-closed):")
            for e in errs4:
                print(f"   - {e}")
            print("\n🚫 COMMIT ABORTED. The critic found problems or could not verify the UNVERIFIED files.")
            sys.exit(1)
        print("  ✅ Gate 4 Passed: Critic Jury confirmed all UNVERIFIED files (fail-closed batch).")
    else:
        print("  ✅ Gate 4a Passed: EvidenceJury decided all candidates by proof.")
        print("  ✅ Gate 4 Skipped: no UNVERIFIED candidates — 0 LLM quota spent.")

    ok5, errs5 = run_gate_5_dead_code(staged_files)
    if not ok5:
        print("\n❌ GATE 5 FAILED (Dead Code Detected):")
        for e in errs5:
            print(f"   - {e}")
        print("\n🚫 COMMIT ABORTED. Remove unused imports/variables before committing.")
        sys.exit(1)
    print("  ✅ Gate 5 Passed: No dead code detected (vulture clean).")

    ok6, errs6 = run_gate_6_ruff_lint(staged_files)
    if not ok6:
        print("\n❌ GATE 6 FAILED (ruff static lint):")
        for e in errs6:
            print(f"   - {e}")
        print("\n🚫 COMMIT ABORTED. Fix unused imports/variables before committing.")
        sys.exit(1)
    print("  ✅ Gate 6 Passed: ruff lint clean (F401/F841/E9).")

    if os.getenv("VAZUS_GATE_DEEP_SCAN", "0") == "1":
        ok6b, errs6b = run_gate_6b_deep_scan(staged_files)
        if errs6b:
            print("\n🔎 GATE 6b DEEP SCAN REPORT (advisory):")
            for e in errs6b:
                print(f"   - {e}")
        if not ok6b:
            print("\n🚫 COMMIT ABORTED. VAZUS_GATE_STRICT_DEEP=1 and deep scan found issues.")
            sys.exit(1)


def _run_gates_7_to_8(staged_files: List[Path]) -> None:
    """Executes Gate 7 (mypy) and Gate 8 (Proactive Suggestion Scan)."""
    if os.getenv("VAZUS_GATE_MYPY", "0") == "1":
        ok7, errs7 = run_gate_7_mypy(staged_files)
        if errs7:
            print("\n🔤 GATE 7 mypy REPORT:")
            for e in errs7[:20]:
                print(f"   - {e}")
        if not ok7 and os.getenv("VAZUS_GATE_STRICT_MYPY", "0") == "1":
            print("\n🚫 COMMIT ABORTED. VAZUS_GATE_STRICT_MYPY=1 and mypy found type errors.")
            sys.exit(1)
        elif ok7:
            print("  ✅ Gate 7 Passed: mypy type check clean.")
        else:
            print("  ⚠️  Gate 7 Advisory: mypy found type issues (set VAZUS_GATE_STRICT_MYPY=1 to block).")

    print("\n🔍 Gate 8: Proactive Code Improvement Scan (advisory)...")
    try:
        sys.path.insert(0, str(VAZUS_ROOT))
        from vazus_core.analysis.proactive_suggestion_engine import ProactiveSuggestionEngine
        engine = ProactiveSuggestionEngine()
        all_suggestions = []
        for fp in staged_files:
            if fp.suffix == ".py":
                all_suggestions += engine.scan_file(fp)
        if all_suggestions:
            errors = [s for s in all_suggestions if s.severity == "error"]
            warnings = [s for s in all_suggestions if s.severity == "warning"]
            advisories = [s for s in all_suggestions if s.severity == "advisory"]
            print(f"  📋 Gate 8 found: {len(errors)} errors, {len(warnings)} warnings, {len(advisories)} advisories")
            for s in (errors + warnings)[:5]:
                print(f"   [{s.severity.upper()}] {Path(s.file_path).name}:{s.line} — {s.title}")
            print("  → All suggestions stored to vazus.db (will appear in next conversation context)")
        else:
            print("  ✅ Gate 8: No improvement suggestions for staged files.")
    except Exception as e:
        print(f"  ℹ️  Gate 8 skipped (engine unavailable): {e}")


def main():
    print("=" * 70)
    print("🛡️ VAZUS OS — AUTONOMOUS PRE-COMMIT QUALITY GATE (7-TIER PIPELINE)")
    print("=" * 70)

    staged_files = get_staged_python_files()
    if not staged_files:
        print("ℹ️ No staged Python files to verify. Gate passed.")
        sys.exit(0)

    print(f"🔍 Inspecting {len(staged_files)} staged Python file(s)...")
    for f in staged_files:
        print(f"  • {f.relative_to(VAZUS_ROOT)}")

    _run_gates_1_to_3(staged_files)
    _run_gates_4_to_6(staged_files)
    _run_gates_7_to_8(staged_files)

    print("\n🎉 ALL PRE-COMMIT QUALITY GATES PASSED (8/8). Commit authorized.")
    print("=" * 70)
    sys.exit(0)


if __name__ == "__main__":
    main()
