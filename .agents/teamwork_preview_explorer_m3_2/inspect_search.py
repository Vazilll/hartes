import sqlite3
import json
import time
import sys
import os
sys.path.insert(0, r"C:\vazus")
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

t0 = time.time()
conn = sqlite3.connect(r"C:\vazus\vazus.db")
cur = conn.cursor()

rows = cur.execute("SELECT id, name, node_type, description, properties, embedding_json FROM kg_nodes WHERE embedding_json IS NOT NULL AND node_type IN ('MediaScene', 'TelegramMessage')").fetchall()
t_load = time.time() - t0
print(f"Loaded {len(rows)} nodes in {t_load*1000:.2f} ms")

# Try initializing UnifiedEmbeddingManager
try:
    from vazus_core.embeddings import UnifiedEmbeddingManager
    embedder = UnifiedEmbeddingManager()
    query_text = "как проходить уроки"
    t_emb0 = time.time()
    query_vec = np.array(embedder.get_embedding(query_text), dtype=np.float32)
    t_emb = time.time() - t_emb0
    print(f"Query embedding generated in {t_emb*1000:.2f} ms (dim: {len(query_vec)})")
except Exception as e:
    print(f"Embedding manager fallback: {e}")
    embedder = None
    query_vec = None

node_ids = []
node_types = []
node_names = []
node_props = []
vectors = []

for r in rows:
    if r[5]:
        try:
            vec = json.loads(r[5])
            if len(vec) == 768:
                node_ids.append(r[0])
                node_names.append(r[1])
                node_types.append(r[2])
                node_props.append(r[4])
                vectors.append(vec)
        except Exception:
            pass

mat = np.array(vectors, dtype=np.float32)
print(f"Vector matrix shape: {mat.shape}")

if query_vec is not None and mat.shape[0] > 0:
    t_sim0 = time.time()
    # Normalize vectors just in case
    mat_norm = mat / np.linalg.norm(mat, axis=1, keepdims=True)
    q_norm = query_vec / np.linalg.norm(query_vec)
    scores = np.dot(mat_norm, q_norm)
    top_indices = np.argsort(scores)[::-1][:5]
    t_sim = time.time() - t_sim0
    print(f"Cosine similarity search across {len(scores)} vectors completed in {t_sim*1000:.2f} ms")
    
    print("\nTop 5 Results:")
    for idx in top_indices:
        print(f"[{node_types[idx]}] {node_names[idx]} (Score: {scores[idx]:.4f})")
