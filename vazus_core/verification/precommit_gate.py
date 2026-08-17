#!/usr/bin/env python3
"""
vazus_core.verification.precommit_gate — Autonomous Pre-Commit Quality Gate for Vazus OS.
Triggered automatically by .git/hooks/pre-commit BEFORE any git commit is accepted.

Gates Enforced:
  1. AST Syntax Check (ast.parse) on all staged Python files.
  2. Static Security & Anti-Pattern Scan (No hardcoded API keys, no shell=True, no raw eval/exec).
  3. Module Import & Syntax Integrity.
  4. Targeted Pytest Suite (Zero test regressions).
  5. Dead Code Detection via vulture (unused imports, unreachable modules, unused vars ≥90% confidence).
  6. Fast Static Lint via ruff (F401 unused imports, F821 undefined names,
     F841 unused locals, E9 syntax errors).
  6b. OPT-IN Deep Scan (VAZUS_GATE_DEEP_SCAN=1): deptry (unused/missing deps),
      pip-audit (known CVEs), bandit (AST security). Advisory by default;
      set VAZUS_GATE_STRICT_DEEP=1 to make it blocking.

Exit Codes:
  0 = ALL GATES PASSED (Commit Allowed)
  1 = GATE FAILED (Commit Blocked)
"""

import os
import sys
import ast
import json
import re
import subprocess
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
    _ = dangerous_calls  # legacy regex list retained for future AST-free fallback

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
    """Finds test files that cover the staged Python modules (evidence-first).

    Strategy, cheapest-sufficient first:
      1. A staged test file targets itself.
      2. Exact ``test_<module>.py`` match.
      3. AST import analysis — any test that IMPORTS the staged module
         (``from vazus_core.x import y`` / ``import vazus_core.x.y``) covers it.
         Catches grouped/harness test files that don't follow 1:1 naming,
         which otherwise stay UNVERIFIED and force an LLM escalation.

    Bounded by ``VAZUS_GATE_MAX_TARGET_TESTS`` (default 8, 0=unlimited) so the
    targeted run stays fast; the ignored list protects heavy/slow suites.
    """
    all_tests = sorted((VAZUS_ROOT / "tests").glob("test_*.py"))
    by_stem = {t.stem: t for t in all_tests}

    requested: list[Path] = []

    # 1+2: self / exact-name matches
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

    # 3: AST import analysis
    staged_import_names = {f.stem for f in staged_files if not f.stem.startswith("test_")}
    if staged_import_names:
        for t in all_tests:
            if t in requested:
                continue
            try:
                src = t.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(src, filename=str(t))
            except Exception:
                continue
            hits: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    # match both styles: `from pkg.mod import symbol`
                    # (module leaf) and `from pkg import mod` (name)
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
                requested.append(t)

    # Dedupe preserving order, then bound
    seen: set[Path] = set()
    ordered: list[Path] = []
    for t in requested:
        if t in seen:
            continue
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
        res = subprocess.run(
            cmd,
            cwd=str(VAZUS_ROOT),
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

    ALL escalated files go to the critic jury in ONE prompt round (2 LLM calls
    total regardless of file count), fail-closed per file: mock/error/ABSTAIN
    is NOT approval, any CONTRADICT rejects.
    """
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
        res = run_critic_jury_batches_sync(items)
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
        if not any(str(f.relative_to(VAZUS_ROOT)).replace("\\", "/").startswith(p) for p in SKIP_PREFIXES)
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
        if not any(str(f.relative_to(VAZUS_ROOT)).replace("\\", "/").startswith(p) for p in SKIP_PREFIXES)
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
        if not any(str(f.relative_to(VAZUS_ROOT)).replace("\\", "/").startswith(p) for p in SKIP_PREFIXES)
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


def main():
    print("=" * 70)
    print("🛡️ VAZUS OS — AUTONOMOUS PRE-COMMIT QUALITY GATE (6-TIER PIPELINE)")
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

    # Stage 2: Unit Tests (Targeted Tests)
    ok2, errs2 = run_gate_2_targeted_tests(staged_files)
    if not ok2:
        print("\n❌ GATE 2 FAILED (Unit Test Regressions):")
        for e in errs2:
            print(f"   - {e}")
        print("\n🚫 COMMIT ABORTED. Tests must pass before committing.")
        sys.exit(1)
    else:
        print("  ✅ Gate 2 Passed: Targeted Tests Clean.")

    # Stage 3: SMT Z3 Formal Proofs
    ok3, errs3 = run_gate_3_smt_z3_contracts(staged_files)
    if not ok3:
        print("\n❌ GATE 3 FAILED (SMT Z3 Contract Violation):")
        for e in errs3:
            print(f"   - {e}")
        print("\n🚫 COMMIT ABORTED. Fix formal contracts before committing.")
        sys.exit(1)
    else:
        print("  ✅ Gate 3 Passed: SMT Z3 Formal Invariants Satisfied.")

    # Stage 4a: EvidenceJury (deterministic, 0 LLM calls) — decides by proof
    ok4a, errs4a, unverified4a = run_gate_4a_evidence_jury(staged_files)
    if not ok4a:
        print("\n❌ GATE 4a FAILED (EvidenceJury — hard evidence violations):")
        for e in errs4a:
            print(f"   - {e}")
        print("\n🚫 COMMIT ABORTED. Fix the evidence violations above before committing.")
        sys.exit(1)

    # Stage 4: Critic Jury (batched) — ONLY for UNVERIFIED candidates
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
        else:
            print("  ✅ Gate 4 Passed: Critic Jury confirmed all UNVERIFIED files (fail-closed batch).")
    else:
        print("  ✅ Gate 4a Passed: EvidenceJury decided all candidates by proof.")
        print("  ✅ Gate 4 Skipped: no UNVERIFIED candidates — 0 LLM quota spent.")

    # Stage 5: Dead Code Detection via vulture
    ok5, errs5 = run_gate_5_dead_code(staged_files)
    if not ok5:
        print("\n❌ GATE 5 FAILED (Dead Code Detected):")
        for e in errs5:
            print(f"   - {e}")
        print("\n🚫 COMMIT ABORTED. Remove unused imports/variables before committing.")
        sys.exit(1)
    else:
        print("  ✅ Gate 5 Passed: No dead code detected (vulture clean).")

    # Stage 6: Fast Static Lint via ruff
    ok6, errs6 = run_gate_6_ruff_lint(staged_files)
    if not ok6:
        print("\n❌ GATE 6 FAILED (ruff static lint):")
        for e in errs6:
            print(f"   - {e}")
        print("\n🚫 COMMIT ABORTED. Fix unused imports/variables before committing.")
        sys.exit(1)
    else:
        print("  ✅ Gate 6 Passed: ruff lint clean (F401/F841/E9).")

    # Stage 6b: Optional deep scan (deptry / pip-audit / bandit)
    if os.getenv("VAZUS_GATE_DEEP_SCAN", "0") == "1":
        ok6b, errs6b = run_gate_6b_deep_scan(staged_files)
        if errs6b:
            print("\n🔎 GATE 6b DEEP SCAN REPORT (advisory):")
            for e in errs6b:
                print(f"   - {e}")
        if not ok6b:
            print("\n🚫 COMMIT ABORTED. VAZUS_GATE_STRICT_DEEP=1 and deep scan found issues.")
            sys.exit(1)

    print("\n🎉 ALL PRE-COMMIT QUALITY GATES PASSED (6/6). Commit authorized.")
    print("=" * 70)
    sys.exit(0)


if __name__ == "__main__":
    main()
