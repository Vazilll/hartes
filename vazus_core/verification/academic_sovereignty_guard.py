#!/usr/bin/env python3
"""
vazus_core.verification.academic_sovereignty_guard — Academic Sovereignty & Socratic Tutor Guardrail.

Strictly enforces USER.md#L37:
- FORBIDDEN: Solving homework, laboratories, tests, and typical calculations for the student.
- REQUIRED: Socratic mentoring — guiding questions, theoretical explanations, pointing out errors.
"""

import logging
import re
from typing import Any, Dict

logger = logging.getLogger("vazus.academic_sovereignty")

# Keywords that indicate academic evaluation tasks
ACADEMIC_TASK_PATTERNS = [
    re.compile(r"(?i)\b(?:лабораторн\w*|типов\w*\s+расчет\w*|тест\w*\s+сдо|контрольн\w*|экзамен\w*|дз|задани\w*)\b"),
    re.compile(r"(?i)\b(?:сдо|иит|китпипи|ивбо-22-25|25и0566)\b"),
]

# Markers of direct complete solution dumps
DIRECT_SOLUTION_PATTERNS = [
    re.compile(
        r"(?i)(?:готовое\s+решение|вот\s+готовый\s+код|полный\s+код\s+лабораторной|правильный\s+ответ\s*[:=]\s*[a-d1-4]|вот\s+ответ\s+на\s+тест)"
    ),
    re.compile(r"(?i)(?:спиши\s+это|просто\s+вставь\s+этот\s+код\s+в\s+сдо)"),
]

# Markers of Socratic mentoring (guiding questions, reflective prompts)
SOCRATIC_INDICATORS = [
    re.compile(
        r"(?i)\b(?:подумай|обрати\s+внимание|какой\s+метод|почему|вспомни|как\s+ты\s+считаешь|попробуй|что\s+произойдет|как\s+ты\s+думаешь|в\s+чем\s+причина|каков\s+смысл|проанализируй|сформулируй)\b"
    ),
    re.compile(r"(?i)\b(?:what\s+(?:would|happens|is\s+the)|why\s+does|how\s+would\s+you|think\s+about|consider)\b"),
]


class AcademicSovereigntyGuard:
    """
    Evaluates agent proposals against academic sovereignty invariants (USER.md#L37).
    Guarantees that student learning autonomy is preserved.
    """

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def is_academic_context(self, context_or_prompt: str) -> bool:
        """Returns True if the context relates to academic coursework/testing."""
        if not context_or_prompt:
            return False
        return any(pat.search(context_or_prompt) for pat in ACADEMIC_TASK_PATTERNS)

    def verify_response(self, prompt: str, response: str) -> Dict[str, Any]:
        """
        Verifies whether an agent's response satisfies Socratic mentoring invariants.
        Returns:
            {
                "allowed": bool,
                "is_academic": bool,
                "has_socratic_guidance": bool,
                "has_direct_solution_leak": bool,
                "reason": str,
                "remediation_hint": Optional[str]
            }
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

        # Check for direct solution leaks
        has_direct_leak = any(pat.search(response) for pat in DIRECT_SOLUTION_PATTERNS)

        # Detect executable code dumps in academic context (functions, computations)
        has_code_dump = False
        code_blocks = re.findall(r"```(?:python|py|cpp|c|java|go|rust)?\s*\n(.*?)\n```", response, re.DOTALL)
        for block in code_blocks:
            lines = [line.strip() for line in block.strip().splitlines() if line.strip() and not line.strip().startswith("#")]
            if len(lines) >= 8 or any(re.search(r"\bdef\s+\w+\s*\(.*?\):", l) for l in lines):
                has_code_dump = True
                break

        # Check for Socratic inquiry markers
        has_socratic = any(pat.search(response) for pat in SOCRATIC_INDICATORS)

        if has_direct_leak or has_code_dump:
            return {
                "allowed": False,
                "is_academic": True,
                "has_socratic_guidance": has_socratic,
                "has_direct_solution_leak": True,
                "reason": "[SOVEREIGNTY VIOLATION] Direct solution dump detected in academic task. "
                "USER.md#L37 strictly prohibits solving assignments for the student.",
                "remediation_hint": "Reformulate response into Socratic guiding questions and explain underlying principles.",
            }

        if not has_socratic and self.strict_mode:
            # If academic but has zero questions or guiding cues
            return {
                "allowed": False,
                "is_academic": True,
                "has_socratic_guidance": False,
                "has_direct_solution_leak": False,
                "reason": "[SOVEREIGNTY WARNING] Academic response lacks Socratic guidance or probing questions.",
                "remediation_hint": "Add leading questions or conceptual explanations to encourage independent student deduction.",
            }

        return {
            "allowed": True,
            "is_academic": True,
            "has_socratic_guidance": True,
            "has_direct_solution_leak": False,
            "reason": "Socratic mentoring invariant satisfied (USER.md#L37).",
            "remediation_hint": None,
        }
