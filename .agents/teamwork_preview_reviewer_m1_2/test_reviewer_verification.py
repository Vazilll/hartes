import os
import sys
import json
import sqlite3
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\vazus")
import vazus_core.multimodal_knowledge as mk
from vazus_core.embeddings import UnifiedEmbeddingManager

def run_checks():
    print("=== CHECK 1: SuperGraph 768D Vector Embedding Alignment ===")
    mgr = UnifiedEmbeddingManager()
    sample_text = "Тестовая транскрипция аудио фрагмента для проверки векторов"
    vec = mgr.get_embedding(sample_text)
    print(f"Embedding length: {len(vec)}")
    print(f"Vector sample: {vec[:5]}")
    assert len(vec) == 768, f"Expected 768D embedding, got {len(vec)}"
    assert all(isinstance(x, float) for x in vec), "Embedding elements must be floats"
    print("-> 768D Vector Alignment PASS")

    print("\n=== CHECK 2: Database Schema & Contracts in vazus.db and services/memory/vazus.db ===")
    dbs = [r"C:\vazus\vazus.db", r"C:\vazus\services\memory\vazus.db"]
    for db_path in dbs:
        assert os.path.exists(db_path), f"Database missing: {db_path}"
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        nodes = cur.execute("SELECT id, name, domain, node_type, description, tags, properties, embedding_json FROM kg_nodes WHERE domain='multimodal_av'").fetchall()
        print(f"DB {db_path} -> Found {len(nodes)} MediaScene nodes")
        assert len(nodes) > 0, "No kg_nodes found in domain='multimodal_av'"
        
        for n in nodes:
            nid, name, domain, ntype, desc, tags, props_json, emb_json = n
            assert domain == 'multimodal_av', f"Unexpected domain: {domain}"
            assert ntype == 'MediaScene', f"Unexpected node_type: {ntype}"
            emb = json.loads(emb_json)
            assert len(emb) == 768, f"Embedding in DB is {len(emb)}D, expected 768D"
            props = json.loads(props_json)
            assert "scene_id" in props
            assert "source_file" in props
            assert "start_sec" in props
            assert "end_sec" in props
            assert "thumbnail_path" in props

        edges_belongs = cur.execute("SELECT source_id, target_id, relation FROM kg_edges WHERE relation='BELONGS_TO'").fetchall()
        edges_next = cur.execute("SELECT source_id, target_id, relation FROM kg_edges WHERE relation='NEXT_SCENE'").fetchall()
        print(f"DB {db_path} -> BELONGS_TO edges: {len(edges_belongs)}, NEXT_SCENE edges: {len(edges_next)}")
        assert len(edges_belongs) > 0, "No BELONGS_TO edges found"
        conn.close()
    print("-> Database Schema & Edge Contracts PASS")

    print("\n=== CHECK 3: Thumbnail Rendering (Audio, Video Keyframe, Dark-Mode Preview) ===")
    out_dir = r"C:\vazus\.agents\teamwork_preview_reviewer_m1_2\test_thumbs"
    os.makedirs(out_dir, exist_ok=True)

    # 3a. Audio thumbnail check
    audio_thumb = mk.generate_thumbnail("test_track.oga", 10.0, os.path.join(out_dir, "test_audio.jpg"))
    print("Audio thumbnail generated at:", audio_thumb)
    assert os.path.exists(audio_thumb), "Audio thumbnail file does not exist"
    with Image.open(audio_thumb) as img:
        print("Audio thumb size:", img.size, img.mode)
        assert img.size == (320, 180), f"Expected 320x180 thumbnail, got {img.size}"

    # 3b. Video keyframe check (real video if available)
    sample_video = r"C:\vazus\knowledge\telegram_courses\МЫШЦЫ 20_80\2025-07-22 00-42-20_msg19.mp4"
    if os.path.exists(sample_video):
        video_thumb = mk.generate_thumbnail(sample_video, 5.0, os.path.join(out_dir, "test_video.jpg"))
        print("Video keyframe thumbnail generated at:", video_thumb)
        assert os.path.exists(video_thumb)
        with Image.open(video_thumb) as img:
            print("Video thumb size:", img.size, img.mode)
            assert img.size == (320, 180)

    # 3c. Corrupt video fallback check
    corrupt_thumb = mk.generate_thumbnail("nonexistent_corrupt.mp4", 15.0, os.path.join(out_dir, "test_corrupt.jpg"))
    print("Corrupt video thumbnail generated at:", corrupt_thumb)
    assert os.path.exists(corrupt_thumb)
    with Image.open(corrupt_thumb) as img:
        print("Corrupt thumb size:", img.size, img.mode)
        assert img.size == (320, 180)

    print("-> Thumbnail Rendering PASS")

    print("\n=== CHECK 4: Code Execution & Pipeline Verification ===")
    sample_audio = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\media_174.oga"
    if os.path.exists(sample_audio):
        print(f"Testing full transcription pipeline on: {sample_audio}")
        scenes = mk.transcribe_and_chunk_media(sample_audio, output_thumbnail_dir=out_dir)
        print(f"Pipeline produced {len(scenes)} scenes:")
        for sc in scenes:
            print(f" - [{sc['scene_id']}] ({sc['start_sec']}s -> {sc['end_sec']}s): {sc['transcript'][:60]}...")
            assert os.path.exists(sc['thumbnail_path']), f"Thumbnail missing: {sc['thumbnail_path']}"
            assert sc['start_sec'] < sc['end_sec'], "Invalid timestamp interval"
            assert len(sc['transcript']) > 0, "Empty transcript text"
        
        indexed = mk.index_scenes_to_supergraph(scenes)
        print(f"Successfully indexed {indexed} scenes to SuperGraph!")
        assert indexed == len(scenes)

    print("\n=== ALL VERIFICATION CHECKS COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_checks()
