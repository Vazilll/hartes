import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\vazus")
import sqlite3
import os
import json
from PIL import Image
import vazus_core.multimodal_knowledge as mk

print("=== 1. Testing Video Transcription & Chunking ===")
video_path = r"C:\vazus\knowledge\telegram_courses\МЫШЦЫ 20_80\2025-07-22 00-42-20_msg30.mp4"
if os.path.exists(video_path):
    print("Transcribing video:", video_path)
    video_scenes = mk.transcribe_and_chunk_media(video_path)
    print(f"Generated {len(video_scenes)} video scenes:")
    for sc in video_scenes:
        print(f" - ID: {sc['scene_id']}, Range: {sc['start_sec']}s -> {sc['end_sec']}s, Media: {sc['media_type']}")
        print(f"   Thumbnail: {sc['thumbnail_path']}")
    indexed_video = mk.index_scenes_to_supergraph(video_scenes)
    print(f"Indexed {indexed_video} video scenes into SuperGraph!")

print("\n=== 2. Verifying SQLite Database Entries ===")
for db_p in [r"C:\vazus\vazus.db", r"C:\vazus\services\memory\vazus.db"]:
    print("Checking DB:", db_p)
    conn = sqlite3.connect(db_p)
    cursor = conn.cursor()
    nodes = cursor.execute("SELECT id, name, domain, node_type, embedding_json, properties FROM kg_nodes WHERE domain='multimodal_av'").fetchall()
    print(f" Total kg_nodes in domain=multimodal_av: {len(nodes)}")
    for n in nodes[:5]:
        n_id, name, domain, node_type, emb_str, props_str = n
        emb = json.loads(emb_str) if emb_str else []
        props = json.loads(props_str) if props_str else {}
        print(f"  - Node ID: {n_id}")
        print(f"    Name: {name}")
        print(f"    Vector Dim: {len(emb)}")
        print(f"    Source File: {props.get('source_file')}")
        print(f"    Thumbnail Path: {props.get('thumbnail_path')}")

    edges = cursor.execute("SELECT source_id, target_id, relation FROM kg_edges WHERE relation IN ('BELONGS_TO', 'NEXT_SCENE')").fetchall()
    print(f" Total relevant kg_edges: {len(edges)}")
    for e in edges[:10]:
        print(f"  - Edge: {e[0]} --[{e[2]}]--> {e[1]}")
    conn.close()

print("\n=== 3. Verifying Thumbnails in .thumbnails ===")
thumb_dir = r"C:\vazus\knowledge\.thumbnails"
if os.path.exists(thumb_dir):
    files = [os.path.join(thumb_dir, f) for f in os.listdir(thumb_dir) if f.endswith('.jpg')]
    print(f"Total JPG thumbnails in {thumb_dir}: {len(files)}")
    for f in files[:10]:
        size_kb = os.path.getsize(f) / 1024.0
        with Image.open(f) as img:
            w, h = img.size
        print(f"  - {os.path.basename(f)}: {w}x{h} px, {size_kb:.1f} KB")
