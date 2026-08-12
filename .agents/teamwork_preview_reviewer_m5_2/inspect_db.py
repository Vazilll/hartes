import sqlite3
import os
import json

def inspect_db(db_path):
    print(f"=== Inspecting {db_path} ===")
    if not os.path.exists(db_path):
        print("FILE NOT FOUND")
        return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()
    print("Tables:", [t[0] for t in tables])
    for table in tables:
        tname = table[0]
        cur.execute(f"SELECT count(*) FROM [{tname}];")
        cnt = cur.fetchone()[0]
        print(f"  Table [{tname}]: {cnt} rows")
        cur.execute(f"PRAGMA table_info([{tname}]);")
        cols = [c[1] for c in cur.fetchall()]
        print(f"    Columns: {cols}")
    conn.close()

inspect_db(r"C:\vazus\services\memory\vazus.db")
print("\n" + "="*50 + "\n")
inspect_db(r"C:\vazus\memory\dnts.db")
