"""
vazus_autonomous_harness.engine — Anti-Thrashing Circuit Breaker & Human Escalation Gate.

Subsystem for Milestone 3 (F8, F9):
- F8: Anti-Thrashing Circuit Breaker (anti_thrashing.py)
- F9: Human Escalation Diagnostic Briefing (escalation_gate.py)
"""

from vazus_autonomous_harness.engine.anti_thrashing import (
    AntiThrashingCircuitBreaker,
    TaskAttempt,
    compute_ast_hash,
    normalize_ast,
)
from vazus_autonomous_harness.engine.escalation_gate import (
    EscalationBriefingGenerator,
    HumanDecisionFork,
    HumanEscalationGate,
)

__all__ = [
    "AntiThrashingCircuitBreaker",
    "TaskAttempt",
    "compute_ast_hash",
    "normalize_ast",
    "EscalationBriefingGenerator",
    "HumanDecisionFork",
    "HumanEscalationGate",
]
