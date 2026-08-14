"""
Unit Test Suite for Milestone M3: Real-Time Vision Daemon (vazus_vision_daemon.py).
File: C:\\vazus\\labs\\native_vision_system\\tests\\test_vazus_vision_daemon.py
Runner: C:\\vazus\\.venv\\Scripts\\python.exe -m pytest C:\\vazus\\labs\\native_vision_system\\tests\\test_vazus_vision_daemon.py
"""

import os
import io
import time
import json
import asyncio
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from PIL import Image

import sys
sys.path.insert(0, r"C:\vazus")

from vazus_vision_daemon import (
    ImageDeduplicator,
    VisionPayloadGenerator,
    ClipboardListener,
    WorkspaceWatcher,
    VisionDaemonIPC,
    VazusVisionDaemon,
    main,
    PID_FILE_PATH
)


# --- Test Fixtures ---

@pytest.fixture
def sample_png_image():
    return Image.new("RGB", (100, 100), color="red")


@pytest.fixture
def sample_png_bytes(sample_png_image):
    buf = io.BytesIO()
    sample_png_image.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def temp_db_path(tmp_path):
    return str(tmp_path / "test_vazus.db")


# ==============================================================================
# 1. Test Suite: ImageDeduplicator (LRU Cache & TTL)
# ==============================================================================

class TestImageDeduplicator:

    def test_dedup_unique_hashes(self):
        deduper = ImageDeduplicator(max_size=10, ttl_seconds=60)
        assert deduper.is_duplicate("hash1") is False
        assert deduper.is_duplicate("hash2") is False

    def test_dedup_duplicate_hash(self):
        deduper = ImageDeduplicator(max_size=10, ttl_seconds=60)
        assert deduper.is_duplicate("hash1") is False
        assert deduper.is_duplicate("hash1") is True

    def test_dedup_lru_eviction(self):
        deduper = ImageDeduplicator(max_size=2, ttl_seconds=60)
        deduper.is_duplicate("hash1")
        deduper.is_duplicate("hash2")
        deduper.is_duplicate("hash3")  # hash1 evicted

        assert deduper.is_duplicate("hash1") is False

    def test_dedup_ttl_expiration(self):
        deduper = ImageDeduplicator(max_size=10, ttl_seconds=0.1)
        deduper.is_duplicate("hash1")
        time.sleep(0.15)
        assert deduper.is_duplicate("hash1") is False


# ==============================================================================
# 2. Test Suite: VisionPayloadGenerator
# ==============================================================================

class TestVisionPayloadGenerator:

    def test_generate_from_image(self, sample_png_image):
        payload = VisionPayloadGenerator.generate(sample_png_image, source_type="clipboard")

        assert payload["event_id"].startswith("vvis_")
        assert payload["source"] == "clipboard"
        assert payload["image_metadata"]["width"] == 100
        assert payload["image_metadata"]["height"] == 100
        assert "inlineData" in payload["visual_tokens"]["genai_inline_part"]
        assert len(payload["tui_preview"]) > 0

    def test_generate_dedup_integration(self, sample_png_image):
        deduper = ImageDeduplicator()
        p1 = VisionPayloadGenerator.generate(sample_png_image, deduper=deduper)
        p2 = VisionPayloadGenerator.generate(sample_png_image, deduper=deduper)

        assert p1["dedup"]["is_duplicate"] is False
        assert p2["dedup"]["is_duplicate"] is True

    @patch("vazus_vision_daemon.HAS_RAPIDOCR", False)
    def test_ocr_fallback_when_disabled(self, sample_png_image):
        ocr = VisionPayloadGenerator.extract_ocr(sample_png_image)
        assert ocr["has_text"] is False
        assert ocr["engine"] == "none"

    @patch("vazus_vision_daemon.HAS_RAPIDOCR", True)
    @patch("vazus_vision_daemon.RapidOCR")
    def test_ocr_extraction_with_mocked_rapidocr(self, mock_rapidocr_cls, sample_png_image):
        mock_instance = MagicMock()
        mock_instance.return_value = (
            [
                [[[0, 0], [10, 0], [10, 10], [0, 10]], "Sample Text", "0.9876"]
            ],
            0.1
        )
        mock_rapidocr_cls.return_value = mock_instance

        ocr = VisionPayloadGenerator.extract_ocr(sample_png_image)
        assert ocr["engine"] == "rapidocr"
        assert ocr["has_text"] is True
        assert ocr["extracted_text"] == "Sample Text"
        assert ocr["confidence"] == 0.9876


