"""Live fail-injection probe: does EvidenceJury actually block bad code?

Creates temp files with known violations and asserts the jury FAILs them.
Nothing is committed; temp files are removed at the end.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "C:/vazus")
from vazus_core.verification.evidence_jury import EvidenceJury  # noqa: E402

CASES = {
    "os_system": "import os\ndef run(c):\n    os.system(c)\n",
    "shell_true": "import subprocess\ndef run(c):\n    subprocess.run(c, shell=True)\n",
    "hardcoded_key": 'api_key = "AIzaSy' + "A" * 33 + '"\n',
    "syntax_error": "def broken(:\n    pass\n",
    "clean_code": "def add(a, b):\n    return a + b\n",
}

tmpdir = Path(tempfile.mkdtemp(prefix="vazus_audit_"))
jury = EvidenceJury()
print(f"{'CASE':<16} {'VERDICT':<12} REASON")
print("-" * 78)
results = {}
for name, src in CASES.items():
    # Name must not contain gate/verif/jury/evidence/guardrail (security scan is
    # skipped for those, per evidence_jury.py:120) — use neutral module names.
    fp = tmpdir / f"probe_{name}.py"
    fp.write_text(src, encoding="utf-8")
    res = jury.evaluate(fp, run_tests=False)
    results[name] = res["verdict"]
    print(f"{name:<16} {res['verdict']:<12} {str(res.get('reason'))[:52]}")

print()
expected_fail = ["os_system", "shell_true", "hardcoded_key", "syntax_error"]
blocked = [n for n in expected_fail if results.get(n) == "FAIL"]
missed = [n for n in expected_fail if results.get(n) != "FAIL"]
print(f"BLOCKED  ({len(blocked)}/{len(expected_fail)}): {blocked}")
print(f"MISSED   ({len(missed)}): {missed}")
print(f"clean_code verdict: {results.get('clean_code')} (expected UNVERIFIED - no tests)")
print()
print("GATE EFFECTIVENESS:", "PASS - blocks all injected violations" if not missed
      else f"PARTIAL - {missed} slipped through")

for f in tmpdir.glob("*"):
    f.unlink()
tmpdir.rmdir()
