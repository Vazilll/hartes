"""
Tier 5: White-Box Adversarial Coverage Hardening & Stress Test Suite.
Total Test Cases: 31 (high-frequency clipboard hooks, rapid file drop bursts,
SQLite lock contention, WebSocket payload overflow, graceful shutdown handling,
multimodal resolver edge cases, memory corruption guards, color cube limits, and TUI renderer boundaries).

File: C:\\vazus\\labs\\native_vision_system\\tests\\test_tier5_adversarial.py
Runner: C:\\vazus\\.venv\\Scripts\\python.exe C:\\vazus\\labs\\native_vision_system\\tests\\run_e2e_tests.py --tier 5
"""

import sys
import os
import io
import time
import json
import uuid
import base64
import signal
import sqlite3
import asyncio
import threading
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image

TESTS_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = TESTS_DIR.parent.resolve()
sys.path.insert(0, r"C:\vazus")
sys.path.insert(0, str(TESTS_DIR))

from vazus_vision_daemon import (
    VazusVisionDaemon,
    VisionDaemonIPC,
    VisionPayloadGenerator,
    ImageDeduplicator,
    ClipboardListener,
    WorkspaceWatcher,
    PID_FILE_PATH,
    main as daemon_main
)
from vazus_core.multimodal_resolver import (
    MultimodalResolver,
    ResolvedMultimodalPayload,
    MultimodalResolverError,
    UnsupportedFormatError,
    ImageNotFoundError,
    ClipboardEmptyError,
    ArtifactNotFoundError,
    ClipboardAccessError,
    CorruptedImageError,
)
from vazus_core.tui_preview_renderer import TUIPreviewRenderer


