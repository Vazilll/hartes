"""tests/test_intent_similarity.py — lexical, polarity-aware comparison, incl. its documented blind spots."""

import pytest

from vazus_core.memory.intent_similarity import compare, is_negative, similarity, word_diff


@pytest.mark.parametrize(
    "text,neg",
    [
        ("Не решать задачи", True),
        ("Никогда не создавать заглушки", True),  # Russian negative concord (prohibition)
        ("Запрещено удалять файлы", True),
        ("Решать задачи", False),
        ("Never delete files", True),
    ],
)
def test_polarity(text, neg):
    assert is_negative(text) is neg


def test_duplicate_ignores_case_punctuation_and_stopwords():
    assert compare("Закрыть долги по анализу.", "закрыть долги  анализу").relation == "duplicate"


def test_refines_shows_only_small_difference():
    c = compare("Проверять тестами каждое изменение кода", "Проверять тестами и линтером каждое изменение кода")
    assert c.relation == "refines" and c.diff == "+и линтером"


def test_conflict_is_detected_where_embeddings_failed():
    c = compare("Не решать задачи МИРЭА за студента", "Решать задачи МИРЭА за студента")
    assert c.relation == "conflicts" and c.similarity == 1.0 and c.diff == "-не"


def test_unrelated_is_new():
    assert compare("Закрыть долги по анализу", "Настроить резервное копирование").relation == "new"


def test_known_blind_spot_paraphrase_without_shared_words_is_new():
    """Documented limitation: no shared stems => no match. Embeddings on this machine do no better (measured)."""
    a = "Не решать задачи МИРЭА за студента"
    b = "Запрещено выполнять за пользователя лабораторные и контрольные"
    assert similarity(a, b) == 0.0 and compare(a, b).relation == "new"


def test_word_diff_empty_when_equal():
    assert word_diff("одно и то же", "Одно и то же") == ""
