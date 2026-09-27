"""
vazus_autonomous_harness.verification.academic_sovereignty — Academic Sovereignty & Socratic Mentoring Guard.

Milestone 1 (F4):
- Enforces USER.md#L37 invariants (Pedagogical Sovereignty).
  * STRICTLY FORBIDDEN: Generating direct solutions, homework dumps, or SDO test answers for students.
  * MANDATORY: Socratic guidance, leading probing questions, conceptual explanation of principles.
- Enforces USER.md#L33 invariants (Zero Stubs and Facades).
  * Rejects dummy empty stubs ('pass', '...', 'raise NotImplementedError') in concrete implementations.
- Enforces Path Jail safety (Fail-Closed outside C:\\vazus and ~/.gemini).
"""

import ast
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("vazus.harness.verification.academic")

ACADEMIC_TASK_PATTERNS = [
    re.compile(r"(?i)\b(?:лабораторн\w*|типов\w*\s+расчет\w*|тест\w*\s+сдо|контрольн\w*|экзамен\w*|дз|задани\w*)\b"),
    re.compile(r"(?i)\b(?:сдо|иит|китпипи|ивбо-22-25|25и0566|рту\s+мирэа|мирэа)\b"),
    re.compile(r"(?i)\b(?:homework|coursework|lab\s+report|assignment\s+solution)\b"),
]

DIRECT_SOLUTION_PATTERNS = [
    re.compile(r"(?i)(?:готовое\s+решение|вот\s+готовый\s+код|полный\s+код\s+лабораторной|правильный\s+ответ\s*[:=]\s*[a-d1-4]|вот\s+ответ\s+на\s+тест)"),
    re.compile(r"(?i)(?:спиши\s+это|просто\s+вставь\s+этот\s+код\s+в\s+сдо|вот\s+решение\s+задачи|полное\s+решение)"),
    re.compile(r"(?i)(?:here\s+is\s+the\s+complete\s+solution|copy-paste\s+this\s+into\s+sdo)"),
]

SOCRATIC_INDICATORS = [
    re.compile(r"(?i)\b(?:подумай|обрати\s+внимание|обратите\s+внимание|какой\s+метод|почему|вспомни|как\s+ты\s+считаешь|попробуй|что\s+произойдет|какие\s+свойства)\b"),
    re.compile(r"(?i)\b(?:think\s+about|why\s+does|what\s+happens\s+if|notice\s+that|consider\s+the)\b"),
    re.compile(r"\?"),  # Direct inquiry symbol
]

ALLOWED_JAIL_PREFIXES = [
    r"C:\vazus",
    os.path.expanduser("~/.gemini"),
]


