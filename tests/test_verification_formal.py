"""
Tests for Formal Verification & SMT Invariant Cores in vazus_autonomous_harness.verification.
"""

import pytest
from vazus_autonomous_harness.verification.smt_equivalence_prover import SMTEquivalenceProver
from vazus_autonomous_harness.verification.academic_sovereignty_guard import AcademicSovereigntyGuard
from vazus_autonomous_harness.verification.concordia_jury import ConcordiaJuryCore


def test_smt_equivalence_prover_valid_equivalence():
    prover = SMTEquivalenceProver()
    # a * 2 + a * 3 == 5 * a
    res = prover.verify_expression_equivalence("a * 2 + a * 3", "5 * a", ["a"])
    assert res["equivalent"] is True
    assert res["status"] == "PROVEN_EQUIVALENT"


def test_smt_equivalence_prover_disproof_counterexample():
    prover = SMTEquivalenceProver()
    # x + 1 != x + 2
    res = prover.verify_expression_equivalence("x + 1", "x + 2", ["x"])
    assert res["equivalent"] is False
    assert res["status"] == "DISPROVEN"
    assert "counterexample" in res


def test_academic_sovereignty_direct_leak_veto():
    guard = AcademicSovereigntyGuard(strict_mode=True)
    prompt = "Помоги с лабораторной работой по ИВТ"
    bad_response = "Вот готовый код лабораторной: просто вставь этот код в СДО."

    res = guard.verify_response(prompt, bad_response)
    assert res["allowed"] is False
    assert res["has_direct_solution_leak"] is True
    assert "SOVEREIGNTY VIOLATION" in res["reason"]


def test_academic_sovereignty_socratic_allowed():
    guard = AcademicSovereigntyGuard(strict_mode=True)
    prompt = "Помоги с типовым расчетом"
    good_response = "Обрати внимание на метод вычисления определителя. Как ты считаешь, почему здесь возникает нулевая строка?"

    res = guard.verify_response(prompt, good_response)
    assert res["allowed"] is True
    assert res["has_socratic_guidance"] is True
    assert res["has_direct_solution_leak"] is False


def test_academic_sovereignty_non_academic_allowed():
    guard = AcademicSovereigntyGuard(strict_mode=True)
    prompt = "Какая сейчас погода в Москве?"
    response = "На улице около +15 градусов."

    res = guard.verify_response(prompt, response)
    assert res["allowed"] is True
    assert res["is_academic"] is False


def test_concordia_jury_consensus_and_byzantine_filter():
    jury = ConcordiaJuryCore(min_quorum=3, consensus_threshold=0.66)
    code = "def add(a, b): return a + b"

    # 3 honest passing votes
    votes = [
        {"agent": "Planner", "verdict": "PASS", "approved": True, "confidence": 0.85, "reason": "Modular architecture clean"},
        {"agent": "RLM_Coder", "verdict": "PASS", "approved": True, "confidence": 0.90, "reason": "AST logic verified and efficient"},
        {"agent": "Verifier_Worker", "verdict": "PASS", "approved": True, "confidence": 0.95, "reason": "SMT contract invariants hold"},
    ]
    verdict = jury.evaluate_proposal(code, votes)
    assert verdict.approved is True
    assert verdict.consensus_ratio == 1.0
    assert verdict.byzantine_count == 0

    # Inject Byzantine vote: confidence 1.0 with stub reason "ok"
    votes_with_byzantine = [
        {"agent": "Planner", "verdict": "PASS", "approved": True, "confidence": 0.85, "reason": "Modular architecture clean"},
        {"agent": "RLM_Coder", "verdict": "PASS", "approved": True, "confidence": 0.90, "reason": "AST logic verified and efficient"},
        {"agent": "Verifier_Worker", "verdict": "PASS", "approved": True, "confidence": 0.95, "reason": "SMT contract invariants hold"},
        {"agent": "Malicious_Bot", "verdict": "PASS", "approved": True, "confidence": 1.0, "reason": "ok"},
    ]
    verdict2 = jury.evaluate_proposal(code, votes_with_byzantine)
    assert verdict2.byzantine_count == 1
    # Byzantine vote is quarantined, remaining 3 votes still pass
    assert verdict2.approved is True


def test_concordia_jury_dangerous_code_veto():
    jury = ConcordiaJuryCore(min_quorum=3, consensus_threshold=0.66)
    dangerous_code = "import os; os.system('echo dangerous')"
    votes = [
        {"agent": "Planner", "verdict": "PASS", "approved": True, "confidence": 0.85, "reason": "Architecture ok"},
        {"agent": "RLM_Coder", "verdict": "PASS", "approved": True, "confidence": 0.85, "reason": "Logic ok"},
        {"agent": "Verifier", "verdict": "PASS", "approved": True, "confidence": 0.85, "reason": "Contract ok"},
    ]
    verdict = jury.evaluate_proposal(dangerous_code, votes)
    assert verdict.approved is False
    assert any("Dangerous pattern" in r for r in verdict.rejection_reasons)
