import sys
import os
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, r"C:\vazus")
from vazus_core.multimodal_knowledge import transcribe_and_chunk_media, transcribe_media_high_precision, index_scenes_to_supergraph

def test_transcription():
    print("=== Testing ASR Transcription & Chunking ===")
    
    sample_dir = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_"
    audio_file = os.path.join(sample_dir, "media_174.oga")
    video_file = os.path.join(sample_dir, "video_msg107.mp4")

    files_to_test = []
    if os.path.exists(audio_file):
        files_to_test.append(audio_file)
    if os.path.exists(video_file):
        files_to_test.append(video_file)

    if not files_to_test:
        print("[FAIL] No sample media files found!")
        return False, []

    all_scenes = []
    thumb_dir = r"C:\vazus\knowledge\.thumbnails"

    for media_path in files_to_test:
        print(f"\n[TEST] Transcribing media file: {media_path}")
        try:
            scenes = transcribe_and_chunk_media(media_path, output_thumbnail_dir=thumb_dir)
            print(f"Generated {len(scenes)} scene chunks for {os.path.basename(media_path)}")
            for idx, sc in enumerate(scenes):
                print(f"  Scene #{idx+1}: ID={sc['scene_id']}, Time={sc['start_sec']}s..{sc['end_sec']}s, Words={sc['words_count']}")
                print(f"    Transcript: {sc['transcript'][:100]}...")
                print(f"    Thumbnail:  {sc['thumbnail_path']}")
                
                # Check thumbnail existence
                t_path = sc['thumbnail_path']
                if os.path.exists(t_path) and os.path.getsize(t_path) > 0:
                    print(f"    [PASS] Thumbnail exists ({os.path.getsize(t_path)} bytes)")
                else:
                    print(f"    [FAIL] Thumbnail missing or empty: {t_path}")
            all_scenes.extend(scenes)
        except Exception as e:
            print(f"[FAIL] Error during transcription of {media_path}: {e}")

    return True, all_scenes

def test_supergraph_indexing(scenes):
    print("\n=== Testing SuperGraph Database Indexing ===")
    if not scenes:
        print("[SKIP] No scenes to index.")
        return False
    try:
        test_db = r"C:\vazus\.agents\teamwork_preview_challenger_m1_1\test_vazus.db"
        indexed_count = index_scenes_to_supergraph(scenes, db_path=test_db)
        print(f"[PASS] Successfully indexed {indexed_count} scenes into {test_db}")
        return True
    except Exception as e:
        print(f"[FAIL] SuperGraph indexing error: {e}")
        return False

if __name__ == "__main__":
    success, scenes = test_transcription()
    if success:
        test_supergraph_indexing(scenes)
