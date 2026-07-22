"""
pyenv/scripts/test_supergraph_integration.py — Integration test for Unified SuperGraph & 768D Embeddings.

Verifies:
1. UnifiedGoogleEmbedder 768D vector generation.
2. SuperGraphLinker 4-component hybrid metric computation:
   S(u, v) = 0.45 * S_cosine + 0.25 * S_fts + 0.20 * S_structural + 0.10 * S_provenance
3. Loading/linking Layer A (AST code nodes) and Layer B (Memory Wiki notes).
4. Saving 768D embeddings into `llm_cache` / `kg_nodes` and edge records into `kg_edges`.
5. Direct execution with Exit Code 0.
"""

import sys
import json
import sqlite3
from pathlib import Path

# Setup Python Path
PYENV_DIR = Path("C:/vazus/pyenv")
if str(PYENV_DIR) not in sys.path:
    sys.path.insert(0, str(PYENV_DIR))

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from vazus_core.embeddings import UnifiedGoogleEmbedder
from vazus_core.supergraph_linker import (
    SuperGraphLinker,
    calculate_cosine_similarity,
    calculate_fts_similarity,
    calculate_structural_similarity,
    calculate_provenance_similarity
)


def run_verification():
    print("=" * 60)
    print("🧪 UNIFIED SUPERGRAPH & 768D EMBEDDINGS INTEGRATION TEST")
    print("=" * 60)

    # Step 1: Verify 768D Embeddings
    print("\n1. Testing Google Gemini 768D Embedder...")
    embedder = UnifiedGoogleEmbedder()
    test_text = "def supergraph_linking_kernel(): return '768D Vector Space Alignment'"
    vec = embedder.embed_query(test_text)
    
    print(f"   - Generated vector length: {len(vec)}")
    assert len(vec) == 768, f"Error: Vector dimension must be 768, got {len(vec)}"
    assert isinstance(vec[0], float), "Error: Vector elements must be floats"
    print("   ✅ 768D Vector Dimension Verified.")

    # Step 2: Verify 4-Component Hybrid Metric Functions
    print("\n2. Testing 4-Component Hybrid Metric Functions...")
    sample_ast = {
        "id": "ast:vazus_core_supergraph_linker_main",
        "name": "SuperGraphLinker",
        "domain": "ast_code",
        "node_type": "Class",
        "description": "Unified SuperGraph Linker for AST code and Memory Wiki 768D integration.",
        "source_file": "vazus_core/supergraph_linker.py",
        "community": 1,
        "_origin": "ast",
        "tags": "ast,code,supergraph,linker"
    }

    sample_wiki = {
        "id": "wiki:Architecture_2026_Report",
        "name": "Architecture 2026 Report",
        "domain": "memory_wiki",
        "node_type": "WikiNote",
        "description": "System architecture report detailing SuperGraph, 768D vectors, and AST topology.",
        "content": "Integrates AST code topology nodes with memory wiki using 768D Google embeddings.",
        "source_file": "Architecture_2026_Report.md",
        "community": 1,
        "_origin": "wiki",
        "tags": "wiki,memory,architecture,supergraph"
    }

    text_ast = f"{sample_ast.get('name', '')} {sample_ast.get('description', '')}".strip()
    text_wiki = f"{sample_wiki.get('name', '')} {sample_wiki.get('description', '')} {sample_wiki.get('content', '')}".strip()

    emb_ast = embedder.embed_query(text_ast)
    emb_wiki = embedder.embed_query(text_wiki)

    s_cosine = calculate_cosine_similarity(emb_ast, emb_wiki)
    s_fts = calculate_fts_similarity(text_ast, text_wiki)
    s_structural = calculate_structural_similarity(sample_ast, sample_wiki)
    s_provenance = calculate_provenance_similarity(sample_ast, sample_wiki)

    linker = SuperGraphLinker()
    metrics = linker.compute_hybrid_metric(sample_ast, sample_wiki, emb_ast, emb_wiki)

    expected_score = (
        0.45 * s_cosine +
        0.25 * s_fts +
        0.20 * s_structural +
        0.10 * s_provenance
    )

    print(f"   - S_cosine: {s_cosine:.4f}")
    print(f"   - S_fts: {s_fts:.4f}")
    print(f"   - S_structural: {s_structural:.4f}")
    print(f"   - S_provenance: {s_provenance:.4f}")
    print(f"   - Total Hybrid Score S(u, v): {metrics['total_score']:.4f}")

    assert abs(metrics["total_score"] - expected_score) < 1e-5, "Hybrid metric calculation mismatch!"
    assert 0.0 <= metrics["total_score"] <= 1.0, "Total score must be bounded in [0.0, 1.0]"

    # Robustness checks identified by Challenger
    import math
    assert calculate_cosine_similarity([float('nan'), 1.0], [1.0, 1.0]) == 0.0, "NaN vector must return 0.0 similarity"
    assert calculate_cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0, "Zero norm vector must return 0.0 similarity"
    assert calculate_provenance_similarity({"id": "a"}, {"id": "b"}) == 0.0, "No provenance match must return 0.0 baseline score"

    print("   ✅ 4-Component Hybrid Metric Verified (including Robustness Improvements).")

    # Step 3: Verify Node Linking & Database Storage
    print("\n3. Testing SuperGraph Linking & Database Persistence...")
    ast_nodes = [sample_ast] + linker.load_ast_nodes()
    wiki_nodes = [sample_wiki] + linker.load_memory_wiki_nodes()

    print(f"   - Loaded AST nodes: {len(ast_nodes)}")
    print(f"   - Loaded Memory Wiki notes: {len(wiki_nodes)}")

    result = linker.run_supergraph_integration(threshold=0.10)
    print(f"   - Edges created/linked: {result['edges_created']}")
    assert result["edges_created"] > 0, "Error: Expected at least 1 edge to be created!"

    # Step 4: Verify Database SQLite Tables (kg_nodes, kg_edges, llm_cache)
    print("\n4. Verifying SQLite Database Insertions in dnts.db...")
    with linker._get_connection() as conn:
        # Check kg_edges
        edge_row = conn.execute("SELECT * FROM kg_edges WHERE relation = 'SUPERGRAPH_LINK' LIMIT 1").fetchone()
        assert edge_row is not None, "Error: No SUPERGRAPH_LINK edge found in kg_edges!"
        print(f"   - Found edge in kg_edges: {edge_row['source_id']} -> {edge_row['target_id']} (strength: {edge_row['strength']})")

        props = json.loads(edge_row["properties"])
        assert "s_cosine" in props, "Edge properties missing s_cosine"
        assert props["vector_dim"] == 768, f"Expected vector_dim 768 in edge properties, got {props.get('vector_dim')}"

        # Check kg_nodes
        node_row = conn.execute("SELECT * FROM kg_nodes WHERE embedding_json IS NOT NULL LIMIT 1").fetchone()
        assert node_row is not None, "Error: No node with embedding_json found in kg_nodes!"
        emb_list = json.loads(node_row["embedding_json"])
        assert len(emb_list) == 768, f"kg_nodes embedding length expected 768, got {len(emb_list)}"
        print(f"   - Verified kg_nodes entry: id='{node_row['id']}', embedding_dim={len(emb_list)}")

        # Check llm_cache
        cache_row = conn.execute("SELECT * FROM llm_cache LIMIT 1").fetchone()
        assert cache_row is not None, "Error: No record found in llm_cache!"
        cache_emb = json.loads(cache_row["embedding_json"])
        assert len(cache_emb) == 768, f"llm_cache embedding length expected 768, got {len(cache_emb)}"
        print(f"   - Verified llm_cache entry: key='{cache_row['cache_key'][:16]}...', embedding_dim={len(cache_emb)}")

    print("\n" + "=" * 60)
    print("🎉 UNIFIED SUPERGRAPH & 768D EMBEDDINGS INTEGRATION TEST PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_verification()
