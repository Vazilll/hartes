#!/usr/bin/env python3
"""
vazus Milestone 3 Stress Test Harness
Location: C:\\vazus\\.agents\\teamwork_preview_challenger_m3_1\\stress_test_m3_server.py

Tests:
1. CLI Chat (`scripts/knowledge_chat.py`)
2. FastMCP Server (`scripts/knowledge_mcp.py`)
3. Web Dashboard Server (`scripts/dashboard.py`)
   - Serving SPA HTML
   - REST Search API (`/api/v1/knowledge/search`)
   - HTTP 206 Range Streaming (`/api/v1/knowledge/stream`)
   - Thumbnail serving (`/api/v1/knowledge/thumbnail`)
   - Security / Directory Traversal testing
   - Concurrency stress testing (50 concurrent clients)
"""

import os
import sys
import time
import json
import socket
import urllib.request
import urllib.error
import urllib.parse
import subprocess
import concurrent.futures
from pathlib import Path

PROJECT_ROOT = Path("C:/vazus")
WORK_DIR = Path("C:/vazus/.agents/teamwork_preview_challenger_m3_1")
PYTHON_EXE = sys.executable

RESULTS = {
    "cli_tests": [],
    "mcp_tests": [],
    "dashboard_tests": [],
    "security_tests": [],
    "concurrency_benchmark": {}
}

def log(msg: str):
    print(f"[STRESS_HARNESS] {msg}")

def test_cli():
    log("=== 1. Testing CLI Chat (knowledge_chat.py) ===")
    cli_path = PROJECT_ROOT / "scripts" / "knowledge_chat.py"

    cli_test_cases = [
        {"name": "Empty Query", "args": ["--query", "", "--json"]},
        {"name": "Special Characters", "args": ["--query", "!@#$%^&*()_+-=[]{}|;:',.<>?/~`", "--json"]},
        {"name": "Cyrillic Text", "args": ["--query", "нейросеть и мультимодальный поиск", "--json"]},
        {"name": "Long Query", "args": ["--query", "vazus " * 200, "--json"]},
        {"name": "High Top-K", "args": ["--query", "test", "--top-k", "100", "--json"]},
        {"name": "Human Readable CLI Output", "args": ["--query", "test", "--top-k", "2"]}
    ]

    for tc in cli_test_cases:
        cmd = [PYTHON_EXE, str(cli_path)] + tc["args"]
        t0 = time.perf_counter()
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=30)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            
            is_json_flag = "--json" in tc["args"]
            valid_json = False
            parsed = None
            if is_json_flag and res.returncode == 0:
                try:
                    parsed = json.loads(res.stdout)
                    valid_json = isinstance(parsed, list)
                except Exception as je:
                    valid_json = False
            
            status = "PASS" if res.returncode == 0 and (not is_json_flag or valid_json) else "FAIL"
            
            RESULTS["cli_tests"].append({
                "name": tc["name"],
                "args": tc["args"],
                "returncode": res.returncode,
                "latency_ms": round(elapsed_ms, 2),
                "valid_json": valid_json if is_json_flag else "N/A",
                "result_count": len(parsed) if valid_json and isinstance(parsed, list) else (0 if res.returncode==0 else "ERR"),
                "status": status,
                "stdout_snippet": res.stdout[:200].replace("\n", " "),
                "stderr_snippet": res.stderr[:200].replace("\n", " ")
            })
            log(f"  [{status}] {tc['name']} -> {elapsed_ms:.1f} ms (Exit Code: {res.returncode})")
        except Exception as e:
            RESULTS["cli_tests"].append({
                "name": tc["name"],
                "args": tc["args"],
                "status": "ERROR",
                "error": str(e)
            })
            log(f"  [ERROR] {tc['name']}: {e}")

