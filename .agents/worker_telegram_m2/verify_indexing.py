import sys
import os
import sqlite3
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'C:/vazus')

from vazus_core.embeddings import UnifiedEmbeddingManager

dbs = ["C:/vazus/services/memory/vazus.db", "C:/vazus/vazus.db"]

for db_path in dbs:
    print(f"\n==========================================")
    print(f"VERIFYING DATABASE: {db_path}")
    print(f"==========================================")

    if not os.path.exists(db_path):
        print(f"ERROR: Database file {db_path} does not exist!")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Verify Nodes Breakdown
    node_counts = cur.execute(
        "SELECT domain, node_type, COUNT(*) FROM kg_nodes GROUP BY domain, node_type"
    ).fetchall()
    print("Node breakdown:")
    for dom, ntype, cnt in node_counts:
        print(f"  [{dom}] {ntype}: {cnt}")

    # 2. Check TelegramMessage and TelegramChannel exact counts
    tg_msg_cnt = cur.execute(
        "SELECT COUNT(*) FROM kg_nodes WHERE domain='telegram_discussion' AND node_type='TelegramMessage'"
    ).fetchone()[0]
    tg_ch_cnt = cur.execute(
        "SELECT COUNT(*) FROM kg_nodes WHERE domain='telegram_discussion' AND node_type='TelegramChannel'"
    ).fetchone()[0]

    print(f"\nTelegramMessage count: {tg_msg_cnt} (Expected: 4906)")
    print(f"TelegramChannel count: {tg_ch_cnt} (Expected: 5)")

    if tg_msg_cnt != 4906:
        print(f"ERROR: Expected 4906 TelegramMessage nodes, got {tg_msg_cnt}")
        sys.exit(1)
    if tg_ch_cnt != 5:
        print(f"ERROR: Expected 5 TelegramChannel nodes, got {tg_ch_cnt}")
        sys.exit(1)

    # 3. Verify Embeddings (Check vector length == 768 for all telegram_discussion nodes)
    emb_rows = cur.execute(
        "SELECT id, embedding_json FROM kg_nodes WHERE domain='telegram_discussion'"
    ).fetchall()
    
    valid_embeddings = 0
    for nid, emb_json in emb_rows:
        if not emb_json:
            continue
        emb = json.loads(emb_json)
        if isinstance(emb, list) and len(emb) == 768:
            valid_embeddings += 1

    print(f"Nodes with valid 768D embeddings: {valid_embeddings}/{len(emb_rows)}")
    if valid_embeddings != len(emb_rows):
        print(f"ERROR: Not all nodes have 768D embeddings!")
        sys.exit(1)

    # 4. Verify Edges Breakdown
    edge_counts = cur.execute(
        "SELECT relation, COUNT(*) FROM kg_edges GROUP BY relation"
    ).fetchall()
    print("\nEdge breakdown:")
    for rel, cnt in edge_counts:
        print(f"  Relation '{rel}': {cnt}")

    belongs_to_cnt = cur.execute(
        "SELECT COUNT(*) FROM kg_edges WHERE relation='BELONGS_TO' AND source_id LIKE 'tg_msg_%'"
    ).fetchone()[0]
    media_edge_cnt = cur.execute(
        "SELECT COUNT(*) FROM kg_edges WHERE relation='REFERENCES_MEDIA'"
    ).fetchone()[0]

    print(f"\nBELONGS_TO edges for Telegram messages: {belongs_to_cnt} (Expected: 4906)")
    print(f"REFERENCES_MEDIA edges: {media_edge_cnt}")

    # 5. Inspect Sample Message Node & Edge
    sample_node = cur.execute(
        "SELECT id, name, description, properties FROM kg_nodes WHERE domain='telegram_discussion' AND node_type='TelegramMessage' LIMIT 1"
    ).fetchone()
    print("\nSample TelegramMessage node:")
    print(f"  ID: {sample_node[0]}")
    print(f"  Name: {sample_node[1]}")
    print(f"  Snippet: {sample_node[2][:100]}...")
    print(f"  Properties: {sample_node[3][:150]}...")

    conn.close()

# 6. Test Semantic Search using UnifiedEmbeddingManager over vazus.db
print(f"\n==========================================")
print(f"TESTING SEMANTIC VECTOR SEARCH")
print(f"==========================================")

embedder = UnifiedEmbeddingManager()
search_query = "покоритель наташек"
print(f"Running search query: '{search_query}'...")
results = embedder.search_unified_vector_space(
    query=search_query,
    db_path=Path("C:/vazus/vazus.db"),
    top_k=5,
    domain_filter="telegram_discussion"
)

print(f"Search results count: {len(results)}")
for idx, res in enumerate(results, 1):
    print(f"  [{idx}] {res['name']} (Sim: {res['similarity']})")
    print(f"      Text: {res['description'][:80]}...")

print("\nAll database & search verifications passed successfully!")
