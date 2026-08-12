import glob
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

db_paths = [
    r"C:\vazus\vazus.db",
    r"C:\vazus\services\memory\vazus.db",
    r"C:\vazus\memory\vazus.db",
    r"C:\vazus\memory\dnts.db"
]

for p in db_paths:
    if os.path.exists(p):
        print(f"\n=================== DB: {p} ===================")
        try:
            conn = sqlite3.connect(p)
            cursor = conn.cursor()
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            for tname, tsql in tables:
                print(f"\nTable: {tname}")
                print(f"Schema SQL:\n{tsql}")
                cursor.execute(f"PRAGMA table_info({tname});")
                cols = cursor.fetchall()
                print("Columns:", [c[1] for c in cols])
                cursor.execute(f"SELECT COUNT(*) FROM {tname};")
                cnt = cursor.fetchone()[0]
                print(f"Row count: {cnt}")
            conn.close()
        except Exception as e:
            print(f"Error reading DB {p}: {e}")
    else:
        print(f"DB path does not exist yet: {p}")