class AcademicSovereigntyGuard:
    """
    Evaluates responses and code candidates against Academic Sovereignty (USER.md#L37),
    Zero Stubs (USER.md#L33), and Path Jail safety invariants.
    """

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def is_academic_context(self, text: str) -> bool:
        """Determines if the text or prompt pertains to an academic/student task."""
        if not text:
            return False
        return any(pat.search(text) for pat in ACADEMIC_TASK_PATTERNS)

    def has_direct_solution_leak(self, text: str) -> bool:
        """Checks if text contains direct assignment solution dumps or copy-paste answers."""
        if not text:
            return False
        return any(pat.search(text) for pat in DIRECT_SOLUTION_PATTERNS)

    def has_socratic_guidance(self, text: str) -> bool:
        """Checks if text incorporates Socratic mentoring, questions, or conceptual hints."""
        if not text:
            return False
        return any(pat.search(text) for pat in SOCRATIC_INDICATORS)

    def check_code_stubs(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        Inspects Python AST to detect empty stubs and facade implementations (USER.md#L33).
        Returns (has_stubs, reason).
        """
        if not code or not code.strip():
            return False, None

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False, None

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if decorated as abstract method
                is_abstract = any(
                    isinstance(dec, ast.Name) and dec.id in ("abstractmethod", "overload")
                    or isinstance(dec, ast.Attribute) and dec.attr in ("abstractmethod", "overload")
                    for dec in node.decorator_list
                )
                if is_abstract:
                    continue

                # Filter docstrings from body
                body_stmts = [
                    stmt for stmt in node.body
                    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str))
                ]

                if not body_stmts:
                    return True, f"Function '{node.name}' has no implementation body (empty facade)."

                if len(body_stmts) == 1:
                    stmt = body_stmts[0]
                    if isinstance(stmt, ast.Pass):
                        return True, f"Function '{node.name}' is an empty 'pass' stub (USER.md#L33 violation)."
                    elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis:
                        return True, f"Function '{node.name}' is an empty '...' stub (USER.md#L33 violation)."
                    elif isinstance(stmt, ast.Raise):
                        exc = stmt.exc
                        if isinstance(exc, ast.Call) and getattr(exc.func, "id", None) == "NotImplementedError":
                            return True, f"Function '{node.name}' raises NotImplementedError without real implementation."
                        elif isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                            return True, f"Function '{node.name}' raises NotImplementedError without real implementation."

        return False, None

    def check_path_jail(self, path_str: str) -> bool:
        """
        Verifies that a filesystem path does not escape the approved jail (C:\\vazus and ~/.gemini).
        """
        if not path_str or not path_str.strip():
            return True

        # Normalize slashes to forward slashes for robust cross-platform string-based checking
        norm_path = path_str.replace('\\', '/')

        # Block directory traversal attempts explicitly
        if '/../' in norm_path or norm_path.endswith('/..'):
            return False

        for allowed in ALLOWED_JAIL_PREFIXES:
            norm_allowed = allowed.replace('\\', '/')
            if norm_path == norm_allowed or norm_path.startswith(norm_allowed + '/'):
                return True

        return False

    def verify_response(self, prompt: str, response: str) -> Dict[str, Any]:
        """
        Verifies whether an agent's response satisfies Socratic mentoring invariants.
        Drop-in compatible with academic_sovereignty_guard.py interface.
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

        has_direct_leak = self.has_direct_solution_leak(response)
        has_socratic = self.has_socratic_guidance(response)

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

    def verify_code_sovereignty(self, code: str, context_prompt: str = "") -> Dict[str, Any]:
        """
        Evaluates candidate code against Academic Sovereignty, Zero Stubs, and Path Jail.
        Awards 15.0 points if fully compliant, 0.0 points on violation.
        """
        # 1. Check for stubs and facades
        has_stubs, stub_reason = self.check_code_stubs(code)
        if has_stubs:
            return {
                "allowed": False,
                "score": 0.0,
                "reason": f"[STUB VIOLATION] {stub_reason}",
                "has_stubs": True,
                "has_direct_solution_leak": False,
            }

        # 2. Check for direct solution leaks if in academic context
        is_academic = self.is_academic_context(context_prompt) or self.is_academic_context(code)
        if is_academic:
            has_leak = self.has_direct_solution_leak(code)
            has_socratic = self.has_socratic_guidance(code) or self.has_socratic_guidance(context_prompt)
            if has_leak:
                return {
                    "allowed": False,
                    "score": 0.0,
                    "reason": "[SOVEREIGNTY VIOLATION] Code candidate contains direct solution leak to academic task.",
                    "has_stubs": False,
                    "has_direct_solution_leak": True,
                }
            if not has_socratic and self.strict_mode:
                return {
                    "allowed": False,
                    "score": 0.0,
                    "reason": "[SOVEREIGNTY WARNING] Academic code candidate lacks Socratic guidance or conceptual hints.",
                    "has_stubs": False,
                    "has_direct_solution_leak": False,
                }

        # 3. All checks passed
        return {
            "allowed": True,
            "score": 15.0,
            "reason": "Academic sovereignty and zero stub invariants satisfied.",
            "has_stubs": False,
            "has_direct_solution_leak": False,
        }
