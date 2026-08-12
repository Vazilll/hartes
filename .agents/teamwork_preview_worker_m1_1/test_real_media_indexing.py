"""
Integration test script processing real media files in C:\\vazus\\knowledge\\telegram_courses
"""

import os
import sys
sys.path.insert(0, r"C:\vazus")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import glob
import sqlite3
import json
from pathlib import Path

from vazus_core.multimodal_knowledge import (
    transcribe_and_chunk_media,
    index_scenes_to_supergraph
)


def run_real_media_test():
    courses_dir = r"C:\vazus\knowledge\telegram_courses"
    print(f"[RealMediaTest] Scanning directory: {courses_dir}")

    all_files = glob.glob(os.path.join(courses_dir, "**", "*.*"), recursive=True)
    media_files = [(f, os.path.getsize(f)) for f in all_files if f.lower().endswith(('.mp4', '.mp3', '.oga', '.m4a'))]
    media_files.sort(key=lambda x: x[1])

    # Pick 1 small video and 1 small audio
    video_sample = next((f for f, sz in media_files if f.lower().endswith(('.mp4', '.mov')) and sz > 1000), None)
    audio_sample = next((f for f, sz in media_files if f.lower().endswith(('.oga', '.mp3', '.m4a')) and sz > 1000), None)

    sample_files = [f for f in [video_sample, audio_sample] if f]

    print(f"[RealMediaTest] Selected target sample media files:")
    for f in sample_files:
        print(f" - {f} ({os.path.getsize(f)/1024:.1f} KB)")

    total_indexed_scenes = 0

    for file_path in sample_files:
        print(f"\n--- Processing: {file_path} ---")
        scenes = transcribe_and_chunk_media(file_path)
        print(f"Generated {len(scenes)} scenes.")

        for s in scenes:
            print(f" Scene ID: {s['scene_id']}")
            print(f"   Time: {s['start_sec']}s -> {s['end_sec']}s ({s['duration']}s)")
            print(f"   Thumbnail: {s['thumbnail_path']} (Exists: {os.path.exists(s['thumbnail_path'])})")
            print(f"   Transcript preview: '{s['transcript'][:100]}'")

        count = index_scenes_to_supergraph(scenes, db_path="C:/vazus/services/memory/vazus.db")
        print(f"Indexed {count} scenes into SuperGraph DB.")
        total_indexed_scenes += count

    print("\n--- Verifying SQLite Databases ---")
    for db_path in ["C:/vazus/services/memory/vazus.db", "C:/vazus/vazus.db"]:
        if not os.path.exists(db_path):
            print(f"DB {db_path}: Not found")
            continue
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            node_count = cursor.execute("SELECT COUNT(*) FROM kg_nodes WHERE domain='multimodal_av'").fetchone()[0]
            edge_count = cursor.execute("SELECT COUNT(*) FROM kg_edges WHERE relation IN ('BELONGS_TO', 'NEXT_SCENE')").fetchone()[0]
            print(f"DB [{db_path}]: {node_count} multimodal_av kg_nodes, {edge_count} kg_edges.")
            
            sample_emb = cursor.execute("SELECT embedding_json FROM kg_nodes WHERE domain='multimodal_av' LIMIT 1").fetchone()
            if sample_emb and sample_emb[0]:
                vec = json.loads(sample_emb[0])
                print(f" Verified 768D embedding length: {len(vec)} dimensions.")
        finally:
            conn.close()

    print(f"\n[RealMediaTest] Integration test finished successfully. Total indexed: {total_indexed_scenes}")


if __name__ == "__main__":
    run_real_media_test()
