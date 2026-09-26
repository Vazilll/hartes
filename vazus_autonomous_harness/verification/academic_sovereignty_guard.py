"""
vazus_autonomous_harness.verification.academic_sovereignty_guard

Enforces Academic Sovereignty and Socratic Mentoring Invariants (USER.md#L37).
1. STRICTLY FORBIDDEN: Generating direct solutions, answers or completed assignments for student.
2. MANDATORY: Providing Socratic leading questions, conceptual explanations, pointing out logical errors.
"""

import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("vazus.harness.verification.academic")

ACADEMIC_TASK_PATTERNS = [
    re.compile(r"(?i)\b(?:лабораторн\w*|типов\w*\s+расчет\w*|тест\w*\s+сдо|контрольн\w*|экзамен\w*|дз|задани\w*)\b"),
    re.compile(r"(?i)\b(?:сдо|иит|китпипи|ивбо-22-25|25и0566)\b"),
]

DIRECT_SOLUTION_PATTERNS = [
    re.compile(r"(?i)(?:готовое\s+решение|вот\s+готовый\s+код|полный\s+код\s+лабораторной|правильный\s+ответ\s*[:=]\s*[a-d1-4]|вот\s+ответ\s+на\s+тест)"),
    re.compile(r"(?i)(?:спиши\s+это|просто\s+вставь\s+этот\s+код\s+в\s+сдо)"),
]

SOCRATIC_INDICATORS = [
    re.compile(r"(?i)\b(?:подумай|обрати\s+внимание|какой\s+метод|почему|вспомни|как\s+ты\s+считаешь|попробуй|что\s+произойдет)\b"),
    re.compile(r"\?"),  # Direct inquiry symbol
]


class AcademicSovereigntyGuard:
    """
    Evaluates responses and plans against academic sovereignty invariants (USER.md#L37).
    Guarantees student learning autonomy.
    """

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def is_academic_context(self, text: str) -> bool:
        if not text:
            return False
        return any(pat.search(text) for pat in ACADEMIC_TASK_PATTERNS)

    def verify_response(self, prompt: str, response: str) -> Dict[str, Any]:
        """
        Verifies whether an agent's response satisfies Socratic mentoring invariants.
        """
        is_academic = self.is_academic_context(prompt) or self.is_academic_context(response)
        if not is_academic:
            return {
                "allowed": True,
                "is_academic": False,
                "has_socratic_guidance": True,
                "has_direct_solution_leak": False,
                "reason": "Non-academic context: standard operational response permitted.",
                "remediation_hint": None,
            }

        has_direct_leak = any(pat.search(response) for pat in DIRECT_SOLUTION_PATTERNS)
        has_socratic = any(pat.search(response) for pat in SOCRATIC_INDICATORS)

        if has_direct_leak:
            return {
                "allowed": False,
                "is_academic": True,
                "has_socratic_guidance": has_socratic,
                "has_direct_solution_leak": True,
                "reason": "[SOVEREIGNTY VIOLATION] Direct solution dump detected in academic task. "
                          "USER.md#L37 strictly prohibits solving assignments for the student.",
                "remediation_hint": "Reformulate response into Socratic guiding questions and explain underlying principles."
            }

        if not has_socratic and self.strict_mode:
            return {
                "allowed": False,
                "is_academic": True,
                "has_socratic_guidance": False,
                "has_direct_solution_leak": False,
                "reason": "[SOVEREIGNTY WARNING] Academic response lacks Socratic guidance or probing questions.",
                "remediation_hint": "Add leading questions or conceptual explanations to encourage independent student deduction."
            }

        return {
            "allowed": True,
            "is_academic": True,
            "has_socratic_guidance": True,
            "has_direct_solution_leak": False,
            "reason": "Socratic mentoring invariant satisfied (USER.md#L37).",
            "remediation_hint": None,
        }
