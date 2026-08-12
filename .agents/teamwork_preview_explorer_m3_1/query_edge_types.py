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
    rel_counts = cursor.execute("SELECT relation, COUNT(*) FROM kg_edges GROUP BY relation").fetchall()
    for rel, count in rel_counts:
        print(f"  Relation '{rel}': {count} edges")
    conn.close()
