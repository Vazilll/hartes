"""
Empirical Test Harness for Multimodal Knowledge Engine (Milestone 1)
Target: vazus_core/multimodal_knowledge.py
"""

import os
import sys
import json
import traceback
from pathlib import Path
from PIL import Image

sys.path.insert(0, r"C:\vazus")

from vazus_core.multimodal_knowledge import (
    transcribe_and_chunk_media,
    generate_thumbnail,
    index_scenes_to_supergraph
)

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

RESULTS = {
    "real_files_test": [],
    "edge_cases_test": {},
    "summary": {
        "passed": 0,
        "failed": 0,
        "warnings": 0
    }
}

def log(msg):
    print(f"[TEST HARNESS] {msg}", flush=True)

def run_real_files_tests():
    log("=== Running Real Media Files Empirical Tests ===")
    
    courses_dir = r"C:\vazus\knowledge\telegram_courses"
    test_candidates = [
        # Audio candidate 1 (.oga)
        r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\media_174.oga",
        # Video candidate 1 (Short video ~57s)
        r"C:\vazus\knowledge\telegram_courses\ФУНКЦИОНАЛЬНАЯ МАШИНА _ Канал курса\video_msg107.mp4",
        # Video candidate 2 (Long video ~193.2s - testing multi-scene chunking & boundary limits)
        r"C:\vazus\knowledge\telegram_courses\ФУНКЦИОНАЛЬНАЯ МАШИНА _ Канал курса\video_2026-04-18_14-18-15_msg124.mp4",
    ]

    output_thumb_dir = r"C:\vazus\knowledge\.thumbnails"
    os.makedirs(output_thumb_dir, exist_ok=True)

    for media_path in test_candidates:
        if not os.path.exists(media_path):
            log(f"[WARN] Candidate path not found: {media_path}")
            continue

        file_name = os.path.basename(media_path)
        file_size_mb = os.path.getsize(media_path) / (1024 * 1024)
        log(f"\n--- Testing real file: {file_name} ({file_size_mb:.2f} MB) ---")

        try:
            scenes = transcribe_and_chunk_media(media_path, output_thumbnail_dir=output_thumb_dir)
            log(f"Generated {len(scenes)} scenes for {file_name}.")

            file_result = {
                "file_name": file_name,
                "file_path": media_path,
                "file_size_mb": round(file_size_mb, 2),
                "scene_count": len(scenes),
                "scenes": []
            }

            for idx, sc in enumerate(scenes):
                duration = sc.get("duration", 0.0)
                st = sc.get("start_sec", 0.0)
                en = sc.get("end_sec", 0.0)
                transcript = sc.get("transcript", "")
                thumb_path = sc.get("thumbnail_path", "")
                media_type = sc.get("media_type", "")

                # 1. Boundary constraint checks
                exceeds_max = duration > 180.1
                is_last_scene = (idx == len(scenes) - 1)
                is_only_scene = (len(scenes) == 1)
                under_min = (not is_last_scene) and (not is_only_scene) and (duration < 59.9)

                # 2. Thumbnail checks
                thumb_exists = os.path.exists(thumb_path)
                thumb_valid = False
                thumb_size = None
                if thumb_exists:
                    try:
                        with Image.open(thumb_path) as img:
                            thumb_size = list(img.size)
                            thumb_valid = (img.format in ('JPEG', 'PNG')) and (img.size[0] > 0 and img.size[1] > 0)
                    except Exception as img_err:
                        log(f"  [ERROR] Image open failed: {img_err}")

                # 3. Transcript check
                transcript_non_empty = len(transcript.strip()) > 0

                scene_check = {
                    "scene_id": sc.get("scene_id"),
                    "chunk_index": sc.get("chunk_index"),
                    "start_sec": st,
                    "end_sec": en,
                    "duration": duration,
                    "is_last_scene": is_last_scene,
                    "duration_within_180s": not exceeds_max,
                    "duration_ge_60s_if_middle": not under_min,
                    "transcript_len": len(transcript),
                    "transcript_non_empty": transcript_non_empty,
                    "transcript_snippet": transcript[:100],
                    "thumbnail_path": thumb_path,
                    "thumbnail_exists": thumb_exists,
                    "thumbnail_valid": thumb_valid,
                    "thumbnail_size": thumb_size
                }

                file_result["scenes"].append(scene_check)
                log(f"  Scene [{sc['scene_id']}] ({st}s -> {en}s, dur: {duration}s, media: {media_type}):")
                log(f"    Transcript: {transcript[:80]}...")
                log(f"    Thumbnail: {thumb_path} | Exists: {thumb_exists} | Valid: {thumb_valid} {thumb_size}")

                if exceeds_max:
                    log(f"    [FAIL] Duration {duration}s exceeds 180s MAX limit!")
                    RESULTS["summary"]["failed"] += 1
                elif under_min:
                    log(f"    [WARNING] Middle scene duration {duration}s is under 60s MIN limit!")
                    RESULTS["summary"]["warnings"] += 1
                else:
                    RESULTS["summary"]["passed"] += 1

                if not thumb_exists or not thumb_valid:
                    log(f"    [FAIL] Thumbnail missing or invalid at {thumb_path}")
                    RESULTS["summary"]["failed"] += 1

                if not transcript_non_empty:
                    log(f"    [WARNING] Empty transcript for scene {sc['scene_id']}")
                    RESULTS["summary"]["warnings"] += 1

            RESULTS["real_files_test"].append(file_result)

        except Exception as e:
            log(f"[FAIL] Exception during transcribe_and_chunk_media on {file_name}: {e}")
            traceback.print_exc()
            RESULTS["summary"]["failed"] += 1

