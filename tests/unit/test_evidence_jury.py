"""Tests for the dual-jury verification system (Jury-A evidence + Jury-B critic).

Jury-A is deterministic and offline — these tests run without any LLM.
"""

import os
import sys
import tempfile

sys.path.insert(0, "C:/vazus")

from vazus_core.verification.concordia_jury import is_mock_response  # noqa: E402
from vazus_core.verification.evidence_jury import EvidenceJury  # noqa: E402
from vazus_core.verification.critic_jury import _parse_critic_verdict  # noqa: E402


def _tmp_py(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ── Mock detector ────────────────────────────────────────────────────────

def test_mock_detector_true_cases():
    assert is_mock_response("[MOCK] Mock LLM generation response (VAZUS_TEST_MODE=1).")
    assert is_mock_response('{"approved": true, "reason": "looks fine (Test Mode)"}')


def test_mock_detector_false_cases():
    assert not is_mock_response("Real analysis: the code looks fine.")
    assert not is_mock_response("")
    assert not is_mock_response(None)  # type: ignore[arg-type]


# ── Jury-A verdicts ──────────────────────────────────────────────────────

def test_evidence_jury_fails_on_syntax_error():
    p = _tmp_py("def broken(:\n    return 1\n")
    try:
        res = EvidenceJury().evaluate(p, run_tests=False)
    finally:
        os.unlink(p)
    assert res["verdict"] == "FAIL"
    assert "SyntaxError" in res["reason"]


def test_evidence_jury_fails_on_os_system():
    p = _tmp_py("import os\ndef f():\n    os.system('dir')\n")
    try:
        res = EvidenceJury().evaluate(p, run_tests=False)
    finally:
        os.unlink(p)
    assert res["verdict"] == "FAIL"
    assert "os.system" in res["reason"]


def test_evidence_jury_unverified_without_tests():
    p = _tmp_py("def add(a, b):\n    return a + b\n")
    try:
        res = EvidenceJury().evaluate(p, run_tests=True)
    finally:
        os.unlink(p)
    assert res["verdict"] == "UNVERIFIED"
    assert res["llm_calls"] == 0


def test_evidence_jury_verification_modules_skip_security():
    # EvidenceJury on itself must not self-match the pattern literals.
    res = EvidenceJury().evaluate("vazus_core/verification/evidence_jury.py", run_tests=False)
    assert res["checks"]["security"] == "SKIPPED (verification module)"
    assert res["verdict"] in ("PASS", "UNVERIFIED")  # never FAIL on its own regexes


def test_evidence_jury_passes_with_targeted_tests():
    # code_content (no contracts → NO_CONTRACTS) + real targeted tests = PASS.
    res = EvidenceJury().evaluate(
        "vazus_core/verification/smt_z3_verifier.py",
        code_content="def add(a, b):\n    return a + b\n",
        run_tests=True,
    )
    assert res["verdict"] == "PASS", res
    assert res["checks"]["pytest"]["failed"] == 0


# ── Jury-B verdict parsing (offline, no LLM) ─────────────────────────────

def test_critic_parse_confirm():
    assert _parse_critic_verdict('{"verdict": "CONFIRM", "issue": ""}') == "CONFIRM"


def test_critic_parse_contradict():
    assert _parse_critic_verdict('{"verdict": "CONTRADICT", "issue": "sql injection"}') == "CONTRADICT"


def test_critic_parse_garbage_abstains():
    assert _parse_critic_verdict("no idea what to say") == "ABSTAIN"


def test_critic_extract_issue_from_fenced_json():
    from vazus_core.verification.critic_jury import _extract_issue
    raw = '```json\n{"verdict": "CONTRADICT", "issue": "os.system call at line 3"}\n```'
    assert "os.system" in _extract_issue(raw)
    assert _extract_issue("not json") == ""


# ── Jury-B batch mode (offline, no LLM) ──────────────────────────────────

def test_critic_batch_parse_full():
    from vazus_core.verification.critic_jury import _parse_batch_verdicts
    raw = '{"files": {"a.py": {"verdict": "CONFIRM", "issue": ""}, "b.py": {"verdict": "CONTRADICT", "issue": "os.system call"}}}'
    out = _parse_batch_verdicts(raw, ["a.py", "b.py"])
    assert out["a.py"]["verdict"] == "CONFIRM"
    assert out["b.py"]["verdict"] == "CONTRADICT"
    assert "os.system" in out["b.py"]["issue"]


def test_critic_batch_parse_missing_file_abstains():
    from vazus_core.verification.critic_jury import _parse_batch_verdicts
    out = _parse_batch_verdicts('{"files": {}}', ["x.py"])
    assert out["x.py"]["verdict"] == "ABSTAIN"
    assert out["x.py"]["issue"]


def test_critic_batch_prompt_truncates_long_code():
    from vazus_core.verification.critic_jury import _build_batch_prompt, BATCH_TOTAL_BUDGET
    prompt = _build_batch_prompt([{"path": "big.py", "proposal": "x = 1\n" * 5000, "evidence": "{}"}])
    assert "TRUNCATED" in prompt
    assert len(prompt) < BATCH_TOTAL_BUDGET + 2000  # prompt stays bounded