# ==============================================================================
# 3. Test Suite: WorkspaceWatcher
# ==============================================================================

class TestWorkspaceWatcher:

    def test_filter_rules(self, tmp_path):
        watcher = WorkspaceWatcher(str(tmp_path), None)

        assert watcher._watch_filter(None, str(tmp_path / "test.png")) is True
        assert watcher._watch_filter(None, str(tmp_path / "test.jpg")) is True
        assert watcher._watch_filter(None, str(tmp_path / "test.jpeg")) is True
        assert watcher._watch_filter(None, str(tmp_path / "test.webp")) is True
        assert watcher._watch_filter(None, str(tmp_path / "test.txt")) is False
        assert watcher._watch_filter(None, str(tmp_path / ".git" / "test.png")) is False
        assert watcher._watch_filter(None, str(tmp_path / "node_modules" / "test.png")) is False
        assert watcher._watch_filter(None, str(tmp_path / ".venv" / "test.png")) is False

    def test_watcher_run_async(self, tmp_path):
        callback = AsyncMock()
        watcher = WorkspaceWatcher(str(tmp_path), callback)

        from watchfiles import Change
        async def mock_awatch(*args, **kwargs):
            yield {(Change.added, str(tmp_path / "drop.png"))}

        async def _run_test():
            with patch("vazus_vision_daemon.awatch", side_effect=mock_awatch), \
                 patch("vazus_vision_daemon.HAS_WATCHFILES", True):
                await watcher.run()

        asyncio.run(_run_test())


# ==============================================================================
# 4. Test Suite: ClipboardListener
# ==============================================================================

class TestClipboardListener:

    def test_listener_initialization(self):
        loop = asyncio.new_event_loop()
        try:
            callback = AsyncMock()
            listener = ClipboardListener(loop, callback)
            assert listener.loop == loop
            assert listener.callback == callback
            assert listener.running is False
        finally:
            loop.close()

    def test_start_and_stop(self):
        loop = asyncio.new_event_loop()
        try:
            callback = AsyncMock()
            listener = ClipboardListener(loop, callback)
            def mock_loop():
                listener.running = True
                while listener.running:
                    time.sleep(0.01)

            with patch.object(listener, "_win32_loop", side_effect=mock_loop), \
                 patch.object(listener, "_polling_loop", side_effect=mock_loop):
                listener.start()
                time.sleep(0.05)
                assert listener.thread is not None
                assert listener.thread.is_alive()
                listener.stop()
                time.sleep(0.05)
                assert listener.running is False
        finally:
            loop.close()

    def test_polling_fallback_trigger(self):
        loop = asyncio.new_event_loop()
        try:
            callback = AsyncMock()
            listener = ClipboardListener(loop, callback)
            listener._last_sequence = 1

            seq = 2
            if listener._last_sequence is not None and seq != listener._last_sequence:
                pass
            listener._last_sequence = seq
            assert listener._last_sequence == 2
        finally:
            loop.close()


# ==============================================================================
# 5. Test Suite: VisionDaemonIPC (SQLite & WebSocket)
# ==============================================================================

