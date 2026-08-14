"""
Tier 2: Boundary, Edge & Corner Cases Test Suite for Native Terminal Multimodal Vision System.
Total Test Cases: 30 (spanning 6 edge categories: Empty Inputs, Extreme Dimensions, Corrupt Bytes,
Malformed @ References, Viewport Extremes, and Rapid Event Stress).

File: C:\\vazus\\labs\\native_vision_system\\tests\\test_tier2_boundary.py
Runner: C:\\vazus\\.venv\\Scripts\\python.exe C:\\vazus\\labs\\native_vision_system\\tests\\run_e2e_tests.py --tier 2
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

from vazus_core.multimodal_resolver import (
    MultimodalResolver,
    ResolvedMultimodalPayload,
    MultimodalResolverError,
    UnsupportedFormatError,
    ImageNotFoundError,
    ClipboardEmptyError,
    ArtifactNotFoundError,
    ClipboardAccessError,
    CorruptedImageError
)

from test_helpers import TUIPreviewRenderer, VisionDaemonStub


# ============================================================================
# CATEGORY A: Empty Files & References (5 Test Cases)
# ============================================================================

class TestCategoryAEmptyInputs:

    def test_tc_t2_emp_01_zero_byte_disk_image_file(self, tmp_path):
        """TC-T2-EMP-01: 0-byte disk image file raises CorruptedImageError / ValueError."""
        empty_file = tmp_path / "empty.png"
        empty_file.write_bytes(b"")

        with pytest.raises((CorruptedImageError, ValueError)):
            MultimodalResolver.resolve(empty_file)

    def test_tc_t2_emp_02_empty_byte_array(self):
        """TC-T2-EMP-02: Empty byte array (b'') raises CorruptedImageError / ValueError."""
        with pytest.raises((CorruptedImageError, ValueError)):
            MultimodalResolver.resolve(b"")

    def test_tc_t2_emp_03_whitespace_or_empty_string_path(self):
        """TC-T2-EMP-03: Whitespace string path ('   ') raises ValueError."""
        with pytest.raises(ValueError):
            MultimodalResolver.resolve("   ")

    @patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard")
    def test_tc_t2_emp_04_clipboard_empty_resolution(self, mock_grab):
        """TC-T2-EMP-04: @clipboard resolution when Windows clipboard is empty."""
        mock_grab.return_value = None
        with pytest.raises(ClipboardEmptyError):
            MultimodalResolver.resolve("@clipboard")

    def test_tc_t2_emp_05_latest_reference_in_empty_workspace(self, tmp_path):
        """TC-T2-EMP-05: @latest reference in workspace directory containing zero images."""
        empty_dir = tmp_path / "empty_dir"
        empty_dir.mkdir()
        with pytest.raises(ImageNotFoundError):
            MultimodalResolver.resolve("@latest", workspace_dir=empty_dir, extra_search_dirs=[])


# ============================================================================
# CATEGORY B: Zero-Size & Extreme Dimensions (5 Test Cases)
# ============================================================================

class TestCategoryBExtremeDimensions:

    def test_tc_t2_dim_01_single_pixel_1x1_image(self):
        """TC-T2-DIM-01: 1x1 single pixel image resolution and rendering."""
        img = Image.new("RGB", (1, 1), color="red")
        payload = MultimodalResolver.resolve(img)
        assert payload.width == 1
        assert payload.height == 1
        ansi_str = TUIPreviewRenderer.render(payload, max_cols=5, max_rows=5)
        assert len(ansi_str) > 0

    def test_tc_t2_dim_02_zero_dimension_sanitization(self):
        """TC-T2-DIM-02: Zero dimension inputs sanitized to min safe grid 1x1."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(0, 0, max_cols=0, max_rows=0)
        assert cols >= 1
        assert rows >= 1

    def test_tc_t2_dim_03_ultrawide_10000x1_pixel_image(self):
        """TC-T2-DIM-03: Ultra-wide aspect ratio image (10000x1 px)."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(10000, 1, max_cols=80, max_rows=40)
        assert cols <= 80
        assert rows <= 40

    def test_tc_t2_dim_04_ultratall_1x10000_pixel_image(self):
        """TC-T2-DIM-04: Ultra-tall aspect ratio image (1x10000 px)."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(1, 10000, max_cols=80, max_rows=40)
        assert cols <= 80
        assert rows <= 40

    def test_tc_t2_dim_05_extreme_resolution_16k_image(self):
        """TC-T2-DIM-05: 4000x4000 high resolution image scaling without panic."""
        img = Image.new("RGB", (4000, 4000), color="blue")
        payload = MultimodalResolver.resolve(img)
        assert payload.width == 4000
        assert payload.height == 4000


