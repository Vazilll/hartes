"""Verify the 3 F821 (undefined name) findings are real, and measure blast radius.

F821 sites found by ruff (which the pre-commit gate does NOT select):
  1. vazus_core/memory/embeddings.py:495   `Dict` undefined
  2. vazus_core/verification/precommit_gate.py:34  `_resolve_workspace_root` used before def
  3. vazus_core/integrations/google_super_sync_engine.py:246  `synced` undefined

For each: is it a latent landmine or a live crash? Read-only probes.
"""
import ast
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, r"C:/vazus")
VENV_PY = r"C:/vazus/.venv/Scripts/python.exe"
print(f"running under: {sys.version.split()[0]}  (venv={VENV_PY})\n")

# ---- 1. embeddings.py: Dict -----------------------------------------------
print("=" * 70)
print("1) embeddings.py:495  `Dict` undefined")
print("=" * 70)
print("PEP 649 (py3.14+) defers annotation evaluation, so module import survives.")
print("Anything that materialises annotations raises NameError. Probes:\n")

probes = {
    "module import": "import vazus_core.memory.embeddings as m; print('ok')",
    "access __annotations__": (
        "import vazus_core.memory.embeddings as m\n"
        "try:\n    m.__annotations__\n    print('ok - no error')\n"
        "except NameError as e:\n    print('NameError:', e)"
    ),
    "typing.get_type_hints(module)": (
        "import typing, vazus_core.memory.embeddings as m\n"
        "try:\n    typing.get_type_hints(m)\n    print('ok - no error')\n"
        "except NameError as e:\n    print('NameError:', e)"
    ),
}
for label, code in probes.items():
    r = subprocess.run([VENV_PY, "-c", code], capture_output=True, text=True, timeout=180)
    out = (r.stdout + r.stderr).strip().splitlines()
    print(f"  [{label}] rc={r.returncode}: {out[-1] if out else '(no output)'}")

# does the repo pin python? which interpreters can run this code?
print("\n  target-version in pyproject.toml: ", end="")
pt = Path(r"C:/vazus/pyproject.toml").read_text(encoding="utf-8")
for line in pt.splitlines():
    if "target-version" in line or "requires-python" in line:
        print(line.strip(), end="  ")
print()
sys_py = subprocess.run(["python", "-V"], capture_output=True, text=True)
print(f"  system `python` on PATH: {sys_py.stdout.strip() or sys_py.stderr.strip()}")
r = subprocess.run(["python", "-c", "import vazus_core"], capture_output=True, text=True, timeout=180)
last = (r.stdout + r.stderr).strip().splitlines()
print(f"  system python `import vazus_core`: rc={r.returncode} -> {last[-1] if last else ''}")

# ---- 2. precommit_gate.py: use-before-def --------------------------------
print("\n" + "=" * 70)
print("2) precommit_gate.py:34  `_resolve_workspace_root` used before its def")
print("=" * 70)
print("  Line 34: VAZUS_ROOT = Path(os.getenv('VAZUS_WORKSPACE_DIR','')) or _resolve_workspace_root()")
print(f"  bool(Path('')) = {bool(Path(''))}   <- Path has no __bool__, always truthy")
print("  => the `or` ALWAYS short-circuits, so the not-yet-defined function is never called.")
r = subprocess.run(
    [VENV_PY, "-c",
     "import vazus_core.verification.precommit_gate as g; print('import ok, VAZUS_ROOT =', g.VAZUS_ROOT)"],
    capture_output=True, text=True, timeout=180,
)
print(f"  live import: rc={r.returncode} -> {(r.stdout + r.stderr).strip().splitlines()[-1]}")
print("  Landmine: if VAZUS_WORKSPACE_DIR handling is ever changed to a str/None,")
print("  line 34 raises NameError and the pre-commit hook dies for every commit.")

# ---- 3. google_super_sync_engine.py: `synced` ------------------------------
print("\n" + "=" * 70)
print("3) google_super_sync_engine.py:246  `synced` undefined in a SUCCESS return")
print("=" * 70)
src = Path(r"C:/vazus/vazus_core/integrations/google_super_sync_engine.py").read_text(encoding="utf-8")
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.lineno <= 246 <= (node.end_lineno or node.lineno):
            fn = node
print(f"  enclosing function: {fn.name}()  lines {fn.lineno}-{fn.end_lineno}")
body_src = "\n".join(src.splitlines()[fn.lineno - 1:fn.end_lineno])
assigns = [n.targets[0].id for n in ast.walk(fn)
           if isinstance(n, ast.Assign) and n.targets and isinstance(n.targets[0], ast.Name)]
print(f"  names assigned inside the function: {sorted(set(assigns))}")
print(f"  'synced' assigned anywhere in the function? {'synced' in assigns}")
print(f"  'synced' assigned anywhere in the module?   {'synced' in [n.targets[0].id for n in ast.walk(tree) if isinstance(n, ast.Assign) and n.targets and isinstance(n.targets[0], ast.Name)]}")
print("  The reference sits INSIDE a try/except Exception -> a live NameError is")
print("  swallowed and reported to the caller as {'status':'error'} — the sync")
print("  function can NEVER return success. Silent permanent failure.")
print("\n  is it reachable / called anywhere?")
r = subprocess.run(["grep", "-rn", f"{fn.name}(", r"C:/vazus/vazus_core", r"C:/vazus/scripts"],
                   capture_output=True, text=True)
for line in (r.stdout or "").splitlines()[:10]:
    print("   ", line.strip())

# ---- 4. WHY the gate misses all of this -----------------------------------
print("\n" + "=" * 70)
print("4) WHY Gate-6 cannot catch these")
print("=" * 70)
gate = Path(r"C:/vazus/vazus_core/verification/precommit_gate.py").read_text(encoding="utf-8")
for line in gate.splitlines():
    if "--select" in line:
        print(f"  gate ruff args : {line.strip()}")
print("  pyproject select: " + next(line.strip() for line in pt.splitlines() if line.strip().startswith("select")))
print("  -> pyproject's \"F\" family INCLUDES F821, but the gate hardcodes only")
print("     F401,F841,E9 and therefore is blind to undefined names.")
print("     `ruff check` by hand finds them; the gate does not.")

print("\n  Does Gate-1 (AST+security) catch undefined names?")
print("  " + "\n  ".join(
    line.strip() for line in gate.splitlines()
    if "def run_gate_1" in line or "ast.parse" in line)[:400])
print("  -> ast.parse only validates SYNTAX; undefined names are semantic. No.")

print("\n== F821 sweep over own code ==")
r = subprocess.run([VENV_PY, "-m", "ruff", "check", "--select", "F821", "--output-format", "concise",
                    "vazus_core", "scripts", "services"],
                   capture_output=True, text=True, cwd=r"C:/vazus", timeout=300)
print(r.stdout.strip() or "(clean)")
