import sys
import os
import sqlite3
import json
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Ensure C:\vazus is in sys.path
sys.path.insert(0, r"C:\vazus")

from vazus_core.telegram_indexer import index_telegram_messages, parse_jsonl_file, parse_md_file
from vazus_core.embeddings import UnifiedEmbeddingManager

def run_tests():
    print("--- 1. Inspecting Raw Data for Replies & Media ---")
    messages_dir = r"C:\vazus\knowledge\telegram_messages"
    db_path = r"C:\vazus\vazus.db"
    
    # Check sample raw jsonl and md lines
    for f in os.listdir(messages_dir):
        fpath = os.path.join(messages_dir, f)
        if f.endswith(".jsonl"):
            msgs = parse_jsonl_file(fpath)
            replies = [m for m in msgs if m.get("reply_to_msg_id") is not None]
            print(f"File {f}: total parsed msgs = {len(msgs)}, msgs with reply_to_msg_id = {len(replies)}")
            if replies:
                print(f"  Sample reply: {replies[0]}")
            else:
                # Inspect first 3 raw json lines directly to see JSON structure
                with open(fpath, "r", encoding="utf-8") as raw_f:
                    lines = [raw_f.readline() for _ in range(3)]
                print(f"  Sample raw lines from {f}:")
                for l in lines:
                    if l.strip():
                        print(f"    {l.strip()[:150]}")

    print("\n--- 2. Running Telegram Indexer ---")
    summary = index_telegram_messages(messages_dir=messages_dir, db_path=db_path)
    print("Indexing summary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    print("\n--- 3. Inspecting Database State in C:\\vazus\\vazus.db ---")
    dbs_to_check = [r"C:\vazus\vazus.db", r"C:\vazus\services\memory\vazus.db"]
    
    for db in dbs_to_check:
        if not os.path.exists(db):
            print(f"DB File {db} does NOT exist!")
            continue
        
        print(f"\n--- Checking DB: {db} ---")
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        
        # Check Node Counts by node_type
        cur.execute("SELECT node_type, COUNT(*) FROM kg_nodes WHERE domain='telegram_discussion' GROUP BY node_type")
        node_counts = dict(cur.fetchall())
        print(f"Node counts by node_type in 'telegram_discussion': {node_counts}")
        
        # Check 768D Vector Dimensions
        cur.execute("SELECT id, embedding_json FROM kg_nodes WHERE domain='telegram_discussion' LIMIT 5")
        rows = cur.fetchall()
        
        dim_samples = []
        for nid, emb_str in rows:
            if emb_str:
                emb = json.loads(emb_str)
                dim_samples.append(len(emb))
        
        cur.execute("SELECT COUNT(*) FROM kg_nodes WHERE domain='telegram_discussion' AND embedding_json IS NOT NULL AND length(embedding_json) > 10")
        nodes_with_emb = cur.fetchone()[0]
        
        print(f"Sample node embedding dimensions: {set(dim_samples)}")
        print(f"Total nodes with embeddings in 'telegram_discussion': {nodes_with_emb}")
        
        # Check Edge Counts by relation
        cur.execute("SELECT relation, COUNT(*) FROM kg_edges GROUP BY relation")
        edge_counts = dict(cur.fetchall())
        print(f"Edge counts by relation: {edge_counts}")
        
        conn.close()
        
    print("\n--- 4. Testing Vector Search Retrieval on C:\\vazus\\vazus.db ---")
    conn = sqlite3.connect(r"C:\vazus\vazus.db")
    cur = conn.cursor()
    
    cur.execute("SELECT id, name, description, properties, embedding_json FROM kg_nodes WHERE domain='telegram_discussion' AND node_type='TelegramMessage'")
    msg_rows = cur.fetchall()
    print(f"Loaded {len(msg_rows)} message nodes for semantic search.")
    
    embedder = UnifiedEmbeddingManager()
    query_text = "настройка и обучение нейросетей"
    query_emb = embedder.get_embedding(query_text)
    q_vec = np.array(query_emb, dtype=np.float32)
    q_norm = np.linalg.norm(q_vec)
    
    scores = []
    for nid, name, desc, props_str, emb_str in msg_rows:
        if not emb_str:
            continue
        emb = json.loads(emb_str)
        vec = np.array(emb, dtype=np.float32)
        v_norm = np.linalg.norm(vec)
        if q_norm > 0 and v_norm > 0:
            sim = float(np.dot(q_vec, vec) / (q_norm * v_norm))
            scores.append((sim, nid, name, desc))
            
    scores.sort(key=lambda x: x[0], reverse=True)
    
    print(f"\nTop 5 semantic search results for query: '{query_text}':")
    for sim, nid, name, desc in scores[:5]:
        print(f"  Score: {sim:.4f} | ID: {nid} | Name: {name}")
        clean_desc = desc.replace("\n", " ")[:120]
        print(f"    Snippet: {clean_desc}...\n")
        
    conn.close()

if __name__ == "__main__":
    run_tests()
