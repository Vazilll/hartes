"""
vazus_autonomous_harness.verification — Formal Verification & SMT Invariant Cores.

Core Components:
1. SMTEquivalenceProver: Proves mathematical equivalence ∀ x: f_old(x) == f_new(x) via Z3.
2. AcademicSovereigntyGuard: Enforces Socratic mentoring and prevents direct solution leaks (USER.md#L37).
3. ConcordiaJuryCore: 3-subagent consensus jury with MSR Byzantine anomaly filtering.
"""

from vazus_autonomous_harness.verification.smt_equivalence_prover import SMTEquivalenceProver
from vazus_autonomous_harness.verification.academic_sovereignty_guard import AcademicSovereigntyGuard
from vazus_autonomous_harness.verification.concordia_jury import ConcordiaJuryCore, JuryVerdict

__all__ = [
    "SMTEquivalenceProver",
    "AcademicSovereigntyGuard",
    "ConcordiaJuryCore",
    "JuryVerdict",
]
