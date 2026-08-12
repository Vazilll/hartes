import sys
import os
import sqlite3
import json
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, r"C:\vazus")
from vazus_core.embeddings import UnifiedEmbeddingManager

def verify_all():
    db_path = r"C:\vazus\vazus.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    print("=== EMPIRICAL VERIFICATION REPORT ===")
    
    # 1. Node Counts
    cur.execute("SELECT node_type, COUNT(*) FROM kg_nodes WHERE domain='telegram_discussion' GROUP BY node_type")
    nodes_by_type = dict(cur.fetchall())
    print(f"\n1. Node Counts (domain='telegram_discussion'):")
    print(f"   TelegramMessage nodes: {nodes_by_type.get('TelegramMessage', 0)} (Expected: 4906)")
    print(f"   TelegramChannel nodes: {nodes_by_type.get('TelegramChannel', 0)} (Expected: 5)")
    
    # 2. Embedding Dimensions
    cur.execute("SELECT id, embedding_json FROM kg_nodes WHERE domain='telegram_discussion'")
    emb_rows = cur.fetchall()
    dims = set()
    null_emb_count = 0
    for nid, emb_str in emb_rows:
        if not emb_str:
            null_emb_count += 1
            continue
        try:
            emb = json.loads(emb_str)
            dims.add(len(emb))
        except Exception:
            null_emb_count += 1
            
    print(f"\n2. Vector Dimensions:")
    print(f"   Unique Embedding Dimensions found: {dims} (Expected: {{768}})")
    print(f"   Nodes with null/invalid embeddings: {null_emb_count} (Expected: 0)")
    
    # 3. Edge Counts
    cur.execute("SELECT relation, COUNT(*) FROM kg_edges GROUP BY relation")
    edges_by_relation = dict(cur.fetchall())
    print(f"\n3. Edge Counts (all relations in vazus.db):")
    for rel, cnt in edges_by_relation.items():
        print(f"   {rel}: {cnt}")
        
    # Check specific telegram edges
    cur.execute("""
        SELECT e.relation, COUNT(*) 
        from kg_edges e 
        JOIN kg_nodes n ON e.source_id = n.id 
        WHERE n.domain='telegram_discussion' 
        GROUP BY e.relation
    """)
    tg_edges = dict(cur.fetchall())
    print(f"\n4. Edges originating from Telegram nodes:")
    for rel, cnt in tg_edges.items():
        print(f"   {rel}: {cnt}")
        
    # 4. Semantic Search Query Test
    print(f"\n5. Semantic Retrieval Test:")
    embedder = UnifiedEmbeddingManager()
    
    queries = [
        "настройка и обучение нейросетей",
        "скрипт для сайтов знакомств",
        "рейтинговый норматив и зачёт"
    ]
    
    cur.execute("SELECT id, name, description, embedding_json FROM kg_nodes WHERE domain='telegram_discussion' AND node_type='TelegramMessage'")
    msg_rows = cur.fetchall()
    
    for q in queries:
        q_emb = embedder.get_embedding(q)
        q_vec = np.array(q_emb, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        
        scores = []
        for nid, name, desc, emb_str in msg_rows:
            if not emb_str:
                continue
            emb = json.loads(emb_str)
            vec = np.array(emb, dtype=np.float32)
            v_norm = np.linalg.norm(vec)
            if q_norm > 0 and v_norm > 0:
                sim = float(np.dot(q_vec, vec) / (q_norm * v_norm))
                scores.append((sim, nid, name, desc))
                
        scores.sort(key=lambda x: x[0], reverse=True)
        top1 = scores[0] if scores else (0.0, None, None, None)
        print(f"   Query: '{q}'")
        print(f"     Top 1: [{top1[0]:.4f}] {top1[2]}")
        print(f"     Snippet: {top1[3][:100]}...\n")
        
    conn.close()

if __name__ == "__main__":
    verify_all()
