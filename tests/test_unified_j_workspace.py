"""
tests/test_unified_j_workspace.py
==================================
Test suite for UnifiedJWorkspace:
- Bounded capacity (K-sparse attention bottleneck)
- Automatic vector persistence into SQLite
- Fast cosine similarity search across concepts
- Concept modulation and activation decay
"""

import os
import pytest
import numpy as np
from vazus_core.memory.unified_j_workspace import UnifiedJWorkspace, JSpaceConcept


def test_unified_initialization():
    ws = UnifiedJWorkspace(capacity=8, db_path=":memory:")
    assert ws.capacity == 8
    assert ws.embedding_dim == 768
    assert len(ws.get_active_concepts()) == 0


def test_unified_broadcast_and_persistence():
    ws = UnifiedJWorkspace(capacity=4, db_path=":memory:")
    dummy_vec = [0.1] * 768
    # L2 normalize
    norm = np.linalg.norm(dummy_vec)
    dummy_vec = (np.array(dummy_vec) / norm).tolist()

    concept = ws.broadcast_concept(
        concept_id="c_smt",
        semantic_label="SMT_Z3_Verification",
        activation_strength=0.95,
        source_subagent="verifier",
        embedding_vector=dummy_vec,
        metadata={"target": "rule_safety"}
    )
    assert concept.concept_id == "c_smt"
    assert concept.activation_strength == 0.95
    assert len(ws.get_active_concepts()) == 1

    # Search similar vector
    results = ws.search_similar(dummy_vec, top_k=3)
    assert len(results) >= 1
    assert results[0]["concept_id"] == "c_smt"
    assert results[0]["similarity"] > 0.99


def test_unified_capacity_eviction():
    ws = UnifiedJWorkspace(capacity=3, db_path=":memory:")
    ws.broadcast_concept("c1", "Concept 1", 0.2, "a")
    ws.broadcast_concept("c2", "Concept 2", 0.5, "a")
    ws.broadcast_concept("c3", "Concept 3", 0.9, "a")
    ws.broadcast_concept("c4", "Concept 4", 0.7, "a")

    active = ws.get_active_concepts()
    assert len(active) == 3
    # c1 with lowest strength (0.2) must be evicted from active RAM
    assert "c1" not in active
    assert "c4" in active


def test_unified_modulation_and_decay():
    ws = UnifiedJWorkspace(capacity=5, db_path=":memory:")
    ws.broadcast_concept("c1", "Task A", 0.8, "planner")
    
    # Modulate
    ok = ws.modulate_concept("c1", 0.5)
    assert ok is True
    assert ws.get_concept("c1").activation_strength == 0.5

    # Decay 0.5 - 0.1 = 0.4
    ws.decay_activations(decay_rate=0.1)
    assert pytest.approx(ws.get_concept("c1").activation_strength, 0.01) == 0.4

    # Modulate to 0 evicts from active concepts
    ws.modulate_concept("c1", 0.0)
    assert ws.get_concept("c1") is None


def test_unified_decay_concepts_and_bounded_history():
    ws = UnifiedJWorkspace(capacity=10, db_path=":memory:")
    # Broadcast 120 items to verify broadcast_history is capped at 100
    for i in range(120):
        ws.broadcast_concept(f"c_{i}", f"Concept {i}", 0.1)
    assert len(ws.broadcast_history) == 100

    # Verify decay_concepts prunes low salience concepts
    ws.active_concepts.clear()
    ws.broadcast_concept("high", "High salience", 0.9)
    ws.broadcast_concept("low", "Low salience", 0.08)
    pruned = ws.decay_concepts(decay_rate=0.5, min_threshold=0.05)
    assert pruned == 1
    assert "low" not in ws.active_concepts
    assert "high" in ws.active_concepts


# ---------------------------------------------------------------- intent anchors
def _vec(seed: int, dim: int = 768):
    rng = np.random.default_rng(seed)
    return rng.normal(size=dim).astype(np.float32)


