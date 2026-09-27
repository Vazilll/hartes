"""
vazus_autonomous_harness.academic — Academic Debt Navigation & DC Circuit Socratic Tutor.

Milestone 7 (F18, F19):
- F18: 18-Debt Academic Navigator cross-referencing vazus.db, STUDY.md, and real_retake_schedule.xlsx.
- F19: Semester 3 Stage 1 DC Circuit Socratic Tutor under strict USER.md#L37 pedagogical sovereignty.
"""

from .debt_navigator import AcademicDebtItem, AcademicDebtNavigator
from .dc_circuit_tutor import DCCircuitSocraticTutor

__all__ = [
    "AcademicDebtItem",
    "AcademicDebtNavigator",
    "DCCircuitSocraticTutor",
]
