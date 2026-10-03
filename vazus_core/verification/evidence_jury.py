"""Jury-A: deterministic evidence-based code verification. ZERO LLM calls.

Design (AG2 discussion 15.08, "2 jury" proposal):
  Verdicts come from proof, not votes:
    FAIL       — hard evidence of breakage (syntax, secrets, shell=True,
                 os.system, ruff E9/F errors, vulture "unused import",
                 SMT contract violation, pytest red)
    PASS       — all applicable checks ran AND are clean; targeted tests
                 must exist and pass (otherwise the candidate is UNVERIFIED)
    UNVERIFIED — not enough evidence to decide (no discoverable tests, no
                 contracts). Callers escalate to Jury-B (LLM critic) or a human.

Usage:
    jury = EvidenceJury()
    res = jury.evaluate("vazus_core/engine/llm_client.py")
    print(res["verdict"])  # PASS | FAIL | UNVERIFIED
"""

from __future__ import annotations

import ast
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("vazus_core.verification.evidence_jury")

VAZUS_ROOT = Path("C:/vazus")
VENV_DIR = VAZUS_ROOT / ".venv" / "Scripts"

SECRET_PATTERNS = [
    re.compile(r"""(?i)(?:api_key|auth_token|apikey)\s*=\s*['"](AIzaSy[0-9A-Za-z\-_]{33})['"]"""),
    re.compile(r"""(?i)(?:api_key|auth_token|apikey)\s*=\s*['"](sk-[a-zA-Z0-9]{30,})['"]"""),
]
DANGEROUS_PATTERNS = [
    (
        re.compile(r"""subprocess\.(?:Popen|run|call|check_output)\(.*shell\s*=\s*True""", re.S),
        "shell=True in subprocess",
    ),
    (re.compile(r"""\bos\.system\("""), "Prohibited os.system()"),
    (re.compile(r"""\b(?:eval|exec)\("""), "Prohibited eval()/exec()"),
]

PYTEST_COUNTS_RE = re.compile(r"(\d+)\s+passed|(\d+)\s+failed|(\d+)\s+error")
VULTURE_UNUSED_IMPORT_RE = re.compile(r"unused import", re.I)


def _find_tests_root(file_path: Path) -> Path | None:
    """Walks up from the file to the repo root and returns its tests/ dir."""
    p = file_path.resolve().parent
    while p != p.parent:
        if (p / "tests").is_dir():
            return p / "tests"
        if (p / ".git").exists():
            return p / "tests"
        p = p.parent
    return None


def _scan_test_imports(tests_root: Path, module_stem: str) -> list[Path]:
    """AST-scans all test_*.py files for imports of module_stem.

    Returns files that import or from-import the target stem, enabling
    EvidenceJury to find tests regardless of their filename.
    """
    matches: list[Path] = []
    for test_file in tests_root.rglob("test_*.py"):
        try:
            src = test_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src)
        except Exception as exc:
            logger.debug("Failed to parse test AST in %s: %s", test_file, exc)
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if module_stem in alias.name:
                        matches.append(test_file)
                        break
            elif isinstance(node, ast.ImportFrom):
                if node.module and module_stem in node.module:
                    matches.append(test_file)
                    break
    return matches


def _find_targeted_test_file(file_path: Path) -> Path | None:
    """Locates the most likely test file for a source file (tests/ tree).

    Strategy (in priority order):
    1. Exact name match: tests/test_<stem>.py
    2. Glob name match: tests/**/*<stem>*.py
    3. AST import scan: any test_*.py that imports the module by stem

    Never returns the evaluated file itself — a test file evaluating itself
    would spawn pytest on itself recursively.
    """
    tests_root = _find_tests_root(file_path)
    if tests_root is None:
        return None
    self_resolved = file_path.resolve()

    # Priority 1: exact name match
    candidates = [
        tests_root / f"test_{file_path.stem}.py",
        tests_root / f"test_{file_path.name}",
    ]
    for c in candidates:
        if c.exists() and c.resolve() != self_resolved:
            return c

    # Priority 2: glob name match
    matches = [p for p in tests_root.rglob(f"*{file_path.stem}*.py") if p.resolve() != self_resolved]
    if matches:
        return sorted(matches, key=lambda p: len(str(p)))[0]

    # Priority 3: AST import scan (catches test_sota_suite.py → voice_thought_engine)
    import_matches = _scan_test_imports(tests_root, file_path.stem)
    if import_matches:
        return sorted(import_matches, key=lambda p: len(str(p)))[0]

    return None