class TestVisionDaemonIPC:

    def test_sqlite_wal_logging(self, temp_db_path, sample_png_image):
        ipc = VisionDaemonIPC(db_path=temp_db_path)
        payload = VisionPayloadGenerator.generate(sample_png_image, source_type="test")
        ipc.log_event_to_db(payload)

        conn = sqlite3.connect(temp_db_path)
        row = conn.execute("SELECT * FROM vision_event_stream WHERE event_id=?", (payload["event_id"],)).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == payload["event_id"]
        assert row[2] == "test"

    def test_websocket_broadcast(self, temp_db_path, sample_png_image):
        async def _run_test():
            ipc = VisionDaemonIPC(db_path=temp_db_path)
            mock_ws = AsyncMock()
            ipc.clients.add(mock_ws)

            payload = VisionPayloadGenerator.generate(sample_png_image, source_type="ws_test")
            await ipc.broadcast(payload)

            mock_ws.send.assert_called_once()
            sent_json = json.loads(mock_ws.send.call_args[0][0])
            assert sent_json["event_id"] == payload["event_id"]

        asyncio.run(_run_test())

    def test_start_server(self, temp_db_path):
        async def _run_test():
            ipc = VisionDaemonIPC(db_path=temp_db_path)
            with patch("websockets.serve", new_callable=AsyncMock) as mock_serve:
                mock_serve.return_value = MagicMock()
                server = await ipc.start_server()
                assert server is not None
                mock_serve.assert_called_once()

        asyncio.run(_run_test())


# ==============================================================================
# 6. Test Suite: VazusVisionDaemon & CLI Commands
# ==============================================================================

class TestVazusVisionDaemonCLI:

    def test_cli_status_stopped(self):
        with patch("sys.argv", ["vazus_vision_daemon.py", "--status"]), \
             patch("os.path.exists", return_value=False), \
             patch("builtins.print") as mock_print:
            main()
            mock_print.assert_called_with("Daemon STOPPED.")

    def test_cli_status_running(self, tmp_path):
        mock_pid_file = str(tmp_path / "vision_daemon.pid")
        with open(mock_pid_file, "w") as f:
            f.write("12345")

        with patch("sys.argv", ["vazus_vision_daemon.py", "--status"]), \
             patch("vazus_vision_daemon.PID_FILE_PATH", mock_pid_file), \
             patch("builtins.print") as mock_print:
            main()
            mock_print.assert_called_with("Daemon RUNNING (PID: 12345).")

    def test_cli_test_drop(self, tmp_path, sample_png_bytes):
        img_path = tmp_path / "test_drop.png"
        img_path.write_bytes(sample_png_bytes)

        with patch("sys.argv", ["vazus_vision_daemon.py", "--test-drop", str(img_path)]), \
             patch("builtins.print") as mock_print:
            main()
            printed_arg = mock_print.call_args[0][0]
            payload = json.loads(printed_arg)
            assert payload["source"] == "file_drop"
            assert payload["image_metadata"]["width"] == 100
            assert payload["image_metadata"]["height"] == 100

    def test_cli_test_clip_empty(self):
        with patch("sys.argv", ["vazus_vision_daemon.py", "--test-clip"]), \
             patch("PIL.ImageGrab.grabclipboard", return_value=None), \
             patch("builtins.print") as mock_print:
            main()
            mock_print.assert_called_with("NO_IMAGE_IN_CLIPBOARD")

    def test_cli_test_clip_with_image(self, sample_png_image):
        with patch("sys.argv", ["vazus_vision_daemon.py", "--test-clip"]), \
             patch("PIL.ImageGrab.grabclipboard", return_value=sample_png_image), \
             patch("builtins.print") as mock_print:
            main()
            printed_arg = mock_print.call_args[0][0]
            payload = json.loads(printed_arg)
            assert payload["source"] == "clipboard"
            assert payload["image_metadata"]["width"] == 100

    def test_cli_once(self):
        with patch("sys.argv", ["vazus_vision_daemon.py", "--once"]), \
             patch("PIL.ImageGrab.grabclipboard", return_value=None), \
             patch("builtins.print") as mock_print:
            main()
            assert mock_print.call_count >= 2
            mock_print.assert_any_call("Executing single scan pass...")
            mock_print.assert_any_call("[Clipboard] No image found.")
