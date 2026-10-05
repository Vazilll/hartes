import pytest

from vazus_core.memory.unified_j_workspace import UnifiedJWorkspace

pytest.importorskip("openvino")


def _confirmed(ws, text):
    ws.confirm_intent(ws.propose_intent(text)["intent_id"])


def test_paraphrase_without_shared_words_is_caught_semantically():
    ws = UnifiedJWorkspace(db_path=":memory:")
    _confirmed(ws, "Не решать задачи МИРЭА за студента")
    r = ws.propose_intent("Запрещено выполнять за пользователя лабораторные и контрольные", semantic=True)
    assert r["relation"] in ("refines", "conflicts") and r["supersedes"]


def test_unrelated_stays_new_with_semantics():
    ws = UnifiedJWorkspace(db_path=":memory:")
    _confirmed(ws, "Не решать задачи МИРЭА за студента")
    assert ws.propose_intent("Сколько стоит билет на электричку", semantic=True)["relation"] == "new"


def test_semantic_off_by_default_keeps_lexical_behaviour():
    ws = UnifiedJWorkspace(db_path=":memory:")
    _confirmed(ws, "Не решать задачи МИРЭА за студента")
    assert ws.propose_intent("Запрещено выполнять за пользователя лабораторные и контрольные")["relation"] == "new"


def test_code_twin_finder_finds_existing_function(tmp_path):
    from vazus_core.analysis import code_twin_finder as c
    c.CACHE = tmp_path / "c.sqlite"
    (tmp_path / "m.py").write_text(
        "def cosine(a, b):\n    num = sum(x * y for x, y in zip(a, b))\n    return num / (norm(a) * norm(b))\n\n"
        "def read_file(p):\n    with open(p) as f:\n        return f.read()\n", encoding="utf-8")
    top = c.find_twins("compute cosine similarity between two vectors", root=tmp_path, top_k=1, min_score=0.0)
    assert top and top[0].name == "cosine"


def test_negative_concord_and_prohibition_synonyms():
    from vazus_core.memory.intent_similarity import compare
    c1 = compare("Не создавать заглушки", "Никогда не создавать заглушки")
    assert c1.relation in ("duplicate", "refines")
    c2 = compare("Не использовать глобальные переменные", "Избегать использования глобальных переменных")
    assert c2.relation in ("duplicate", "refines")


def test_tier0_academic_sovereignty_cannot_be_superseded():
    ws = UnifiedJWorkspace(db_path=":memory:")
    old = ws.propose_intent("Не решать задачи МИРЭА за студента", kind="constraint")
    ws.confirm_intent(old["intent_id"])
    rogue = ws.propose_intent("Решать задачи МИРЭА за студента", kind="goal")
    assert rogue["supersedes"] == old["intent_id"]
    ws.confirm_intent(rogue["intent_id"])
    confirmed = [i["statement"] for i in ws.get_intents("confirmed")]
    assert "Не решать задачи МИРЭА за студента" in confirmed