class EvidenceJury:
    """Deterministic evidence-based verdict engine (Jury-A). No network, no LLM."""

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else VAZUS_ROOT

    @staticmethod
    def _read_source(fp: Path, code_content: str | None) -> Tuple[Optional[str], Optional[str]]:
        if code_content is not None:
            return code_content, None
        try:
            return fp.read_text(encoding="utf-8", errors="replace"), None
        except OSError as e:
            return None, f"ERROR: {e}"

    @staticmethod
    def _check_ast_syntax(src: str, fp: Path) -> Tuple[bool, str]:
        try:
            ast.parse(src, filename=str(fp))
            return True, "OK"
        except SyntaxError as se:
            return False, f"SyntaxError line {se.lineno}: {se.msg}"

    def _check_security_and_scanners(self, src: str, fp: Path, evidence: dict) -> Optional[dict]:
        skip_security = any(k in fp.name.lower() for k in ("gate", "verif", "jury", "evidence", "guardrail"))
        if skip_security:
            evidence["checks"]["security"] = "SKIPPED (verification module)"
            return None

        sec_issues = self._security_scan(src)
        evidence["checks"]["security"] = sec_issues if sec_issues else "OK"
        if sec_issues:
            return self._verdict(evidence, "FAIL", "; ".join(sec_issues))

        semgrep_issues = self._run_semgrep(fp)
        evidence["checks"]["semgrep"] = semgrep_issues if semgrep_issues else "OK"
        if semgrep_issues:
            return self._verdict(evidence, "FAIL", "; ".join(semgrep_issues[:3]))

        ast_grep_issues = self._run_ast_grep(fp)
        evidence["checks"]["ast_grep"] = ast_grep_issues if ast_grep_issues else "OK"
        if ast_grep_issues:
            return self._verdict(evidence, "FAIL", "; ".join(ast_grep_issues[:3]))
        return None

    def _check_static_linters(self, fp: Path, evidence: dict) -> Optional[dict]:
        ruff_errors = self._run_ruff(fp)
        evidence["checks"]["ruff"] = ruff_errors if ruff_errors else "OK"
        if ruff_errors:
            return self._verdict(evidence, "FAIL", "; ".join(ruff_errors[:5]))

        vulture_out = self._run_vulture(fp)
        evidence["checks"]["vulture"] = vulture_out.strip() if vulture_out else "OK"
        if VULTURE_UNUSED_IMPORT_RE.search(vulture_out):
            return self._verdict(evidence, "FAIL", "vulture: unused import detected")
        return None

    def _determine_final_verdict(self, evidence: dict, test_res: Optional[dict], smt: str, run_tests: bool) -> dict:
        has_green_tests = bool(test_res and test_res.get("collected", 0) > 0 and not test_res.get("failed"))
        if has_green_tests:
            note = f" (SMT advisory: {smt})" if smt.startswith("SMT_ERROR") else ""
            return self._verdict(evidence, "PASS", "all evidence checks clean, tests green" + note)
        if run_tests and not test_res:
            return self._verdict(evidence, "UNVERIFIED", "no targeted tests discovered (run full suite to upgrade)")
        if test_res and test_res.get("collected", 0) == 0:
            return self._verdict(evidence, "UNVERIFIED", "targeted test file collected 0 tests")
        return self._verdict(evidence, "UNVERIFIED", "insufficient evidence (no tests ran)")

    # ------------------------------------------------------------------ #
    def evaluate(
        self,
        file_path: str | Path,
        code_content: str | None = None,
        run_tests: bool = True,
        full_suite: bool = False,
        test_timeout: int = 600,
    ) -> dict:
        fp = Path(file_path) if Path(file_path).is_absolute() else self.root / Path(file_path)
        evidence: dict = {"file": str(fp), "checks": {}}

        src, read_err = self._read_source(fp, code_content)
        if read_err:
            evidence["checks"]["read"] = read_err
            return self._verdict(evidence, "FAIL", "cannot read file")

        ast_ok, ast_msg = self._check_ast_syntax(src, fp)
        evidence["checks"]["ast"] = ast_msg
        if not ast_ok:
            return self._verdict(evidence, "FAIL", ast_msg)

        sec_failure = self._check_security_and_scanners(src, fp, evidence)
        if sec_failure is not None:
            return sec_failure

        linter_failure = self._check_static_linters(fp, evidence)
        if linter_failure is not None:
            return linter_failure

        smt = self._run_smt(src)
        evidence["checks"]["smt"] = smt
        if smt == "CONTRACT_VIOLATION":
            return self._verdict(evidence, "FAIL", "SMT: contract violation (counterexample found)")

        test_res = None
        if run_tests:
            test_res = self._run_targeted_tests(fp, full_suite=full_suite, timeout=test_timeout)
            evidence["checks"]["pytest"] = test_res
            if test_res and test_res.get("failed"):
                return self._verdict(evidence, "FAIL", "pytest: red tests")

        return self._determine_final_verdict(evidence, test_res, smt, run_tests)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _verdict(evidence: dict, verdict: str, reason: str) -> dict:
        evidence["verdict"] = verdict
        evidence["reason"] = reason
        evidence["llm_calls"] = 0
        return evidence

    def _security_scan(self, src: str) -> list[str]:
        issues = []
        for pat in SECRET_PATTERNS:
            if pat.search(src):
                issues.append("hardcoded API key/secret detected")
                break
        for pat, label in DANGEROUS_PATTERNS:
            if pat.search(src):
                issues.append(label)
        return issues

    def _run_semgrep(self, fp: Path) -> list[str]:
        semgrep = VENV_DIR / "semgrep.exe"
        if not semgrep.exists():
            return []
        try:
            res = subprocess.run(
                # FIX: was --config=auto (requires network). Now uses offline bundled rulesets.
                [
                    str(semgrep),
                    "scan",
                    "--config=p/python",
                    "--config=p/security-audit",
                    "--json",
                    "--quiet",
                    "--no-git-ignore",
                    str(fp),
                ],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace",
            )
            if res.stdout.strip():
                import json

                try:
                    data = json.loads(res.stdout)
                    findings = data.get("results", [])
                    return [
                        f"{r.get('check_id')}: {r.get('extra', {}).get('message', '')}"
                        for r in findings
                        if r.get("extra", {}).get("severity") in ("ERROR", "HIGH", "WARNING")
                    ]
                except json.JSONDecodeError as jde:
                    logger.debug("Semgrep json decode non-fatal: %s", jde)
            return []
        except Exception as e:
            logger.debug("Semgrep execution non-fatal: %s", e)
            return []

    def _run_ast_grep(self, fp: Path) -> list[str]:
        """L3: structural AST pattern scan via ast-grep (sg). Offline, zero-network."""
        issues = []
        DANGEROUS_AST_PATTERNS = [
            ("eval($X)", "Dangerous eval() call"),
            ("exec($X)", "Dangerous exec() call"),
            ("os.system($CMD)", "Prohibited os.system() call"),
            ("subprocess.Popen($$$ARGS, shell=True)", "subprocess shell=True"),
        ]
        try:
            import json as _json

            for pattern, label in DANGEROUS_AST_PATTERNS:
                res = subprocess.run(
                    ["ast-grep", "run", "--pattern", pattern, "--lang", "python", "--json", str(fp)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    encoding="utf-8",
                    errors="replace",
                )
                if res.stdout.strip():
                    try:
                        matches = _json.loads(res.stdout)
                        if isinstance(matches, list) and matches:
                            issues.append(f"[ast-grep] {label} in {fp.name}")
                    except _json.JSONDecodeError as jde:
                        logger.debug("ast-grep json decode non-fatal: %s", jde)
                        issues.append(f"[ast-grep] {label} in {fp.name}")
        except FileNotFoundError as fnf:
            logger.debug("ast-grep binary not found: %s", fnf)
        except Exception as e:
            logger.debug("ast-grep run non-fatal: %s", e)
        return issues

    def _run_ruff(self, fp: Path) -> list[str]:
        ruff = VENV_DIR / "ruff.exe"
        if not ruff.exists():
            return []
        try:
            res = subprocess.run(
                [str(ruff), "check", "--select", "E9,F", "--no-fix", "--output-format", "text", str(fp)],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=120,
            )
            return [ln.strip() for ln in res.stdout.splitlines() if ln.strip() and not ln.startswith("warning:")]
        except Exception:
            return []

    def _run_vulture(self, fp: Path) -> str:
        vulture = VENV_DIR / "vulture.exe"
        if not vulture.exists():
            return ""
        try:
            res = subprocess.run(
                [str(vulture), str(fp), "--min-confidence", "80"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=120,
            )
            return res.stdout or ""
        except Exception:
            return ""

    def _run_smt(self, src: str) -> str:
        try:
            from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier

            res = SMTZ3Verifier(depth=10).verify_code_contracts(code_str=src)
            if hasattr(res, "get"):
                status = str(res.get("status") or "")
                satisfied = res.get("contract_satisfied")
            else:
                status = str(getattr(res, "status", "") or "")
                satisfied = getattr(res, "contract_satisfied", None)
            # Only a real SAT counterexample is hard evidence of violation.
            # ERROR/SYNTAX_ERROR mean the verifier could not process the input
            # (e.g. whole-file sources) — honest, but NOT a violation.
            if status == "SAT":
                return "CONTRACT_VIOLATION"
            if status in ("ERROR", "SYNTAX_ERROR"):
                return f"SMT_ERROR({status})"
            if status == "UNSAT" or satisfied is True:
                return "UNSAT"
            return status or "NO_CONTRACTS"
        except Exception as e:
            return f"SMT_ERROR: {e}"

    def _resolve_test_targets(self, fp: Path, full_suite: bool) -> list[Path]:
        if full_suite:
            tests_root = self.root / "tests"
            return [tests_root] if tests_root.exists() else []
        t = _find_targeted_test_file(fp)
        return [t] if t else []

    @staticmethod
    def _parse_pytest_counts(stdout: str) -> Tuple[int, int, int]:
        # Truncate to last 4096 bytes to prevent context bloat from large test suites
        tail = stdout[-4096:]
        passed = failed = 0
        for m in re.finditer(r"(\d+)\s+passed", tail):
            passed = max(passed, int(m.group(1)))
        for m in re.finditer(r"(\d+)\s+failed", tail):
            failed = max(failed, int(m.group(1)))
        return passed + failed, passed, failed

    @staticmethod
    def _exec_pytest_suite(*pytest_args: str) -> Tuple[int, str]:
        """Executes pytest subprocess in workspace sandbox."""
        res = subprocess.run(
            list(pytest_args),
            cwd="C:/vazus",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        return res.returncode, res.stdout or ""

    def _run_targeted_tests(self, fp: Path, full_suite: bool = False, timeout: int = 600) -> dict | None:
        py = VENV_DIR / "python.exe"
        if not py.exists():
            return None
        targets = self._resolve_test_targets(fp, full_suite)
        if not targets:
            return None

        cmd = [str(py), "-m", "pytest", "-q", "--tb=line", "--no-header"] + [str(t) for t in targets]
        try:
            returncode, stdout = self._exec_pytest_suite(*cmd)
        except subprocess.TimeoutExpired:
            return {"collected": 0, "passed": 0, "failed": True, "error": f"pytest timeout >{timeout}s"}
        except Exception as e:
            return {"collected": 0, "passed": 0, "failed": True, "error": str(e)}

        collected, passed, failed = self._parse_pytest_counts(stdout)
        return {
            "collected": collected,
            "passed": passed,
            "failed": failed,
            "exit_code": returncode,
            "targets": [str(t.relative_to(self.root)) for t in targets],
        }


def run_evidence_jury(file_path: str, **kwargs) -> dict:
    """Convenience wrapper: sync, returns a plain dict."""
    return EvidenceJury().evaluate(file_path, **kwargs)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import json

    target = sys.argv[1] if len(sys.argv) > 1 else "vazus_core/verification/evidence_jury.py"
    print(json.dumps(EvidenceJury().evaluate(target), ensure_ascii=False, indent=2, default=str))
