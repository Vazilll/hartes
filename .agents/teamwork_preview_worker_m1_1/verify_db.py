import sqlite3
import json
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

for db_path in ['C:/vazus/services/memory/vazus.db', 'C:/vazus/vazus.db']:
    print(f"=== DB: {db_path} ===")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    nodes = cursor.execute("SELECT id, name, domain, node_type, embedding_json FROM kg_nodes WHERE domain='multimodal_av' LIMIT 5").fetchall()
    edges = cursor.execute("SELECT source_id, target_id, relation FROM kg_edges WHERE relation IN ('BELONGS_TO', 'NEXT_SCENE') LIMIT 5").fetchall()
    print(f"Total multimodal_av kg_nodes: {len(nodes)}")
    for n in nodes:
        emb_len = len(json.loads(n[4])) if n[4] else 0
        print(f" Node {n[0]}: name='{n[1]}', domain={n[2]}, type={n[3]}, 768D vector dim={emb_len}")
    print(f"Edges sample count: {len(edges)}")
    for e in edges:
        print(f" Edge: {e[0]} -[{e[2]}]-> {e[1]}")
    conn.close()