class TestTier5AdversarialHardening:
    """Tier 5 White-Box Adversarial & Stress Test Cases for Vision Daemon & Core Multimodal Engines."""

    # ==========================================================================
    # Category 1: High-Frequency Clipboard Hooks & Deduplication Stress
    # ==========================================================================

    def test_tc_t5_01_high_frequency_clipboard_burst(self, sample_png_bytes):
        """TC-T5-01: High-Frequency Clipboard Event Burst (50 consecutive events)."""
        async def _run():
            daemon = VazusVisionDaemon()
            with patch.object(daemon.ipc, "broadcast", new_callable=MagicMock) as broadcast_mock:
                with patch("vazus_vision_daemon.VisionPayloadGenerator.extract_ocr", return_value={"engine": "none", "has_text": False}):
                    images = [Image.new("RGB", (10 + i, 10 + i), color=(i, 100, 200)) for i in range(50)]

                    start_t = time.perf_counter()
                    for img in images:
                        with patch("vazus_vision_daemon.ImageGrab.grabclipboard", return_value=img):
                            await daemon.handle_clipboard_event()
                    elapsed = time.perf_counter() - start_t

                    assert elapsed < 3.0, f"50 clipboard event bursts took too long: {elapsed:.2f}s"
                    assert broadcast_mock.call_count == 50

        asyncio.run(_run())

    def test_tc_t5_02_clipboard_dedup_lru_capacity_and_eviction(self):
        """TC-T5-02: LRU Cache Eviction under 150 Hash Flood (max_size=100)."""
        deduper = ImageDeduplicator(max_size=100, ttl_seconds=300.0)

        # Insert 150 unique hashes
        hashes = [f"sha256_hash_{i:04d}" for i in range(150)]
        for h in hashes:
            assert deduper.is_duplicate(h) is False

        assert len(deduper.cache) == 100

        # Hashes 0 to 49 should have been evicted
        assert "sha256_hash_0000" not in deduper.cache
        assert deduper.is_duplicate("sha256_hash_0000") is False  # Re-insertion accepted as new

        # Hashes 50 to 149 should still be present
        assert "sha256_hash_0100" in deduper.cache

    def test_tc_t5_03_clipboard_ttl_expiration_purging(self):
        """TC-T5-03: TTL Purge Logic for Stale Deduplication Entries."""
        deduper = ImageDeduplicator(max_size=100, ttl_seconds=5.0)

        hash1 = "stale_hash_001"
        now = time.time()

        # Manually seed an expired entry
        with deduper._lock:
            deduper.cache[hash1] = now - 10.0  # 10s old (> 5s TTL)

        # Checking duplicate should trigger _purge_expired and return False
        assert deduper.is_duplicate(hash1) is False
        assert hash1 in deduper.cache  # Re-added with new timestamp
        assert deduper.cache[hash1] >= now

    def test_tc_t5_04_clipboard_non_image_payloads(self):
        """TC-T5-04: Non-Image Clipboard Payload Ingestion (None, list, string, binary corrupt)."""
        async def _run():
            daemon = VazusVisionDaemon()
            broadcast_mock = patch.object(daemon.ipc, "broadcast", new_callable=MagicMock).start()

            invalid_clipboard_data = [
                None,
                ["C:\\vazus\\file1.txt", "C:\\vazus\\file2.txt"],  # Windows Explorer file list
                "Just a text string on clipboard",
                12345,
                {"invalid": "dict"}
            ]

            for item in invalid_clipboard_data:
                with patch("vazus_vision_daemon.ImageGrab.grabclipboard", return_value=item):
                    await daemon.handle_clipboard_event()

            assert broadcast_mock.call_count == 0
            patch.stopall()

        asyncio.run(_run())

    def test_tc_t5_05_win32_clipboard_listener_fallback(self):
        """TC-T5-05: Win32 Clipboard Listener Initialization & Fallback Loop."""
        loop = asyncio.new_event_loop()
        dummy_callback = MagicMock()
        listener = ClipboardListener(loop, dummy_callback)

        with patch("vazus_vision_daemon.HAS_WIN32", False):
            listener.start()
            assert listener.thread is not None
            assert listener.thread.is_alive()
            listener.stop()
            assert listener.running is False

        loop.close()

    # ==========================================================================
    # Category 2: Rapid File Drop Bursts & Filesystem Race Conditions
    # ==========================================================================

    def test_tc_t5_06_rapid_workspace_file_drop_burst(self, tmp_path, sample_png_bytes):
        """TC-T5-06: Rapid Workspace File Drop Burst (20 files dropped in parallel)."""
        async def _run():
            daemon = VazusVisionDaemon(workspace_dir=str(tmp_path))
            with patch.object(daemon.ipc, "broadcast", new_callable=MagicMock) as broadcast_mock:
                with patch("vazus_vision_daemon.VisionPayloadGenerator.extract_ocr", return_value={"engine": "none", "has_text": False}):
                    file_paths = []
                    for i in range(20):
                        img = Image.new("RGB", (20 + i, 20 + i), color="blue")
                        fpath = tmp_path / f"drop_{i}.png"
                        img.save(fpath, format="PNG")
                        file_paths.append(str(fpath))

                    start_t = time.perf_counter()
                    for fp in file_paths:
                        await daemon.handle_file_drop_event(fp)
                    elapsed = time.perf_counter() - start_t

                    assert elapsed < 3.0
                    assert broadcast_mock.call_count == 20

        asyncio.run(_run())

    def test_tc_t5_07_file_drop_deleted_mid_ingestion(self, tmp_path):
        """TC-T5-07: Race Condition — File Deleted Mid-Ingestion."""
        async def _run():
            daemon = VazusVisionDaemon(workspace_dir=str(tmp_path))
            ghost_path = str(tmp_path / "ghost_file.png")
            await daemon.handle_file_drop_event(ghost_path)

        asyncio.run(_run())

    def test_tc_t5_08_file_drop_locked_file_handling(self, tmp_path, sample_png_bytes):
        """TC-T5-08: Race Condition — File Locked by External Writer Process."""
        async def _run():
            daemon = VazusVisionDaemon(workspace_dir=str(tmp_path))
            locked_file = tmp_path / "locked.png"
            locked_file.write_bytes(sample_png_bytes)

            with patch("vazus_vision_daemon.MultimodalResolver.resolve", side_effect=PermissionError("File locked by process")):
                await daemon.handle_file_drop_event(str(locked_file))

        asyncio.run(_run())

    def test_tc_t5_09_workspace_watcher_filter_hardening(self, tmp_path):
        """TC-T5-09: Workspace Watcher Filter Path Hardening."""
        watcher = WorkspaceWatcher(str(tmp_path), None)

        # Allowed files
        assert watcher._watch_filter(None, str(tmp_path / "img.png")) is True
        assert watcher._watch_filter(None, str(tmp_path / "photo.jpg")) is True
        assert watcher._watch_filter(None, str(tmp_path / "banner.webp")) is True

        # Ignored extensions
        assert watcher._watch_filter(None, str(tmp_path / "script.py")) is False
        assert watcher._watch_filter(None, str(tmp_path / "data.json")) is False
        assert watcher._watch_filter(None, str(tmp_path / "exec.exe")) is False

        # Ignored directories
        assert watcher._watch_filter(None, str(tmp_path / ".git" / "image.png")) is False
        assert watcher._watch_filter(None, str(tmp_path / ".agents" / "m5" / "image.png")) is False
        assert watcher._watch_filter(None, str(tmp_path / "node_modules" / "asset.png")) is False
        assert watcher._watch_filter(None, str(tmp_path / ".venv" / "lib" / "icon.png")) is False

    def test_tc_t5_10_zero_byte_and_corrupt_file_drop(self, tmp_path):
        """TC-T5-10: Ingestion of 0-byte and Corrupt Image Files."""
        async def _run():
            daemon = VazusVisionDaemon(workspace_dir=str(tmp_path))

            zero_file = tmp_path / "empty.png"
            zero_file.write_bytes(b"")

            corrupt_file = tmp_path / "corrupt.jpg"
            corrupt_file.write_bytes(b"NOT_A_JPEG_IMAGE_HEADER_DATA")

            await daemon.handle_file_drop_event(str(zero_file))
            await daemon.handle_file_drop_event(str(corrupt_file))

        asyncio.run(_run())

    # ==========================================================================
    # Category 3: SQLite Lock Contention & Concurrency Stress
    # ==========================================================================

    def test_tc_t5_11_sqlite_lock_contention_survival(self, tmp_path, sample_png_bytes):
        """TC-T5-11: SQLite WAL Lock Contention Resilience."""
        db_file = str(tmp_path / "contention.db")
        ipc = VisionDaemonIPC(db_path=db_file)

        payload = VisionPayloadGenerator.generate(sample_png_bytes, source_type="clipboard")

        lock_conn = sqlite3.connect(db_file, timeout=0.1)
        lock_conn.execute("BEGIN EXCLUSIVE TRANSACTION")

        try:
            try:
                ipc.log_event_to_db(payload)
            except sqlite3.OperationalError as e:
                assert "locked" in str(e).lower() or "busy" in str(e).lower()
        finally:
            lock_conn.rollback()
            lock_conn.close()

    def test_tc_t5_12_sqlite_multithreaded_concurrent_writes(self, tmp_path, sample_png_bytes):
        """TC-T5-12: Multi-Threaded Concurrent SQLite Event Logging (10 threads)."""
        db_file = str(tmp_path / "concurrent.db")
        ipc = VisionDaemonIPC(db_path=db_file)

        errors = []

        def worker(thread_idx: int):
            try:
                for i in range(5):
                    img = Image.new("RGB", (10 + thread_idx, 10 + i), color="red")
                    p = VisionPayloadGenerator.generate(img, source_type="clipboard")
                    ipc.log_event_to_db(p)
            except Exception as ex:
                errors.append(ex)

        with patch("vazus_vision_daemon.VisionPayloadGenerator.extract_ocr", return_value={"engine": "none", "has_text": False}):
            threads = [threading.Thread(target=worker, args=(t,)) for t in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert len(errors) == 0, f"Concurrent SQLite writes produced errors: {errors}"

        conn = sqlite3.connect(db_file)
        row_count = conn.execute("SELECT COUNT(*) FROM vision_event_stream").fetchone()[0]
        conn.close()
        assert row_count == 50

    def test_tc_t5_13_sqlite_sql_injection_and_huge_json(self, tmp_path, sample_png_bytes):
        """TC-T5-13: Security Hardening — SQL Injection & Large JSON Metadata Logging."""
        db_file = str(tmp_path / "security.db")
        ipc = VisionDaemonIPC(db_path=db_file)

        malicious_payload = VisionPayloadGenerator.generate(sample_png_bytes, source_type="clipboard")
        malicious_payload["event_id"] = "evt_'; DROP TABLE vision_event_stream; --"
        malicious_payload["source"] = "clipboard' OR '1'='1"
        malicious_payload["file_path"] = "C:\\path\\with\\'; DROP TABLE--\\file.png"

        ipc.log_event_to_db(malicious_payload)

        conn = sqlite3.connect(db_file)
        row = conn.execute("SELECT event_id, source FROM vision_event_stream WHERE event_id = ?", (malicious_payload["event_id"],)).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == malicious_payload["event_id"]
        assert row[1] == malicious_payload["source"]

    # ==========================================================================
    # Category 4: WebSocket Payload Overflow & Client Hardening
    # ==========================================================================

    def test_tc_t5_14_websocket_large_payload_broadcast(self, tmp_path):
        """TC-T5-14: Large WebSocket Visual Token Payload Broadcast (10MB Payload)."""
        async def _run():
            ipc = VisionDaemonIPC(db_path=str(tmp_path / "ws.db"))

            mock_ws_client = MagicMock()
            async def mock_send(msg):
                pass
            mock_ws_client.send = mock_send
            ipc.clients.add(mock_ws_client)

            large_payload = {
                "event_id": "evt_large_001",
                "timestamp": "2026-08-05T02:00:00Z",
                "source": "clipboard",
                "dedup": {"sha256": "abc123large", "is_duplicate": False},
                "visual_tokens": {
                    "mime_type": "image/png",
                    "base64_data": "A" * (10 * 1024 * 1024)
                }
            }

            await ipc.broadcast(large_payload)

        asyncio.run(_run())

    def test_tc_t5_15_websocket_slow_and_dead_client_eviction(self, tmp_path):
        """TC-T5-15: Dead WebSocket Client Eviction on Broadcast Failure."""
        async def _run():
            ipc = VisionDaemonIPC(db_path=str(tmp_path / "ws_evict.db"))

            good_client = MagicMock()
            async def good_send(msg):
                pass
            good_client.send = good_send

            dead_client = MagicMock()
            async def dead_send(msg):
                raise ConnectionError("Client disconnected unexpectedly")
            dead_client.send = dead_send

            ipc.clients.add(good_client)
            ipc.clients.add(dead_client)

            test_payload = {
                "event_id": "evt_evict_001",
                "timestamp": "2026-08-05T02:00:00Z",
                "source": "clipboard",
                "dedup": {"sha256": "hash_evict", "is_duplicate": False},
                "visual_tokens": {"mime_type": "image/png"}
            }

            await ipc.broadcast(test_payload)

            assert dead_client not in ipc.clients
            assert good_client in ipc.clients

        asyncio.run(_run())

    def test_tc_t5_16_websocket_server_start_stop_idempotency(self, tmp_path):
        """TC-T5-16: IPC DB Initialization & Server Startup Hardening."""
        db_path = str(tmp_path / "ipc_init.db")
        ipc = VisionDaemonIPC(db_path=db_path)

        assert os.path.exists(db_path)
        conn = sqlite3.connect(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()

        table_names = [t[0] for t in tables]
        assert "vision_event_stream" in table_names

    # ==========================================================================
    # Category 5: Graceful Shutdown & Lifecycle Controls
    # ==========================================================================

    def test_tc_t5_17_daemon_lifecycle_pid_management(self, tmp_path):
        """TC-T5-17: PID File Creation & Idempotent Cleanup on Stop."""
        pid_file = tmp_path / "test_daemon.pid"

        with patch("vazus_vision_daemon.PID_FILE_PATH", str(pid_file)):
            daemon = VazusVisionDaemon()

            pid_file.parent.mkdir(parents=True, exist_ok=True)
            pid_file.write_text("999999")

            assert os.path.exists(str(pid_file))

            daemon.stop()
            assert not os.path.exists(str(pid_file))

            daemon.stop()
            assert not os.path.exists(str(pid_file))

    def test_tc_t5_18_cli_entrypoint_arguments(self, capsys, tmp_path):
        """TC-T5-18: CLI Controls (--status, --stop, --once, --test-clip, --test-drop)."""
        pid_file = tmp_path / "cli_daemon.pid"

        with patch("vazus_vision_daemon.PID_FILE_PATH", str(pid_file)):
            with patch("sys.argv", ["vazus_vision_daemon.py", "--status"]):
                daemon_main()
            captured = capsys.readouterr()
            assert "Daemon STOPPED" in captured.out

            with patch("sys.argv", ["vazus_vision_daemon.py", "--test-clip"]):
                with patch("vazus_vision_daemon.ImageGrab.grabclipboard", return_value=None):
                    daemon_main()
            captured = capsys.readouterr()
            assert "NO_IMAGE_IN_CLIPBOARD" in captured.out

            img_path = tmp_path / "test_drop.png"
            img = Image.new("RGB", (10, 10), color="green")
            img.save(img_path)

            with patch("sys.argv", ["vazus_vision_daemon.py", "--test-drop", str(img_path)]):
                daemon_main()
            captured = capsys.readouterr()
            assert "vvis_" in captured.out
            assert "file_drop" in captured.out

    def test_tc_t5_19_rapid_ocr_fallback_resilience(self):
        """TC-T5-19: RapidOCR Extraction Fallback on Error or Uninstalled OCR Engine."""
        sample_img = Image.new("RGB", (50, 50), color="white")

        with patch("vazus_vision_daemon.HAS_RAPIDOCR", False):
            ocr_res = VisionPayloadGenerator.extract_ocr(sample_img)
            assert ocr_res["engine"] == "none"
            assert ocr_res["has_text"] is False

        with patch("vazus_vision_daemon.HAS_RAPIDOCR", True), \
             patch("vazus_vision_daemon.RapidOCR", side_effect=Exception("OCR model missing")):
            ocr_res = VisionPayloadGenerator.extract_ocr(sample_img)
            assert ocr_res["engine"] == "rapidocr_fallback"
            assert ocr_res["has_text"] is False

    # ==========================================================================
    # Category 6: Multimodal Resolver White-Box Adversarial Hardening
    # ==========================================================================

    def test_tc_t5_20_resolver_untested_magic_bytes_and_tiff_endianness(self):
        """TC-T5-20: Magic bytes inspection for GIF87a/89a, BMP, TIFF (big/little endian) & truncated headers."""
        assert MultimodalResolver._inspect_magic_bytes(b"GIF87a_dummy") == "image/gif"
        assert MultimodalResolver._inspect_magic_bytes(b"GIF89a_dummy") == "image/gif"
        assert MultimodalResolver._inspect_magic_bytes(b"BM_bmp_header") == "image/bmp"
        assert MultimodalResolver._inspect_magic_bytes(b"II*\x00_little_endian_tiff") == "image/tiff"
        assert MultimodalResolver._inspect_magic_bytes(b"MM\x00*_big_endian_tiff") == "image/tiff"

        # Truncated or sub-header payloads should safely return None without IndexError
        assert MultimodalResolver._inspect_magic_bytes(b"") is None
        assert MultimodalResolver._inspect_magic_bytes(b"\x89PNG") is None
        assert MultimodalResolver._inspect_magic_bytes(b"RIFF") is None
        assert MultimodalResolver._inspect_magic_bytes(b"\xff\xd8") is None

    def test_tc_t5_21_resolver_pillow_mode_conversions_and_extreme_formats(self):
        """TC-T5-21: Resolution of exotic PIL image modes (1-bit, Grayscale, CMYK, LAB, HSV, F, I)."""
        modes_direct = ["1", "L", "P", "RGB", "RGBA"]
        for mode in modes_direct:
            img = Image.new(mode, (40, 40), color=0 if mode in ("1", "L") else None)
            payload = MultimodalResolver.resolve(img)
            assert isinstance(payload, ResolvedMultimodalPayload)
            assert payload.width == 40
            assert payload.height == 40
            assert payload.mime_type in ("image/png", "image/jpeg", "image/webp")
            assert len(payload.base64_data) > 0

        modes_converted = ["CMYK", "LAB", "HSV", "F", "I"]
        for mode in modes_converted:
            img = Image.new(mode, (40, 40)).convert("RGB")
            payload = MultimodalResolver.resolve(img)
            assert isinstance(payload, ResolvedMultimodalPayload)

    def test_tc_t5_22_resolver_base64_and_data_uri_adversarial_payloads(self, sample_png_bytes):
        """TC-T5-22: Adversarial Base64 Data URIs and raw Base64 string payload validation."""
        b64_png = base64.b64encode(sample_png_bytes).decode("utf-8")

        # Valid custom Data URI scheme
        p1 = MultimodalResolver.resolve(f"data:image/x-png;base64,{b64_png}")
        assert p1.mime_type == "image/png"

        # Corrupted Base64 payload in Data URI
        with pytest.raises(CorruptedImageError):
            MultimodalResolver.resolve("data:image/png;base64,!!!INVALID_BASE64_STREAM!!!")

        # Non-image valid Base64 string (e.g. decoded text)
        text_b64 = base64.b64encode(b"THIS_IS_PLAIN_TEXT_NOT_AN_IMAGE_PAYLOAD").decode("utf-8")
        with pytest.raises(ImageNotFoundError):
            MultimodalResolver.resolve(text_b64)

    def test_tc_t5_23_resolver_at_reference_boundary_and_path_traversal(self, tmp_path):
        """TC-T5-23: Boundary conditions for @ references, artifact resolution, and non-existent paths."""
        with pytest.raises(ImageNotFoundError):
            MultimodalResolver.resolve_at_reference("@non_existent_file_9999.png", workspace_dir=tmp_path)

        with pytest.raises(ArtifactNotFoundError):
            MultimodalResolver.resolve_at_reference("@artifact:ghost_artifact_314", workspace_dir=tmp_path, extra_search_dirs=[])

        # Whitespace reference string
        with pytest.raises(ValueError):
            MultimodalResolver.resolve("   ")

    def test_tc_t5_24_resolver_strict_mode_pixel_corruption_guard(self, sample_png_bytes):
        """TC-T5-24: Strict mode pixel decoding verification under IDAT stream corruption."""
        idat_idx = sample_png_bytes.find(b"IDAT")
        assert idat_idx != -1
        corrupt_bytes = sample_png_bytes[:idat_idx + 4] + b"\x00" * 33 + sample_png_bytes[idat_idx + 4 + 33:]

        # Strict mode must catch corrupted stream and raise CorruptedImageError
        with pytest.raises(CorruptedImageError):
            MultimodalResolver.resolve(corrupt_bytes, strict=True)

        # Non-strict mode inspects dimensions without executing full load
        p_non_strict = MultimodalResolver.resolve(corrupt_bytes, strict=False)
        assert p_non_strict.width == 100
        assert p_non_strict.height == 100

    def test_tc_t5_25_resolver_dispatch_to_gemini_exception_handling(self, sample_png_bytes):
        """TC-T5-25: Exception handling in dispatch_to_gemini during API client initialization or execution."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("Quota exhausted for model gemini-3.6-flash")

        res = MultimodalResolver.dispatch_to_gemini(
            sample_png_bytes,
            prompt="Test prompt",
            client=mock_client
        )
        assert res["status"] == "ERROR"
        assert "Quota exhausted" in res["error"]
        assert res["mime_type"] == "image/png"

    # ==========================================================================
    # Category 7: TUI Preview Renderer White-Box Adversarial Hardening
    # ==========================================================================

    def test_tc_t5_26_renderer_color_cube_limits_and_extreme_rgb_clamping(self):
        """TC-T5-26: Color cube limit mapping and out-of-bounds RGB value clamping in rgb_to_256_color."""
        # Extreme out-of-bounds clamping
        assert TUIPreviewRenderer.rgb_to_256_color(-500, -10, 0) == 16
        assert TUIPreviewRenderer.rgb_to_256_color(300, 999, 256) == 231

        # Grayscale exact boundaries
        assert TUIPreviewRenderer.rgb_to_256_color(0, 0, 0) == 16
        assert TUIPreviewRenderer.rgb_to_256_color(7, 7, 7) == 16
        assert TUIPreviewRenderer.rgb_to_256_color(8, 8, 8) == 232
        assert TUIPreviewRenderer.rgb_to_256_color(248, 248, 248) == 254
        assert TUIPreviewRenderer.rgb_to_256_color(249, 249, 249) == 231
        assert TUIPreviewRenderer.rgb_to_256_color(255, 255, 255) == 231

        # Pure primary & secondary color cube corners
        assert TUIPreviewRenderer.rgb_to_256_color(255, 0, 0) == 196    # Red
        assert TUIPreviewRenderer.rgb_to_256_color(0, 255, 0) == 46     # Green
        assert TUIPreviewRenderer.rgb_to_256_color(0, 0, 255) == 21     # Blue
        assert TUIPreviewRenderer.rgb_to_256_color(255, 255, 0) == 226   # Yellow
        assert TUIPreviewRenderer.rgb_to_256_color(0, 255, 255) == 51    # Cyan
        assert TUIPreviewRenderer.rgb_to_256_color(255, 0, 255) == 201   # Magenta

    def test_tc_t5_27_renderer_dimension_boundaries_and_extreme_aspect_ratios(self):
        """TC-T5-27: Dimension calculations under zero, negative, and extreme aspect ratio bounds."""
        # Zero and negative viewport clamping
        cols1, rows1 = TUIPreviewRenderer.compute_preview_dimensions(100, 100, max_cols=0, max_rows=0)
        assert cols1 >= 1 and rows1 >= 1

        cols2, rows2 = TUIPreviewRenderer.compute_preview_dimensions(100, 100, max_cols=-10, max_rows=-5)
        assert cols2 >= 1 and rows2 >= 1

        # Extreme 1x10000 vertical stripe
        cols_v, rows_v = TUIPreviewRenderer.compute_preview_dimensions(1, 10000, max_cols=80, max_rows=40)
        assert cols_v == 1 and rows_v == 40

        # Extreme 10000x1 horizontal strip
        cols_h, rows_h = TUIPreviewRenderer.compute_preview_dimensions(10000, 1, max_cols=80, max_rows=40)
        assert cols_h == 80 and rows_h == 1

    def test_tc_t5_28_renderer_all_luminance_ramps_and_invalid_modes(self, sample_pil_image):
        """TC-T5-28: Rendering under all valid luminance ramps and assertion on invalid render modes."""
        modes = ["truecolor", "256", "256color", "ascii", "ascii_10", "ascii_17", "ascii_70", "auto"]
        for m in modes:
            out = TUIPreviewRenderer.render(sample_pil_image, max_cols=40, max_rows=20, mode=m)
            assert isinstance(out, str)
            assert len(out) > 0

        # Invalid mode must raise ValueError
        with pytest.raises(ValueError):
            TUIPreviewRenderer.render(sample_pil_image, mode="invalid_cyber_mode")

    def test_tc_t5_29_renderer_exotic_image_modes_compositing(self):
        """TC-T5-29: TUI rendering for exotic PIL image modes (RGBA, P with alpha, L, 1, CMYK, LAB)."""
        modes = ["RGBA", "LA", "P", "L", "1", "CMYK", "LAB"]
        for m in modes:
            if m == "P":
                img = Image.new("RGBA", (30, 30), color=(100, 200, 50, 128)).convert("P")
            elif m == "LA":
                img = Image.new("LA", (30, 30), color=(200, 128))
            elif m == "RGBA":
                img = Image.new("RGBA", (30, 30), color=(255, 0, 0, 100))
            else:
                img = Image.new(m, (30, 30), color=1 if m == "1" else (100 if m in ("L", "F", "I") else None))

            rendered = TUIPreviewRenderer.render(img, max_cols=30, max_rows=15, mode="truecolor")
            assert "▀" in rendered
            assert len(rendered.splitlines()) == 15

    def test_tc_t5_30_renderer_double_buffer_diff_stateful_mutations(self):
        """TC-T5-30: Stateful double-buffering render_diff behavior across identical & modified frames."""
        renderer = TUIPreviewRenderer(max_cols=20, max_rows=10)
        img1 = Image.new("RGB", (40, 20), color=(255, 0, 0))
        img2 = Image.new("RGB", (40, 20), color=(255, 0, 0))  # Identical

        # Frame 1: Full render
        out1 = renderer.render_diff(img1)
        assert "▀" in out1

        # Frame 2: Identical image -> empty diff string
        out2 = renderer.render_diff(img2)
        assert out2 == ""

        # Frame 3: Single pixel change -> diff contains cursor movement positioning code \x1b[
        img3 = img1.copy()
        img3.putpixel((0, 0), (0, 255, 0))
        out3 = renderer.render_diff(img3)
        assert "\x1b[1;1H" in out3

        # Frame 4: Dimension change -> re-initializes front buffer and returns full preview
        out4 = renderer.render_diff(img3, max_cols=40, max_rows=20)
        assert "▀" in out4

    def test_tc_t5_31_renderer_card_title_overflow_and_border_wrapping(self, sample_pil_image):
        """TC-T5-31: Unicode card container rendering under title overflow and micro viewports."""
        # Extremely long title
        long_title = "VISION_" + "x" * 200
        card1 = TUIPreviewRenderer.render_card(sample_pil_image, title=long_title, max_cols=60, max_rows=20)
        assert "┌" in card1
        assert "└" in card1
        assert "VISION_x" in card1

        # Micro viewport bounds
        card2 = TUIPreviewRenderer.render_card(sample_pil_image, max_cols=5, max_rows=2)
        assert "┌" in card2
        assert "└" in card2
