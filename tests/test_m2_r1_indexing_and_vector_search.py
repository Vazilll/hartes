"""
C:\vazus\tests\test_m2_r1_indexing_and_vector_search.py
Unit & Integration Test Suite for Milestone 2 Requirement R1:
Obsidian Wiki Notes Indexing, [[Note]] Wikilink Extraction, 768D Vector Space Persistence & Unified Vector Search.
"""

import sys
import os
import json
import sqlite3
from pathlib import Path

VAZUS_DIR = Path("C:/vazus")
if str(VAZUS_DIR) not in sys.path:
    sys.path.insert(0, str(VAZUS_DIR))

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from vazus_core.embeddings import UnifiedGoogleEmbedder, UnifiedEmbeddingManager
from vazus_core.supergraph_linker import SuperGraphLinker


def run_test_suite():
    print("=" * 70)
    print("🧪 MILESTONE 2 REQUIREMENT R1 VERIFICATION TEST SUITE")
    print("=" * 70)

    # 1. Initialize SuperGraphLinker & run full integration indexing
    print("\n[Step 1] Running SuperGraphLinker indexing across Wiki notes & AST code nodes...")
    linker = SuperGraphLinker()
    report = linker.run_supergraph_integration(threshold=0.10)

    print(f"  - AST Code Nodes:        {report['ast_nodes_count']}")
    print(f"  - Wiki Note Nodes:       {report['wiki_notes_count']}")
    print(f"  - Wiki Section Nodes:    {report['wiki_sections_count']}")
    print(f"  - Extracted [[Note]] Links: {report['wikilinks_count']}")
    print(f"  - Section Edges:         {report['section_edges_count']}")
    print(f"  - Hybrid Similarity Edges:{report['hybrid_edges_count']}")
    print(f"  - Total Created Edges:   {report['edges_created']}")

    assert report["wiki_notes_count"] > 0, "Failed: Expected wiki_notes_count > 0"
    assert report["wiki_sections_count"] > 0, "Failed: Expected wiki_sections_count > 0"
    assert report["wikilinks_count"] > 0, "Failed: Expected wikilinks_count > 0"
    assert report["edges_created"] > 0, "Failed: Expected edges_created > 0"
    print("  ✅ Indexing completed cleanly.")

    # 2. Inspect vazus.db database tables
    print("\n[Step 2] Verifying database persistence in vazus.db...")
    with linker._get_connection() as conn:
        nodes_count = conn.execute("SELECT count(*) FROM kg_nodes").fetchone()[0]
        wiki_nodes = conn.execute("SELECT count(*) FROM kg_nodes WHERE domain = 'memory_wiki'").fetchone()[0]
        ast_nodes = conn.execute("SELECT count(*) FROM kg_nodes WHERE domain = 'ast_code'").fetchone()[0]
        wikilink_edges = conn.execute("SELECT count(*) FROM kg_edges WHERE relation = 'WIKILINK'").fetchone()[0]
        contains_edges = conn.execute("SELECT count(*) FROM kg_edges WHERE relation = 'CONTAINS_SECTION'").fetchone()[0]
        supergraph_edges = conn.execute("SELECT count(*) FROM kg_edges WHERE relation = 'SUPERGRAPH_LINK'").fetchone()[0]

        print(f"  - Total kg_nodes in DB:       {nodes_count}")
        print(f"    - Wiki Memory Nodes:        {wiki_nodes}")
        print(f"    - AST Code Nodes:           {ast_nodes}")
        print(f"  - kg_edges in DB:")
        print(f"    - WIKILINK Edges:           {wikilink_edges}")
        print(f"    - CONTAINS_SECTION Edges:   {contains_edges}")
        print(f"    - SUPERGRAPH_LINK Edges:    {supergraph_edges}")

        assert wiki_nodes > 0, "Failed: No memory_wiki nodes found in kg_nodes"
        assert wikilink_edges > 0, "Failed: No WIKILINK edges found in kg_edges"
        assert contains_edges > 0, "Failed: No CONTAINS_SECTION edges found in kg_edges"

        # Verify vector dimensionality in kg_nodes
        sample_node = conn.execute("SELECT id, embedding_json FROM kg_nodes WHERE embedding_json IS NOT NULL LIMIT 1").fetchone()
        assert sample_node is not None, "Failed: No node with embedding_json"
        emb = json.loads(sample_node["embedding_json"])
        assert len(emb) == 768, f"Failed: Expected vector dimensionality 768, got {len(emb)}"
        print(f"  ✅ Database persistence verified with 768D vector embeddings.")

    # 3. Test Unified Vector Similarity Search across AST and Wiki nodes
    print("\n[Step 3] Testing Unified 768D Vector Similarity Search...")

    # Query 1: Architectural query expecting both AST and Wiki results
    q1 = "Vision Pipeline Benchmark Results LFM base64 screen vision"
    results_q1 = linker.search_unified_vector_space(query=q1, top_k=5)
    print(f"\n  Query: '{q1}'")
    print(f"  Results returned: {len(results_q1)}")
    for idx, r in enumerate(results_q1, 1):
        print(f"    {idx}. [{r['domain']}:{r['node_type']}] {r['id']} (sim: {r['similarity']:.4f}) — {r['name']}")

    assert len(results_q1) > 0, "Failed: Search query returned 0 results"
    
    # Query 2: Supergraph code & architecture query
    q2 = "SuperGraph 768D embeddings vector space linker AST topology"
    results_q2 = linker.search_unified_vector_space(query=q2, top_k=5)
    print(f"\n  Query: '{q2}'")
    print(f"  Results returned: {len(results_q2)}")
    for idx, r in enumerate(results_q2, 1):
        print(f"    {idx}. [{r['domain']}:{r['node_type']}] {r['id']} (sim: {r['similarity']:.4f}) — {r['name']}")

    assert len(results_q2) > 0, "Failed: Search query returned 0 results"

    # Query 3: Domain filter test
    wiki_only = linker.search_unified_vector_space(query="testing insights", top_k=5, domain_filter="memory_wiki")
    print(f"\n  Domain Filter 'memory_wiki': {len(wiki_only)} results")
    for r in wiki_only:
        assert r["domain"] == "memory_wiki", f"Failed: Expected domain memory_wiki, got {r['domain']}"

    ast_only = linker.search_unified_vector_space(query="cleardb", top_k=5, domain_filter="ast_code")
    print(f"  Domain Filter 'ast_code': {len(ast_only)} results")
    for r in ast_only:
        assert r["domain"] == "ast_code", f"Failed: Expected domain ast_code, got {r['domain']}"

    print("\n" + "=" * 70)
    print("🎉 ALL TEST CASES FOR REQUIREMENT R1 PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_test_suite()
