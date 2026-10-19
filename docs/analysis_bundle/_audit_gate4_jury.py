"""Gate-4 (Critic Jury / Concordia) fail-injection audit — ZERO real LLM calls.

Claim under test (bundle): "Gate 4 is fail-closed: mock/error/ABSTAIN is NOT
approval, any CONTRADICT rejects."

Method: patch llm_client.async_generate_llm with injected critic replies and
drive the REAL evaluate_batch / run_gate_4_concordia_jury code paths. Nothing
leaves the machine; IDE quota untouched.

Cases:
  A mock reply (quota fallback)      -> expect ABSTAIN, approved=False
  B LLM raises                       -> expect ABSTAIN, approved=False
  C both critics CONFIRM             -> expect CONFIRM, approved=True
  D one CONTRADICT                   -> expect REJECT, approved=False
  E garbage / unparsable reply       -> expect ABSTAIN, approved=False
  F verdict for a DIFFERENT path     -> expect ABSTAIN (no silent approval)
  G split CONFIRM + ABSTAIN          -> expect ABSTAIN (unanimity required)
  H real gate wrapper blocks on mock -> run_gate_4_concordia_jury ok=False
"""
import asyncio
import os
import sys

sys.path.insert(0, r"C:/vazus")
# make sure we are NOT in test mode for the wrapper checks unless a case wants it
os.environ.pop("VAZUS_TEST_MODE", None)
os.environ.pop("PYTEST_CURRENT_TEST", None)

from pathlib import Path  # noqa: E402

from vazus_core.engine import llm_client  # noqa: E402
from vazus_core.verification import critic_jury  # noqa: E402
from vazus_core.verification.concordia_jury import MOCK_MARKERS, is_mock_response  # noqa: E402

ITEM = {
    "path": "vazus_core/dummy_probe.py",
    "proposal": "def add(a, b):\n    return a + b\n",
    "evidence": '{"verdict": "UNVERIFIED", "reasons": ["no tests discovered"]}',
}

results = []


def check(case, got_verdict, got_approved, want_verdict, want_approved, note=""):
    ok = (got_verdict == want_verdict) and (got_approved is want_approved)
    results.append((case, ok, f"got {got_verdict}/approved={got_approved} want {want_verdict}/{want_approved} {note}"))
    print(f"[{'PASS' if ok else 'FAIL'}] {case}: got={got_verdict} approved={got_approved} "
          f"(want {want_verdict}/{want_approved}) {note}", flush=True)


def run_with(replies, item=ITEM):
    """Drive the REAL evaluate_batch with a scripted async_generate_llm."""
    calls = {"n": 0}

    async def fake(prompt, system_prompt="", model="", temperature=0.0, **kw):
        i = calls["n"]
        calls["n"] += 1
        r = replies[i % len(replies)]
        if isinstance(r, Exception):
            raise r
        return r

    orig = llm_client.async_generate_llm
    llm_client.async_generate_llm = fake
    try:
        res = asyncio.run(critic_jury.evaluate_batch([item]))
    finally:
        llm_client.async_generate_llm = orig
    v = res["verdicts"][item["path"]]
    return v, res, calls["n"]


def verdict_json(path, verdict, issue="x"):
    return '{"files": {"%s": {"verdict": "%s", "issue": "%s"}}}' % (path, verdict, issue)


print("== MOCK MARKERS ==")
print(MOCK_MARKERS)
mock_text = llm_client._generate_mock_response("p", "s")
print(f"llm_client mock text: {mock_text!r} -> is_mock_response={is_mock_response(mock_text)}")
results.append(("mock-detector recognises llm_client mock", is_mock_response(mock_text), mock_text))
print()

# ---- A: mock reply (the quota-fallback scenario) -------------------------
v, res, n = run_with([mock_text, mock_text])
check("A mock reply", v["verdict"], v["approved"], "ABSTAIN", False, f"llm_calls={res['llm_calls']} issue={v['issue'][:40]!r}")

# ---- B: LLM raises ------------------------------------------------------
v, res, n = run_with([RuntimeError("429 quota exhausted"), RuntimeError("429 quota exhausted")])
check("B LLM raises", v["verdict"], v["approved"], "ABSTAIN", False, f"issue={v['issue'][:40]!r}")

# ---- C: both CONFIRM (positive control - gate must be able to pass) -----
ok_reply = verdict_json(ITEM["path"], "CONFIRM", "looks fine")
v, res, n = run_with([ok_reply, ok_reply])
check("C both CONFIRM", v["verdict"], v["approved"], "CONFIRM", True)

# ---- D: one CONTRADICT --------------------------------------------------
bad = verdict_json(ITEM["path"], "CONTRADICT", "unsafe eval")
v, res, n = run_with([ok_reply, bad])
check("D one CONTRADICT", v["verdict"], v["approved"], "REJECT", False)

# ---- E: garbage reply ---------------------------------------------------
v, res, n = run_with(["I think the code is good, ship it!", "LGTM"])
check("E garbage reply", v["verdict"], v["approved"], "ABSTAIN", False)

# ---- F: verdict keyed to a DIFFERENT path -------------------------------
wrong = verdict_json("some/other/file.py", "CONFIRM", "approved elsewhere")
v, res, n = run_with([wrong, wrong])
check("F wrong-path verdict", v["verdict"], v["approved"], "ABSTAIN", False)

# ---- G: split CONFIRM + ABSTAIN ----------------------------------------
abst = verdict_json(ITEM["path"], "ABSTAIN", "not sure")
v, res, n = run_with([ok_reply, abst])
check("G split CONFIRM+ABSTAIN", v["verdict"], v["approved"], "ABSTAIN", False)

# ---- H: real gate wrapper on a real staged-like file, mock LLM ----------
print("\n== H: run_gate_4_concordia_jury (real wrapper, mocked LLM) ==")
probe = Path(r"C:/vazus/vazus_core/_audit_gate4_probe.py")
probe.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
try:
    from vazus_core.verification import precommit_gate

    async def fake_mock(prompt, system_prompt="", model="", temperature=0.0, **kw):
        return mock_text

    orig = llm_client.async_generate_llm
    llm_client.async_generate_llm = fake_mock
    try:
        ok, errs = precommit_gate.run_gate_4_concordia_jury([probe])
    finally:
        llm_client.async_generate_llm = orig
    print(f"  ok={ok} errors={errs}")
    good = (ok is False) and any("ABSTAIN" in e or "abstention" in e or "mock" in e for e in errs)
    results.append(("H gate wrapper blocks on mock LLM", good, f"ok={ok} errs={errs}"))
    print(f"[{'PASS' if good else 'FAIL'}] H gate wrapper blocks on mock LLM (ok must be False)")
finally:
    probe.unlink(missing_ok=True)

print("\n===== SUMMARY =====")
passed = sum(1 for _, ok, _ in results if ok)
for name, ok, detail in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
print(f"\n{passed}/{len(results)} checks passed")
print("REAL LLM CALLS MADE: 0 (async_generate_llm patched in every case)")
sys.exit(0 if passed == len(results) else 1)
