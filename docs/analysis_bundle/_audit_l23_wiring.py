"""
AUDIT (сессия 18.08 #2): открытый вопрос #2 из AUDIT_STATE.md
"Валидность claim L2/L3 в связке с тем, что telemetry подключён только к self_check_5layers.py"

Проверяем:
  A. Wiring: кто импортирует telemetry/codemods/verification-харвестеры ВНЕ tests/ и вне самих модулей.
  B. Живые данные: есть ли строки в telemetry_call_edges / telemetry_function_hits в vazus.db (RO).
  C. Vacuous-check ключевых тестов 5-слоёв (assert True / bare pass / skips).
  D. Живой прогон ключевых компонентов L2/L3 (trace collector + codemod router) — smoke.
"""
from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:/vazus")
MODULES = [
    "dynamic_trace_collector", "upstream_scanner",
    "ast_grep_runner", "libcst_pruner", "codemod_router",
    "supergraph_bridge", "candidate_harvester", "whitelist_manager",
    "smt_equivalence_prover",
]
SKIP_DIRS = ("/.venv/", "/__pycache__/", "/.git/", "/labs/", "/node_modules/",
             "/services/inference/", "/docs/analysis_bundle/")

def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)

# ------------------------------------------------------------- A. wiring sweep
hr("A. WIRING: кто ссылается на L2/L3-модули ВНЕ tests/ (grep-свип по *.py)")
for m in MODULES:
    refs = []
    for p in ROOT.rglob("*.py"):
        s = str(p).replace("\\", "/")
        if any(d in s for d in SKIP_DIRS):
            continue
        if s.endswith(f"/{m}.py") or "/tests/" in s:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if m in txt:
            refs.append(s.replace("C:/vazus/", ""))
    print(f"  {m:<28} <- {refs if refs else 'ORPHAN (только self_check/tests)'}")

# ------------------------------------------------------------- B. live telemetry data
hr("B. ЖИВЫЕ ДАННЫЕ: telemetry-таблицы в vazus.db (read-only)")
db = ROOT / "services/memory/vazus.db"
try:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'telemetry%'").fetchall()]
    print(f"  telemetry-таблицы: {tables if tables else 'ОТСУТСТВУЮТ'}")
    for t in tables:
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        try:
            last = cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 1").fetchone()
            cols = [d[1] for d in cur.execute(f"PRAGMA table_info({t})").fetchall()]
        except Exception:
            last, cols = None, []
        print(f"  {t}: {n} строк; последняя: {dict(zip(cols, last)) if last else '(пусто)'}")
    conn.close()
except Exception as e:
    print(f"  !! БД недоступна: {e}")

# ------------------------------------------------------------- C. vacuous tests
hr("C. VACUOUS-CHECK ключевых тестов 5-слоёв")
for rel in ["tests/test_closed_loop_5layers.py", "tests/test_codemod_router.py",
            "tests/test_dynamic_trace_collector.py", "tests/test_smt_equivalence_prover.py"]:
    p = ROOT / rel
    if not p.exists():
        print(f"  {rel}: ОТСУТСТВУЕТ")
        continue
    txt = p.read_text(encoding="utf-8", errors="replace")
    n_tests = len(re.findall(r"def test_", txt))
    n_at = len(re.findall(r"assert True\b", txt))
    n_pass = len(re.findall(r"^\s+pass\s*$", txt, re.M))
    n_skip = len(re.findall(r"skipif|skip\(", txt))
    print(f"  {rel}: tests={n_tests} assertTrue={n_at} barepass={n_pass} skips={n_skip}")

# ------------------------------------------------------------- D. live smoke L2/L3
hr("D. LIVE SMOKE: DynamicTraceCollector + CodemodRouter (0 сети)")
sys.path.insert(0, str(ROOT))
try:
    from vazus_core.telemetry.dynamic_trace_collector import get_global_trace_collector
    c = get_global_trace_collector()
    c.start()
    def _probe(x):  # пара вызовов под трейсером
        return x * 2
    _probe(21)
    c.stop()
    print(f"  DynamicTraceCollector: start/stop OK, тип={type(c).__name__}")
except Exception as e:
    print(f"  DynamicTraceCollector FAIL: {type(e).__name__}: {e}")
try:
    from vazus_core.codemods.codemod_router import CodemodRouter
    r = CodemodRouter()
    res = r.run_ruff_hygiene("vazus_core/telemetry")
    print(f"  CodemodRouter.run_ruff_hygiene: success={res.get('success')} errors={len(res.get('errors', []))}")
except Exception as e:
    print(f"  CodemodRouter FAIL: {type(e).__name__}: {e}")
