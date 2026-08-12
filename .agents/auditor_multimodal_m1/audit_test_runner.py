import os
import sys
import json
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\vazus")

print("--- AUDIT EXECUTION TEST ---")

# Test 1: Module Import
import vazus_core.multimodal_knowledge as mk
print("[PASS] Import successful")

# Test 2: Audio Transcription & Hybrid Chunking
audio_path = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\media_174.oga"
assert os.path.exists(audio_path), f"Audio file missing: {audio_path}"

scenes = mk.transcribe_and_chunk_media(audio_path)
print(f"[PASS] Audio transcription completed. Generated {len(scenes)} scenes.")
assert len(scenes) > 0, "No scenes generated from audio!"

for idx, sc in enumerate(scenes):
    print(f"  Scene {idx+1}: ID={sc['scene_id']}, Time={sc['start_sec']}s->{sc['end_sec']}s (duration: {sc['duration']}s)")
    print(f"    Transcript ({sc['words_count']} words): {sc['transcript'][:90]}...")
    print(f"    Thumbnail: {sc['thumbnail_path']}")
    assert os.path.exists(sc['thumbnail_path']), f"Thumbnail does not exist: {sc['thumbnail_path']}"
    assert os.path.getsize(sc['thumbnail_path']) > 0, "Thumbnail file is empty!"

# Test 3: Video Keyframe Extraction
video_path = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\2025-07-22 00-42-20_msg19.mp4"
if os.path.exists(video_path):
    thumb_path = mk.generate_thumbnail(video_path, 5.0, r"C:\vazus\knowledge\.thumbnails\test_audit_video.jpg")
    print(f"[PASS] Video thumbnail generated: {thumb_path}")
    assert os.path.exists(thumb_path), "Video thumbnail file missing!"
    assert os.path.getsize(thumb_path) > 1000, "Video thumbnail file suspicious size!"

# Test 4: Embeddings 768D Vector Verification
emb_mgr = mk.get_embedding_manager()
vec = emb_mgr.get_embedding(scenes[0]['transcript'])
print(f"[PASS] Vector Embedding generated. Dimension: {len(vec)}")
assert len(vec) == 768, f"Vector dimension mismatch! Expected 768, got {len(vec)}"
assert any(v != 0.0 for v in vec), "Vector is all zeros!"

# Test 5: SuperGraph Database Indexing
count = mk.index_scenes_to_supergraph(scenes)
print(f"[PASS] Indexed {count} scenes to SuperGraph DB.")

db_path = r"C:\vazus\vazus.db"
assert os.path.exists(db_path), f"DB file missing: {db_path}"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
nodes = cur.execute("SELECT id, name, domain, node_type, embedding_json FROM kg_nodes WHERE domain='multimodal_av'").fetchall()
print(f"[PASS] DB Query verified {len(nodes)} MediaScene nodes in vazus.db.")

for n in nodes:
    emb = json.loads(n[4])
    assert len(emb) == 768, f"Stored embedding is not 768D! got {len(emb)}"

conn.close()
print("--- ALL VERIFICATION TESTS SUCCEEDED ---")
