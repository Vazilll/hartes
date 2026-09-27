r"""
Unit tests for Confidence-Penalized Weighted Byzantine Fault Tolerance (CP-WBFT).
(arXiv:2605.09076) implemented in ConcordiaJuryCore.

Verifies:
- Receiver-Side MSR Byzantine Outlier Quarantine
- Dynamic Overconfidence Penalty: W_i = w_i * max(0, 1 - lambda * Penalty_overconf)
- Strict >= 2/3 Quorum Requirement (consensus_threshold = 2.0 / 3.0, min_quorum >= 3)
- AST Syntax & Dangerous Primitive Gates
"""

import pytest
from vazus_autonomous_harness.verification.concordia_jury import (
    ConcordiaJuryCore,
    JuryVerdict,
)


def test_cp_wbft_initialization_defaults_and_clamps():
    """Verifies that ConcordiaJuryCore enforces default 2/3 threshold and min_quorum >= 3."""
    jury = ConcordiaJuryCore()
    assert jury.min_quorum >= 3
    assert abs(jury.consensus_threshold - (2.0 / 3.0)) < 1e-6

    # Attempt to set min_quorum < 3 should be clamped to 3
    clamped_jury = ConcordiaJuryCore(min_quorum=1)
    assert clamped_jury.min_quorum == 3


def test_cp_wbft_quorum_enforcement():
    """Verifies that proposals with fewer than min_quorum active votes fail."""
    jury = ConcordiaJuryCore(min_quorum=3)
    code = "def safe_add(a, b): return a + b"

    # Only 2 votes provided (insufficient quorum)
    votes_2 = [
        {"agent": "A1", "verdict": "PASS", "approved": True, "confidence": 0.85, "reason": "Thoroughly tested and verified modular design"},
        {"agent": "A2", "verdict": "PASS", "approved": True, "confidence": 0.90, "reason": "Contract invariants hold for all edge cases"},
    ]
    verdict = jury.evaluate_proposal(code, votes_2)
    assert verdict.quorum_satisfied is False
    assert verdict.approved is False
    assert any("Quorum insufficient: 2/3" in r for r in verdict.rejection_reasons)

    # 3 votes provided (quorum satisfied)
    votes_3 = votes_2 + [
        {"agent": "A3", "verdict": "PASS", "approved": True, "confidence": 0.80, "reason": "Parsimonious code structure and zero bloat"},
    ]
    verdict3 = jury.evaluate_proposal(code, votes_3)
    assert verdict3.quorum_satisfied is True
    assert verdict3.approved is True


def test_cp_wbft_consensus_threshold_two_thirds():
    """
    Verifies that strict 2/3 consensus is required.
    - 2 PASS out of 3 equal votes (ratio = 2/3) -> APPROVED.
    - 2 PASS out of 4 equal votes (ratio = 1/2 < 2/3) -> REJECTED.
    """
    jury = ConcordiaJuryCore(min_quorum=3, consensus_threshold=2.0 / 3.0)
    code = "def multiply(x, y): return x * y"

    # 2 PASS, 1 FAIL with equal confidence and reasoning lengths
    votes_3 = [
        {"agent": "A1", "verdict": "PASS", "approved": True, "confidence": 0.70, "reason": "Acceptable implementation"},
        {"agent": "A2", "verdict": "PASS", "approved": True, "confidence": 0.70, "reason": "Acceptable implementation"},
        {"agent": "A3", "verdict": "FAIL", "approved": False, "confidence": 0.70, "reason": "Acceptable implementation"},
    ]
    v3 = jury.evaluate_proposal(code, votes_3)
    assert v3.quorum_satisfied is True
    assert abs(v3.consensus_ratio - (2.0 / 3.0)) < 1e-4
    assert v3.approved is True

    # 2 PASS, 2 FAIL (ratio = 0.50 < 0.6667)
    votes_4 = votes_3 + [
        {"agent": "A4", "verdict": "FAIL", "approved": False, "confidence": 0.70, "reason": "Acceptable implementation"},
    ]
    v4 = jury.evaluate_proposal(code, votes_4)
    assert v4.consensus_ratio == 0.50
    assert v4.approved is False
    assert any("Consensus ratio" in r for r in v4.rejection_reasons)


def test_cp_wbft_byzantine_msr_outlier_quarantine():
    """
    Verifies that Byzantine outliers (confidence >= 0.99 with terse reasoning < 15 chars)
    are quarantined, excluded from active votes, and assigned zero weight.
    """
    jury = ConcordiaJuryCore(min_quorum=3)
    code = "def valid_code(): return 42"

    raw_votes = [
        {"agent": "A1", "verdict": "PASS", "approved": True, "confidence": 0.85, "reason": "Verified contract specifications sound"},
        {"agent": "A2", "verdict": "PASS", "approved": True, "confidence": 0.90, "reason": "Empirical tests and AST tree confirmed"},
        {"agent": "ByzantineAgent", "verdict": "PASS", "approved": True, "confidence": 1.0, "reason": "ok"},  # Byz: 2 chars
    ]

    filtered = jury.filter_byzantine_votes(raw_votes)
    assert len(filtered) == 3
    byz_vote = next(v for v in filtered if v["agent"] == "ByzantineAgent")
    assert byz_vote.get("quarantined") is True
    assert byz_vote.get("verdict") == "FAIL"
    assert byz_vote.get("effective_weight") == 0.0

    # Because Byz is quarantined, only 2 active votes remain -> Quorum fails!
    verdict = jury.evaluate_proposal(code, raw_votes)
    assert verdict.byzantine_count == 1
    assert verdict.quorum_satisfied is False
    assert verdict.approved is False

    # If we add a 4th honest vote, active votes = 3 -> passes
    raw_votes_4 = raw_votes + [
        {"agent": "A3", "verdict": "PASS", "approved": True, "confidence": 0.88, "reason": "Verified algorithmic complexity optimal"},
    ]
    verdict4 = jury.evaluate_proposal(code, raw_votes_4)
    assert verdict4.byzantine_count == 1
    assert verdict4.quorum_satisfied is True
    assert verdict4.approved is True