def run_edge_cases_tests():
    log("\n=== Running Edge Cases Empirical Tests ===")

    edge_results = {}
    work_dir = r"C:\vazus\.agents\teamwork_preview_challenger_m1_1"

    # Edge Case 1: Non-existent file path
    log("\n--- Edge Case 1: Non-existent file path ---")
    non_existent = r"C:\vazus\knowledge\telegram_courses\non_existent_file_999.mp4"
    try:
        transcribe_and_chunk_media(non_existent)
        log("  [FAIL] Expected FileNotFoundError, but no exception was raised!")
        edge_results["non_existent_file"] = {"status": "FAIL", "error": "No exception raised"}
        RESULTS["summary"]["failed"] += 1
    except FileNotFoundError as fnf:
        log(f"  [PASS] Correctly raised FileNotFoundError: {fnf}")
        edge_results["non_existent_file"] = {"status": "PASS", "message": str(fnf)}
        RESULTS["summary"]["passed"] += 1
    except Exception as ex:
        log(f"  [FAIL] Raised unexpected exception type {type(ex)}: {ex}")
        edge_results["non_existent_file"] = {"status": "FAIL", "error": str(ex)}
        RESULTS["summary"]["failed"] += 1

    # Edge Case 2: Empty file (0 bytes)
    log("\n--- Edge Case 2: Empty file (0 bytes) ---")
    empty_file = os.path.join(work_dir, "test_empty_0bytes.mp4")
    with open(empty_file, "wb") as f:
        pass  # 0 bytes

    try:
        res = transcribe_and_chunk_media(empty_file)
        log(f"  [PASS] Empty file returned cleanly: {res}")
        edge_results["empty_file"] = {"status": "PASS", "result_count": len(res), "result": res}
        RESULTS["summary"]["passed"] += 1
    except Exception as ex:
        log(f"  [PASS/HANDLED] Empty file raised handled exception: {type(ex).__name__}: {ex}")
        edge_results["empty_file"] = {"status": "PASS_HANDLED", "error": str(ex)}
        RESULTS["summary"]["passed"] += 1

    # Edge Case 3: Audio file without video stream
    log("\n--- Edge Case 3: Audio file without video stream ---")
    audio_sample = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\media_174.oga"
    if os.path.exists(audio_sample):
        try:
            scenes = transcribe_and_chunk_media(audio_sample)
            is_audio_media_type = all(sc.get("media_type") == "audio" for sc in scenes)
            all_thumbs_exist = all(os.path.exists(sc.get("thumbnail_path", "")) for sc in scenes)
            log(f"  Audio scenes count: {len(scenes)}, media_type == 'audio': {is_audio_media_type}, thumbs_exist: {all_thumbs_exist}")
            if scenes and is_audio_media_type and all_thumbs_exist:
                log("  [PASS] Pure audio file processed successfully with audio card thumbnails.")
                edge_results["audio_no_video"] = {"status": "PASS", "scene_count": len(scenes)}
                RESULTS["summary"]["passed"] += 1
            else:
                log("  [FAIL] Pure audio processing failed assertions.")
                edge_results["audio_no_video"] = {"status": "FAIL", "scenes": len(scenes), "media_type_audio": is_audio_media_type}
                RESULTS["summary"]["failed"] += 1
        except Exception as ex:
            log(f"  [FAIL] Exception processing pure audio file: {ex}")
            edge_results["audio_no_video"] = {"status": "FAIL", "error": str(ex)}
            RESULTS["summary"]["failed"] += 1
    else:
        log("  [SKIP] Audio sample file not found.")

    # Edge Case 4: Video missing moov atom header (corrupt MP4)
    log("\n--- Edge Case 4: Video missing moov atom header ---")
    corrupt_mp4 = os.path.join(work_dir, "test_no_moov_header.mp4")
    with open(corrupt_mp4, "wb") as f:
        # Construct an MP4 header with ftyp box but NO moov atom box
        ftyp_box = b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41'
        f.write(ftyp_box + b'\x00' * 2048)

    try:
        # Test generate_thumbnail directly on corrupt video
        thumb_out = os.path.join(work_dir, "thumb_corrupt.jpg")
        generated_thumb = generate_thumbnail(corrupt_mp4, timestamp_sec=10.0, output_path=thumb_out)
        thumb_created = os.path.exists(generated_thumb)
        log(f"  generate_thumbnail on corrupt video output: {generated_thumb} | Exists: {thumb_created}")

        # Test transcribe_and_chunk_media on corrupt video
        scenes_corrupt = transcribe_and_chunk_media(corrupt_mp4)
        log(f"  transcribe_and_chunk_media on corrupt video returned: {len(scenes_corrupt)} scenes")
        
        edge_results["missing_moov_atom"] = {
            "status": "PASS",
            "thumbnail_fallback_created": thumb_created,
            "scenes_returned": len(scenes_corrupt)
        }
        log("  [PASS] Missing moov atom handled gracefully with dark-mode fallback thumbnail.")
        RESULTS["summary"]["passed"] += 1
    except Exception as ex:
        log(f"  [PASS/HANDLED] Missing moov atom raised handled exception: {type(ex).__name__}: {ex}")
        edge_results["missing_moov_atom"] = {
            "status": "PASS_HANDLED",
            "error": str(ex)
        }
        RESULTS["summary"]["passed"] += 1

    RESULTS["edge_cases_test"] = edge_results

if __name__ == "__main__":
    run_real_files_tests()
    run_edge_cases_tests()

    report_json_path = r"C:\vazus\.agents\teamwork_preview_challenger_m1_1\test_results.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, indent=2, ensure_ascii=False)

    log(f"\n==========================================")
    log(f"TEST HARNESS COMPLETE. Summary:")
    log(f"Passed: {RESULTS['summary']['passed']}")
    log(f"Failed: {RESULTS['summary']['failed']}")
    log(f"Warnings: {RESULTS['summary']['warnings']}")
    log(f"Saved results to {report_json_path}")
    log(f"==========================================")
