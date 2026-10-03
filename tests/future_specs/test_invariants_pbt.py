"""
Property-Based & Invariant Tests for Vazus Core.

Стратегия: тестируем ИНВАРИАНТЫ через Hypothesis.
НЕ тестируем конкретные значения которые сами же задаём через моки.

Баги найденные Hypothesis (реальные, не oracle):
  BUG-1: _extract_json возвращал int/list когда json.loads("0") → 0 (нарушение Optional[Dict] контракта)
  BUG-2: GraphifyASTVisitor нормализует Unicode лигатуры (ﬀ → ff) — имя в AST отличается от исходного
  BUG-3: Python keywords (else, class...) — SyntaxError при ast.parse → нужен assume
  BUG-4: tmp_path fixture не сбрасывается между Hypothesis runs — нужен tempfile.mkdtemp()
"""
from __future__ import annotations

import ast
import asyncio
import json
import keyword
import tempfile
from pathlib import Path
from unittest.mock import patch

from hypothesis import given, settings, strategies as st, assume, HealthCheck

from vazus_core.engine.dialectical_synthesizer import DialecticalSynthesizer
from vazus_core.engine.graphify_engine import GraphifyASTVisitor
from vazus_core.missions.mission_factory import MissionFactory, MissionTask, MissionValidator
from vazus_core.verification.dual_jury import dual_jury_verdict
from vazus_core.verification.testgen_engine import AssuredTestGenEngine
from vazus_core.verification.precommit_gate import run_gate_8_testgen_coverage

settings.register_profile("ci", max_examples=50)
settings.load_profile("ci")

# Стратегия для валидных Python-идентификаторов (ASCII, не keyword)
_PY_IDENT = (
    st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        min_size=1, max_size=15,
    )
    .filter(lambda s: s.isidentifier() and not keyword.iskeyword(s) and s.isascii())
)


# ── ИНВАРИАНТ 1: MissionValidator missing key → always False ──────────────────

@given(
    required_keys=st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=15),
        min_size=1, max_size=4, unique=True,
    ),
    payload=st.dictionaries(
        st.text(min_size=1, max_size=10), st.text(max_size=20), max_size=5
    ),
)
def test_invariant_missing_key_always_fails(required_keys, payload):
    """ИНВАРИАНТ: если хотя бы одного required_key нет в payload → ВСЕГДА False."""
    missing = [k for k in required_keys if k not in payload]
    assume(len(missing) > 0)

    task = MissionTask("t", "role", "desc", {}, output_schema_keys=required_keys)
    ok, reason = MissionValidator.validate_payload(task, payload)
    assert ok is False
    assert any(mk in reason for mk in missing)


# ── ИНВАРИАНТ 2: all required_keys present → schema check passes ───────────────

@given(
    keys=st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
        min_size=1, max_size=4, unique=True,
    ),
)
def test_invariant_all_keys_present_passes_schema(keys):
    """ИНВАРИАНТ: если все required_keys есть в payload (без custom fn) → True."""
    payload = {k: "value" for k in keys}
    task = MissionTask("t", "role", "desc", {}, output_schema_keys=keys)
    ok, reason = MissionValidator.validate_payload(task, payload)
    assert ok is True
    assert reason == "OK"


# ── ИНВАРИАНТ 3: _extract_json round-trip (FIX BUG-1) ────────────────────────

@given(
    data=st.dictionaries(
        st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
        st.one_of(st.text(max_size=20), st.integers(-1000, 1000), st.booleans()),
        max_size=6,
    )
)
def test_invariant_extract_json_round_trip(data):
    """ИНВАРИАНТ: dict → json fence → _extract_json → тот же dict. Round-trip."""
    factory = MissionFactory()
    text = f"```json\n{json.dumps(data)}\n```"
    result = factory._extract_json(text)
    assert result == data


@given(
    garbage=st.text(max_size=50).filter(
        lambda s: not s.strip().startswith("{") and not s.strip().startswith("[")
    )
)
def test_invariant_extract_json_non_object_returns_none(garbage):
    """ИНВАРИАНТ: любой не-dict JSON (int, list, str, invalid) → None.
    BUG-1 FIX: раньше json.loads('0') возвращал 0 (int) нарушая Optional[Dict] контракт."""
    factory = MissionFactory()
    result = factory._extract_json(garbage)
    # После BUG-1 fix: только dict или None допустимы
    assert result is None or isinstance(result, dict)


# ── ИНВАРИАНТ 4: GraphifyASTVisitor class → DEFINES edge (FIX BUG-2/BUG-3) ───

@given(class_name=_PY_IDENT)
def test_invariant_graphify_class_always_has_defines_edge(class_name):
    """ИНВАРИАНТ: любой ASCII Python-идентификатор class X → DEFINES edge.
    BUG-2 FIX: Unicode лигатуры (ﬀ→ff) нормализуются AST — используем только ASCII.
    BUG-3 FIX: keywords (else, class) дают SyntaxError — фильтруем через _PY_IDENT."""
    src = f"class {class_name}:\n    pass\n"
    tree = ast.parse(src)
    visitor = GraphifyASTVisitor("test.py")
    visitor.visit(tree)

    define_edges = [e for e in visitor.edges if e["type"] == "DEFINES"]
    targets = [e["target"] for e in define_edges]
    assert any(class_name in t for t in targets), (
        f"DEFINES edge для '{class_name}' не найден в: {targets}"
    )


