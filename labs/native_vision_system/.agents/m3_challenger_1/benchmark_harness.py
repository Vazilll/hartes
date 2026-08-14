"""
Empirical Benchmark and Stress Testing Harness for vazus_vision_daemon.py
Location: C:\\vazus\\labs\\native_vision_system\\.agents\\m3_challenger_1\\benchmark_harness.py
"""

import sys
import os
import io
import time
import json
import subprocess
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, r"C:\vazus")

from vazus_vision_daemon import (
    ImageDeduplicator,
    VisionPayloadGenerator,
    VisionDaemonIPC,
    VazusVisionDaemon
)

def run_latency_benchmark():
    print("\n--- 1. LATENCY BENCHMARK ---")
    results = {}

    img_small = Image.new("RGB", (100, 100), color=(255, 0, 0))
    img_fhd = Image.new("RGB", (1920, 1080), color=(0, 128, 255))
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_png:
        img_small.save(tmp_png.name, format="PNG")
        tmp_png_path = tmp_png.name

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_jpg:
        img_fhd.save(tmp_jpg.name, format="JPEG")
        tmp_jpg_path = tmp_jpg.name

    try:
        # Benchmark 1.1: File Drop Latency (Small PNG, with RapidOCR mocked to avoid ONNX reload)
        with patch.object(VisionPayloadGenerator, "extract_ocr", return_value={"engine": "mock_rapidocr", "has_text": False, "extracted_text": "", "confidence": 0.0}):
            latencies_file_small = []
            for _ in range(10):
                t0 = time.perf_counter()
                payload = VisionPayloadGenerator.generate(tmp_png_path, source_type="file_drop")
                t1 = time.perf_counter()
                latencies_file_small.append((t1 - t0) * 1000.0)

            avg_file_small = sum(latencies_file_small) / len(latencies_file_small)
            max_file_small = max(latencies_file_small)

            # Benchmark 1.2: File Drop Latency (Full HD JPG)
            latencies_file_fhd = []
            for _ in range(10):
                t0 = time.perf_counter()
                payload = VisionPayloadGenerator.generate(tmp_jpg_path, source_type="file_drop")
                t1 = time.perf_counter()
                latencies_file_fhd.append((t1 - t0) * 1000.0)

            avg_file_fhd = sum(latencies_file_fhd) / len(latencies_file_fhd)
            max_file_fhd = max(latencies_file_fhd)

            # Benchmark 1.3: Clipboard RAM Image Latency (PIL Image)
            latencies_clip = []
            for _ in range(10):
                t0 = time.perf_counter()
                payload = VisionPayloadGenerator.generate(img_fhd, source_type="clipboard")
                t1 = time.perf_counter()
                latencies_clip.append((t1 - t0) * 1000.0)

            avg_clip = sum(latencies_clip) / len(latencies_clip)
            max_clip = max(latencies_clip)

        # Benchmark 1.4: Real unmocked single-pass latency (including real RapidOCR pass)
        t0_real = time.perf_counter()
        payload_real = VisionPayloadGenerator.generate(tmp_png_path, source_type="file_drop")
        t1_real = time.perf_counter()
        real_pass_ms = (t1_real - t0_real) * 1000.0

        results["file_small_png"] = {"avg_ms": round(avg_file_small, 2), "max_ms": round(max_file_small, 2), "pass": max_file_small < 500.0}
        results["file_fhd_jpg"] = {"avg_ms": round(avg_file_fhd, 2), "max_ms": round(max_file_fhd, 2), "pass": max_file_fhd < 500.0}
        results["clipboard_fhd"] = {"avg_ms": round(avg_clip, 2), "max_ms": round(max_clip, 2), "pass": max_clip < 500.0}
        results["real_unmocked_pass"] = {"single_pass_ms": round(real_pass_ms, 2)}

        print(f"  File Drop (100x100 PNG)   : Avg = {avg_file_small:.2f}ms | Max = {max_file_small:.2f}ms | Under 500ms: {max_file_small < 500.0}")
        print(f"  File Drop (1920x1080 JPG) : Avg = {avg_file_fhd:.2f}ms | Max = {max_file_fhd:.2f}ms | Under 500ms: {max_file_fhd < 500.0}")
        print(f"  Clipboard (1920x1080 RAM) : Avg = {avg_clip:.2f}ms | Max = {max_clip:.2f}ms | Under 500ms: {max_clip < 500.0}")
        print(f"  Real Unmocked Pass (w/ OCR): {real_pass_ms:.2f}ms")

    finally:
        if os.path.exists(tmp_png_path):
            os.remove(tmp_png_path)
        if os.path.exists(tmp_jpg_path):
            os.remove(tmp_jpg_path)

    return results


