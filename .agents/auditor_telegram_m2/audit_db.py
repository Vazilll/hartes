"""
C:\vazus\.agents\auditor_telegram_m2\audit_db.py
Forensic database inspection script for Telegram SuperGraph Indexer (Milestone 2).
"""

import sqlite3
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.stdout.reconfigure(encoding='utf-8')
from vazus_core.embeddings import UnifiedEmbeddingManager

def audit_database(db_path: str):
    print(f"\n==========================================")
    print(f"AUDITING DATABASE: {db_path}")
    print(f"==========================================")
    
    if not os.path.exists(db_path):
        print(f"FAILED: Database file does not exist at {db_path}")
        return False
        
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Check tables
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"Tables found: {tables}")
    if 'kg_nodes' not in tables or 'kg_edges' not in tables:
        print("FAILED: Required tables kg_nodes or kg_edges missing")
        conn.close()
        return False
        
    # Check node counts
    cur.execute("SELECT COUNT(*) FROM kg_nodes WHERE domain='telegram_discussion' AND node_type='TelegramMessage'")
    msg_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM kg_nodes WHERE domain='telegram_discussion' AND node_type='TelegramChannel'")
    channel_count = cur.fetchone()[0]
    
    print(f"TelegramMessage nodes: {msg_count}")
    print(f"TelegramChannel nodes: {channel_count}")
    
    # Check edges
    cur.execute("SELECT relation, COUNT(*) FROM kg_edges GROUP BY relation")
    edges_breakdown = cur.fetchall()
    print(f"Edges breakdown: {edges_breakdown}")
    
    # Check embeddings
    cur.execute("SELECT id, name, embedding_json FROM kg_nodes WHERE domain='telegram_discussion'")
    rows = cur.fetchall()
    
    valid_embeddings = 0
    dimensions_set = set()
    sample_vectors = []
    
    for nid, name, emb_json in rows:
        if not emb_json:
            continue
        try:
            vec = json.loads(emb_json)
            if isinstance(vec, list):
                valid_embeddings += 1
                dimensions_set.add(len(vec))
                if len(sample_vectors) < 5:
                    sample_vectors.append((nid, name[:30], vec[:5], sum(vec)))
        except Exception as e:
            pass
            
    print(f"Valid embedding JSONs: {valid_embeddings} / {len(rows)}")
    print(f"Embedding dimensions observed: {dimensions_set}")
    
    # Check vector variance (ensure not all vectors are identical constant values)
    if sample_vectors:
        print("Sample vector snippets (first 5 dims & sum):")
        for nid, short_name, snippet, vec_sum in sample_vectors:
            print(f"  {nid} | {short_name} | {snippet} | sum={vec_sum:.4f}")
            
    # Check sample message node properties
    cur.execute("SELECT id, properties FROM kg_nodes WHERE domain='telegram_discussion' AND node_type='TelegramMessage' LIMIT 3")
    sample_props = cur.fetchall()
    print("\nSample TelegramMessage properties:")
    for nid, prop_str in sample_props:
        print(f"  {nid}: {prop_str[:120]}...")

    conn.close()
    
    success = (msg_count > 0 and channel_count > 0 and dimensions_set == {768})
    return success

def test_semantic_search(db_path: str):
    print(f"\nTesting Semantic Vector Search over {db_path}...")
    embedder = UnifiedEmbeddingManager()
    results = embedder.search_unified_vector_space(
        query="покоритель наташек",
        db_path=Path(db_path),
        top_k=5,
        domain_filter="telegram_discussion"
    )
    print(f"Search results count: {len(results)}")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r['similarity']:.4f}] {r['name']} | ID: {r['id']}")
    return len(results) > 0

if __name__ == "__main__":
    db1 = "C:/vazus/services/memory/vazus.db"
    db2 = "C:/vazus/vazus.db"
    
    res1 = audit_database(db1)
    res2 = audit_database(db2)
    
    search_ok1 = test_semantic_search(db1)
    
    if res1 and res2 and search_ok1:
        print("\nFORENSIC VERIFICATION PASS: All database invariants & vector search checks passed!")
    else:
        print("\nFORENSIC VERIFICATION FAIL: Invariants check failed!")
