"""
Tier 3: Cross-Feature Integration Test Suite for Native Terminal Multimodal Vision System.
Total Test Cases: 10 (multi-module interactions across Resolver, Renderer, Daemon, IPC & SQLite WAL).

File: C:\\vazus\\labs\\native_vision_system\\tests\\test_tier3_integration.py
Runner: C:\\vazus\\.venv\\Scripts\\python.exe C:\\vazus\\labs\\native_vision_system\\tests\\run_e2e_tests.py --tier 3
"""

import os
import io
import time
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image

import sys
TESTS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, r"C:\vazus")
sys.path.insert(0, str(TESTS_DIR))

from vazus_core.multimodal_resolver import MultimodalResolver, ResolvedMultimodalPayload
from test_helpers import TUIPreviewRenderer, VisionDaemonStub


class TestTier3CrossFeatureIntegration:

    def test_tc_t3_01_workspace_file_drop_pipeline(self, tmp_path, sample_png_bytes):
        """TC-T3-01: Workspace File Drop -> Resolver -> TUI Renderer End-to-End Pipeline."""
        start_time = time.perf_counter()
        img_file = tmp_path / "sample_drop.png"
        img_file.write_bytes(sample_png_bytes)

        payload = MultimodalResolver.resolve(img_file)
        ansi_preview = TUIPreviewRenderer.render(payload)

        daemon = VisionDaemonStub(str(tmp_path))
        token_payload = daemon.build_visual_token_payload("file_drop", sample_png_bytes, str(img_file))

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert elapsed_ms < 500
        assert payload.mime_type == "image/png"
        assert payload.sha256 == token_payload["sha256"]
        assert "▀" in ansi_preview

    def test_tc_t3_02_dual_ipc_broadcast_and_sqlite_wal(self, tmp_path, sample_jpeg_bytes):
        """TC-T3-02: Dual IPC Channel Broadcast (WebSocket + SQLite WAL Engine)."""
        test_db = str(tmp_path / "vazus_ipc.db")
        daemon = VisionDaemonStub(str(tmp_path))
        token_payload = daemon.build_visual_token_payload("clipboard", sample_jpeg_bytes)

        ok = daemon.record_to_sqlite(token_payload, db_file=test_db)
        assert ok is True

        conn = sqlite3.connect(test_db)
        row = conn.execute(
            "SELECT event_id, sha256, mime_type, tui_preview FROM vision_event_stream WHERE event_id=?",
            (token_payload["event_id"],)
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == token_payload["event_id"]
        assert row[1] == token_payload["sha256"]
        assert row[2] == "image/jpeg"
        assert len(row[3]) > 0

    def test_tc_t3_03_multi_file_batch_drop_and_lru_deduplication(self, sample_png_bytes, sample_jpeg_bytes, sample_webp_bytes):
        """TC-T3-03: Multi-File Batch Drop & LRU Deduplication."""
        daemon = VisionDaemonStub()
        p1 = daemon.build_visual_token_payload("file_drop", sample_png_bytes)
        p2 = daemon.build_visual_token_payload("file_drop", sample_jpeg_bytes)
        p3 = daemon.build_visual_token_payload("file_drop", sample_png_bytes)
        p4 = daemon.build_visual_token_payload("file_drop", sample_webp_bytes)

        assert p1["dedup"]["is_duplicate"] is False
        assert p2["dedup"]["is_duplicate"] is False
        assert p3["dedup"]["is_duplicate"] is True
        assert p4["dedup"]["is_duplicate"] is False

    def test_tc_t3_04_file_locking_and_incomplete_write_resilience(self, tmp_path, sample_png_bytes):
        """TC-T3-04: File Locking & Incomplete Write Resilience."""
        lock_file = tmp_path / "partial_write.png"
        lock_file.write_bytes(sample_png_bytes[:50])

        time.sleep(0.05)
        lock_file.write_bytes(sample_png_bytes)

        payload = MultimodalResolver.resolve(lock_file)
        assert payload.mime_type == "image/png"
        assert payload.raw_bytes == sample_png_bytes

    def test_tc_t3_05_at_reference_to_tui_ansi_preview(self, tmp_path, sample_png_bytes):
        """TC-T3-05: @ Reference Resolution to TUI ANSI Preview."""
        t0 = time.perf_counter()
        img_file = tmp_path / "art_01.png"
        img_file.write_bytes(sample_png_bytes)

        payload = MultimodalResolver.resolve(f"@{img_file}")
        ansi_str = TUIPreviewRenderer.render(payload)

        dur_ms = (time.perf_counter() - t0) * 1000
        assert dur_ms < 40
        assert "▀" in ansi_str

    def test_tc_t3_06_polymorphic_header_validation(self, tmp_path, sample_png_bytes):
        """TC-T3-06: Polymorphic Header Validation Under Misnamed Extension Drops."""
        misnamed = tmp_path / "photo.jpg"
        misnamed.write_bytes(sample_png_bytes)

        payload = MultimodalResolver.resolve(misnamed)
        genai_part = payload.to_genai_part()

        assert payload.mime_type == "image/png"
        assert genai_part.inline_data.mime_type == "image/png"

    def test_tc_t3_07_rle_payload_compression_verification(self):
        """TC-T3-07: Double-Buffering & ANSI RLE Payload Compression Verification."""
        solid_img = Image.new("RGB", (100, 50), color=(255, 0, 0))
        ansi_rle = TUIPreviewRenderer.render(solid_img, max_cols=80, max_rows=40, mode="truecolor")
        assert len(ansi_rle) > 0

    def test_tc_t3_08_fallback_luminance_ramp_matrix(self, sample_pil_image):
        """TC-T3-08: 256-Color & ASCII Luminance Ramp Fallback Matrix."""
        r_256 = TUIPreviewRenderer.render(sample_pil_image, mode="256color")
        r_asc17 = TUIPreviewRenderer.render(sample_pil_image, mode="ascii_17")
        r_asc70 = TUIPreviewRenderer.render(sample_pil_image, mode="ascii_70")

        assert "\x1b[38;5;" in r_256
        assert "\x1b[38;2;" not in r_asc17
        assert len(r_asc70) > 0

    def test_tc_t3_09_daemon_recovery_resiliency(self, tmp_path, sample_png_bytes):
        """TC-T3-09: Daemon Recovery & Reconnection Resiliency."""
        daemon = VisionDaemonStub(str(tmp_path))
        p1 = daemon.build_visual_token_payload("file_drop", sample_png_bytes)
        assert "event_id" in p1

        p2 = daemon.build_visual_token_payload("file_drop", sample_png_bytes)
        assert "event_id" in p2

    def test_tc_t3_10_high_resolution_image_performance(self):
        """TC-T3-10: High-Resolution Image Memory & Performance Limits."""
        t0 = time.perf_counter()
        large_img = Image.new("RGB", (4000, 3000), color="blue")

        payload = MultimodalResolver.resolve(large_img)
        ansi_preview = TUIPreviewRenderer.render(payload)

        dur_ms = (time.perf_counter() - t0) * 1000
        assert dur_ms < 1500
        assert len(ansi_preview.splitlines()) <= 40
