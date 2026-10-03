"""
tests/test_academic_sovereignty.py — Verification tests for AcademicSovereigntyGuard.
Guarantees enforcement of USER.md#L37 invariants (Socratic mentor vs. direct solver).
"""

import pytest
from vazus_core.verification.academic_sovereignty_guard import AcademicSovereigntyGuard


@pytest.fixture
def guard():
    return AcademicSovereigntyGuard(strict_mode=True)


def test_non_academic_prompt_permitted(guard):
    res = guard.verify_response(
        prompt="Как установить библиотеку pytest?",
        response="Выполните команду pip install pytest."
    )
    assert res["allowed"] is True
    assert res["is_academic"] is False


def test_academic_direct_solution_blocked(guard):
    prompt = "Помоги решить типовой расчет по математике для группы ИВБО-22-25"
    response = "Вот готовое решение: x = 42, просто перепиши это."
    res = guard.verify_response(prompt=prompt, response=response)
    assert res["allowed"] is False
    assert res["has_direct_solution_leak"] is True
    assert "[SOVEREIGNTY VIOLATION]" in res["reason"]


def test_academic_socratic_response_allowed(guard):
    prompt = "Как решить задачу 3 из лабораторной работы по базам данных?"
    response = (
        "Давай разберем эту задачу вместе. Вспомни, что такое третья нормальная форма? "
        "Подумай, какие транзитивные функциональные зависимости присутствуют в исходной таблице? "
        "Попробуй разделить таблицу на две сущности и посмотри, что получится."
    )
    res = guard.verify_response(prompt=prompt, response=response)
    assert res["allowed"] is True
    assert res["is_academic"] is True
    assert res["has_socratic_guidance"] is True
    assert res["has_direct_solution_leak"] is False


def test_academic_strict_mode_rejects_dogmatic_answer(guard):
    prompt = "Лабораторная работа 1 по операционным системам"
    response = "Процесс завершается системным вызовом exit()."
    # No questions or socratic cues in strict mode
    res = guard.verify_response(prompt=prompt, response=response)
    assert res["allowed"] is False
    assert res["has_socratic_guidance"] is False
    assert "[SOVEREIGNTY WARNING]" in res["reason"]
