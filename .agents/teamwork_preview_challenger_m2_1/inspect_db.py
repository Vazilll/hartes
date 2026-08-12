import sqlite3
import json
from pathlib import Path

db_path = Path("C:/vazus/services/memory/vazus.db")
if not db_path.exists():
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables in vazus.db:", tables)

for t in tables:
    count = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"  Table {t}: {count} rows")

print("\nkg_nodes domain counts:")
for r in conn.execute("SELECT domain, count(*) as c FROM kg_nodes GROUP BY domain").fetchall():
    print(f"  Domain '{r['domain']}': {r['c']} nodes")

print("\nkg_nodes node_types:")
for r in conn.execute("SELECT node_type, count(*) as c FROM kg_nodes GROUP BY node_type").fetchall():
    print(f"  NodeType '{r['node_type']}': {r['c']} nodes")

print("\nkg_edges relations:")
for r in conn.execute("SELECT relation, count(*) as c FROM kg_edges GROUP BY relation").fetchall():
    print(f"  Relation '{r['relation']}': {r['c']} edges")

sample_node = conn.execute("SELECT * FROM kg_nodes LIMIT 1").fetchone()
if sample_node:
    print("\nSample Node:")
    print("  ID:", sample_node["id"])
    print("  Name:", sample_node["name"])
    print("  Domain:", sample_node["domain"])
    print("  Type:", sample_node["node_type"])
    emb = json.loads(sample_node["embedding_json"]) if sample_node["embedding_json"] else []
    print("  Embedding vector dim:", len(emb))

conn.close()
