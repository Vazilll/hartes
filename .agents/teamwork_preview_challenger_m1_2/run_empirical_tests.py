import os
import sys
import json
import sqlite3
import tempfile
import traceback
import numpy as np
from PIL import Image

# Ensure C:\vazus is in sys.path
sys.path.insert(0, r"C:\vazus")

from vazus_core.multimodal_knowledge import (
    index_scenes_to_supergraph,
    generate_thumbnail,
    transcribe_media_high_precision,
    normalize_russian_text,
    is_garbage_transcript,
    get_embedding_manager
)

def log(msg):
    print(f"[TEST] {msg}")

def test_1_index_scenes_to_supergraph():
    log("=== TEST 1: index_scenes_to_supergraph & Supergraph database verification ===")
    
    test_db = os.path.join(tempfile.gettempdir(), "test_vazus_supergraph.db")
    if os.path.exists(test_db):
        os.remove(test_db)
        
    scenes = [
        {
            "scene_id": "scene_emp_001",
            "source_file": "C:/vazus/test_audio/lecture_part1.oga",
            "start_sec": 0.0,
            "end_sec": 115.5,
            "duration": 115.5,
            "transcript": "Добрый день, уважаемые слушатели. Сегодня мы рассмотрим архитектуру суперграфов знаний.",
            "thumbnail_path": "C:/vazus/knowledge/.thumbnails/thumb_scene_emp_001.jpg",
            "chunk_index": 0,
            "media_type": "audio",
            "whisper_segment_count": 6,
            "words_count": 11,
            "char_count": 88,
            "thumbnail_timestamp_sec": 57.75,
            "prev_scene_id": None,
            "next_scene_id": "scene_emp_002",
        },
        {
            "scene_id": "scene_emp_002",
            "source_file": "C:/vazus/test_audio/lecture_part1.oga",
            "start_sec": 115.5,
            "end_sec": 230.0,
            "duration": 114.5,
            "transcript": "Второй блок лекции посвящен эмбеддингам векторного пространства размером 768 измерений.",
            "thumbnail_path": "C:/vazus/knowledge/.thumbnails/thumb_scene_emp_002.jpg",
            "chunk_index": 1,
            "media_type": "audio",
            "whisper_segment_count": 5,
            "words_count": 11,
            "char_count": 87,
            "thumbnail_timestamp_sec": 172.75,
            "prev_scene_id": "scene_emp_001",
            "next_scene_id": None,
        }
    ]

    count = index_scenes_to_supergraph(scenes, db_path=test_db)
    log(f"index_scenes_to_supergraph returned count: {count}")
    assert count == 2, f"Expected count 2, got {count}"

    # Verify SQLite tables: kg_nodes and kg_edges in test_db
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Check nodes
    cursor.execute("SELECT id, name, domain, node_type, description, tags, properties, embedding_json FROM kg_nodes")
    nodes = cursor.fetchall()
    log(f"Fetched {len(nodes)} nodes from kg_nodes.")
    assert len(nodes) == 2, f"Expected 2 nodes, got {len(nodes)}"

    for node in nodes:
        n_id, name, domain, node_type, description, tags, properties, embedding_json = node
        log(f"Node ID: {n_id}, Name: '{name}', Type: {node_type}, Domain: {domain}")
        assert node_type == "MediaScene", f"Node type mismatch: {node_type}"
        assert domain == "multimodal_av", f"Domain mismatch: {domain}"
        
        # Verify 768D vector
        emb_data = json.loads(embedding_json)
        assert isinstance(emb_data, list), "embedding_json must parse into a list"
        assert len(emb_data) == 768, f"Embedding length error: expected 768, got {len(emb_data)}"
        assert all(isinstance(x, (float, int)) for x in emb_data), "Embedding elements must be numeric"
        log(f"Successfully verified 768D embedding vector for node {n_id} (len={len(emb_data)})")

    # Check edges
    cursor.execute("SELECT source_id, target_id, relation, strength, properties FROM kg_edges")
    edges = cursor.fetchall()
    log(f"Fetched {len(edges)} edges from kg_edges.")
    
    # Expected edges:
    # scene_emp_001 -> media:lecture_part1.oga (BELONGS_TO)
    # scene_emp_001 -> scene_emp_002 (NEXT_SCENE)
    # scene_emp_002 -> media:lecture_part1.oga (BELONGS_TO)
    # Total edges = 3
    assert len(edges) == 3, f"Expected 3 edges, got {len(edges)}"

    relations = {}
    for edge in edges:
        s_id, t_id, rel, strength, props = edge
        relations[(s_id, t_id, rel)] = strength
        log(f"Edge: {s_id} --[{rel}]--> {t_id} (strength={strength})")

    assert ("scene_emp_001", "media:lecture_part1.oga", "BELONGS_TO") in relations, "Missing BELONGS_TO edge for scene 1"
    assert ("scene_emp_002", "media:lecture_part1.oga", "BELONGS_TO") in relations, "Missing BELONGS_TO edge for scene 2"
    assert ("scene_emp_001", "scene_emp_002", "NEXT_SCENE") in relations, "Missing NEXT_SCENE edge from scene 1 to scene 2"

    conn.close()

    # Clean up test DB
    try:
        os.remove(test_db)
    except Exception:
        pass

    log("PASSED Test 1!")


