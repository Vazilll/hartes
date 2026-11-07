"""
vazus_autonomous_harness.verification - Formal Verification and Quality Evaluation Cores.

Components:
1. QualityEvaluationEngine + QualityScore: 100-point multi-dimensional rubric.
2. ASTParsimonyAnalyzer: AST bloat and clean diff parsimony analyzer.
3. SMTProver + SMTEquivalenceProver: Z3 SMT contract and equivalence theorem prover.
4. AcademicSovereigntyGuard: Socratic guard and zero stub guard.
5. ConcordiaJuryCore + JuryVerdict: Multi-agent consensus jury with Byzantine filtering.
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
