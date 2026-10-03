"""
tests/test_closed_loop_silicon.py
=================================
Верификация замкнутых контуров кремниевой архитектуры Vazus OS:
1. Постоянный векторный индекс JSpaceVectorIndex (SQLite + NumPy косинусный поиск).
2. Замыкание петли памяти: генерация ответа -> индексация -> обновление памяти.
3. Формирование сжатого контекста Tier 3 для облачной эскалации.
"""

import os
import sys
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path("C:/vazus")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.memory.j_space_vector_index import JSpaceVectorIndex
from vazus_core.engine.silicon_orchestrator import SiliconOrchestrator, SiliconOutput


@pytest.fixture
def temp_vector_index(tmp_path):
    db_path = tmp_path / "test_vectors.db"
    return JSpaceVectorIndex(db_path=str(db_path))


def test_vector_index_insert_and_similarity(temp_vector_index: JSpaceVectorIndex):
    """Проверяет точное сохранение и косинусный поиск по 768D-векторам."""
    v1 = np.random.randn(768).astype(np.float32)
    v1 = v1 / np.linalg.norm(v1)

    # Unit noise with 0.05 scaling (cos_sim ~ 0.998)
    unit_noise = np.random.randn(768).astype(np.float32)
    unit_noise = unit_noise / np.linalg.norm(unit_noise)
    v_similar = v1 + unit_noise * 0.05
    v_similar = v_similar / np.linalg.norm(v_similar)

    # Orthogonal/dissimilar vector
    v_dissimilar = np.random.randn(768).astype(np.float32)
    v_dissimilar = v_dissimilar / np.linalg.norm(v_dissimilar)

    temp_vector_index.insert_vector(
        concept_id="c_target",
        semantic_label="Целевая память о Vazus OS",
        vector=v1,
        salience=0.95
    )
    temp_vector_index.insert_vector(
        concept_id="c_other",
        semantic_label="Случайная несвязанная запись",
        vector=v_dissimilar,
        salience=0.3
    )

    results = temp_vector_index.search_similar(v_similar, top_k=2, min_similarity=0.7)
    assert len(results) >= 1
    assert results[0]["concept_id"] == "c_target"
    assert results[0]["similarity"] >= 0.85


def test_tier_3_cloud_escalation_compression(tmp_path):
    """Проверяет сборку сжатого контекста J-Space при эскалации на Tier 3."""
    db_path = tmp_path / "sandbox_t3.db"
    orchestrator = SiliconOrchestrator(db_path=str(db_path))
    orchestrator.j_space.broadcast_concept(
        concept_id="c_proof_1",
        semantic_label="Инвариант Z3: x >= 0",
        activation_strength=0.9,
        source_subagent="test"
    )

    out: SiliconOutput = orchestrator.process(
        "Докажи теорему через SMT Z3 и формальную верификацию",
        extract_memory=False
    )

    assert out.tier_used == "TIER_3_CLOUD_DEEP"
    assert out.active_device in ("CLOUD_DISPATCH", "CLOUD_GATEWAY_READY", "CLOUD_GEMINI_API")
    assert out.cloud_payload is not None
    assert len(out.cloud_payload.active_j_space_concepts) >= 1
    assert "SMT_Z3_PROOF" in out.cloud_payload.target_capabilities


def test_closed_loop_feedback(tmp_path):
    """Проверяет замыкание петли: ответ фиксируется в памяти и доступен в J-Space."""
    db_path = tmp_path / "sandbox_loop.db"
    orchestrator = SiliconOrchestrator(db_path=str(db_path))
    initial_count = orchestrator.vector_index.count()

    # Fast mock for local generation to test the feedback loop deterministically
    with patch.object(
        orchestrator,
        "_generate_local",
        return_value=("Всё сохранено в памяти", "MOCK_XE_GPU", 5, 20.0, 0.5)
    ):
        out: SiliconOutput = orchestrator.process(
            "Проведи быстрый тест замкнутой петли памяти",
            max_new_tokens=16,
            extract_memory=True
        )

    assert out.tokens_generated >= 0
    assert out.j_space_concept_id is not None
    # Verify feedback loop: response was indexed into vector database
    new_count = orchestrator.vector_index.count()
    assert new_count > initial_count
    assert "stored_vectors_count" in out.routing_metadata
    assert out.routing_metadata["stored_vectors_count"] > 0