def test_2_audio_only_thumbnails():
    log("=== TEST 2: Audio-only fallback thumbnails (.oga, .mp3, uppercase, corrupt files) ===")

    test_thumb_dir = os.path.join(tempfile.gettempdir(), "test_thumbnails")
    os.makedirs(test_thumb_dir, exist_ok=True)

    audio_extensions = [".oga", ".mp3", ".m4a", ".ogg", ".wav", ".flac", ".MP3", ".OGA"]
    for ext in audio_extensions:
        dummy_audio_path = f"C:/vazus/test_audio/sample_audio{ext}"
        out_thumb = os.path.join(test_thumb_dir, f"thumb_test_{ext.strip('.')}.jpg")

        thumb_path = generate_thumbnail(dummy_audio_path, timestamp_sec=42.5, output_path=out_thumb)
        log(f"Generated thumbnail for extension {ext}: {thumb_path}")

        assert os.path.exists(thumb_path), f"Thumbnail file not created for {ext}"

        # Verify image properties with PIL
        with Image.open(thumb_path) as img:
            log(f"Thumbnail dimensions: {img.size}, mode: {img.mode}, format: {img.format}")
            assert img.size == (320, 180), f"Expected size (320, 180), got {img.size}"
            assert img.mode == "RGB", f"Expected mode RGB, got {img.mode}"
            assert img.format in ("JPEG", "MPO"), f"Expected JPEG format, got {img.format}"

    log("PASSED Test 2!")


def test_3_corrupt_and_edge_cases():
    log("=== TEST 3: Corrupt media, empty scene list, case sensitivity ===")

    test_thumb_dir = os.path.join(tempfile.gettempdir(), "test_thumbnails")
    os.makedirs(test_thumb_dir, exist_ok=True)

    # 1. Non-existent video file (should fall back to dark-mode preview card without throwing exception)
    bad_video_path = "C:/vazus/non_existent_folder/fake_video.mp4"
    out_thumb = os.path.join(test_thumb_dir, "thumb_bad_video.jpg")
    thumb_path = generate_thumbnail(bad_video_path, timestamp_sec=10.0, output_path=out_thumb)
    assert os.path.exists(thumb_path), "Fallback card thumbnail not created for corrupt/non-existent video"
    with Image.open(thumb_path) as img:
        assert img.size == (320, 180), "Bad video fallback thumbnail size mismatch"

    # 2. Empty scene list to index_scenes_to_supergraph
    empty_res = index_scenes_to_supergraph([], db_path=os.path.join(tempfile.gettempdir(), "empty.db"))
    assert empty_res == 0, f"Expected 0 for empty scenes list, got {empty_res}"

    # 3. Single scene (no next scene)
    test_db = os.path.join(tempfile.gettempdir(), "single_scene.db")
    single_scene = [{
        "scene_id": "scene_single_001",
        "source_file": "C:/vazus/test/sample.mp3",
        "start_sec": 0.0,
        "end_sec": 60.0,
        "duration": 60.0,
        "transcript": "Единственная сцена во всем файле.",
        "thumbnail_path": "C:/vazus/knowledge/.thumbnails/thumb_single.jpg",
        "chunk_index": 0,
        "media_type": "audio",
        "whisper_segment_count": 2,
        "words_count": 5,
        "char_count": 35,
        "thumbnail_timestamp_sec": 30.0,
        "prev_scene_id": None,
        "next_scene_id": None,
    }]
    count = index_scenes_to_supergraph(single_scene, db_path=test_db)
    assert count == 1, f"Expected 1, got {count}"
    
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT relation FROM kg_edges")
    rel_rows = cursor.fetchall()
    rels = [r[0] for r in rel_rows]
    assert "BELONGS_TO" in rels, "BELONGS_TO edge missing for single scene"
    assert "NEXT_SCENE" not in rels, "NEXT_SCENE edge should not exist for single scene"
    conn.close()

    try:
        os.remove(test_db)
    except Exception:
        pass

    log("PASSED Test 3!")


def main():
    try:
        test_1_index_scenes_to_supergraph()
        test_2_audio_only_thumbnails()
        test_3_corrupt_and_edge_cases()
        print("\n=========================================")
        print("ALL EMPIRICAL TESTS PASSED SUCCESSFULLY!")
        print("=========================================\n")
    except Exception as e:
        print(f"\n[FAIL] EMPIRICAL TEST FAILED: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