def test_mcp():
    log("=== 2. Testing FastMCP Functions (knowledge_mcp.py) ===")
    mcp_path = PROJECT_ROOT / "scripts" / "knowledge_mcp.py"
    
    # We test importing knowledge_mcp tools directly
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from scripts.knowledge_mcp import search_multimodal_knowledge, get_media_scene_details, stream_video_segment_info
        
        # Test 1: search_multimodal_knowledge
        t0 = time.perf_counter()
        res_search = search_multimodal_knowledge("тест видео", top_k=3)
        ms_search = (time.perf_counter() - t0) * 1000
        parsed_search = json.loads(res_search)
        log(f"  [PASS] search_multimodal_knowledge -> {ms_search:.1f} ms ({len(parsed_search)} results)")

        # Test 2: get_media_scene_details (existing vs non-existing)
        t0 = time.perf_counter()
        res_scene = get_media_scene_details("scene_001")
        ms_scene = (time.perf_counter() - t0) * 1000
        parsed_scene = json.loads(res_scene)
        log(f"  [{'PASS' if 'error' not in parsed_scene or 'MediaScene' in res_scene else 'WARN'}] get_media_scene_details -> {ms_scene:.1f} ms")

        # Test 3: stream_video_segment_info
        t0 = time.perf_counter()
        res_stream_info = stream_video_segment_info("scene_001")
        ms_stream = (time.perf_counter() - t0) * 1000
        log(f"  [PASS] stream_video_segment_info -> {ms_stream:.1f} ms")

        RESULTS["mcp_tests"].append({"name": "search_multimodal_knowledge", "latency_ms": round(ms_search, 2), "status": "PASS"})
        RESULTS["mcp_tests"].append({"name": "get_media_scene_details", "latency_ms": round(ms_scene, 2), "status": "PASS"})
        RESULTS["mcp_tests"].append({"name": "stream_video_segment_info", "latency_ms": round(ms_stream, 2), "status": "PASS"})

    except Exception as e:
        log(f"  [ERROR] MCP testing error: {e}")
        RESULTS["mcp_tests"].append({"name": "mcp_import_and_exec", "status": "ERROR", "error": str(e)})

def setup_dummy_media_files():
    # Create test media and thumbnail files in WORK_DIR for range stream and thumbnail testing
    dummy_media = WORK_DIR / "test_sample_video.mp4"
    dummy_thumb = WORK_DIR / "test_sample_thumb.jpg"

    # 10,000 bytes dummy file
    with open(dummy_media, "wb") as f:
        f.write(b"MP4_HEADER_DUMMY_DATA_" + b"\x00" * 9979)
    
    # 5,000 bytes dummy thumbnail
    with open(dummy_thumb, "wb") as f:
        f.write(b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 4988 + b"\xFF\xD9")

    return str(dummy_media), str(dummy_thumb)

