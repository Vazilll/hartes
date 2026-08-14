import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')
db_path = r"C:\vazus\memory\vazus.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

rows = cursor.execute("SELECT id, name, domain, node_type, description, properties FROM kg_nodes").fetchall()

keywords = ["таблет", "бад", "препарат", "дозиров", "витамин", "омега", "магний", "цинк", "ноотроп", "медикамент", "прием", "аптек", "купить", "здоровье", "медицин", "сон"]

found = []
for r in rows:
    text = f"{r[1]} {r[2]} {r[3]} {r[4]} {r[5]}".lower()
    for kw in keywords:
        if kw in text:
            found.append(r)
            break

print(f"Found {len(found)} matching nodes out of {len(rows)}:")
for f in found:
    print(f"ID: {f[0]} | Name: {f[1]} | Type: {f[3]}")
    print(f"Description: {f[4]}")
    print(f"Properties: {f[5]}")
    print("-" * 60)

conn.close()