def run_dedup_stress_test():
    print("\n--- 2. SHA-256 DEDUPLICATION STRESS TEST ---")
    results = {}

    deduper = ImageDeduplicator(max_size=100, ttl_seconds=1.0)
    hash_val = "a" * 64
    
    first_check = deduper.is_duplicate(hash_val)
    second_check = deduper.is_duplicate(hash_val)

    print(f"  First check (new hash)       : {first_check} (Expected: False)")
    print(f"  Second check (immediate dup) : {second_check} (Expected: True)")

    print("  Sleeping 1.1s for TTL expiration...")
    time.sleep(1.1)
    ttl_check = deduper.is_duplicate(hash_val)
    print(f"  Post-TTL check (after 1.1s)  : {ttl_check} (Expected: False)")

    t0 = time.perf_counter()
    for i in range(50000):
        h = f"hash_{i % 200}"
        deduper.is_duplicate(h)
    t1 = time.perf_counter()
    duration_ms = (t1 - t0) * 1000.0
    print(f"  50,000 LRU lookup throughput: {duration_ms:.2f}ms ({50000 / (t1 - t0):.0f} ops/sec)")

    results["correctness"] = (first_check is False) and (second_check is True) and (ttl_check is False)
    results["throughput_ops_per_sec"] = round(50000 / (t1 - t0), 0)
    return results


def run_cli_verification():
    print("\n--- 3. CLI COMMAND VERIFICATION ---")
    results = {}
    py_exec = sys.executable
    daemon_script = r"C:\vazus\vazus_vision_daemon.py"

    # Test 1: --once
    res_once = subprocess.run([py_exec, daemon_script, "--once"], capture_output=True, text=True)
    print(f"  --once Exit Code: {res_once.returncode}")
    print(f"  --once Output: {res_once.stdout.strip()}")
    results["once_exit_code"] = res_once.returncode == 0

    # Test 2: --status
    res_status = subprocess.run([py_exec, daemon_script, "--status"], capture_output=True, text=True)
    print(f"  --status Exit Code: {res_status.returncode}")
    print(f"  --status Output: {res_status.stdout.strip()}")
    results["status_exit_code"] = res_status.returncode == 0

    # Test 3: --test-drop with temporary PNG
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        img = Image.new("RGB", (200, 150), color="green")
        img.save(tmp_file.name, format="PNG")
        tmp_path = tmp_file.name

    try:
        res_drop = subprocess.run([py_exec, daemon_script, "--test-drop", tmp_path], capture_output=True, text=True)
        print(f"  --test-drop Exit Code: {res_drop.returncode}")
        
        valid_json = False
        if res_drop.returncode == 0:
            try:
                payload = json.loads(res_drop.stdout)
                valid_json = (
                    "event_id" in payload and
                    "visual_tokens" in payload and
                    "tui_preview" in payload and
                    payload["image_metadata"]["width"] == 200
                )
                print(f"  --test-drop JSON Valid: {valid_json} (Event ID: {payload.get('event_id')})")
            except Exception as e:
                print(f"  --test-drop JSON parse error: {e}")

        results["test_drop_exit_code"] = res_drop.returncode == 0
        results["test_drop_valid_json"] = valid_json
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return results

def main():
    print("=========================================================")
    print("VAZUS VISION DAEMON EMPIRICAL BENCHMARK & STRESS TEST")
    print("=========================================================")
    
    latency_res = run_latency_benchmark()
    dedup_res = run_dedup_stress_test()
    cli_res = run_cli_verification()

    print("\n=========================================================")
    print("SUMMARY VERDICT DATA")
    print("=========================================================")
    print(f"Latency Benchmark Pass: {all(r['pass'] for r in latency_res.values() if 'pass' in r)}")
    print(f"Deduplication TTL Pass: {dedup_res['correctness']}")
    print(f"CLI Commands Pass     : {cli_res['once_exit_code'] and cli_res['status_exit_code'] and cli_res['test_drop_valid_json']}")
    
    overall_pass = (
        all(r['pass'] for r in latency_res.values() if 'pass' in r) and
        dedup_res['correctness'] and
        cli_res['once_exit_code'] and
        cli_res['status_exit_code'] and
        cli_res['test_drop_valid_json']
    )
    print(f"OVERALL EMPIRICAL VERDICT: {'PASS' if overall_pass else 'FAIL'}")

if __name__ == "__main__":
    main()