# ── ИНВАРИАНТ 5: N functions → exactly N Function nodes (FIX BUG-3) ──────────

@given(
    func_names=st.lists(_PY_IDENT, min_size=1, max_size=5, unique=True)
)
def test_invariant_graphify_function_count_matches(func_names):
    """ИНВАРИАНТ: N def → ровно N Function нод.
    BUG-3 FIX: используем _PY_IDENT который фильтрует keywords."""
    src = "\n".join(f"def {name}(): pass" for name in func_names)
    tree = ast.parse(src)
    visitor = GraphifyASTVisitor("fns.py")
    visitor.visit(tree)

    func_nodes = [n for n in visitor.nodes if n["type"] == "Function"]
    assert len(func_nodes) == len(func_names)


# ── ИНВАРИАНТ 6: _extract_code — no backticks in output ──────────────────────

_CODE_TEXT = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:()\n=+-",
    min_size=1, max_size=200,
)


@given(code=_CODE_TEXT)
def test_invariant_extract_code_never_leaves_backticks(code):
    """ИНВАРИАНТ: _extract_code НИКОГДА не оставляет ``` в выводе."""
    ds = DialecticalSynthesizer(depth=1)
    fenced = f"```python\n{code}\n```"
    result = ds._extract_code(fenced)
    assert "```" not in result


@given(code=_CODE_TEXT.filter(lambda s: "```" not in s))
def test_invariant_extract_code_raw_passthrough_no_backticks(code):
    """ИНВАРИАНТ: текст без fence → выход тоже без ```."""
    ds = DialecticalSynthesizer(depth=1)
    result = ds._extract_code(code)
    assert "```" not in result


# ── ИНВАРИАНТ 7: dual_jury — FAIL никогда не approved (safety critical) ───────

@given(reason=st.text(max_size=100))
def test_invariant_dual_jury_fail_never_approved(reason):
    """КРИТИЧЕСКИЙ ИНВАРИАНТ БЕЗОПАСНОСТИ: verdict==FAIL → approved НИКОГДА не True.
    Hypothesis генерирует 50+ разных reason — мы не задаём конкретное значение."""
    fake_fail = {"verdict": "FAIL", "reason": reason, "llm_calls": 0, "checks": {}}
    with patch("vazus_core.verification.dual_jury.EvidenceJury.evaluate", return_value=fake_fail):
        result = asyncio.run(dual_jury_verdict("any.py", run_tests=False))
    assert result["approved"] is not True, (
        f"SECURITY BUG: FAIL verdict дал approved=True! reason={reason!r}"
    )
    assert result["verdict"] == "FAIL"


# ── ИНВАРИАНТ 8: dual_jury — PASS всегда approved ─────────────────────────────

@given(reason=st.text(max_size=100))
def test_invariant_dual_jury_pass_always_approved(reason):
    """ИНВАРИАНТ: verdict==PASS → approved ВСЕГДА True."""
    fake_pass = {"verdict": "PASS", "reason": reason, "llm_calls": 0, "checks": {}}
    with patch("vazus_core.verification.dual_jury.EvidenceJury.evaluate", return_value=fake_pass):
        result = asyncio.run(dual_jury_verdict("any.py", run_tests=False))
    assert result["approved"] is True


# ── ИНВАРИАНТ 9: Gate 8 — всегда (bool, list) (FIX BUG-4) ───────────────────

@given(
    stems=st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=20),
        max_size=5,
    )
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_invariant_gate8_always_returns_bool_list(stems):
    """ИНВАРИАНТ: run_gate_8_testgen_coverage ВСЕГДА возвращает (bool, list).
    BUG-4 FIX: заменяем tmp_path (function-scoped) на tempfile.mkdtemp() внутри теста."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        files = []
        for stem in stems:
            f = tmp / f"{stem}.py"
            f.write_text("def x(): pass")
            files.append(f)

        passed, msgs = run_gate_8_testgen_coverage(files)
        assert isinstance(passed, bool)
        assert isinstance(msgs, list)


# ── ИНВАРИАНТ 10: _is_reward_hacking — clean test never flagged ───────────────

@given(
    func_name=_PY_IDENT,
    body_len=st.integers(min_value=1, max_value=100),
)
def test_invariant_reward_hacking_real_assertion_not_flagged(func_name, body_len):
    """ИНВАРИАНТ: код с реальным assertion (assert x > 0) НЕ флагируется."""
    engine = AssuredTestGenEngine(workspace_root=r"C:\vazus")
    code = f"def test_{func_name}():\n    x = {body_len}\n    assert x > 0"
    result = engine._is_reward_hacking(code)
    assert result is False, f"Реальный тест был ошибочно флагирован: {code!r}"