def test_cp_wbft_explicit_outlier_quarantine():
    """Verifies that out-of-range confidence or explicit outlier flags are quarantined."""
    jury = ConcordiaJuryCore(min_quorum=3)

    votes = [
        {"agent": "A1", "confidence": -0.5, "reason": "Corrupted agent"},
        {"agent": "A2", "confidence": 1.5, "reason": "Overflowed confidence"},
        {"agent": "A3", "outlier": True, "confidence": 0.8, "reason": "Flagged by SAC anomaly detector"},
        {"agent": "A4", "confidence": 0.8, "reason": "Legitimate honest evaluation"},
    ]
    filtered = jury.filter_byzantine_votes(votes)
    quarantined = [v for v in filtered if v.get("quarantined")]
    assert len(quarantined) == 3


def test_cp_wbft_dynamic_overconfidence_penalty_calculation():
    """
    Verifies the CP-WBFT dynamic overconfidence penalty:
    Penalty_overconf = max(0, conf - 0.70) * (1 / max(1, len(reason)/25))
    W_i = w_i * max(0, 1 - lambda * Penalty_overconf)
    """
    jury = ConcordiaJuryCore()

    # Case 1: Low confidence <= 0.70 incurs zero penalty
    eff_w1, pen1 = jury.compute_cp_wbft_weight(confidence=0.65, reason="Brief", base_weight=0.65)
    assert pen1 == 0.0
    assert abs(eff_w1 - 0.65) < 1e-6

    # Case 2: High confidence (0.95) with extensive justification (50 chars)
    # len/25 = 2.0 -> penalty = (0.95 - 0.70) / 2.0 = 0.125
    # factor = 1 - 0.5 * 0.125 = 0.9375 -> weight = 0.95 * 0.9375 = 0.890625
    reason_50 = "A" * 50
    eff_w2, pen2 = jury.compute_cp_wbft_weight(confidence=0.95, reason=reason_50, base_weight=0.95)
    assert abs(pen2 - 0.125) < 1e-4
    assert abs(eff_w2 - 0.890625) < 1e-4

    # Case 3: High confidence (0.95) with terse justification (15 chars)
    # len/25 = 1.0 (clamped by max(1.0, ...)) -> penalty = (0.95 - 0.70) / 1.0 = 0.25
    # factor = 1 - 0.5 * 0.25 = 0.875 -> weight = 0.95 * 0.875 = 0.83125
    reason_15 = "A" * 15
    eff_w3, pen3 = jury.compute_cp_wbft_weight(confidence=0.95, reason=reason_15, base_weight=0.95)
    assert abs(pen3 - 0.25) < 1e-4
    assert abs(eff_w3 - 0.83125) < 1e-4

    # Substantive reasoning strictly preserves more weight than terse reasoning
    assert eff_w2 > eff_w3


def test_cp_wbft_overconfident_minority_cannot_override_jury():
    """
    Demonstrates CP-WBFT resilience:
    2 honest reviewers reject proposal with substantive reasons.
    1 overconfident reviewer tries to approve with terse reason.
    Consensus ratio fails strict 2/3 requirement -> Proposal rejected.
    """
    jury = ConcordiaJuryCore(min_quorum=3, consensus_threshold=2.0 / 3.0)
    code = "def risky_mutation(): return None"

    votes = [
        {"agent": "Verifier", "verdict": "FAIL", "approved": False, "confidence": 0.85, "reason": "Failed contract preservation invariance across edge cases"},
        {"agent": "Architect", "verdict": "FAIL", "approved": False, "confidence": 0.80, "reason": "Violates architectural separation of concerns and introduces coupling"},
        {"agent": "OverconfidentAgent", "verdict": "PASS", "approved": True, "confidence": 0.95, "reason": "Fine to commit"},  # 15 chars
    ]

    verdict = jury.evaluate_proposal(code, votes)
    assert verdict.approved is False
    assert verdict.consensus_ratio < 0.50


def test_cp_wbft_ast_syntax_and_dangerous_primitives_veto():
    """Verifies that AST syntax error or dangerous system primitives trigger unconditional veto."""
    jury = ConcordiaJuryCore(min_quorum=3)

    # 1. Syntax Error
    broken_code = "def bad_syntax(x: return x +"
    unanimous_pass = [
        {"agent": "A1", "verdict": "PASS", "approved": True, "confidence": 0.9, "reason": "Thoroughly reviewed and approved"},
        {"agent": "A2", "verdict": "PASS", "approved": True, "confidence": 0.9, "reason": "Thoroughly reviewed and approved"},
        {"agent": "A3", "verdict": "PASS", "approved": True, "confidence": 0.9, "reason": "Thoroughly reviewed and approved"},
    ]
    v_syntax = jury.evaluate_proposal(broken_code, unanimous_pass)
    assert v_syntax.ast_valid is False
    assert v_syntax.approved is False
    assert any("SyntaxError" in r for r in v_syntax.rejection_reasons)

    # 2. Dangerous Primitives
    dangerous_code = "import shutil; shutil.rmtree('/tmp')"
    v_danger = jury.evaluate_proposal(dangerous_code, unanimous_pass)
    assert v_danger.ast_valid is False
    assert v_danger.approved is False
    assert any("Dangerous pattern" in r for r in v_danger.rejection_reasons)
