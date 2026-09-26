"""
vazus_autonomous_harness.verification — Formal Verification & Quality Evaluation Cores.

Milestone 1 Components:
1. QualityEvaluationEngine & QualityScore: 100-point multi-dimensional rubric (F1).
2. ASTParsimonyAnalyzer: AST bloat and clean diff parsimony analyzer (F3).
3. SMTProver & SMTEquivalenceProver: Microsoft Z3 SMT contract and equivalence theorem prover (F2).
4. AcademicSovereigntyGuard: USER.md#L37 Socratic guard and USER.md#L33 zero stub guard (F4).
5. ConcordiaJuryCore & JuryVerdict: Multi-agent consensus jury with Byzantine filtering.
"""

from vazus_autonomous_harness.verification.smt_prover import SMTProver, SMTProofResult, SMTEquivalenceProver
from vazus_autonomous_harness.verification.academic_sovereignty import AcademicSovereigntyGuard
from vazus_autonomous_harness.verification.quality_engine import (
    QualityEvaluationEngine,
    QualityScore,
    ASTParsimonyAnalyzer,
)
from vazus_autonomous_harness.verification.concordia_jury import ConcordiaJuryCore, JuryVerdict

__all__ = [
    "QualityEvaluationEngine",
    "QualityScore",
    "ASTParsimonyAnalyzer",
    "SMTProver",
    "SMTProofResult",
    "SMTEquivalenceProver",
    "AcademicSovereigntyGuard",
    "ConcordiaJuryCore",
    "JuryVerdict",
]
