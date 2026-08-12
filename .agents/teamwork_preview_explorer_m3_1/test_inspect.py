import sys
import sqlite3
import json

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('C:/vazus/vazus.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

ms = cur.execute("SELECT id, name, domain, node_type, description, properties FROM kg_nodes WHERE node_type = 'MediaScene' AND id LIKE 'scene_%' LIMIT 1").fetchone()
if ms:
    props = json.loads(ms["properties"])
    print("MediaScene ID:", ms["id"])
    print("MediaScene Name:", ms["name"])
    print("MediaScene Keys:", list(props.keys()))
    print("MediaScene JSON:\n", json.dumps(props, indent=2, ensure_ascii=False))

conn.close()
