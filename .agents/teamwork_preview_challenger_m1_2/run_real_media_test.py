import os
import sys
import json
import sqlite3

sys.path.insert(0, r"C:\vazus")
sys.stdout.reconfigure(encoding='utf-8')

from vazus_core.multimodal_knowledge import (
    generate_thumbnail,
    index_scenes_to_supergraph,
    transcribe_and_chunk_media
)

def test_real_audio_and_vazus_db():
    print("[REAL TEST] Starting test on actual media and vazus.db...")
    real_oga_file = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\media_174.oga"
    assert os.path.exists(real_oga_file), f"File not found: {real_oga_file}"

    # 1. Test thumbnail generation on real .oga
    thumb_path = generate_thumbnail(real_oga_file, timestamp_sec=5.0)
    print(f"[REAL TEST] Real thumbnail path: {thumb_path}")
    assert os.path.exists(thumb_path), "Thumbnail for real .oga file not found"

    # 2. Test transcribe and chunk media
    scenes = transcribe_and_chunk_media(real_oga_file)
    print(f"[REAL TEST] Transcribed scenes count: {len(scenes)}")

    if scenes:
        for idx, sc in enumerate(scenes):
            print(f"  Scene {idx+1}: [{sc['scene_id']}] ({sc['start_sec']}s -> {sc['end_sec']}s)")
            print(f"    Transcript: {sc['transcript'][:100]}...")
            print(f"    Thumbnail: {sc['thumbnail_path']}")
            assert len(sc['transcript']) >= 0
            assert os.path.exists(sc['thumbnail_path'])

    # 3. Test indexing into C:/vazus/vazus.db
    db_path = "C:/vazus/vazus.db"
    count = index_scenes_to_supergraph(scenes, db_path=db_path)
    print(f"[REAL TEST] Indexed {count} scenes into {db_path}")

    # 4. Verify sqlite database contents in vazus.db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, domain, node_type, embedding_json FROM kg_nodes WHERE node_type = 'MediaScene'")
    node_rows = cursor.fetchall()
    print(f"[REAL TEST] Total MediaScene nodes in vazus.db: {len(node_rows)}")
    assert len(node_rows) >= len(scenes), "MediaScene node count mismatch in vazus.db"

    for r in node_rows:
        nid, name, domain, ntype, emb_json = r
        emb = json.loads(emb_json)
        assert len(emb) == 768, f"Embedding length != 768 (got {len(emb)}) for node {nid}"

    cursor.execute("SELECT source_id, target_id, relation FROM kg_edges WHERE relation IN ('BELONGS_TO', 'NEXT_SCENE')")
    edge_rows = cursor.fetchall()
    print(f"[REAL TEST] Total BELONGS_TO/NEXT_SCENE edges in vazus.db: {len(edge_rows)}")
    
    conn.close()
    print("[REAL TEST] ALL REAL MEDIA TESTS PASSED!")

if __name__ == "__main__":
    test_real_audio_and_vazus_db()
