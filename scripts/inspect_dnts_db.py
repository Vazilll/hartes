import sqlite3, os

db_path = r"C:\vazus\memory\vazus.db"
print("DB Path:", db_path, "Exists:", os.path.exists(db_path))

if not os.path.exists(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    print("Created directory for vazus.db")

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print("Existing tables:", tables)
for t in tables:
    t_name = t[0]
    cur.execute(f"PRAGMA table_info({t_name})")
    cols = cur.fetchall()
    print(f"Table {t_name}: {[c[1] for c in cols]}")

conn.close()