def test_intent_requires_confirmation():
    ws = UnifiedJWorkspace(db_path=":memory:")
    it = ws.propose_intent("Не решать задачи МИРЭА за студента", kind="constraint")
    assert it["status"] == "proposed"
    assert ws.get_intents() == []
    assert ws.get_intent_context() == ""
    assert ws.confirm_intent(it["intent_id"]) is True
    assert [i["statement"] for i in ws.get_intents()] == ["Не решать задачи МИРЭА за студента"]


def test_intent_immune_to_eviction_and_decay():
    ws = UnifiedJWorkspace(capacity=2, db_path=":memory:")
    it = ws.propose_intent("Никаких заглушек", kind="constraint")
    ws.confirm_intent(it["intent_id"])
    for i in range(10):
        ws.broadcast_concept(f"c{i}", f"noise {i}", 0.9)
    for _ in range(50):
        ws.decay_concepts(decay_rate=0.5)
    assert "Никаких заглушек" in ws.get_broadcast_context()


def test_intent_duplicate_and_reject():
    ws = UnifiedJWorkspace(db_path=":memory:")
    a = ws.propose_intent("Цель A")
    assert ws.propose_intent("  цель a ")["intent_id"] == a["intent_id"]
    assert ws.reject_intent(a["intent_id"]) is True
    assert ws.confirm_intent(a["intent_id"]) is False  # no resurrection


def test_intent_refinement_supersedes_old_version():
    ws = UnifiedJWorkspace(db_path=":memory:")
    old = ws.propose_intent("Не создавать заглушки и фасады в коде", kind="constraint")
    ws.confirm_intent(old["intent_id"])
    new = ws.propose_intent("Не создавать заглушки и фасады в коде проекта", kind="constraint")
    assert new["relation"] == "refines"  # one added word is a refinement, not a silent duplicate
    assert new["supersedes"] == old["intent_id"] and new["diff"] == "+проекта"


def test_refines_supersedes_only_after_confirm():
    ws = UnifiedJWorkspace(db_path=":memory:")
    old = ws.propose_intent("Всегда проверять тестами каждое изменение кода")
    ws.confirm_intent(old["intent_id"])
    new = ws.propose_intent("Всегда проверять тестами и линтером каждое изменение")
    assert new["relation"] == "refines" and new["supersedes"] == old["intent_id"]
    assert [i["statement"] for i in ws.get_intents()] == [old["statement"]]
    ws.confirm_intent(new["intent_id"])
    assert [i["statement"] for i in ws.get_intents()] == [new["statement"]]
    assert {i["status"] for i in ws.get_intents(None)} == {"superseded", "confirmed"}


def test_opposite_polarity_is_flagged_as_conflict_with_diff():
    ws = UnifiedJWorkspace(db_path=":memory:")
    old = ws.propose_intent("Не решать задачи МИРЭА за студента", kind="constraint")
    ws.confirm_intent(old["intent_id"])
    new = ws.propose_intent("Решать задачи МИРЭА за студента")
    assert new["relation"] == "conflicts" and new["supersedes"] == old["intent_id"]
    assert "-не" in new["diff"]
    assert [i["statement"] for i in ws.get_intents()] == [old["statement"]]  # old stays in force until user decides


def test_unrelated_intent_stays_new_and_vectors_never_decide():
    ws = UnifiedJWorkspace(db_path=":memory:")
    a = ws.propose_intent("Закрыть долги по математическому анализу", vector=_vec(10))
    ws.confirm_intent(a["intent_id"])
    b = ws.propose_intent("Настроить резервное копирование базы данных", vector=_vec(10))  # identical vector
    assert b["relation"] == "new" and b["supersedes"] is None


def test_intent_persists_across_instances(tmp_path):
    db = str(tmp_path / "ws.db")
    w1 = UnifiedJWorkspace(db_path=db)
    w1.confirm_intent(w1.propose_intent("Сквозная цель")["intent_id"])
    assert "Сквозная цель" in UnifiedJWorkspace(db_path=db).get_broadcast_context()
