import re
import os
from pathlib import Path
from vazus_core.memory.db import get_db_connection
from vazus_core.engine.config import settings

conn = get_db_connection()
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print("Existing tables:", tables)

for t in tables:
    t_name = t[0]
    # Whitelist table name identifier
    if not re.match(r"^[a-zA-Z0-9_]+$", t_name):
        continue
    cur.execute(f"PRAGMA table_info(\"{t_name}\")")
    cols = cur.fetchall()
    print(f"Table {t_name}: {[c[1] for c in cols]}")

conn.close()
