import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

for db_path in [r'C:\vazus\vazus.db', r'C:\vazus\services\memory\vazus.db']:
    if not os.path.exists(db_path):
        continue
    print(f"\n================ DB: {db_path} ================")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query ThesisNode and ProtocolNode
    nodes = cursor.execute("SELECT id, name, node_type, domain, tags, properties FROM kg_nodes WHERE node_type IN ('ThesisNode', 'ProtocolNode') LIMIT 10").fetchall()
    print(f"--- ThesisNode / ProtocolNode count sample ({len(nodes)}) ---")
    for n in nodes:
        print(f"  ID: {n[0]} | Type: {n[2]} | Name: {n[1]} | Tags: {n[4]}")
        print(f"  Props: {n[5][:120] if n[5] else ''}")

    # Query relations CAUSES, REQUIRES, CONTRADICTS
    edges = cursor.execute("SELECT source_id, target_id, relation, strength, properties FROM kg_edges WHERE relation IN ('CAUSES', 'REQUIRES', 'CONTRADICTS', 'BELONGS_TO') LIMIT 15").fetchall()
    print(f"\n--- Specific Edge Relations ({len(edges)}) ---")
    for e in edges:
        print(f"  Edge: {e[0]} --[{e[2]} (str={e[3]})]--> {e[1]}")

    conn.close()
