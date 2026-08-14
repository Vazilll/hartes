import sqlite3
import sqlite_vec
import os

db_paths = [
    r"C:\vazus\services\memory\vazus.db",  # canonical — единственная БД
]

for db in db_paths:
    if os.path.exists(db):
        print(f"Backfilling {db}...")
        conn = sqlite3.connect(db)
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
        except Exception as e:
            print(f"Failed to load vec for {db}: {e}")
            continue
            
        conn.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_kg_nodes USING vec0(
                node_id TEXT KEY,
                embedding float[768]
            );
            DELETE FROM vec_kg_nodes;
            INSERT INTO vec_kg_nodes(node_id, embedding)
            SELECT id, embedding_json FROM kg_nodes 
            WHERE embedding_json IS NOT NULL AND embedding_json != '[]';
        """)
        conn.commit()
        
        count = conn.execute("SELECT count(*) FROM vec_kg_nodes").fetchone()[0]
        print(f"Backfilled {count} vectors in {db}")
        conn.close()
