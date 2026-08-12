import json
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

db_path = r"C:\vazus\services\memory\vazus.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== SAMPLE KG_NODES ===")
cursor.execute("SELECT id, name, domain, node_type, description, tags, properties FROM kg_nodes LIMIT 10;")
nodes = cursor.fetchall()
for n in nodes:
    print(f"ID: {n[0]} | Name: {n[1]} | Domain: {n[2]} | Type: {n[3]}")
    print(f"  Description: {n[4][:80]}...")
    print(f"  Properties: {n[6]}")

print("\n=== SAMPLE KG_EDGES ===")
cursor.execute("SELECT source_id, target_id, relation, strength, properties FROM kg_edges LIMIT 10;")
edges = cursor.fetchall()
for e in edges:
    print(f"Source: {e[0]} -> Target: {e[1]} | Relation: {e[2]} | Strength: {e[3]}")
    print(f"  Properties: {e[4]}")

print("\n=== DOMAINS IN KG_NODES ===")
cursor.execute("SELECT DISTINCT domain, node_type, COUNT(*) FROM kg_nodes GROUP BY domain, node_type;")
print(cursor.fetchall())

conn.close()
