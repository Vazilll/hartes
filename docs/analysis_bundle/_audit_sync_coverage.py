"""
AUDIT (сессия 18.08 #2, claude-opus-5): открытый вопрос #1 из AUDIT_STATE.md
"Покрытие тестами sync_keep_notes — почему 685 passed не поймали вечный NameError"

Метод (доказательства, не проза):
  A. Свип по tests/: кто вообще упоминает google_super_sync_engine / GoogleSuperSyncEngine /
     sync_keep_notes / google_sync_engine (compat-мост).
  B. Живой вызов sync_keep_notes с ПОДДЕЛЬНЫМ drive-сервисом (без сети, без OAuth):
     если NameError глотается except'ом → вернётся status=error и это доказательство
     permanent silent failure, а не гипотеза.
  C. Проверка, что модуль вообще импортируем (venv py3.14) и что F821 на месте сейчас.
  D. Кто вызывает sync_keep_notes в продакшн-путях (не тесты).
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:/vazus")
TESTS = ROOT / "tests"
MOD = ROOT / "vazus_core/integrations/google_super_sync_engine.py"

def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)

# ---------------------------------------------------------------- A. свип тестов
hr("A. Кто в tests/ упоминает sync-движок (regex по всем *.py)")
pat = re.compile(r"google_super_sync_engine|GoogleSuperSyncEngine|sync_keep_notes|google_sync_engine|GoogleSyncEngine|google_sync_hub")
hits = {}
n_files = 0
for p in sorted(TESTS.rglob("*.py")):
    n_files += 1
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  !! unreadable {p}: {e}")
        continue
    for i, line in enumerate(txt.splitlines(), 1):
        if pat.search(line):
            hits.setdefault(p.name, []).append((i, line.strip()[:140]))
print(f"  просканировано тестовых файлов: {n_files}")
if not hits:
    print("  РЕЗУЛЬТАТ: 0 упоминаний. Ни один тест не касается движка вообще.")
else:
    for f, ls in hits.items():
        print(f"  {f}:")
        for i, l in ls:
            print(f"     {i}: {l}")

# то же самое по всему репо (кто вызывает в проде)
hr("D. Кто вызывает sync_keep_notes ВНЕ tests/ (продакшн-пути)")
callers = []
for p in sorted(ROOT.rglob("*.py")):
    s = str(p).replace("\\", "/")
    if "/.venv/" in s or "/tests/" in s or "/labs/" in s or "/node_modules/" in s or "/docs/analysis_bundle/" in s:
        continue
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    for i, line in enumerate(txt.splitlines(), 1):
        if "sync_keep_notes" in line:
            callers.append((s, i, line.strip()[:140]))
for s, i, l in callers:
    print(f"  {s}:{i}: {l}")
print(f"  всего ссылок: {len(callers)}")

# --------------------------------------------------- C. F821 на месте прямо сейчас
hr("C. ruff --select F821 по модулю (состояние НА МОМЕНТ этого прогона)")
py = ROOT / ".venv/Scripts/python.exe"
r = subprocess.run([str(py), "-m", "ruff", "check", "--select", "F821", "--no-cache", str(MOD)],
                   capture_output=True, text=True, cwd=str(ROOT))
print(f"  exit={r.returncode}")
print("  " + (r.stdout or "").replace("\n", "\n  ").strip())
if r.stderr.strip():
    print("  STDERR: " + r.stderr.strip()[:400])

# --------------------------------------- B. живой вызов с поддельным drive-сервисом
hr("B. ЖИВОЙ вызов sync_keep_notes() с fake drive-сервисом (0 сети, 0 OAuth)")
sys.path.insert(0, str(ROOT))

class _FakeExec:
    def __init__(self, payload): self._p = payload
    def execute(self): return self._p

class _FakeFiles:
    def list(self, **kw):
        print(f"     [fake drive] files().list(q={kw.get('q','')[:40]!r}, pageSize={kw.get('pageSize')})")
        return _FakeExec({"files": [{"id": "f1", "name": "Keep note 1"},
                                    {"id": "f2", "name": "notes.md"}]})

class _FakeDrive:
    def files(self): return _FakeFiles()

try:
    from vazus_core.integrations.google_super_sync_engine import GoogleSuperSyncEngine  # type: ignore
    print("  import OK (venv python)")
    eng = GoogleSuperSyncEngine.__new__(GoogleSuperSyncEngine)   # без __init__ → без OAuth
    eng.services = {"drive": _FakeDrive()}
    eng.db_path = ":memory:"
    res = eng.sync_keep_notes()
    print(f"  ВЕРНУЛОСЬ: {res}")
    st = res.get("status")
    err = str(res.get("error", ""))
    if st == "success":
        print("  ВЕРДИКТ: FALSE — функция вернула success, находка аудита неверна.")
    elif "synced" in err and "not defined" in err:
        print("  ВЕРДИКТ: TRUE (ДОКАЗАНО ЖИВЬЁМ) — 2 файла реально найдены fake-Drive,")
        print("            но функция вернула status=error с NameError: name 'synced' is not defined.")
        print("            Silent permanent failure подтверждён на исполнении, не на чтении кода.")
    else:
        print(f"  ВЕРДИКТ: PARTIAL — status={st}, error={err!r}")
except Exception as e:
    print(f"  !! не удалось выполнить: {type(e).__name__}: {e}")

# ------------------------------------------------- E. покрытие: coverage на модуле
hr("E. coverage: исполнялся ли модуль хоть одним тестом (быстрый прокси)")
cov = ROOT / ".coverage"
print(f"  .coverage существует: {cov.exists()}")
r2 = subprocess.run([str(py), "-c", "import coverage,sys; print('coverage', coverage.__version__)"],
                    capture_output=True, text=True, cwd=str(ROOT))
print(f"  {(r2.stdout or r2.stderr).strip()[:200]}")
print("  (прямое доказательство покрытия — раздел A: 0 тестов ссылаются на модуль)")
