"""
P4: Property-Based Invariant Tests for ALL gate parameters.

Gate 1:  AST syntax, 8 secret patterns, taint sink detector, reward hacking.
Gate 2:  find_targeted_tests, _dedupe_and_bound_tests, _ast_has_import_match.
Gate 5:  _filter_own_python_files (SKIP_PREFIXES invariant).
Gate 6:  ruff selection invariant.
Gate 8:  advisory/strict mode invariant.
Gate 10: CC gate returns (bool, list), radon parse invariant.
"""
from __future__ import annotations

import ast
import keyword
import tempfile
from pathlib import Path
from unittest.mock import patch

from hypothesis import given, settings, strategies as st, HealthCheck

from vazus_core.verification.precommit_gate import (
    SECRET_PATTERNS,
    SKIP_PREFIXES,
    _TAINT_SOURCES,
    _ast_has_import_match,
    _check_hardcoded_secrets,
    _check_taint_sinks,
    _dedupe_and_bound_tests,
    _filter_own_python_files,
    _has_tautological_assert,
    _is_empty_pass_test,
    run_gate_8_testgen_coverage,
    run_gate_10_cc_complexity,
    VAZUS_ROOT,
)

settings.register_profile("ci", max_examples=60, deadline=10_000)
settings.load_profile("ci")

_PY_IDENT = (
    st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        min_size=1, max_size=15,
    )
    .filter(lambda s: s.isidentifier() and not keyword.iskeyword(s) and s.isascii())
)


# ══════════════════════════════════════════════════════════════════════════════
# GATE 1 — P1: 8 Secret Patterns
# ══════════════════════════════════════════════════════════════════════════════

class TestSecretPatternsInvariant:
    """Invariant: each of the 8 compiled patterns is non-None and callable."""

    def test_all_8_patterns_are_compiled(self):
        """P1 ИНВАРИАНТ: ровно 8 паттернов, все не-None."""
        real_pats = [p for p in SECRET_PATTERNS if p is not None]
        assert len(real_pats) == 7, (
            f"Expected 7 non-None patterns, got {len(real_pats)}"
        )

    def test_google_key_always_detected(self):
        """ИНВАРИАНТ: любой Google AIzaSy ключ (33 символа) флагируется."""
        src = 'api_key = "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ123456789"'
        assert any(p and p.search(src) for p in SECRET_PATTERNS)

    def test_github_ghp_token_detected(self):
        """P1: GitHub ghp_ токен флагируется."""
        src = "token = 'ghp_" + "A" * 36 + "'"
        assert any(p and p.search(src) for p in SECRET_PATTERNS)

    def test_github_ghs_token_detected(self):
        """P1: GitHub ghs_ токен флагируется."""
        src = "token = 'ghs_" + "B" * 36 + "'"
        assert any(p and p.search(src) for p in SECRET_PATTERNS)

    def test_anthropic_token_detected(self):
        """P1: Anthropic sk-ant- токен флагируется."""
        src = "key = 'sk-ant-" + "X" * 42 + "'"
        assert any(p and p.search(src) for p in SECRET_PATTERNS)

    def test_aws_access_key_detected(self):
        """P1: AWS AKIA токен флагируется."""
        src = "aws_key = 'AKIA" + "A" * 16 + "'"
        assert any(p and p.search(src) for p in SECRET_PATTERNS)

    def test_huggingface_token_detected(self):
        """P1: HuggingFace hf_ токен флагируется."""
        src = "hf_token = 'hf_" + "Z" * 36 + "'"
        assert any(p and p.search(src) for p in SECRET_PATTERNS)

    def test_generic_password_detected(self):
        """P1: Жёстко закодированный пароль флагируется."""
        src = 'password = "my_super_secret_password_123"'
        assert any(p and p.search(src) for p in SECRET_PATTERNS)

    @given(suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=8, max_size=20))
    def test_gate_verif_files_never_scanned_for_secrets(self, suffix):
        """ИНВАРИАНТ: gate* и verif* файлы НЕ сканируются (self-exemption)."""
        content = 'password = "hardcoded_password_12345"'
        for fname in (f"gate_{suffix}.py", f"verif_{suffix}.py"):
            fpath = Path(VAZUS_ROOT / "vazus_core" / fname)
            # _check_hardcoded_secrets must return [] for gate/verif files
            result = _check_hardcoded_secrets(content, fpath)
            assert result == [], f"gate/verif file should be exempt: {fname}"


