"""
Unit tests for Concordia Multi-Agent Jury Engine with 3-Subagent Voting (Milestone M1).
"""

import pytest
from vazus_core.concordia_jury import ConcordiaJury, SOTA2027JuryEngine, JuryVerdict


def test_concordia_jury_unanimous_pass():
    """Verify ConcordiaJury approves proposals with unanimous subagent consensus (3/3 = 100%)."""
    jury = ConcordiaJury(consensus_threshold=0.66, min_quorum=3)
    proposal = """
def add_positive(a: int, b: int) -> int:
    \"\"\"
    :requires: a >= 0 and b >= 0
    :ensures: result >= 0
    \"\"\"
    return a + b
"""
    votes = [
        {"agent": "Planner", "verdict": "PASS"},
        {"agent": "RLM_Coder", "verdict": "PASS"},
        {"agent": "Verifier", "verdict": "PASS"},
    ]
    verdict = jury.vote(proposal=proposal, votes=votes)
    assert verdict.approved is True
    assert verdict.consensus_ratio == 1.0
    assert verdict.quorum_satisfied is True
    assert verdict.ast_valid is True
    assert verdict.smt_satisfied is True


def test_concordia_jury_2_of_3_pass():
    """Verify ConcordiaJury approves proposals meeting >= 66% threshold (2/3 = 66.7%)."""
    jury = ConcordiaJury(consensus_threshold=0.66, min_quorum=3)
    proposal = "def compute(x): return x * 2"
    votes = [
        {"agent": "Planner", "verdict": "PASS"},
        {"agent": "RLM_Coder", "verdict": "PASS"},
        {"agent": "Verifier", "verdict": "FAIL"},
    ]
    verdict = jury.vote(proposal=proposal, votes=votes)
    assert verdict.approved is True
    assert verdict.consensus_ratio >= 0.66
    assert verdict.quorum_satisfied is True


def test_concordia_jury_rejection_below_threshold():
    """Verify ConcordiaJury rejects proposals falling below consensus threshold (1/3 = 33.3%)."""
    jury = ConcordiaJury(consensus_threshold=0.66, min_quorum=3)
    proposal = "def compute(x): return x"
    votes = [
        {"agent": "Planner", "verdict": "PASS"},
        {"agent": "RLM_Coder", "verdict": "FAIL"},
        {"agent": "Verifier", "verdict": "FAIL"},
    ]
    verdict = jury.vote(proposal=proposal, votes=votes)
    assert verdict.approved is False
    assert verdict.consensus_ratio < 0.66
    assert len(verdict.rejection_reasons) > 0


def test_concordia_jury_ast_syntax_failure():
    """Verify ConcordiaJury rejects proposals with AST syntax errors."""
    jury = ConcordiaJury()
    proposal = "def broken_func(x) return x +"
    votes = [
        {"agent": "Planner", "verdict": "PASS"},
        {"agent": "RLM_Coder", "verdict": "PASS"},
        {"agent": "Verifier", "verdict": "PASS"},
    ]
    verdict = jury.vote(proposal=proposal, votes=votes)
    assert verdict.approved is False
    assert verdict.ast_valid is False
    assert any("AST SyntaxError" in r for r in verdict.rejection_reasons)


def test_concordia_jury_verdict_dict_access():
    """Verify JuryVerdict subscript access, get(), and to_dict() conversion."""
    verdict = JuryVerdict(
        approved=True,
        consensus_ratio=1.0,
        quorum_satisfied=True,
        ast_valid=True,
        smt_satisfied=True,
        votes=[],
        rejection_reasons=[],
    )
    assert verdict["approved"] is True
    assert verdict.get("consensus_ratio") == 1.0
    to_d = verdict.to_dict()
    assert isinstance(to_d, dict)
    assert to_d["approved"] is True
