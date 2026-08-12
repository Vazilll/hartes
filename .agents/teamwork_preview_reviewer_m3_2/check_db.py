import sqlite3
import json

for db_path in ["C:/vazus/vazus.db", "C:/vazus/services/memory/vazus.db"]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    wiki_notes = c.execute("SELECT id, name, node_type, embedding_json FROM kg_nodes WHERE node_type = 'WikiNote'").fetchall()
    wiki_sections = c.execute("SELECT id, name, node_type, embedding_json FROM kg_nodes WHERE node_type = 'WikiSection'").fetchall()

    print(f"--- DB: {db_path} ---")
    print(f"WikiNote count: {len(wiki_notes)}")
    print(f"WikiSection count: {len(wiki_sections)}")

    if wiki_notes:
        sample = wiki_notes[0]
        emb = json.loads(sample["embedding_json"])
        print(f"Sample WikiNote ID: {sample['id']}")
        print(f"Sample WikiNote Name: {sample['name']}")
        print(f"Embedding Vector Dimension: {len(emb)}")

    if wiki_sections:
        sample_sec = wiki_sections[0]
        emb_sec = json.loads(sample_sec["embedding_json"])
        print(f"Sample WikiSection ID: {sample_sec['id']}")
        print(f"Sample WikiSection Name: {sample_sec['name']}")
        print(f"Section Embedding Vector Dimension: {len(emb_sec)}")

    conn.close()
