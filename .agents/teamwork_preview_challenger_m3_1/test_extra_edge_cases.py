"""
Extra Edge Case Verification for SQLite kg_edges and Embeddings.
"""
import sqlite3
import math
import json

# Test NaN min/max behavior in Python
sim_nan = float('nan')
clamped = max(0.0, min(1.0, float(sim_nan)))
print(f"Python min(1.0, nan): {min(1.0, sim_nan)}")
print(f"Python max(0.0, min(1.0, nan)): {clamped}")

# Test SQLite PRIMARY KEY with NULL source_id
conn = sqlite3.connect(":memory:")
conn.execute("""
    CREATE TABLE kg_edges (
        source_id TEXT,
        target_id TEXT,
        relation TEXT,
        strength REAL,
        properties TEXT,
        PRIMARY KEY (source_id, target_id, relation)
    )
""")

conn.execute("INSERT INTO kg_edges VALUES (NULL, 'target1', 'rel1', 0.5, '{}')")
conn.execute("INSERT INTO kg_edges VALUES (NULL, 'target1', 'rel1', 0.8, '{}')")
rows = conn.execute("SELECT * FROM kg_edges").fetchall()
print(f"SQLite rows with NULL source_id in PRIMARY KEY: {len(rows)}")
for r in rows:
    print(" ", r)
