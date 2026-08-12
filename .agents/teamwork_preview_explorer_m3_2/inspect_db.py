import sqlite3
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"C:\vazus\vazus.db")
cur = conn.cursor()

print("=== MediaScene Sample ===")
row_scene = cur.execute("SELECT id, name, domain, node_type, description, tags, properties FROM kg_nodes WHERE node_type='MediaScene' LIMIT 1").fetchone()
if row_scene:
    print("ID:", row_scene[0])
    print("Name:", row_scene[1])
    print("Domain:", row_scene[2])
    print("Tags:", row_scene[5])
    props = json.loads(row_scene[6])
    print("Properties:")
    for k, v in props.items():
        print(f"  {k}: {repr(v)[:100]}")

print("\n=== TelegramMessage Sample ===")
row_msg = cur.execute("SELECT id, name, domain, node_type, description, tags, properties FROM kg_nodes WHERE node_type='TelegramMessage' LIMIT 1").fetchone()
if row_msg:
    print("ID:", row_msg[0])
    print("Name:", row_msg[1])
    print("Domain:", row_msg[2])
    print("Tags:", row_msg[5])
    props = json.loads(row_msg[6])
    print("Properties:")
    for k, v in props.items():
        print(f"  {k}: {repr(v)[:100]}")

print("\n=== TelegramChannel Sample ===")
row_ch = cur.execute("SELECT id, name, domain, node_type, description, tags, properties FROM kg_nodes WHERE node_type='TelegramChannel' LIMIT 1").fetchone()
if row_ch:
    print("ID:", row_ch[0])
    print("Name:", row_ch[1])
    print("Properties:", json.loads(row_ch[6]))

print("\n=== Edge Relations ===")
edges = cur.execute("SELECT relation, COUNT(*) FROM kg_edges GROUP BY relation").fetchall()
for r, cnt in edges:
    print(f"  Relation '{r}': {cnt}")
