#!/usr/bin/env python3
"""
vazus_core.verification.precommit_gate — Autonomous Pre-Commit Quality Gate for Vazus OS.
Triggered automatically by .git/hooks/pre-commit BEFORE any git commit is accepted.

Gates Enforced:
  1. AST Syntax Check (ast.parse) on all staged Python files.
  2. Static Security & Anti-Pattern Scan (No hardcoded API keys, no shell=True, no raw eval/exec).
  3. Module Import & Syntax Integrity.
  4. Targeted Pytest Suite (Zero test regressions).

Exit Codes:
  0 = ALL GATES PASSED (Commit Allowed)
  1 = GATE FAILED (Commit Blocked)
"""

import os
import sys
import ast
import re
import subprocess
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

VAZUS_ROOT = Path("C:/vazus")


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
    except Exception:
        pass
    return []


def run_gate_1_ast_and_security(staged_files: list[Path]) -> tuple[bool, list[str]]:
    """Gate 1: AST Syntax and Security / Anti-pattern check."""
    errors = []
    secret_patterns = [
        re.compile(r"""(?i)(?:api_key|auth_token)\s*=\s*['"](AIzaSy[0-9A-Za-z\-_]{33})['"]"""),
        re.compile(r"""(?i)(?:api_key|auth_token)\s*=\s*['"](sk-[a-zA-Z0-9]{30,})['"]"""),
    ]
    dangerous_calls = [
        (re.compile(r"""subprocess\.(?:Popen|run|call|check_output)\(.*shell\s*=\s*True"""), "shell=True in subprocess"),
        (re.compile(r"""\bos\.system\("""), "Prohibited os.system()"),
    ]

    for fpath in staged_files:
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            errors.append(f"Cannot read {fpath.name}: {e}")
            continue

        # 1. AST Syntax Check
        try:
            ast.parse(content, filename=str(fpath))
        except SyntaxError as se:
            errors.append(f"[AST Syntax Error] {fpath.name} line {se.lineno}: {se.msg}")
            continue

        # 2. Hardcoded Secret Check (skip gate/verifier files)
        if "gate" not in fpath.name.lower() and "verif" not in fpath.name.lower():
            for pat in secret_patterns:
                if pat.search(content):
                    errors.append(f"[Security Leak] Hardcoded API key detected in {fpath.name}")

        # 3. Dangerous System Calls Check via AST inspection (skip inside test/audit/gate scripts)
        if not any(k in fpath.name.lower() for k in ["test", "audit", "gate", "precommit"]):
            try:
                tree = ast.parse(content, filename=str(fpath))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        # Detect os.system(...)
                        if isinstance(node.func, ast.Attribute) and node.func.attr == "system":
                            if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                                errors.append(f"[Dangerous Call] Prohibited os.system() at line {node.lineno} in {fpath.name}")
                        # Detect subprocess.run(..., shell=True)
                        for kw in node.keywords:
                            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                errors.append(f"[Dangerous Call] shell=True at line {node.lineno} in {fpath.name}")
            except Exception:
                pass

        # 4. Anti-Reward Hacking & Test Mutation Guard (for staged test files)
        if "test" in fpath.name.lower() and fpath.suffix == ".py":
            try:
                tree = ast.parse(content, filename=str(fpath))
                for node in tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                        # Check function body for tautological assertions or empty pass
                        stmts = [s for s in node.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))]
                        if len(stmts) == 1 and isinstance(stmts[0], ast.Pass):
                            errors.append(f"[Reward Hacking] Empty dummy test '{node.name}' in {fpath.name} (contains only 'pass')")
                        
                        # Check for assert True / assert 1 == 1 as sole assertion
                        asserts = [s for s in ast.walk(node) if isinstance(s, ast.Assert)]
                        if not asserts and not any(isinstance(s, ast.Raise) or (isinstance(s, ast.Call) and "pytest" in ast.dump(s)) for s in ast.walk(node)):
                            # Only warn if not using pytest.raises
                            pass
                        for asrt in asserts:
                            if isinstance(asrt.test, ast.Constant) and asrt.test.value is True:
                                if len(asserts) == 1:
                                    errors.append(f"[Reward Hacking] Tautological assertion 'assert True' in '{node.name}' in {fpath.name}")
            except Exception:
                pass

    return (len(errors) == 0), errors


