import re
from vazus_core.memory.db import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()
tables = [t[0] for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
print("Tables:", tables)

for t in tables:
    # Whitelist / sanitize table identifier to prevent SQL injection
    if not re.match(r"^[a-zA-Z0-9_]+$", t):
        continue
    try:
        count = cursor.execute(f"SELECT COUNT(*) FROM \"{t}\"").fetchone()[0]
        print(f"Table {t}: {count} rows")
        if any(k in t for k in ["kg", "node", "wiki", "memory", "rayt"]):
            rows = cursor.execute(f"SELECT * FROM \"{t}\" LIMIT 5").fetchall()
            print(f"  Sample {t}: {rows[:2]}")
    except Exception as e:
        print(f"Error reading {t}: {e}")

conn.close()
