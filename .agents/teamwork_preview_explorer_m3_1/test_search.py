import sys
import time
import json
import sqlite3
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, "C:/vazus")
from vazus_core.embeddings import UnifiedEmbeddingManager

embedder = UnifiedEmbeddingManager()

query = "тест"
t0 = time.time()

# Get query embedding
q_vec = embedder.embed_query(query)
t1 = time.time()

print(f"Query: '{query}'")
print(f"Embedding computation time: {(t1 - t0)*1000:.2f} ms (dim={len(q_vec)})")

# Search vazus.db
results = embedder.search_unified_vector_space(query, db_path=Path("C:/vazus/vazus.db"), top_k=5)
t2 = time.time()

print(f"Vector search time: {(t2 - t1)*1000:.2f} ms")
print(f"Top {len(results)} results:")
for idx, r in enumerate(results, 1):
    print(f"\n{idx}. [{r['node_type']}] {r['name']} (score: {r['similarity']:.4f})")
    print(f"   ID: {r['id']}")
    print(f"   Description: {r['description'][:100]}...")
    props = r.get("properties", {})
    if r['node_type'] == 'MediaScene':
        print(f"   Timestamps: {props.get('start_sec')}s - {props.get('end_sec')}s")
        print(f"   Thumbnail: {props.get('thumbnail_path')}")
        print(f"   Source: {props.get('source_file')}")
    elif r['node_type'] == 'TelegramMessage':
        print(f"   Sender: {props.get('sender')} | Channel: {props.get('channel_name')}")
        print(f"   Msg ID: {props.get('msg_id')} | Reply To: {props.get('reply_to_msg_id')}")
