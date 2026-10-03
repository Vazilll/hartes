"""
labs.deepmind.alphaproof_socratic.engine
=========================================
AlphaProof-Inspired Socratic Tutoring Engine for RTU MIREA Curriculum (18 Debts).
Strictly adheres to USER.md#L37:
- FORBIDDEN: Solving homework, laboratories, tests, and typical calculations for the student.
- MANDATORY: Socratic method only — guiding questions, theoretical intuition, decomposition hints,
  and pointing out conceptual errors in the student's reasoning.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from vazus_core.verification.academic_sovereignty_guard import AcademicSovereigntyGuard

logger = logging.getLogger("labs.deepmind.alphaproof_socratic.engine")

SUBJECT_THEORY_GUIDES = {
    "математический анализ": [
        "Теорема Коши о промежуточных значениях",
        "Интегрирование по частям и замена переменной",
        "Критерий сходимости числовых и степенных рядов Даламбера и Коши",
    ],
    "программирование": [
        "Инварианты циклов и сложность O(n log n)",
        "Управление ресурсами и RAII",
        "Разделение ответственности и чистые функции",
    ],
    "теория информации": [
        "Энтропия Шеннона и избыточность алфавита",
        "Неравенство Крафта-Макмиллана для префиксных кодов",
        "Теорема Шеннона о кодировании для канала с шумом",
    ],
    "дискретная математика": [
        "Принцип математической индукции и инварианты графов",
        "Теорема Эйлера о планарности графов",
        "Булевы функции и функциональная полнота (теорема Поста)",
    ],
}


class SocraticProofEngine:
    """
    AlphaProof Socratic Tutor.
    Deconstructs student academic questions into deductive hints without revealing complete answers.
    """

    FORBIDDEN_ACTIONS = [
        "provide_solution",
        "complete_lab_work",
        "solve_test_question",
        "write_homework",
        "write_complete_code",
    ]

    def __init__(self, llm_engine: Optional[Any] = None, strict_sovereignty: bool = True):
        self.llm = llm_engine
        self.guard = AcademicSovereigntyGuard(strict_mode=strict_sovereignty)

    def classify_question_type(self, question: str) -> str:
        """Categorizes input into assignment task vs theoretical question."""
        q_lower = question.lower()
        if any(term in q_lower for term in ("лабораторн", "типовой расчет", "тест", "сдо", "дз", "задача", "реши", "напиши код")):
            return "assignment_task"
        return "pure_theory"

    async def guide(self, student_question: str, subject: str = "Высшая математика") -> str:
        """
        Processes student question and produces strictly Socratic pedagogical guidance.
        Guarantees zero violation of USER.md#L37.
        """
        q_type = self.classify_question_type(student_question)

        # 1. Theoretical queries: explain theoretical concepts
        if q_type == "pure_theory":
            return self._explain_theoretical_concept(student_question, subject)

        # 2. Assignment / homework queries: Socratic guidance only
        return await self._generate_socratic_guidance(student_question, subject)

    async def _generate_socratic_guidance(self, question: str, subject: str) -> str:
        """Constructs guiding inquiry decomposition without ready solutions."""
        subject_lower = subject.lower()
        relevant_theorems = []
        for s_key, theorems in SUBJECT_THEORY_GUIDES.items():
            if s_key in subject_lower:
                relevant_theorems = theorems
                break

        theorem_hint = f"\n💡 Релевантная теоретическая база: {', '.join(relevant_theorems)}" if relevant_theorems else ""

        # Socratic questions tailored to mathematical / computational thinking
        guidance = (
            f"🎓 [Сократический наставник МИРЭА — {subject}]:\n\n"
            f"Я не решаю задания за тебя (USER.md#L37), но помогу тебе самому прийти к верному доказательству.{theorem_hint}\n\n"
            f"Давай разложим задачу по шагам:\n"
            f"1. **Каковы начальные условия и инвариант?** Какое утверждение должно оставаться истинным на каждом шаге?\n"
            f"2. **Какой метод здесь применим?** Рассмотри: можно ли свести это к базовой теореме или применить метод от противного?\n"
            f"3. **Какой твой первый шаг?** Напиши, с чего ты начал рассуждение, и где именно возник затык — я укажу на ошибку в логике.\n"
        )

        # Verify compliance through Sovereignty Guard
        audit = self.guard.verify_response(prompt=question, response=guidance)
        if not audit.get("allowed", True):
            logger.warning("[SocraticEngine] Sovereignty guard intervention triggered.")
            return "Подумай: какое ключевое определение или теорему здесь следует применить в первую очередь?"

        return guidance

    def _explain_theoretical_concept(self, question: str, subject: str) -> str:
        """Explains pure theoretical concepts with pedagogical clarity."""
        return (
            f"📘 [Теоретический обзор — {subject}]:\n\n"
            f"В основе этого понятия лежит строгое математическое определение. "
            f"Обрати внимание на граничные условия и условия применимости теоремы. "
            f"Как ты формулируешь базовое утверждение?"
        )

    def verify_no_direct_solution(self, text: str) -> bool:
        """Verifies that generated text contains zero forbidden direct solution markers."""
        audit = self.guard.verify_response(prompt="задание", response=text)
        return audit.get("allowed", True)