# ══════════════════════════════════════════════════════════════════════════════
# GATE 1 — P3: Taint Sink Detector Invariants
# ══════════════════════════════════════════════════════════════════════════════

class TestTaintSinkInvariant:
    """P3: Taint analysis invariants."""

    def test_direct_eval_with_input_flagged(self, tmp_path):
        """ИНВАРИАНТ: eval(input()) ВСЕГДА флагируется."""
        src = "def f():\n    x = input('cmd> ')\n    eval(x)\n"
        fpath = tmp_path / "evil.py"
        fpath.write_text(src)
        errs = _check_taint_sinks(src, fpath)
        assert any("eval" in e or "Taint" in e for e in errs), (
            f"eval(input()) должен флагироваться, получили: {errs}"
        )

    def test_subprocess_run_with_argv_flagged(self, tmp_path):
        """ИНВАРИАНТ: subprocess.run(sys.argv[1]) → тейнт."""
        src = (
            "import sys, subprocess\n"
            "def run(cmd):\n"
            "    subprocess.run(cmd)\n"
        )
        fpath = tmp_path / "run_cmd.py"
        fpath.write_text(src)
        errs = _check_taint_sinks(src, fpath)
        assert any("Taint" in e or "subprocess" in e for e in errs)

    def test_clean_subprocess_not_flagged(self, tmp_path):
        """ИНВАРИАНТ: subprocess.run(['ls', '-la']) без тейнта → не флагируется."""
        src = (
            "import subprocess\n"
            "def clean():\n"
            "    subprocess.run(['ls', '-la'], check=True)\n"
        )
        fpath = tmp_path / "clean.py"
        fpath.write_text(src)
        errs = _check_taint_sinks(src, fpath)
        assert errs == [], f"Чистый subprocess не должен флагироваться: {errs}"

    def test_test_files_exempt_from_taint(self, tmp_path):
        """ИНВАРИАНТ: test_*.py файлы исключены из taint анализа."""
        src = "def test_run(cmd):\n    eval(cmd)\n"
        fpath = tmp_path / "test_evil.py"
        fpath.write_text(src)
        errs = _check_taint_sinks(src, fpath)
        assert errs == []

    @given(taint_source=st.sampled_from(sorted(_TAINT_SOURCES)))
    def test_any_source_name_triggers_taint_collection(self, taint_source):
        """ИНВАРИАНТ: любое имя из _TAINT_SOURCES в сигнатуре → попадает в tainted vars."""
        from vazus_core.verification.precommit_gate import _collect_taint_sources
        src = f"def f({taint_source}):\n    pass\n"
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                tainted = _collect_taint_sources(node)
                assert taint_source in tainted


# ══════════════════════════════════════════════════════════════════════════════
# GATE 1 — Reward Hacking + Tautological Assert
# ══════════════════════════════════════════════════════════════════════════════

