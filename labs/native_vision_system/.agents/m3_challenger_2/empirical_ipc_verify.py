"""
Empirical Verification Script for M3 Real-Time Vision Daemon IPC & SQLite Persistence.
Agent: m3_challenger_2
File: C:\\vazus\\labs\\native_vision_system\\.agents\\m3_challenger_2\\empirical_ipc_verify.py
"""

import sys
import os
import io
import time
import json
import asyncio
import sqlite3
from pathlib import Path
from PIL import Image

sys.path.insert(0, r"C:\vazus")
sys.path.insert(0, r"C:\vazus\labs\native_vision_system\tests")

# 1. Imports check
from vazus_vision_daemon import (
    VisionDaemonIPC,
    VisionPayloadGenerator,
    ImageDeduplicator,
    VazusVisionDaemon
)
from test_helpers import VisionDaemonStub

import websockets

async def run_empirical_tests():
    print("=== STARTING EMPIRICAL VERIFICATION FOR M3 VISION DAEMON ===")
    
    # Test 3: Verify VisionDaemonStub export and functionality
    print("\n--- Test 1: VisionDaemonStub Export & Functionality ---")
    stub = VisionDaemonStub(workspace_dir=r"C:\vazus")
    test_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    stub_payload = stub.build_visual_token_payload("clipboard", test_bytes, ocr_text="STUB TEST")
    assert stub_payload["source_type"] == "clipboard"
    assert stub_payload["mime_type"] == "image/png"
    assert stub_payload["ocr_text"] == "STUB TEST"
    
    tmp_db = r"C:\vazus\labs\native_vision_system\.agents\m3_challenger_2\test_stub.db"
    if os.path.exists(tmp_db):
        os.remove(tmp_db)
    
    rec_result = stub.record_to_sqlite(stub_payload, db_file=tmp_db)
    assert rec_result is True
    
    conn_stub = sqlite3.connect(tmp_db)
    row_stub = conn_stub.execute("SELECT event_id, source_type, ocr_text FROM vision_event_stream").fetchone()
    conn_stub.close()
    assert row_stub[0] == stub_payload["event_id"]
    assert row_stub[1] == "clipboard"
    assert row_stub[2] == "STUB TEST"
    print("PASS: VisionDaemonStub export verified successfully.")

    # Test 2: SQLite Persistence to vazus.db and schema validation
    print("\n--- Test 2: SQLite Persistence & Schema Verification ---")
    vazus_db_path = r"C:\vazus\memory\vazus.db"
    ipc = VisionDaemonIPC(db_path=vazus_db_path)
    
    # Check schema
    conn = sqlite3.connect(vazus_db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(vision_event_stream);")
    columns = {col[1]: col[2] for col in cursor.fetchall()}
    print(f"Table columns in vision_event_stream: {columns}")
    
    expected_cols = ["event_id", "timestamp", "source", "file_path", "sha256", "mime_type", "payload_json", "created_at"]
    for col in expected_cols:
        assert col in columns, f"Missing column {col} in vision_event_stream table"
    
    # Check index
    cursor.execute("PRAGMA index_list(vision_event_stream);")
    indices = [idx[1] for idx in cursor.fetchall()]
    print(f"Indices on vision_event_stream: {indices}")
    assert "idx_vision_event_sha256" in indices, "Missing idx_vision_event_sha256 index"
    conn.close()

    # Generate a real payload
    img = Image.new("RGB", (32, 32), color="green")
    payload = VisionPayloadGenerator.generate(img, source_type="empirical_test")
    ipc.log_event_to_db(payload)
    
    # Verify reading back from vazus.db
    conn = sqlite3.connect(vazus_db_path)
    row = conn.execute("SELECT event_id, source, sha256, mime_type, payload_json FROM vision_event_stream WHERE event_id=?", (payload["event_id"],)).fetchone()
    conn.close()
    
    assert row is not None, "Payload was not written to vazus.db"
    assert row[0] == payload["event_id"]
    assert row[1] == "empirical_test"
    assert row[2] == payload["dedup"]["sha256"]
    assert row[3] == "image/png"
    parsed_json = json.loads(row[4])
    assert parsed_json["event_id"] == payload["event_id"]
    assert "tui_preview" in parsed_json
    assert "visual_tokens" in parsed_json
    print("PASS: SQLite persistence in C:\\vazus\\memory\\vazus.db verified successfully.")

    # Test 1: WebSocket Server connection & Broadcast
    print("\n--- Test 3: WebSocket Server (ws://127.0.0.1:8766/ws/vision) Connection & Broadcast ---")
    ws_port = 8766
    ipc_ws = VisionDaemonIPC(host="127.0.0.1", port=ws_port, db_path=vazus_db_path)
    
    # Start WS server
    server = await ipc_ws.start_server()
    print("WebSocket server started on port 8766.")
    
    # Connect client
    ws_uri = "ws://127.0.0.1:8766/ws/vision"
    async with websockets.connect(ws_uri) as client_ws:
        print("Client connected to ws://127.0.0.1:8766/ws/vision.")
        
        # Broadcast visual token payload
        test_img = Image.new("RGB", (64, 64), color="blue")
        ws_payload = VisionPayloadGenerator.generate(test_img, source_type="ws_broadcast_test")
        
        broadcast_task = asyncio.create_task(ipc_ws.broadcast(ws_payload))
        
        # Client receives message
        received_msg = await asyncio.wait_for(client_ws.recv(), timeout=5.0)
        await broadcast_task
        
        rx_payload = json.loads(received_msg)
        assert rx_payload["event_id"] == ws_payload["event_id"]
        assert rx_payload["source"] == "ws_broadcast_test"
        assert rx_payload["visual_tokens"]["mime_type"] == "image/png"
        assert "genai_inline_part" in rx_payload["visual_tokens"]
        assert rx_payload["visual_tokens"]["genai_inline_part"]["inlineData"]["mimeType"] == "image/png"
        assert "tui_preview" in rx_payload
        print(f"PASS: WebSocket broadcast received valid visual token payload for event {rx_payload['event_id']}.")

    server.close()
    await server.wait_closed()
    print("WebSocket server closed.")

    # Test 4: Stress & Edge Cases
    print("\n--- Test 4: Stress-Testing & Edge Cases ---")
    # Rapid broadcast stress test
    ipc_stress = VisionDaemonIPC(host="127.0.0.1", port=8766, db_path=vazus_db_path)
    server_stress = await ipc_stress.start_server()
    
    async with websockets.connect("ws://127.0.0.1:8766") as client_ws:
        print("Executing 50 rapid sequential broadcasts...")
        start_t = time.time()
        for i in range(50):
            p = VisionPayloadGenerator.generate(Image.new("RGB", (10+i, 10+i)), source_type=f"stress_{i}")
            await ipc_stress.broadcast(p)
            msg = await asyncio.wait_for(client_ws.recv(), timeout=2.0)
            data = json.loads(msg)
            assert data["source"] == f"stress_{i}"
        elapsed = time.time() - start_t
        print(f"50 rapid broadcasts completed in {elapsed:.3f}s ({elapsed/50*1000:.1f}ms per payload).")
    
    server_stress.close()
    await server_stress.wait_closed()
    print("PASS: Stress testing passed.")

    print("\n=== ALL EMPIRICAL VERIFICATIONS PASSED 100% ===")

if __name__ == "__main__":
    asyncio.run(run_empirical_tests())
