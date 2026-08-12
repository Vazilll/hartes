import json
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

db_path = r"C:\vazus\services\memory\vazus.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT id, name, domain, node_type, description, tags, properties FROM kg_nodes WHERE domain='multimodal_av' LIMIT 10;")
scenes = cursor.fetchall()
for s in scenes:
    print(f"ID: {s[0]}")
    print(f"Name: {s[1]}")
    print(f"Type: {s[3]}")
    print(f"Description: {s[4][:100]}...")
    print(f"Tags: {s[5]}")
    print(f"Properties: {s[6]}")
    print("-" * 50)

conn.close()