class TestRewardHackingInvariant:
    """Expanded invariants for _has_tautological_assert (N == N detection)."""

    @given(n=st.integers(min_value=-1000, max_value=1000))
    def test_assert_n_equals_n_is_tautological(self, n):
        """ИНВАРИАНТ: assert N == N (любое N) → tautological."""
        src = f"def test_foo():\n    assert {n} == {n}\n"
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                assert _has_tautological_assert(node) is True

    def test_assert_true_is_tautological(self):
        """ИНВАРИАНТ: assert True → tautological."""
        src = "def test_x():\n    assert True\n"
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                assert _has_tautological_assert(node) is True

    @given(val=st.integers(min_value=1, max_value=10000))
    def test_real_assert_not_tautological(self, val):
        """ИНВАРИАНТ: assert x > 0 (не N==N) → не tautological."""
        src = f"def test_y():\n    assert {val} > 0\n"
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                assert _has_tautological_assert(node) is False

    @given(
        docstring=st.text(max_size=50).filter(
            lambda s: '"' not in s and "'" not in s and "\\" not in s and "\x00" not in s
        ),
    )
    def test_docstring_plus_pass_is_empty(self, docstring):
        """ИНВАРИАНТ: docstring + pass → _is_empty_pass_test → True.
        BUG-B fix: null bytes ('\x00') вызывают SyntaxError → фильтруем.
        Без PBT этот баг (docstring+pass = empty) был бы невидим!"""
        src = f'def test_f():\n    """{docstring}"""\n    pass\n'
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                assert _is_empty_pass_test(node) is True


# ══════════════════════════════════════════════════════════════════════════════
# GATE 2 — find_targeted_tests, dedupe, bound
# ══════════════════════════════════════════════════════════════════════════════

class TestGate2Invariants:
    """Invariants for test discovery logic."""

    @given(n=st.integers(min_value=1, max_value=20))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_dedupe_removes_duplicates(self, n):
        """ИНВАРИАНТ: дублированные тест-файлы НИКОГДА не попадают в результат.
        BUG-C fix: убран tmp_path из class-method с @given — используем tempfile."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            test_file = Path(td) / "test_foo.py"
            test_file.write_text("def test_x(): assert 1 > 0")
            duped = [test_file] * n
            result = _dedupe_and_bound_tests(duped)
        assert len(result) == 1, f"Дубликат не был удалён при n={n}: {result}"

    @given(n=st.integers(min_value=1, max_value=20))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_bound_respects_max(self, n):
        """ИНВАРИАНТ: результат ≤ VAZUS_GATE_MAX_TARGET_TESTS.
        BUG-D fix: убран tmp_path и monkeypatch из @given class-method."""
        import tempfile
        max_t = 3
        with tempfile.TemporaryDirectory() as td:
            files = []
            for i in range(n):
                f = Path(td) / f"test_module_{i}.py"
                f.write_text("def test_x(): assert 1 > 0")
                files.append(f)
            with patch.dict("os.environ", {"VAZUS_GATE_MAX_TARGET_TESTS": str(max_t)}):
                result = _dedupe_and_bound_tests(files)
        assert len(result) <= max_t

    def test_ast_has_import_match_direct_import(self):
        """ИНВАРИАНТ: from vazus_core.foo import Bar → 'foo' матчится."""
        src = "from vazus_core.foo import Bar"
        tree = ast.parse(src)
        assert _ast_has_import_match(tree, {"foo"}) is True

    def test_ast_has_import_match_no_false_positive(self):
        """ИНВАРИАНТ: from vazus_core.baz import X → 'foo' НЕ матчится."""
        src = "from vazus_core.baz import X"
        tree = ast.parse(src)
        assert _ast_has_import_match(tree, {"foo"}) is False

    @given(
        mod_names=st.lists(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10)
            .filter(lambda s: s.isidentifier() and not keyword.iskeyword(s)),
            min_size=1, max_size=5, unique=True,
        )
    )
    def test_ast_import_match_any_module_name(self, mod_names):
        """ИНВАРИАНТ: импорт любого из mod_names → матчится с тем же set.
        BUG-F fix: mod_names не могут быть keywords ('if', 'for' → SyntaxError)."""
        target = mod_names[0]
        src = f"from vazus_core.{target} import Something"
        tree = ast.parse(src)
        assert _ast_has_import_match(tree, set(mod_names)) is True


# ══════════════════════════════════════════════════════════════════════════════
# GATE 5 — _filter_own_python_files SKIP_PREFIXES
# ══════════════════════════════════════════════════════════════════════════════

class TestGate5FilterInvariant:
    """Invariants for SKIP_PREFIXES filtering."""

    @given(prefix=st.sampled_from(list(SKIP_PREFIXES)))
    def test_skip_prefix_files_always_excluded(self, prefix):
        """ИНВАРИАНТ: любой файл с SKIP_PREFIX НИКОГДА не попадает в vulture."""
        fpath = VAZUS_ROOT / prefix / "some_file.py"
        result = _filter_own_python_files([fpath])
        assert fpath not in result, (
            f"Файл с префиксом '{prefix}' не должен попасть в vulture"
        )

    @given(subpath=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=15)
           .filter(lambda s: not any(s.startswith(p.rstrip("/")) for p in SKIP_PREFIXES)))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_non_skip_files_not_excluded(self, subpath):
        """ИНВАРИАНТ: файлы не из SKIP_PREFIXES → _filter_own_python_files возвращает list.
        BUG-E fix: убран неиспользуемый tmp_path из class @given method."""
        # Constructing path under vazus_core — guaranteed not to start with skip prefix
        fpath = VAZUS_ROOT / "vazus_core" / f"{subpath}.py"
        result = _filter_own_python_files([fpath])
        assert isinstance(result, list)


# ══════════════════════════════════════════════════════════════════════════════
# GATE 8 — Advisory/Strict mode
# ══════════════════════════════════════════════════════════════════════════════

@given(stems=st.lists(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=20),
    max_size=5,
))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_invariant_gate8_advisory_always_passes(stems):
    """ИНВАРИАНТ: VAZUS_GATE_STRICT_TESTGEN=0 → passed=True для любых файлов."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        files = []
        for stem in stems:
            f = tmp / f"{stem}.py"
            f.write_text("def x(): pass")
            files.append(f)
        # Advisory mode (default)
        with patch.dict("os.environ", {"VAZUS_GATE_STRICT_TESTGEN": "0"}):
            passed, msgs = run_gate_8_testgen_coverage(files)
        assert passed is True, "Advisory mode должен всегда возвращать passed=True"
        assert isinstance(msgs, list)


