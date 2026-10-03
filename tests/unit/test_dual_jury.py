"""
Tests for vazus_core.verification.dual_jury — dual_jury_verdict & run_dual_jury_sync.
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch, AsyncMock

from vazus_core.verification.dual_jury import dual_jury_verdict, run_dual_jury_sync


FAKE_FILE = "vazus_core/verification/evidence_jury.py"

_PASS_RESULT = {"verdict": "PASS", "reason": "all checks clean", "llm_calls": 0, "checks": {}}
_FAIL_RESULT = {"verdict": "FAIL", "reason": "syntax error", "llm_calls": 0, "checks": {}}
_UNVERIFIED_RESULT = {"verdict": "UNVERIFIED", "reason": "no targeted tests", "llm_calls": 0, "checks": {}}


class TestDualJuryVerdict:
    def test_jury_a_pass_returns_immediately(self):
        with patch("vazus_core.verification.dual_jury.EvidenceJury.evaluate", return_value=_PASS_RESULT):
            result = asyncio.run(dual_jury_verdict(FAKE_FILE, run_tests=False))

        assert result["verdict"] == "PASS"
        assert result["approved"] is True
        assert result["jury"] == "A"
        assert "jury_b" not in result

    def test_jury_a_fail_returns_immediately(self):
        with patch("vazus_core.verification.dual_jury.EvidenceJury.evaluate", return_value=_FAIL_RESULT):
            result = asyncio.run(dual_jury_verdict(FAKE_FILE, run_tests=False))

        assert result["verdict"] == "FAIL"
        assert result["approved"] is False
        assert result["jury"] == "A"
        assert "jury_b" not in result

    def test_unverified_without_llm_safe_rejection(self):
        with patch("vazus_core.verification.dual_jury.EvidenceJury.evaluate", return_value=_UNVERIFIED_RESULT):
            result = asyncio.run(dual_jury_verdict(FAKE_FILE, allow_llm=False, run_tests=False))

        assert result["verdict"] == "UNVERIFIED"
        assert result["approved"] is False
        assert "jury_b" not in result

    def test_unverified_with_llm_escalates_to_jury_b(self):
        jury_b_result = {"verdict": "PASS", "approved": True, "llm_calls": 1}

        with (
            patch("vazus_core.verification.dual_jury.EvidenceJury.evaluate", return_value=_UNVERIFIED_RESULT),
            patch("vazus_core.verification.critic_jury.evaluate", new=AsyncMock(return_value=jury_b_result)),
            patch("vazus_core.verification.dual_jury._read_file", return_value="def foo(): pass"),
        ):
            result = asyncio.run(dual_jury_verdict(FAKE_FILE, allow_llm=True, run_tests=False))

        assert result["jury"] == "B"
        assert "jury_b" in result
        assert result["llm_calls"] >= 1

    def test_result_always_has_required_fields(self):
        with patch("vazus_core.verification.dual_jury.EvidenceJury.evaluate", return_value=_PASS_RESULT):
            result = asyncio.run(dual_jury_verdict(FAKE_FILE, run_tests=False))

        for field in ("file", "allow_llm", "verdict", "approved", "jury", "reason", "llm_calls"):
            assert field in result, f"Missing field: {field}"


class TestRunDualJurySync:
    def test_sync_wrapper_returns_dict(self):
        with patch("vazus_core.verification.dual_jury.EvidenceJury.evaluate", return_value=_PASS_RESULT):
            result = run_dual_jury_sync(FAKE_FILE, run_tests=False, allow_llm=False)

        assert isinstance(result, dict)
        assert result["verdict"] in ("PASS", "FAIL", "UNVERIFIED")