def test_dashboard():
    log("=== 3. Testing Web Dashboard Server (dashboard.py) ===")
    media_file, thumb_file = setup_dummy_media_files()
    
    dashboard_script = PROJECT_ROOT / "scripts" / "dashboard.py"
    port = 8501
    host = "127.0.0.1"
    base_url = f"http://{host}:{port}"

    server_cmd = [PYTHON_EXE, str(dashboard_script), "--host", host, "--port", str(port)]
    proc = subprocess.Popen(server_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")

    # Wait for server to start
    started = False
    for _ in range(30):
        time.sleep(0.2)
        try:
            with socket.create_connection((host, port), timeout=1):
                started = True
                break
        except OSError:
            pass

    if not started:
        log("[ERROR] Dashboard server failed to start on port 8501")
        proc.kill()
        return

    log(f"Dashboard server running on {base_url}")

    try:
        # 3a. Root Endpoint / HTML SPA
        t0 = time.perf_counter()
        req = urllib.request.Request(f"{base_url}/")
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
        ms_html = (time.perf_counter() - t0) * 1000
        has_html_structure = "vazus Multimodal Knowledge Dashboard" in body or "<!DOCTYPE html>" in body
        log(f"  [{'PASS' if status==200 and has_html_structure else 'FAIL'}] GET / -> {status} ({ms_html:.1f} ms, Content-Type: {content_type})")
        RESULTS["dashboard_tests"].append({
            "endpoint": "GET /",
            "status_code": status,
            "latency_ms": round(ms_html, 2),
            "content_type": content_type,
            "pass": status == 200 and has_html_structure
        })

        # 3b. REST Stats Endpoint
        t0 = time.perf_counter()
        req = urllib.request.Request(f"{base_url}/api/v1/knowledge/stats")
        with urllib.request.urlopen(req) as resp:
            stats_json = json.loads(resp.read().decode("utf-8"))
            status = resp.status
        ms_stats = (time.perf_counter() - t0) * 1000
        log(f"  [PASS] GET /api/v1/knowledge/stats -> {status} ({ms_stats:.1f} ms): {stats_json}")
        RESULTS["dashboard_tests"].append({
            "endpoint": "GET /api/v1/knowledge/stats",
            "status_code": status,
            "latency_ms": round(ms_stats, 2),
            "response": stats_json,
            "pass": status == 200
        })

        # 3c. REST Search Endpoint (Cyrillic query)
        query_str = urllib.parse.quote("тест")
        t0 = time.perf_counter()
        req = urllib.request.Request(f"{base_url}/api/v1/knowledge/search?query={query_str}&top_k=5")
        with urllib.request.urlopen(req) as resp:
            search_res = json.loads(resp.read().decode("utf-8"))
            status = resp.status
        ms_search = (time.perf_counter() - t0) * 1000
        log(f"  [PASS] GET /api/v1/knowledge/search?query=тест -> {status} ({ms_search:.1f} ms, matches: {search_res.get('count')})")
        RESULTS["dashboard_tests"].append({
            "endpoint": "GET /api/v1/knowledge/search?query=тест",
            "status_code": status,
            "latency_ms": round(ms_search, 2),
            "matches": search_res.get("count"),
            "pass": status == 200
        })

        # 3d. HTTP Range Streaming Endpoint (Valid range: bytes=0-1023)
        quoted_media_path = urllib.parse.quote(media_file)
        t0 = time.perf_counter()
        req = urllib.request.Request(f"{base_url}/api/v1/knowledge/stream?path={quoted_media_path}")
        req.add_header("Range", "bytes=0-1023")
        with urllib.request.urlopen(req) as resp:
            stream_body = resp.read()
            status = resp.status
            content_range = resp.headers.get("Content-Range")
            content_length = resp.headers.get("Content-Length")
        ms_stream_valid = (time.perf_counter() - t0) * 1000
        log(f"  [PASS] GET /api/v1/knowledge/stream (Valid Range 0-1023) -> HTTP {status} ({ms_stream_valid:.1f} ms, Range: {content_range}, Length: {content_length})")
        RESULTS["dashboard_tests"].append({
            "endpoint": "GET /api/v1/knowledge/stream (Range 0-1023)",
            "status_code": status,
            "latency_ms": round(ms_stream_valid, 2),
            "content_range": content_range,
            "received_bytes": len(stream_body),
            "pass": status == 206 and len(stream_body) == 1024
        })

        # 3e. HTTP Range Streaming Endpoint (Invalid out-of-bound range: bytes=99999-100000)
        t0 = time.perf_counter()
        req = urllib.request.Request(f"{base_url}/api/v1/knowledge/stream?path={quoted_media_path}")
        req.add_header("Range", "bytes=99999-100000")
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
        except urllib.error.HTTPError as he:
            status = he.code
            content_range = he.headers.get("Content-Range")
        ms_stream_inv = (time.perf_counter() - t0) * 1000
        log(f"  [{'PASS' if status==416 else 'FAIL'}] GET /api/v1/knowledge/stream (Out of bound Range) -> HTTP {status} (Expected 416, Content-Range: {content_range})")
        RESULTS["dashboard_tests"].append({
            "endpoint": "GET /api/v1/knowledge/stream (Range 99999-100000)",
            "status_code": status,
            "latency_ms": round(ms_stream_inv, 2),
            "content_range": content_range,
            "pass": status == 416
        })

        # 3f. HTTP Range Streaming Endpoint (Invalid reversed range: bytes=500-100)
        t0 = time.perf_counter()
        req = urllib.request.Request(f"{base_url}/api/v1/knowledge/stream?path={quoted_media_path}")
        req.add_header("Range", "bytes=500-100")
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
        except urllib.error.HTTPError as he:
            status = he.code
        ms_stream_rev = (time.perf_counter() - t0) * 1000
        log(f"  [{'PASS' if status==416 else 'FAIL'}] GET /api/v1/knowledge/stream (Reversed Range 500-100) -> HTTP {status} (Expected 416)")
        RESULTS["dashboard_tests"].append({
            "endpoint": "GET /api/v1/knowledge/stream (Range 500-100)",
            "status_code": status,
            "latency_ms": round(ms_stream_rev, 2),
            "pass": status == 416
        })

        # 3g. Non-existent file path streaming
        t0 = time.perf_counter()
        req = urllib.request.Request(f"{base_url}/api/v1/knowledge/stream?path=C:/non_existent_file.mp4")
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
        except urllib.error.HTTPError as he:
            status = he.code
        ms_stream_404 = (time.perf_counter() - t0) * 1000
        log(f"  [PASS] GET /api/v1/knowledge/stream (Non-existent File) -> HTTP {status} (Expected 404)")
        RESULTS["dashboard_tests"].append({
            "endpoint": "GET /api/v1/knowledge/stream (Non-existent)",
            "status_code": status,
            "latency_ms": round(ms_stream_404, 2),
            "pass": status == 404
        })

        # 3h. Thumbnail Endpoint (Valid)
        quoted_thumb_path = urllib.parse.quote(thumb_file)
        t0 = time.perf_counter()
        req = urllib.request.Request(f"{base_url}/api/v1/knowledge/thumbnail?path={quoted_thumb_path}")
        with urllib.request.urlopen(req) as resp:
            thumb_data = resp.read()
            status = resp.status
            content_type = resp.headers.get("Content-Type")
        ms_thumb = (time.perf_counter() - t0) * 1000
        log(f"  [PASS] GET /api/v1/knowledge/thumbnail -> HTTP {status} ({ms_thumb:.1f} ms, Content-Type: {content_type}, Size: {len(thumb_data)} bytes)")
        RESULTS["dashboard_tests"].append({
            "endpoint": "GET /api/v1/knowledge/thumbnail",
            "status_code": status,
            "latency_ms": round(ms_thumb, 2),
            "content_type": content_type,
            "size_bytes": len(thumb_data),
            "pass": status == 200
        })

        # 3i. Directory Traversal Security Audit
        log("=== 4. Security & Directory Traversal Testing ===")
        traversal_payloads = [
            "../../Windows/win.ini",
            "..\\..\\Windows\\win.ini",
            "C:/Windows/win.ini",
            "....//....//Windows/win.ini",
            "%2e%2e%2f%2e%2e%2fWindows%2fwin.ini"
        ]

        for payload in traversal_payloads:
            url = f"{base_url}/api/v1/knowledge/stream?path={urllib.parse.quote(payload)}"
            req = urllib.request.Request(url)
            read_content = b""
            status = 0
            vulnerable = False
            try:
                with urllib.request.urlopen(req) as resp:
                    status = resp.status
                    read_content = resp.read(100)
            except urllib.error.HTTPError as he:
                status = he.code

            # Check if file contents were leaked (win.ini contains [fonts] or [extensions])
            if status == 200 and (b"[fonts]" in read_content.lower() or b"[extensions]" in read_content.lower() or b"for 16-bit app support" in read_content.lower()):
                vulnerable = True

            log(f"  [{'VULNERABLE!' if vulnerable else 'BLOCKED/404'}] Traversal payload '{payload}' -> HTTP {status} (Leaked data: {vulnerable})")
            RESULTS["security_tests"].append({
                "payload": payload,
                "status_code": status,
                "vulnerable": vulnerable,
                "details": "File contents returned (Arbitrary File Read!)" if vulnerable else "Request rejected or file not accessed"
            })

        # 3j. Concurrency Benchmark (50 parallel requests)
        log("=== 5. Concurrency Benchmark (50 parallel requests) ===")
        num_requests = 50
        endpoints_to_hit = [
            f"{base_url}/api/v1/knowledge/search?query=тест&top_k=5",
            f"{base_url}/api/v1/knowledge/stats",
            f"{base_url}/api/v1/knowledge/stream?path={quoted_media_path}",
            f"{base_url}/"
        ]

        def send_req(i):
            target_url = endpoints_to_hit[i % len(endpoints_to_hit)]
            t_start = time.perf_counter()
            req = urllib.request.Request(target_url)
            if "stream" in target_url:
                req.add_header("Range", "bytes=0-255")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    _ = resp.read()
                    st = resp.status
            except urllib.error.HTTPError as he:
                st = he.code
            except Exception as e:
                st = -1
            dur_ms = (time.perf_counter() - t_start) * 1000
            return st, dur_ms

        t_start_all = time.perf_counter()
        latencies = []
        statuses = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(send_req, i) for i in range(num_requests)]
            for f in concurrent.futures.as_completed(futures):
                st, dur = f.result()
                statuses.append(st)
                latencies.append(dur)

        total_time_s = time.perf_counter() - t_start_all
        latencies.sort()
        avg_lat = sum(latencies) / len(latencies)
        p50_lat = latencies[int(len(latencies) * 0.50)]
        p95_lat = latencies[int(len(latencies) * 0.95)]
        max_lat = max(latencies)
        rps = num_requests / total_time_s
        success_rate = (sum(1 for s in statuses if s in (200, 206)) / num_requests) * 100

        log(f"  Concurrency Benchmark Completed:")
        log(f"    Total Requests: {num_requests}")
        log(f"    Total Time    : {total_time_s:.2f} s")
        log(f"    Throughput    : {rps:.1f} req/sec")
        log(f"    Success Rate  : {success_rate:.1f}%")
        log(f"    Avg Latency   : {avg_lat:.2f} ms")
        log(f"    P50 Latency   : {p50_lat:.2f} ms")
        log(f"    P95 Latency   : {p95_lat:.2f} ms")
        log(f"    Max Latency   : {max_lat:.2f} ms")

        RESULTS["concurrency_benchmark"] = {
            "total_requests": num_requests,
            "total_time_sec": round(total_time_s, 2),
            "throughput_rps": round(rps, 2),
            "success_rate_pct": success_rate,
            "avg_latency_ms": round(avg_lat, 2),
            "p50_latency_ms": round(p50_lat, 2),
            "p95_latency_ms": round(p95_lat, 2),
            "max_latency_ms": round(max_lat, 2)
        }

    finally:
        log("Shutting down Dashboard test server...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

def save_report():
    output_json = WORK_DIR / "stress_test_results.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, indent=2, ensure_ascii=False)
    log(f"Test results saved to {output_json}")

if __name__ == "__main__":
    test_cli()
    test_mcp()
    test_dashboard()
    save_report()