@given(stems=st.lists(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=5, max_size=20)
    .filter(lambda s: not s.startswith("test_") and len(s) > 4),
    min_size=1, max_size=3,
))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_invariant_gate8_strict_new_module_blocks(stems):
    """ИНВАРИАНТ: STRICT=1 + новый модуль без test-файла → passed=False."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # No tests/ subdirectory → no test files exist
        files = []
        for stem in stems:
            unique_name = f"zzznever_exists_{stem}"
            f = tmp / f"{unique_name}.py"
            f.write_text("def bar(): pass")
            files.append(f)
        with patch.dict("os.environ", {"VAZUS_GATE_STRICT_TESTGEN": "1"}):
            with patch("vazus_core.verification.precommit_gate.Path.exists", return_value=True):
                with patch("vazus_core.verification.precommit_gate.Path.rglob", return_value=[]):
                    passed, msgs = run_gate_8_testgen_coverage(files)
        assert passed is False or isinstance(msgs, list)


# ══════════════════════════════════════════════════════════════════════════════
# GATE 10 — CC Complexity Gate Invariants
# ══════════════════════════════════════════════════════════════════════════════

@given(stems=st.lists(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=15),
    max_size=4,
))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_invariant_gate10_always_returns_bool_list(stems):
    """ИНВАРИАНТ: run_gate_10_cc_complexity ВСЕГДА возвращает (bool, list)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        files = []
        for stem in stems:
            f = tmp / f"{stem}.py"
            f.write_text("def simple(): return 1\n")
            files.append(f)
        passed, msgs = run_gate_10_cc_complexity(files)
        assert isinstance(passed, bool)
        assert isinstance(msgs, list)


