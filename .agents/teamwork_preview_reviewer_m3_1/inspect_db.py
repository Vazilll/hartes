import sqlite3
import json

db_path = "C:/vazus/memory/dnts.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("Tables in dnts.db:", tables)

for t in ["kg_nodes", "kg_edges", "llm_cache"]:
    cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"Table {t} row count: {cnt}")

sample_edge = conn.execute("SELECT * FROM kg_edges LIMIT 1").fetchone()
if sample_edge:
    print("\nSample edge:")
    print("  source_id:", sample_edge["source_id"])
    print("  target_id:", sample_edge["target_id"])
    print("  relation: ", sample_edge["relation"])
    print("  strength: ", sample_edge["strength"])
    props = json.loads(sample_edge["properties"])
    print("  properties:", props)

sample_node = conn.execute("SELECT id, name, domain, node_type, embedding_json FROM kg_nodes WHERE embedding_json IS NOT NULL LIMIT 1").fetchone()
if sample_node:
    print("\nSample node:")
    print("  id:", sample_node["id"])
    print("  name:", sample_node["name"])
    print("  domain:", sample_node["domain"])
    emb = json.loads(sample_node["embedding_json"])
    print("  embedding dim:", len(emb))

sample_cache = conn.execute("SELECT cache_key, created_at, embedding_json FROM llm_cache LIMIT 1").fetchone()
if sample_cache:
    print("\nSample llm_cache:")
    print("  cache_key:", sample_cache["cache_key"])
    emb_c = json.loads(sample_cache["embedding_json"])
    print("  embedding dim:", len(emb_c))