# ============================================================================
# CATEGORY C: Corrupt Bytes & Partial Writes (5 Test Cases)
# ============================================================================

class TestCategoryCCorruptBytes:

    def test_tc_t2_cor_01_truncated_png_header(self, tmp_path):
        """TC-T2-COR-01: File with truncated 4-byte PNG header raises CorruptedImageError."""
        bad_file = tmp_path / "truncated.png"
        bad_file.write_bytes(b"\x89PNG")

        with pytest.raises((CorruptedImageError, UnsupportedFormatError, ValueError)):
            MultimodalResolver.resolve(bad_file)

    def test_tc_t2_cor_02_random_garbage_bytes(self, tmp_path):
        """TC-T2-COR-02: File containing random garbage bytes raises UnsupportedFormatError."""
        garbage_file = tmp_path / "garbage.png"
        garbage_file.write_bytes(os.urandom(1024))

        with pytest.raises((UnsupportedFormatError, CorruptedImageError, ValueError)):
            MultimodalResolver.resolve(garbage_file)

    def test_tc_t2_cor_03_unsupported_binary_payload(self):
        """TC-T2-COR-03: Raw invalid binary string raises UnsupportedFormatError."""
        with pytest.raises((UnsupportedFormatError, CorruptedImageError, ValueError)):
            MultimodalResolver.resolve(b"INVALID_NON_IMAGE_BINARY_PAYLOAD_STRING")

    def test_tc_t2_cor_04_mid_write_partial_file_handling(self, sample_png_bytes):
        """TC-T2-COR-04: Daemon queue processing partial write payloads cleanly."""
        daemon = VisionDaemonStub()
        payload = daemon.build_visual_token_payload("file_drop", sample_png_bytes[:20])
        assert payload["mime_type"] == "image/png"

    def test_tc_t2_cor_05_invalid_data_uri_string(self):
        """TC-T2-COR-05: Malformed Base64 Data URI raises CorruptedImageError."""
        with pytest.raises((CorruptedImageError, UnsupportedFormatError, ValueError)):
            MultimodalResolver.resolve("data:image/png;base64,INVALID_NOT_BASE64!@#$%^")


# ============================================================================
# CATEGORY D: Malformed & Non-Existent @ References (5 Test Cases)
# ============================================================================

class TestCategoryDMalformedAtReferences:

    def test_tc_t2_ref_01_unknown_at_reference_tag(self, tmp_path):
        """TC-T2-REF-01: Unknown @ reference tag raises ImageNotFoundError."""
        with pytest.raises(ImageNotFoundError):
            MultimodalResolver.resolve("@invalid_reference_tag_12345", workspace_dir=tmp_path)

    def test_tc_t2_ref_02_missing_brain_artifact(self, tmp_path):
        """TC-T2-REF-02: Non-existent artifact reference raises ArtifactNotFoundError."""
        with pytest.raises(ArtifactNotFoundError):
            MultimodalResolver.resolve("@artifact:nonexistent_mockup_chart", workspace_dir=tmp_path, extra_search_dirs=[])

    def test_tc_t2_ref_03_non_existent_file_path(self):
        """TC-T2-REF-03: Non-existent disk file path raises ImageNotFoundError or FileNotFoundError."""
        with pytest.raises((ImageNotFoundError, FileNotFoundError, ValueError)):
            MultimodalResolver.resolve(r"C:\non_existent_path_vision_system_12345.png")

    @patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard")
    def test_tc_t2_ref_04_clipboard_locked_by_os(self, mock_grab):
        """TC-T2-REF-04: Windows clipboard locked by external process raises ClipboardAccessError."""
        mock_grab.side_effect = OSError("Clipboard locked by another Win32 handle")
        with pytest.raises(ClipboardAccessError):
            MultimodalResolver.resolve("@clip")

    def test_tc_t2_ref_05_unsupported_input_type(self):
        """TC-T2-REF-05: Unsupported integer source type raises TypeError."""
        with pytest.raises(TypeError):
            MultimodalResolver.resolve(987654321)


# ============================================================================
# CATEGORY E: Terminal Viewport Boundaries (5 Test Cases)
# ============================================================================

