import sys
import os
import sqlite3
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def verify():
    print("=== Verifying Generated Thumbnails and SQLite DB ===")
    
    thumb_dir = r"C:\vazus\knowledge\.thumbnails"
    files = os.listdir(thumb_dir)
    print(f"Thumbnails in {thumb_dir}: {files}")

    for f in files:
        full_p = os.path.join(thumb_dir, f)
        if os.path.isfile(full_p):
            im = Image.open(full_p)
            print(f"File: {f} | Format: {im.format} | Size: {im.size} | Mode: {im.mode}")

    db_path = r"C:\vazus\.agents\teamwork_preview_challenger_m1_1\test_vazus.db"
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        cur.execute("SELECT id, name, node_type, description FROM kg_nodes")
        nodes = cur.fetchall()
        print(f"\nNodes in DB ({len(nodes)}):")
        for n in nodes:
            print(f" Node ID: {n[0]} | Type: {n[2]} | Name: {n[1]}")

        cur.execute("SELECT source_id, target_id, relation FROM kg_edges")
        edges = cur.fetchall()
        print(f"\nEdges in DB ({len(edges)}):")
        for e in edges:
            print(f" Edge: {e[0]} --[{e[2]}]--> {e[1]}")
        
        conn.close()

if __name__ == "__main__":
    verify()
