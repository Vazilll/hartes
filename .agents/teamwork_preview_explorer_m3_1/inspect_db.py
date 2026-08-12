import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

db_paths = [r'C:\vazus\vazus.db', r'C:\vazus\services\memory\vazus.db']

for path in db_paths:
    if os.path.exists(path):
        print(f"=== DB: {path} | Size: {os.path.getsize(path)} bytes ===")
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print("Tables:", [t[0] for t in tables])
        for t in tables:
            tname = t[0]
            count = cursor.execute(f'SELECT COUNT(*) FROM "{tname}"').fetchone()[0]
            cols = cursor.execute(f'PRAGMA table_info("{tname}")').fetchall()
            print(f"\n--- Table: {tname} ({count} rows) ---")
            for c in cols:
                print(f"  Col: {c[1]} | Type: {c[2]} | NotNull: {c[3]} | PK: {c[5]}")
            # print sample row if available
            sample = cursor.execute(f'SELECT * FROM "{tname}" LIMIT 2').fetchall()
            if sample:
                for row in sample:
                    print(f"  Sample row (truncated): {str(row)[:150]}")
        conn.close()