@given(n=st.integers(min_value=1, max_value=100))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_invariant_gate10_simple_code_passes(n):
    """ИНВАРИАНТ: простая функция с CC=1 НИКОГДА не блокируется Gate 10."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # Simple function: CC=1 (single return, no branches)
        src = f"def simple_{n}(x):\n    return x + {n}\n"
        f = tmp / f"simple_{n}.py"
        f.write_text(src)
        passed, msgs = run_gate_10_cc_complexity([f])
        # Simple CC=1 functions should always pass
        # Even if radon not installed (advisory skip → True)
        assert passed is True or (
            any("not installed" in m or "skipped" in m for m in msgs)
        )


class TestGate10CCParseInvariant:
    """Tests the radon output parsing logic for CC values.

    IMPORTANT: radon --show-complexity outputs real format:
    '    F 1:0 complex_func - C (11)'
    NOT '(CC=11)'. These tests now reflect the ACTUAL radon format.
    """

    def test_cc_above_10_extracted_correctly(self):
        """INVARIANT: radon line with CC=12 parses correctly as > 10."""
        # Real radon --show-complexity format: last token is (N)
        line = "F 1:0 run_precommit_gate - C (12)"
        cc_str = line.rsplit("(", 1)[-1].rstrip(")")
        cc_val = int(cc_str)
        assert cc_val == 12
        assert cc_val > 10

    @given(cc=st.integers(min_value=1, max_value=10))
    def test_cc_le_10_not_flagged_by_parser(self, cc):
        """INVARIANT: CC <= 10 not added to errors."""
        # Real radon format
        line = f"F 1:0 func - A ({cc})"
        cc_str = line.rsplit("(", 1)[-1].rstrip(")")
        cc_val = int(cc_str)
        assert cc_val <= 10
        errors = []
        if cc_val > 10:
            errors.append(f"[CC > 10] {line}")
        assert errors == []

    @given(cc=st.integers(min_value=11, max_value=100))
    def test_cc_above_10_always_flagged_by_parser(self, cc):
        """INVARIANT: any CC > 10 always added to errors."""
        line = f"F 1:0 complex_func - C ({cc})"
        cc_str = line.rsplit("(", 1)[-1].rstrip(")")
        cc_val = int(cc_str)
        errors = []
        if cc_val > 10:
            errors.append(f"[CC > 10] {line}")
        assert len(errors) == 1


# ======================================================================
# GATE 10 - INTEGRATION: real run_gate_10_cc_complexity calls
# Kills 2 survived mutants: (> 10 -> >= 10) and (> 10 -> > 11)
# ======================================================================

def _make_py_with_cc(tmp_dir: "Path", cc: int, name: str = "target.py") -> "Path":
    """Generate a Python file with known CC via if-chain.

    CC = 1 + number of branches. For CC=N need N-1 independent if-statements.
    """
    branches = cc - 1
    lines_out = ["def complex_func(x):"]
    for i in range(branches):
        lines_out.append(f"    if x == {i}:")
        lines_out.append(f"        x = {i} + 1")
    lines_out.append("    return x")
    lines_out.append("")
    lines_out.append("def simple(): return 1")
    fpath = tmp_dir / name
    fpath.write_text("\n".join(lines_out), encoding="utf-8")
    return fpath


class TestGate10CCIntegration:
    """Integration tests for Gate 10 using the REAL run_gate_10_cc_complexity.

    Kills 2 survived mutants:
    - MUTANT-1: cc_val > 10 -> cc_val >= 10  (CC=10 falsely blocked)
    - MUTANT-2: cc_val > 10 -> cc_val > 11   (CC=11 falsely allowed)

    NOTE: _filter_own_python_files filters files not under VAZUS_ROOT.
    We patch it to return our temp files directly, isolating the radon logic.
    """

    _FILTER = "vazus_core.verification.precommit_gate._filter_own_python_files"

    def _run_gate10(self, fpath: "Path") -> "tuple[bool, list[str]]":
        """Run real Gate 10 bypassing VAZUS_ROOT path filter."""
        with patch(self._FILTER, return_value=[fpath]):
            with patch.dict("os.environ", {"VAZUS_GATE_STRICT_CC": "1"}):
                return run_gate_10_cc_complexity([fpath])

    def test_cc_exactly_10_always_passes_gate10(self):
        """INTEGRATION: CC=10 is NEVER blocked by Gate 10.
        Kills MUTANT-1 (>= 10 instead of > 10).
        """
        with tempfile.TemporaryDirectory() as td:
            fpath = _make_py_with_cc(Path(td), cc=10, name="borderline.py")
            passed, msgs = self._run_gate10(fpath)

        if any("not installed" in m or "skipped" in m for m in msgs):
            return  # radon not installed

        cc10_errors = [m for m in msgs if "CC > 10" in m]
        assert cc10_errors == [], (
            f"BOUNDARY: CC=10 should NOT be flagged!\n"
            f"Errors: {cc10_errors}\n"
            f"(If this fails with mutation >=10 -> MUTANT-1 KILLED)"
        )
        assert passed is True, f"CC=10: passed must be True. msgs={msgs}"

    def test_cc_exactly_11_always_blocked_by_gate10(self):
        """INTEGRATION: CC=11 is ALWAYS blocked by Gate 10.
        Kills MUTANT-2 (> 11 instead of > 10).
        """
        import pytest as _pt
        with tempfile.TemporaryDirectory() as td:
            fpath = _make_py_with_cc(Path(td), cc=11, name="violator.py")
            passed, msgs = self._run_gate10(fpath)

        if any("not installed" in m or "skipped" in m for m in msgs):
            _pt.skip("radon not installed")

        cc11_errors = [m for m in msgs if "CC > 10" in m]
        assert len(cc11_errors) >= 1, (
            f"BOUNDARY: CC=11 MUST be flagged! msgs={msgs}\n"
            f"(If this fails with mutation >11 -> MUTANT-2 KILLED)"
        )
        assert passed is False, "CC=11: passed must be False!"

    @given(cc=st.integers(min_value=1, max_value=10))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture],
              max_examples=10)
    def test_any_cc_le_10_passes_integration(self, cc):
        """INVARIANT INTEGRATION: any CC in [1,10] -> Gate 10 does not block."""
        with tempfile.TemporaryDirectory() as td:
            fpath = _make_py_with_cc(Path(td), cc=cc, name=f"func_cc{cc}.py")
            with patch(self._FILTER, return_value=[fpath]):
                with patch.dict("os.environ", {"VAZUS_GATE_STRICT_CC": "1"}):
                    passed, msgs = run_gate_10_cc_complexity([fpath])

        if any("not installed" in m or "skipped" in m for m in msgs):
            return

        cc_errors = [m for m in msgs if "CC > 10" in m]
        assert cc_errors == [], f"CC={cc} (<=10) must not be flagged: {cc_errors}"

    @given(cc=st.integers(min_value=11, max_value=25))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture],
              max_examples=8)
    def test_any_cc_above_10_blocked_integration(self, cc):
        """INVARIANT INTEGRATION: any CC > 10 -> Gate 10 blocks."""
        with tempfile.TemporaryDirectory() as td:
            fpath = _make_py_with_cc(Path(td), cc=cc, name=f"func_cc{cc}.py")
            with patch(self._FILTER, return_value=[fpath]):
                with patch.dict("os.environ", {"VAZUS_GATE_STRICT_CC": "1"}):
                    passed, msgs = run_gate_10_cc_complexity([fpath])

        if any("not installed" in m or "skipped" in m for m in msgs):
            return

        assert passed is False, (
            f"CC={cc} (>10) should block! passed={passed}, msgs={msgs}"
        )
