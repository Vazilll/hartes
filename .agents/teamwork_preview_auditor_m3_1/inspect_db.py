import sqlite3
import json

db_path = "C:/vazus/memory/dnts.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables in dnts.db:", tables)

for t in tables:
    count = cursor.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"\nTable: {t} (row count: {count})")
    schema = cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{t}'").fetchone()[0]
    print(f"Schema: {schema}")
    
    rows = cursor.execute(f"SELECT * FROM {t} LIMIT 3").fetchall()
    for i, r in enumerate(rows):
        row_dict = dict(r)
        # truncate large fields for display
        if "embedding_json" in row_dict and row_dict["embedding_json"]:
            emb = json.loads(row_dict["embedding_json"])
            row_dict["embedding_json"] = f"List[float] len={len(emb)} first_3={emb[:3]} last_3={emb[-3:]}"
        if "properties" in row_dict and row_dict["properties"] and len(row_dict["properties"]) > 200:
            row_dict["properties"] = row_dict["properties"][:200] + "..."
        if "description" in row_dict and row_dict["description"] and len(row_dict["description"]) > 100:
            row_dict["description"] = row_dict["description"][:100] + "..."
        print(f"  Row {i+1}: {row_dict}")

conn.close()
