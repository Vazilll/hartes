r"""
C:\vazus\.agents\challenger_multimodal_m1\stress_test.py
Empirical stress test suite for vazus_core/multimodal_knowledge.py
"""

import os
import sys
import json
import sqlite3
import traceback
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Ensure vazus root is in sys.path
sys.path.insert(0, r"C:\vazus")

from vazus_core.multimodal_knowledge import (
    transcribe_and_chunk_media,
    generate_thumbnail,
    index_scenes_to_supergraph
)

results = []

def record_test(name, status, details=""):
    results.append({"name": name, "status": status, "details": details})
    symbol = "[PASS]" if status == "PASS" else "[FAIL]"
    print(f"{symbol} {name}", flush=True)
    if details:
        print(f"        {details}", flush=True)

def run_tests():
    print("==================================================", flush=True)
    print("STARTING EMPIRICAL STRESS TESTS: multimodal_knowledge.py", flush=True)
    print("==================================================", flush=True)

    # ----------------------------------------------------
    # TEST 1: Process Audio (.oga) file
    # ----------------------------------------------------
    oga_file = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\media_174.oga"
    oga_scenes = []
    try:
        if not os.path.exists(oga_file):
            record_test("Test 1: Process Audio (.oga)", "FAIL", f"File not found: {oga_file}")
        else:
            oga_scenes = transcribe_and_chunk_media(oga_file)
            if not isinstance(oga_scenes, list) or len(oga_scenes) == 0:
                record_test("Test 1: Process Audio (.oga)", "FAIL", f"Expected list of scenes, got: {oga_scenes}")
            else:
                valid = True
                fail_reason = ""
                for idx, sc in enumerate(oga_scenes):
                    required_keys = ["scene_id", "source_file", "start_sec", "end_sec", "duration", "transcript", "thumbnail_path", "chunk_index", "media_type"]
                    missing = [k for k in required_keys if k not in sc]
                    if missing:
                        valid = False
                        fail_reason = f"Scene #{idx} missing keys: {missing}"
                        break
                    if not os.path.exists(sc["thumbnail_path"]):
                        valid = False
                        fail_reason = f"Thumbnail file does not exist: {sc['thumbnail_path']}"
                        break
                    # Verify thumbnail resolution and format
                    with Image.open(sc["thumbnail_path"]) as img:
                        if img.size != (320, 180):
                            valid = False
                            fail_reason = f"Thumbnail size is {img.size}, expected (320, 180)"
                            break
                        if img.format != "JPEG":
                            valid = False
                            fail_reason = f"Thumbnail format is {img.format}, expected JPEG"
                            break

                if valid:
                    record_test("Test 1: Process Audio (.oga)", "PASS", f"Generated {len(oga_scenes)} valid scene(s) with thumbnails")
                else:
                    record_test("Test 1: Process Audio (.oga)", "FAIL", fail_reason)
    except Exception as e:
        record_test("Test 1: Process Audio (.oga)", "FAIL", f"Exception: {e}\n{traceback.format_exc()}")

    # ----------------------------------------------------
    # TEST 2: Process Video (.mp4) file
    # ----------------------------------------------------
    mp4_file = r"C:\vazus\knowledge\telegram_courses\МЫШЦЫ 20_80\video_msg17.mp4"
    mp4_scenes = []
    try:
        if not os.path.exists(mp4_file):
            record_test("Test 2: Process Video (.mp4)", "FAIL", f"Video file not found: {mp4_file}")
        else:
            mp4_scenes = transcribe_and_chunk_media(mp4_file)
            if not isinstance(mp4_scenes, list):
                record_test("Test 2: Process Video (.mp4)", "FAIL", f"Expected list of scenes, got {type(mp4_scenes)}")
            else:
                valid = True
                fail_reason = ""
                for idx, sc in enumerate(mp4_scenes):
                    if not os.path.exists(sc["thumbnail_path"]):
                        valid = False
                        fail_reason = f"Video thumbnail missing: {sc['thumbnail_path']}"
                        break
                    with Image.open(sc["thumbnail_path"]) as img:
                        if img.size != (320, 180):
                            valid = False
                            fail_reason = f"Video thumbnail size is {img.size}, expected (320, 180)"
                            break
                        if img.format != "JPEG":
                            valid = False
                            fail_reason = f"Video thumbnail format is {img.format}, expected JPEG"
                            break
                if valid:
                    record_test("Test 2: Process Video (.mp4)", "PASS", f"Processed {os.path.basename(mp4_file)} -> {len(mp4_scenes)} scene(s)")
                else:
                    record_test("Test 2: Process Video (.mp4)", "FAIL", fail_reason)
    except Exception as e:
        record_test("Test 2: Process Video (.mp4)", "FAIL", f"Exception: {e}\n{traceback.format_exc()}")

    # ----------------------------------------------------
    # TEST 3: Process Audio (.mp3) file
    # ----------------------------------------------------
    mp3_file = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\20250902-222352_msg140.mp3"
    mp3_scenes = []
    try:
        if not os.path.exists(mp3_file):
            record_test("Test 3: Process Audio (.mp3)", "FAIL", f"File not found: {mp3_file}")
        else:
            mp3_scenes = transcribe_and_chunk_media(mp3_file)
            if not isinstance(mp3_scenes, list):
                record_test("Test 3: Process Audio (.mp3)", "FAIL", f"Expected list, got {type(mp3_scenes)}")
            else:
                record_test("Test 3: Process Audio (.mp3)", "PASS", f"Generated {len(mp3_scenes)} scene(s)")
    except Exception as e:
        record_test("Test 3: Process Audio (.mp3)", "FAIL", f"Exception: {e}\n{traceback.format_exc()}")

    # ----------------------------------------------------
    # TEST 4: Direct `generate_thumbnail` API test
    # ----------------------------------------------------
    try:
        thumb_out = r"C:\vazus\knowledge\.thumbnails\test_direct_thumb.jpg"
        if os.path.exists(thumb_out):
            os.remove(thumb_out)

        res_path = generate_thumbnail(oga_file, 10.5, thumb_out)
        if not os.path.exists(res_path):
            record_test("Test 4: Direct generate_thumbnail()", "FAIL", f"Output thumbnail not created: {res_path}")
        else:
            with Image.open(res_path) as img:
                if img.size == (320, 180):
                    record_test("Test 4: Direct generate_thumbnail()", "PASS", f"Saved thumbnail at {res_path}")
                else:
                    record_test("Test 4: Direct generate_thumbnail()", "FAIL", f"Invalid dimensions: {img.size}")
    except Exception as e:
        record_test("Test 4: Direct generate_thumbnail()", "FAIL", f"Exception: {e}")

    # ----------------------------------------------------
    # TEST 5: Error & Edge Case Handling
    # ----------------------------------------------------
    # Edge case 5a: Non-existent file
    try:
        transcribe_and_chunk_media(r"C:\non_existent_file_xyz.mp4")
        record_test("Test 5a: Non-existent file exception", "FAIL", "Did not raise FileNotFoundError")
    except FileNotFoundError:
        record_test("Test 5a: Non-existent file exception", "PASS", "Raised FileNotFoundError as expected")
    except Exception as e:
        record_test("Test 5a: Non-existent file exception", "FAIL", f"Raised wrong exception: {type(e)}")

    # Edge case 5b: Indexing empty list
    try:
        count = index_scenes_to_supergraph([])
        if count == 0:
            record_test("Test 5b: Index empty scene list", "PASS", "Returned 0 as expected")
        else:
            record_test("Test 5b: Index empty scene list", "FAIL", f"Expected 0, got {count}")
    except Exception as e:
        record_test("Test 5b: Index empty scene list", "FAIL", f"Exception: {e}")

    # ----------------------------------------------------
    # TEST 6: SuperGraph SQLite Persistence & 768D Embedding Verification
    # ----------------------------------------------------
    all_test_scenes = oga_scenes + mp4_scenes + mp3_scenes
    try:
        if not all_test_scenes:
            record_test("Test 6: SuperGraph Database Indexing", "FAIL", "No test scenes collected from previous tests")
        else:
            indexed_count = index_scenes_to_supergraph(all_test_scenes)
            if indexed_count != len(all_test_scenes):
                record_test("Test 6: SuperGraph Database Indexing", "FAIL", f"Expected to index {len(all_test_scenes)}, got {indexed_count}")
            else:
                # Verify databases
                db_paths = ["C:/vazus/vazus.db", "C:/vazus/services/memory/vazus.db"]
                db_verification_passed = True
                db_errs = []

                for dbp in db_paths:
                    if not os.path.exists(dbp):
                        db_verification_passed = False
                        db_errs.append(f"Database file missing: {dbp}")
                        continue

                    conn = sqlite3.connect(dbp)
                    cursor = conn.cursor()

                    # Query kg_nodes for MediaScene nodes
                    cursor.execute("""
                        SELECT id, name, domain, node_type, description, tags, properties, embedding_json
                        FROM kg_nodes
                        WHERE domain='multimodal_av' AND node_type='MediaScene'
                    """)
                    nodes = cursor.fetchall()
                    if len(nodes) < len(all_test_scenes):
                        db_verification_passed = False
                        db_errs.append(f"{dbp}: Expected at least {len(all_test_scenes)} MediaScene nodes, found {len(nodes)}")

                    # Check 768D vector embeddings and JSON structure
                    for node in nodes:
                        node_id, name, domain, node_type, desc, tags, props_json, emb_json = node
                        try:
                            emb = json.loads(emb_json)
                            if not isinstance(emb, list):
                                db_verification_passed = False
                                db_errs.append(f"Node {node_id} embedding is not a list: {type(emb)}")
                            elif len(emb) != 768:
                                db_verification_passed = False
                                db_errs.append(f"Node {node_id} embedding dimension is {len(emb)}, expected 768")
                            elif not all(isinstance(x, (float, int)) for x in emb):
                                db_verification_passed = False
                                db_errs.append(f"Node {node_id} embedding contains non-numeric values")
                        except Exception as parse_e:
                            db_verification_passed = False
                            db_errs.append(f"Node {node_id} embedding_json parse error: {parse_e}")

                        # Check properties JSON
                        try:
                            props = json.loads(props_json)
                            if "scene_id" not in props or "transcript" not in props:
                                db_verification_passed = False
                                db_errs.append(f"Node {node_id} properties JSON missing required keys")
                        except Exception as prop_e:
                            db_verification_passed = False
                            db_errs.append(f"Node {node_id} properties parse error: {prop_e}")

                    # Query kg_edges for BELONGS_TO and NEXT_SCENE
                    cursor.execute("""
                        SELECT source_id, target_id, relation
                        FROM kg_edges
                        WHERE relation IN ('BELONGS_TO', 'NEXT_SCENE')
                    """)
                    edges = cursor.fetchall()
                    belongs_to_edges = [e for e in edges if e[2] == 'BELONGS_TO']
                    next_scene_edges = [e for e in edges if e[2] == 'NEXT_SCENE']

                    if len(belongs_to_edges) == 0:
                        db_verification_passed = False
                        db_errs.append(f"{dbp}: No BELONGS_TO edges found")

                    conn.close()

                if db_verification_passed:
                    record_test("Test 6: SuperGraph Database Indexing & 768D Vector Check", "PASS",
                                f"Successfully verified 768D embeddings, kg_nodes, and kg_edges across {len(db_paths)} databases")
                else:
                    record_test("Test 6: SuperGraph Database Indexing & 768D Vector Check", "FAIL", "; ".join(db_errs))

    except Exception as e:
        record_test("Test 6: SuperGraph Database Indexing & 768D Vector Check", "FAIL", f"Exception: {e}\n{traceback.format_exc()}")

    # ----------------------------------------------------
    # Summary
    # ----------------------------------------------------
    print("==================================================", flush=True)
    print("TEST SUMMARY:", flush=True)
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    print(f"Total Tests: {len(results)} | Passed: {pass_count} | Failed: {fail_count}", flush=True)

    if fail_count > 0:
        print("\nFAILURES:", flush=True)
        for r in results:
            if r["status"] == "FAIL":
                print(f" - {r['name']}: {r['details']}", flush=True)

    return fail_count == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
