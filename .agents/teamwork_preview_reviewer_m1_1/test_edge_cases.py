import os
import sys
import tempfile
import sqlite3
import json

# Ensure vazus root in python path
sys.path.insert(0, r"C:\vazus")

import vazus_core.multimodal_knowledge as mk

def run_tests():
    print("==================================================")
    print("   RUNNING ADVERSARIAL EDGE CASE TEST SUITE")
    print("==================================================")

    # Test 1: Non-existent file handling
    print("\n--- Test 1: Non-existent file ---")
    try:
        mk.transcribe_and_chunk_media(r"C:\vazus\knowledge\non_existent_file.mp4")
        print("FAIL: Expected FileNotFoundError not raised!")
    except FileNotFoundError as e:
        print(f"PASS: Properly raised FileNotFoundError: {e}")

    # Test 2: Audio file transcription and thumbnail in custom output dir
    print("\n--- Test 2: Real Audio File (media_174.oga) with Custom Output Dir ---")
    audio_path = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\media_174.oga"
    custom_thumb_dir = r"C:\vazus\.agents\teamwork_preview_reviewer_m1_1\test_thumbs"
    if os.path.exists(audio_path):
        scenes = mk.transcribe_and_chunk_media(audio_path, output_thumbnail_dir=custom_thumb_dir)
        print(f"Transcribed {len(scenes)} scenes.")
        for sc in scenes:
            assert os.path.exists(sc["thumbnail_path"]), f"Thumbnail missing: {sc['thumbnail_path']}"
            assert sc["source_file"].endswith("media_174.oga")
            assert len(sc["transcript"]) > 0
            assert sc["media_type"] == "audio"
            print(f"  Scene [{sc['scene_id']}]: {sc['start_sec']}s -> {sc['end_sec']}s, transcript len={len(sc['transcript'])}")
        print("PASS: Audio transcription and thumbnail generation verified.")
    else:
        print("SKIP: Sample audio file not found.")

    # Test 3: Corrupted Video missing moov atom / fake mp4 bytes
    print("\n--- Test 3: Corrupted Video File (Fake Bytes) ---")
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(b"CORRUPTED MOOV ATOM HEADER GARBAGE DATA 1234567890")
        corrupt_video_path = tmp.name

    try:
        thumb_out = os.path.join(custom_thumb_dir, "corrupt_test_thumb.jpg")
        result_thumb = mk.generate_thumbnail(corrupt_video_path, timestamp_sec=45.0, output_path=thumb_out)
        assert os.path.exists(result_thumb), "Fallback thumbnail was not generated!"
        print(f"PASS: Corrupted video handled gracefully. Saved fallback card to: {result_thumb}")
    finally:
        if os.path.exists(corrupt_video_path):
            os.remove(corrupt_video_path)

    # Test 4: Uppercase extension audio (.OGA)
    print("\n--- Test 4: Uppercase Audio File Extension ---")
    with tempfile.NamedTemporaryFile(suffix=".OGA", delete=False) as tmp:
        tmp.write(b"DUMMY AUDIO DATA")
        uppercase_audio_path = tmp.name

    try:
        thumb_out = os.path.join(custom_thumb_dir, "uppercase_audio_thumb.jpg")
        result_thumb = mk.generate_thumbnail(uppercase_audio_path, timestamp_sec=12.0, output_path=thumb_out)
        assert os.path.exists(result_thumb), "Audio card thumbnail not generated for .OGA extension!"
        print(f"PASS: Uppercase audio extension handled correctly: {result_thumb}")
    finally:
        if os.path.exists(uppercase_audio_path):
            os.remove(uppercase_audio_path)

    # Test 5: Empty scenes list in index_scenes_to_supergraph
    print("\n--- Test 5: Empty Scenes List Indexing ---")
    count = mk.index_scenes_to_supergraph([])
    assert count == 0
    print("PASS: Empty scenes list returned 0 safely.")

    # Test 6: Indexing Real Scenes & Database Schema Verification
    print("\n--- Test 6: SuperGraph DB Indexing & Vector Schema ---")
    test_db = r"C:\vazus\.agents\teamwork_preview_reviewer_m1_1\test_vazus.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    dummy_scenes = [
        {
            "scene_id": "scene_test001",
            "source_file": "C:/vazus/knowledge/telegram_courses/test_course/lesson1.mp4",
            "start_sec": 0.0,
            "end_sec": 115.5,
            "duration": 115.5,
            "transcript": "Тестовая транскрипция первого эпизода мультимодального курса по нейросетям.",
            "thumbnail_path": "C:/vazus/knowledge/.thumbnails/thumb_scene_test001.jpg",
            "chunk_index": 0,
            "media_type": "video",
            "whisper_segment_count": 12,
            "words_count": 9,
            "char_count": 72,
            "thumbnail_timestamp_sec": 57.75,
            "prev_scene_id": None,
            "next_scene_id": "scene_test002"
        },
        {
            "scene_id": "scene_test002",
            "source_file": "C:/vazus/knowledge/telegram_courses/test_course/lesson1.mp4",
            "start_sec": 115.5,
            "end_sec": 240.0,
            "duration": 124.5,
            "transcript": "Вторая часть лекции про графовую память и векторные эмбеддинги SuperGraph.",
            "thumbnail_path": "C:/vazus/knowledge/.thumbnails/thumb_scene_test002.jpg",
            "chunk_index": 1,
            "media_type": "video",
            "whisper_segment_count": 15,
            "words_count": 9,
            "char_count": 72,
            "thumbnail_timestamp_sec": 177.75,
            "prev_scene_id": "scene_test001",
            "next_scene_id": None
        }
    ]

    indexed_n = mk.index_scenes_to_supergraph(dummy_scenes, db_path=test_db)
    assert indexed_n == 2, f"Expected 2 indexed scenes, got {indexed_n}"

    # Connect and verify test_db
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    nodes = cursor.execute("SELECT id, name, domain, node_type, embedding_json, properties FROM kg_nodes WHERE domain='multimodal_av'").fetchall()
    assert len(nodes) == 2, f"Expected 2 kg_nodes, found {len(nodes)}"

    for n_id, name, domain, node_type, emb_str, props_str in nodes:
        emb = json.loads(emb_str)
        props = json.loads(props_str)
        assert len(emb) == 768, f"Embedding dimension mismatch: expected 768, got {len(emb)}"
        assert domain == "multimodal_av"
        assert node_type == "MediaScene"
        print(f"  Node [{n_id}]: {name}, Embedding dim: {len(emb)}")

    edges = cursor.execute("SELECT source_id, target_id, relation FROM kg_edges").fetchall()
    assert len(edges) >= 3, f"Expected at least 3 edges (2 BELONGS_TO + 1 NEXT_SCENE), got {len(edges)}"
    print(f"  Total Edges created: {len(edges)}")
    for e in edges:
        print(f"    Edge: {e[0]} --[{e[2]}]--> {e[1]}")
    conn.close()

    if os.path.exists(test_db):
        os.remove(test_db)
    print("PASS: SuperGraph DB indexing and vector schema fully verified.")

    print("\n==================================================")
    print("   ALL ADVERSARIAL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