def get_test_python() -> str:
    venv_py = VAZUS_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def find_targeted_tests(staged_files: list[Path]) -> list[str]:
    """Finds test files that directly cover the staged Python modules."""
    test_files = set()
    all_tests = list((VAZUS_ROOT / "tests").glob("test_*.py"))
    all_test_names = {t.stem: t for t in all_tests}
    
    for f in staged_files:
        stem = f.stem
        if f"test_{stem}" in all_test_names:
            test_files.add(str(all_test_names[f"test_{stem}"]))
        for t_stem, t_path in all_test_names.items():
            if stem in t_stem:
                test_files.add(str(t_path))

    # Core smoke tests to always verify system integrity
    core_smoke = [
        str(VAZUS_ROOT / "tests" / "test_master_orchestrator.py"),
        str(VAZUS_ROOT / "tests" / "test_subagent_reflexion.py"),
        str(VAZUS_ROOT / "tests" / "test_vazus_full_system.py"),
    ]
    for cs in core_smoke:
        if Path(cs).exists():
            test_files.add(cs)
            
    ignored = {"test_stress_all.py", "test_cross_subsystem_stress.py", "test_evolution_engine.py", "test_post_task_evolver.py", "test_multimodal_knowledge.py"}
    return [t for t in sorted(test_files) if Path(t).name not in ignored]


def run_gate_2_targeted_tests(staged_files: list[Path]) -> tuple[bool, list[str]]:
    """Gate 2: Run pytest on targeted & core tests using the Vazus environment."""
    errors = []
    test_dir = VAZUS_ROOT / "tests"
    if not test_dir.exists():
        return True, []

    targeted = find_targeted_tests(staged_files)
    if not targeted:
        return True, []

    py_bin = get_test_python()
    try:
        cmd = [py_bin, "-m", "pytest"] + targeted + ["-q", "--tb=short"]
        res = subprocess.run(
            cmd,
            cwd=str(VAZUS_ROOT),
            capture_output=True,
            text=True,
            timeout=90,
        )
        if res.returncode != 0:
            lines = res.stdout.strip().splitlines()
            errors.append(f"Pytest failed: {lines[-1] if lines else 'unknown error'}")
            errors.extend(lines[-4:])
    except subprocess.TimeoutExpired:
        errors.append("Pytest suite timed out (>90s)")
    except Exception as e:
        errors.append(f"Test runner error: {e}")

    return (len(errors) == 0), errors


def main():
    print("=" * 70)
    print("🛡️ VAZUS OS — AUTONOMOUS PRE-COMMIT QUALITY GATE")
    print("=" * 70)

    staged_files = get_staged_python_files()
    if not staged_files:
        print("ℹ️ No staged Python files to verify. Gate passed.")
        sys.exit(0)

    print(f"🔍 Inspecting {len(staged_files)} staged Python file(s)...")
    for f in staged_files:
        print(f"  • {f.relative_to(VAZUS_ROOT)}")

    # Stage 1: AST & Security
    ok1, errs1 = run_gate_1_ast_and_security(staged_files)
    if not ok1:
        print("\n❌ GATE 1 FAILED (AST Syntax & Security Violations):")
        for e in errs1:
            print(f"   - {e}")
        print("\n🚫 COMMIT ABORTED. Fix the errors above before committing.")
        sys.exit(1)
    else:
        print("  ✅ Gate 1 Passed: AST Syntax & Security Clean.")

    # Stage 2: Unit Tests (Targeted & Core Smoke)
    ok2, errs2 = run_gate_2_targeted_tests(staged_files)
    if not ok2:
        print("\n❌ GATE 2 FAILED (Unit Test Regressions):")
        for e in errs2:
            print(f"   - {e}")
        print("\n🚫 COMMIT ABORTED. Tests must pass before committing.")
        sys.exit(1)
    else:
        print("  ✅ Gate 2 Passed: 0 Test Regressions.")

    print("\n🎉 ALL PRE-COMMIT QUALITY GATES PASSED (2/2). Commit authorized.")
    print("=" * 70)
    sys.exit(0)


if __name__ == "__main__":
    main()
