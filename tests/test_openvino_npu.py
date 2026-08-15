"""
tests/test_openvino_npu.py — Unit Tests for OpenVINO NPU Offloading & Unified Embeddings.
"""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vazus_core.embeddings import (
    OpenVINONPUEmbedder,
    UnifiedEmbeddingManager,
    get_embedding,
    _compute_fallback_embedding
)


def test_openvino_runtime_shim():
    """Verifies openvino.runtime import alias shim is present and working."""
    import openvino.runtime as ov_rt
    assert hasattr(ov_rt, "Core"), "openvino.runtime should expose Core class"


def test_openvino_npu_embedder_init_and_inference():
    """Tests OpenVINONPUEmbedder initialization and token embedding."""
    embedder = OpenVINONPUEmbedder(dimension=768)
    assert embedder.is_available is True, "OpenVINONPUEmbedder should be available on NPU runtime"

    # Input token array
    tokens = np.array([[101, 2054, 2003, 1037, 3231, 102]], dtype=np.int64)
    emb = embedder.embed_tokens(tokens)

    assert len(emb) == 768
    assert isinstance(emb[0], float)

    # Unit normalization check
    norm = sum(x * x for x in emb) ** 0.5
    assert abs(norm - 1.0) < 1e-3 or norm == 0.0


def test_unified_embedding_manager_npu_and_simd():
    """Tests UnifiedEmbeddingManager routing through OpenVINO NPU and AVX-512 SIMD."""
    manager = UnifiedEmbeddingManager(dimension=768)

    # 1. Single text embedding
    vec1 = manager.get_embedding("SuperGraph OS Kernel")
    assert len(vec1) == 768

    vec2 = manager.get_embedding("AVX-512 SIMD Vector Search")
    assert len(vec2) == 768

    # 2. Similarity computation
    sim = manager.compute_similarity(vec1, vec2)
    assert 0.0 <= sim <= 1.0

    # Self-similarity should be 1.0
    self_sim = manager.compute_similarity(vec1, vec1)
    assert abs(self_sim - 1.0) < 1e-3

    # 3. Batch similarity
    candidates = [vec2, vec1, _compute_fallback_embedding("Random text")]
    batch_sims = manager.compute_batch_similarity(vec1, candidates)
    assert len(batch_sims) == 3
    assert abs(batch_sims[1] - 1.0) < 1e-3


def test_search_unified_vector_space_mock_db(tmp_path):
    """Tests searching unified 768D vector space using sqlite database."""
    import sqlite3
    import json

    db_file = tmp_path / "vazus_test.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE kg_nodes (
            id TEXT PRIMARY KEY,
            name TEXT,
            domain TEXT,
            node_type TEXT,
            description TEXT,
            tags TEXT,
            properties TEXT,
            embedding_json TEXT
        )
    """)

    manager = UnifiedEmbeddingManager(dimension=768)
    e1 = manager.get_embedding("AST Call Graph Node")
    e2 = manager.get_embedding("Semantic Wiki Document")

    cursor.execute("INSERT INTO kg_nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
        "node_1", "AST_Node_1", "ast_code", "function", "Call graph node", "ast", "{}", json.dumps(e1)
    ))
    cursor.execute("INSERT INTO kg_nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
        "node_2", "Wiki_Note_1", "memory_wiki", "note", "Semantic wiki note", "wiki", "{}", json.dumps(e2)
    ))
    conn.commit()
    conn.close()

    results = manager.search_unified_vector_space("AST Call Graph", db_path=db_file, top_k=2)
    assert len(results) >= 1
    assert results[0]["id"] in ["node_1", "node_2"]


def test_embedding_cloud_path_requires_explicit_opt_in(monkeypatch):
    """Local-first policy: cloud Gemini embedding must NOT be used unless
    VAZUS_EMBEDDING_ALLOW_CLOUD=1 is set explicitly."""
    from unittest.mock import patch
    manager = UnifiedEmbeddingManager(dimension=768)
    monkeypatch.delenv("VAZUS_EMBEDDING_ALLOW_CLOUD", raising=False)
    with patch.object(manager, "_get_npu_embedder", return_value=None), \
         patch.object(manager, "_init_genai") as mock_init_genai:
        vec = manager.get_embedding("local-first embedding check")
        mock_init_genai.assert_not_called()
    assert vec is not None
    assert len(vec) == 768
    assert vec == _compute_fallback_embedding("local-first embedding check", dimension=768)