class TestCategoryETerminalViewportBoundaries:

    def test_tc_t2_vwp_01_micro_viewport_1x1_cell(self, sample_png_bytes):
        """TC-T2-VWP-01: Render preview into 1x1 micro viewport."""
        ansi_str = TUIPreviewRenderer.render(sample_png_bytes, max_cols=1, max_rows=1)
        assert len(ansi_str) > 0

    def test_tc_t2_vwp_02_zero_viewport_clamp(self, sample_png_bytes):
        """TC-T2-VWP-02: Zero viewport max_cols=0, max_rows=0 sanitized."""
        ansi_str = TUIPreviewRenderer.render(sample_png_bytes, max_cols=0, max_rows=0)
        assert len(ansi_str) > 0

    def test_tc_t2_vwp_03_ultrawide_viewport_500x20(self, sample_png_bytes):
        """TC-T2-VWP-03: Ultra-wide terminal viewport (500x20 cells)."""
        ansi_str = TUIPreviewRenderer.render(sample_png_bytes, max_cols=500, max_rows=20)
        assert len(ansi_str.splitlines()) <= 20

    def test_tc_t2_vwp_04_ultratall_viewport_20x500(self, sample_png_bytes):
        """TC-T2-VWP-04: Ultra-tall terminal viewport (20x500 cells)."""
        ansi_str = TUIPreviewRenderer.render(sample_png_bytes, max_cols=20, max_rows=500)
        assert len(ansi_str.splitlines()) <= 500

    def test_tc_t2_vwp_05_negative_viewport_parameters(self, sample_png_bytes):
        """TC-T2-VWP-05: Negative viewport bounds max_cols=-10, max_rows=-5 sanitized."""
        ansi_str = TUIPreviewRenderer.render(sample_png_bytes, max_cols=-10, max_rows=-5)
        assert len(ansi_str) > 0


# ============================================================================
# CATEGORY F: Rapid Clipboard & Concurrent IPC Stress (5 Test Cases)
# ============================================================================

class TestCategoryFRapidEventStress:

    def test_tc_t2_str_01_rapid_payload_generation_burst(self, sample_png_bytes):
        """TC-T2-STR-01: Rapid payload generation burst (20 iterations)."""
        daemon = VisionDaemonStub()
        for i in range(20):
            p = daemon.build_visual_token_payload("clipboard", sample_png_bytes)
            assert "event_id" in p

    def test_tc_t2_str_02_interleaved_mime_payload_burst(self, sample_png_bytes, sample_jpeg_bytes, sample_webp_bytes):
        """TC-T2-STR-02: Interleaved PNG -> JPEG -> WEBP payload burst."""
        daemon = VisionDaemonStub()
        p1 = daemon.build_visual_token_payload("file_drop", sample_png_bytes)
        p2 = daemon.build_visual_token_payload("file_drop", sample_jpeg_bytes)
        p3 = daemon.build_visual_token_payload("file_drop", sample_webp_bytes)

        assert p1["mime_type"] == "image/png"
        assert p2["mime_type"] == "image/jpeg"
        assert p3["mime_type"] == "image/webp"

    def test_tc_t2_str_03_duplicate_sha256_suppression_stress(self, sample_png_bytes):
        """TC-T2-STR-03: Rapid identical payload duplicate suppression."""
        daemon = VisionDaemonStub()
        first = daemon.build_visual_token_payload("clipboard", sample_png_bytes)
        assert first["dedup"]["is_duplicate"] is False
        for _ in range(10):
            nxt = daemon.build_visual_token_payload("clipboard", sample_png_bytes)
            assert nxt["dedup"]["is_duplicate"] is True

    def test_tc_t2_str_04_sqlite_wal_write_stress(self, tmp_path, sample_png_bytes):
        """TC-T2-STR-04: SQLite WAL table multiple rapid insertions."""
        test_db = str(tmp_path / "stress_vazus.db")
        daemon = VisionDaemonStub(str(tmp_path))
        for i in range(10):
            p = daemon.build_visual_token_payload("file_drop", sample_png_bytes)
            p["event_id"] = f"vvis_stress_{i}"
            daemon.record_to_sqlite(p, db_file=test_db)

        conn = sqlite3.connect(test_db)
        count = conn.execute("SELECT COUNT(*) FROM vision_event_stream").fetchone()[0]
        conn.close()
        assert count == 10

    def test_tc_t2_str_05_concurrent_instance_isolation(self, sample_png_bytes):
        """TC-T2-STR-05: Concurrent daemon instance state isolation."""
        d1 = VisionDaemonStub(r"C:\dir1")
        d2 = VisionDaemonStub(r"C:\dir2")

        p1 = d1.build_visual_token_payload("clipboard", sample_png_bytes)
        p2 = d2.build_visual_token_payload("clipboard", sample_png_bytes)

        assert p1["dedup"]["is_duplicate"] is False
        assert p2["dedup"]["is_duplicate"] is False
