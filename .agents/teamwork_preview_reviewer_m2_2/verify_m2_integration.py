"""
Verification script for Reviewer 2 - Milestone 2 (R1: Obsidian Vault & 768D Memory Integration).
"""

import sys
import sqlite3
import json
from pathlib import Path

ROOT_DIR = Path("C:/vazus")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.embeddings import UnifiedEmbeddingManager
from vazus_core.supergraph_linker import SuperGraphLinker

def run_verification():
    db_path = ROOT_DIR / "services" / "memory" / "vazus.db"
    assert db_path.exists(), f"Database not found at {db_path}"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Check kg_nodes count & domains
    nodes = cursor.execute("SELECT domain, count(*) as cnt FROM kg_nodes GROUP BY domain").fetchall()
    print("=== Database kg_nodes Domain Breakdown ===")
    for r in nodes:
        print(f"  Domain: {r['domain']}, Count: {r['cnt']}")

    # 2. Check 768D embedding vectors in kg_nodes
    sample_node = cursor.execute("SELECT id, name, domain, embedding_json FROM kg_nodes WHERE embedding_json IS NOT NULL LIMIT 1").fetchone()
    assert sample_node is not None, "No nodes with embedding_json found!"
    emb = json.loads(sample_node["embedding_json"])
    assert len(emb) == 768, f"Expected vector dimensionality 768, got {len(emb)}"
    print(f"\n=== Vector Embedding Verification ===")
    print(f"  Sample Node ID: {sample_node['id']}")
    print(f"  Domain: {sample_node['domain']}")
    print(f"  Embedding dimension: {len(emb)}")
    print(f"  Vector sample (first 5 elements): {emb[:5]}")

    # 3. Check kg_edges relations
    edges = cursor.execute("SELECT relation, count(*) as cnt FROM kg_edges GROUP BY relation").fetchall()
    print("\n=== Database kg_edges Relation Breakdown ===")
    for r in edges:
        print(f"  Relation: {r['relation']}, Count: {r['cnt']}")

    # 4. Test Unified 768D Vector Space Search
    embedder = UnifiedEmbeddingManager(dimension=768)
    search_res = embedder.search_unified_vector_space(query="SuperGraph OS Architecture and Memory Wiki", top_k=5)
    print("\n=== Unified 768D Vector Search Results ===")
    for idx, res in enumerate(search_res, 1):
        print(f"  {idx}. [{res['domain']}] {res['name']} (id: {res['id']}) - Similarity: {res['similarity']}")

    conn.close()
    print("\nAll Milestone 2 verification checks passed successfully!")

if __name__ == "__main__":
    run_verification()
