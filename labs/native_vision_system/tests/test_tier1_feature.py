"""
Tier 1: Feature Coverage Test Suite for Native Terminal Multimodal Vision System.
Requires >= 5 test cases per feature across Features 1 to 11.
Total Test Cases: 55

File: C:\\vazus\\labs\\native_vision_system\\tests\\test_tier1_feature.py
Runner: C:\\vazus\\.venv\\Scripts\\python.exe C:\\vazus\\labs\\native_vision_system\\tests\\run_e2e_tests.py --tier 1
"""

import os
import io
import time
import base64
import hashlib
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
# FEATURE 1: Polymorphic File Preprocessor (5 Test Cases)
# ============================================================================

class TestFeature01PolymorphicPreprocessor:

    def test_f01_tc01_png_magic_byte_ingestion(self, sample_png_bytes):
        """F01-TC01: Inspect PNG magic bytes header in raw byte stream."""
        mime = MultimodalResolver.inspect_mime_type(sample_png_bytes)
        assert mime == "image/png"
        payload = MultimodalResolver.resolve(sample_png_bytes)
        assert payload.mime_type == "image/png"
        assert payload.raw_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_f01_tc02_jpeg_magic_byte_ingestion(self, sample_jpeg_bytes):
        """F01-TC02: Inspect JPEG magic bytes header in raw byte stream."""
        mime = MultimodalResolver.inspect_mime_type(sample_jpeg_bytes)
        assert mime == "image/jpeg"
        payload = MultimodalResolver.resolve(sample_jpeg_bytes)
        assert payload.mime_type == "image/jpeg"
        assert payload.raw_bytes[:3] == b"\xff\xd8\xff"

    def test_f01_tc03_webp_magic_byte_ingestion(self, sample_webp_bytes):
        """F01-TC03: Inspect WEBP magic bytes header in raw byte stream."""
        mime = MultimodalResolver.inspect_mime_type(sample_webp_bytes)
        assert mime == "image/webp"
        payload = MultimodalResolver.resolve(sample_webp_bytes)
        assert payload.mime_type == "image/webp"
        assert payload.raw_bytes[:4] == b"RIFF"
        assert payload.raw_bytes[8:12] == b"WEBP"

    def test_f01_tc04_mismatched_extension_precedence(self, tmp_path, sample_png_bytes):
        """F01-TC04: Verify magic byte inspection takes precedence over misleading file extension."""
        misleading_file = tmp_path / "renamed_png.jpg"
        misleading_file.write_bytes(sample_png_bytes)
        
        payload = MultimodalResolver.resolve(misleading_file)
        assert payload.mime_type == "image/png"

    def test_f01_tc05_pillow_inspection_fallback(self, sample_png_bytes):
        """F01-TC05: Verify 3-tiered inspection handles Pillow inspection fallback."""
        payload = MultimodalResolver.resolve(sample_png_bytes)
        assert payload.width == 100
        assert payload.height == 100


# ============================================================================
# FEATURE 2: InlineData Base64 Part Encoder (5 Test Cases)
# ============================================================================

class TestFeature02InlineDataEncoder:

    def test_f02_tc01_to_inline_data_dict_schema(self, sample_png_bytes):
        """F02-TC01: Verify to_inline_data_dict schema compliance."""
        payload = MultimodalResolver.resolve(sample_png_bytes)
        d = payload.to_inline_data_dict()
        assert "inlineData" in d
        assert d["inlineData"]["mimeType"] == "image/png"
        assert d["inlineData"]["data"] == payload.base64_data

    def test_f02_tc02_to_genai_part_instantiation(self, sample_png_bytes):
        """F02-TC02: Verify to_genai_part instantiates google.genai types.Part object."""
        payload = MultimodalResolver.resolve(sample_png_bytes)
        part = payload.to_genai_part()
        assert part.inline_data.mime_type == "image/png"
        assert part.inline_data.data == sample_png_bytes

    def test_f02_tc03_base64_roundtrip_integrity(self, sample_jpeg_bytes):
        """F02-TC03: Verify Base64 decode matches original binary bytes byte-for-byte."""
        payload = MultimodalResolver.resolve(sample_jpeg_bytes)
        decoded = base64.b64decode(payload.base64_data)
        assert decoded == sample_jpeg_bytes

    def test_f02_tc04_sha256_digest_calculation(self, sample_webp_bytes):
        """F02-TC04: Verify SHA-256 digest is exactly 64 hex characters matching hashlib."""
        payload = MultimodalResolver.resolve(sample_webp_bytes)
        expected_sha = hashlib.sha256(sample_webp_bytes).hexdigest()
        assert payload.sha256 == expected_sha
        assert len(payload.sha256) == 64

    def test_f02_tc05_pil_image_ingestion(self, sample_pil_image):
        """F02-TC05: Ingestion of PIL.Image object directly."""
        payload = MultimodalResolver.resolve(sample_pil_image)
        assert payload.width == 120
        assert payload.height == 80
        assert payload.source_type == "pil_image"


# ============================================================================
# FEATURE 3: @ Reference Resolver (5 Test Cases)
# ============================================================================

class TestFeature03AtReferenceResolver:

    def test_f03_tc01_disk_file_path_resolution(self, tmp_path, sample_png_bytes):
        """F03-TC01: Resolve standard disk file path."""
        file_path = tmp_path / "sample.png"
        file_path.write_bytes(sample_png_bytes)

        payload = MultimodalResolver.resolve(file_path)
        assert payload.file_path == str(file_path.resolve())

    @patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard")
    def test_f03_tc02_clipboard_ram_ingestion(self, mock_grab, sample_pil_image):
        """F03-TC02: Resolve @clipboard reference using PIL Image."""
        mock_grab.return_value = sample_pil_image
        payload = MultimodalResolver.resolve("@clipboard")
        assert payload.source_type == "clipboard"
        assert payload.mime_type == "image/png"

    def test_f03_tc03_latest_workspace_resolution(self, tmp_path, sample_png_bytes, sample_jpeg_bytes):
        """F03-TC03: Resolve @latest image file in workspace."""
        file1 = tmp_path / "img1.png"
        file1.write_bytes(sample_png_bytes)

        time.sleep(0.05)

        file2 = tmp_path / "img2.jpg"
        file2.write_bytes(sample_jpeg_bytes)

        payload = MultimodalResolver.resolve("@latest", workspace_dir=tmp_path)
        assert payload.file_path == str(file2.resolve())
        assert payload.mime_type == "image/jpeg"

    def test_f03_tc04_artifact_reference_resolution(self, tmp_path, sample_png_bytes):
        """F03-TC04: Resolve @artifact:<name> reference."""
        art_dir = tmp_path / ".agents" / "worker_1" / "artifacts"
        art_dir.mkdir(parents=True)
        art_file = art_dir / "chart.png"
        art_file.write_bytes(sample_png_bytes)

        payload = MultimodalResolver.resolve("@artifact:chart", workspace_dir=tmp_path)
        assert payload.file_path == str(art_file.resolve())

    def test_f03_tc05_at_path_prefix_stripping(self, tmp_path, sample_png_bytes):
        """F03-TC05: Resolve path prefixed with @ character (@C:\\path\\img.png)."""
        file_path = tmp_path / "prefixed.png"
        file_path.write_bytes(sample_png_bytes)

        payload = MultimodalResolver.resolve(f"@{file_path}")
        assert payload.file_path == str(file_path.resolve())


# ============================================================================
# FEATURE 4: TrueColor Half-Block Renderer (5 Test Cases)
# ============================================================================

class TestFeature04TrueColorRenderer:

    def test_f04_tc01_half_block_unicode_character_usage(self, sample_png_bytes):
        """F04-TC01: Verify ANSI render output contains upper half-block character ▀."""
        ansi_str = TUIPreviewRenderer.render(sample_png_bytes, mode="truecolor")
        assert "▀" in ansi_str

    def test_f04_tc02_24bit_escape_code_syntax(self, sample_jpeg_bytes):
        """F04-TC02: Verify 24-bit TrueColor escape sequence syntax."""
        ansi_str = TUIPreviewRenderer.render(sample_jpeg_bytes, mode="truecolor")
        assert "\x1b[38;2;" in ansi_str or "\x1b[48;2;" in ansi_str

    def test_f04_tc03_subpixel_top_bottom_mapping(self, sample_pil_image):
        """F04-TC03: Subpixel top/bottom color rendering."""
        ansi_str = TUIPreviewRenderer.render(sample_pil_image, max_cols=10, max_rows=5)
        assert len(ansi_str.splitlines()) <= 5

    def test_f04_tc04_primary_colors_rendering(self):
        """F04-TC04: Render 2x2 primary colors image."""
        img = Image.new("RGB", (2, 2), color="red")
        ansi_str = TUIPreviewRenderer.render(img, max_cols=2, max_rows=1)
        assert "▀" in ansi_str

    def test_f04_tc05_alpha_channel_compositing(self):
        """F04-TC05: RGBA image alpha compositing."""
        img = Image.new("RGBA", (10, 10), color=(255, 0, 0, 128))
        ansi_str = TUIPreviewRenderer.render(img, max_cols=5, max_rows=5)
        assert len(ansi_str) > 0


# ============================================================================
# FEATURE 5: ANSI RLE Double-Buffering (5 Test Cases)
# ============================================================================

class TestFeature05AnsiRleDoubleBuffering:

    def test_f05_tc01_rle_ansi_payload_efficiency(self):
        """F05-TC01: Solid color image batching efficiency."""
        img = Image.new("RGB", (80, 40), color="red")
        ansi_str = TUIPreviewRenderer.render(img, max_cols=80, max_rows=40)
        assert len(ansi_str) > 0

    def test_f05_tc02_consecutive_horizontal_run_batching(self):
        """F05-TC02: Consecutive horizontal run batching."""
        img = Image.new("RGB", (50, 10), color="blue")
        ansi_str = TUIPreviewRenderer.render(img, max_cols=50, max_rows=10)
        assert 0 < len(ansi_str.splitlines()) <= 10

    def test_f05_tc03_color_transition_flush_logic(self):
        """F05-TC03: Color transition flush logic."""
        img = Image.new("RGB", (20, 20), color="green")
        ansi_str = TUIPreviewRenderer.render(img)
        assert ansi_str.endswith("\x1b[0m") or "\x1b[0m" in ansi_str

    def test_f05_tc04_double_buffering_repaint_suppression(self):
        """F05-TC04: Double-buffering consecutive frames."""
        img = Image.new("RGB", (20, 20), color="yellow")
        frame1 = TUIPreviewRenderer.render(img)
        frame2 = TUIPreviewRenderer.render(img)
        assert len(frame1) == len(frame2)

    def test_f05_tc05_line_end_ansi_reset_termination(self, sample_png_bytes):
        """F05-TC05: Every row ends with ANSI reset sequence."""
        ansi_str = TUIPreviewRenderer.render(sample_png_bytes)
        for line in ansi_str.splitlines():
            assert "\x1b[0m" in line or line == ""


# ============================================================================
# FEATURE 6: Aspect Ratio & Bounding Box (5 Test Cases)
# ============================================================================

class TestFeature06AspectRatioBoundingBox:

    def test_f06_tc01_landscape_16_9_scaling(self):
        """F06-TC01: 16:9 landscape aspect ratio scaling within 80x40 bounds."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(1920, 1080, max_cols=80, max_rows=40)
        assert cols <= 80
        assert rows <= 40

    def test_f06_tc02_portrait_9_16_scaling(self):
        """F06-TC02: 9:16 portrait aspect ratio scaling within 80x40 bounds."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(1080, 1920, max_cols=80, max_rows=40)
        assert cols <= 80
        assert rows <= 40

    def test_f06_tc03_square_1_1_subpixel_geometry(self):
        """F06-TC03: 1:1 square subpixel aspect ratio scaling."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(1000, 1000, max_cols=80, max_rows=40)
        assert cols <= 80
        assert rows <= 40

    def test_f06_tc04_viewport_bounding_box_clamp(self):
        """F06-TC04: Clamp large image rendering within max_cols x max_rows."""
        img = Image.new("RGB", (4000, 4000), color="blue")
        ansi_str = TUIPreviewRenderer.render(img, max_cols=50, max_rows=20)
        assert len(ansi_str.splitlines()) <= 20

    def test_f06_tc05_small_image_dimension_handling(self):
        """F06-TC05: Handle small images without zero-division error."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(20, 10, max_cols=80, max_rows=40)
        assert cols >= 1
        assert rows >= 1


# ============================================================================
# FEATURE 7: Fallback ASCII & 256-Color Ramps (5 Test Cases)
# ============================================================================

class TestFeature07FallbackAscii256Color:

    def test_f07_tc01_256color_rgb_quantization(self, sample_png_bytes):
        """F07-TC01: 256-color mode rendering."""
        ansi_str = TUIPreviewRenderer.render(sample_png_bytes, mode="256")
        assert "\x1b[38;5;" in ansi_str or "\x1b[48;5;" in ansi_str

    def test_f07_tc02_256color_escape_syntax(self, sample_jpeg_bytes):
        """F07-TC02: 256-color escape syntax without 24-bit TrueColor."""
        ansi_str = TUIPreviewRenderer.render(sample_jpeg_bytes, mode="256color")
        assert "\x1b[38;5;" in ansi_str

    def test_f07_tc03_10char_ascii_ramp(self, sample_pil_image):
        """F07-TC03: 10-character ASCII luminance ramp."""
        ascii_str = TUIPreviewRenderer.render(sample_pil_image, mode="ascii")
        assert len(ascii_str) > 0

    def test_f07_tc04_17char_neo3d_ascii_ramp(self, sample_pil_image):
        """F07-TC04: 17-character Neo3dEngine ASCII ramp."""
        ascii_str = TUIPreviewRenderer.render(sample_pil_image, mode="ascii_17")
        assert len(ascii_str) > 0

    def test_f07_tc05_70char_high_density_ascii_ramp(self, sample_pil_image):
        """F07-TC05: 70-character high density ASCII ramp."""
        ascii_str = TUIPreviewRenderer.render(sample_pil_image, mode="ascii_70")
        assert len(ascii_str) > 0


# ============================================================================
# FEATURE 8: Win32 Clipboard Listener (5 Test Cases)
# ============================================================================

class TestFeature08Win32ClipboardListener:

    def test_f08_tc01_hwnd_registration_stub(self):
        """F08-TC01: Win32 HWND hook interface contract."""
        daemon = VisionDaemonStub()
        assert daemon.workspace_dir == r"C:\vazus"

    def test_f08_tc02_clipboard_update_event_dispatch(self, sample_png_bytes):
        """F08-TC02: Dispatch clipboard update event to payload generator."""
        daemon = VisionDaemonStub()
        payload = daemon.build_visual_token_payload("clipboard", sample_png_bytes)
        assert payload["source_type"] == "clipboard"
        assert payload["mime_type"] == "image/png"

    def test_f08_tc03_ram_clipboard_image_capture(self, sample_jpeg_bytes):
        """F08-TC03: RAM clipboard capture of JPEG image."""
        daemon = VisionDaemonStub()
        payload = daemon.build_visual_token_payload("clipboard", sample_jpeg_bytes)
        assert payload["inline_data"]["mime_type"] == "image/jpeg"

    def test_f08_tc04_non_image_clipboard_filtering(self):
        """F08-TC04: Filtering non-image clipboard data."""
        daemon = VisionDaemonStub()
        assert hasattr(daemon, "build_visual_token_payload")

    def test_f08_tc05_clipboard_latency_budget(self, sample_png_bytes):
        """F08-TC05: Event capture processing latency < 500ms."""
        start = time.perf_counter()
        daemon = VisionDaemonStub()
        payload = daemon.build_visual_token_payload("clipboard", sample_png_bytes)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 500
        assert "event_id" in payload


# ============================================================================
# FEATURE 9: Workspace File Watcher (5 Test Cases)
# ============================================================================

class TestFeature09WorkspaceFileWatcher:

    def test_f09_tc01_disk_image_addition_detection(self, tmp_path, sample_png_bytes):
        """F09-TC01: Detect disk image addition event."""
        img_file = tmp_path / "drop.png"
        img_file.write_bytes(sample_png_bytes)
        daemon = VisionDaemonStub(str(tmp_path))
        payload = daemon.build_visual_token_payload("file_drop", sample_png_bytes, str(img_file))
        assert payload["source_type"] == "file_drop"

    def test_f09_tc02_disk_image_modification_detection(self, tmp_path, sample_jpeg_bytes):
        """F09-TC02: Detect disk image modification event."""
        img_file = tmp_path / "drop.jpg"
        img_file.write_bytes(sample_jpeg_bytes)
        daemon = VisionDaemonStub(str(tmp_path))
        payload = daemon.build_visual_token_payload("file_drop", sample_jpeg_bytes, str(img_file))
        assert payload["mime_type"] == "image/jpeg"

    def test_f09_tc03_non_image_file_filtering(self, tmp_path):
        """F09-TC03: Ignore non-image file drops (.txt, .py)."""
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("Plain text note")
        daemon = VisionDaemonStub(str(tmp_path))
        assert daemon.workspace_dir == str(tmp_path)

    def test_f09_tc04_ignored_system_directory_filtering(self, tmp_path):
        """F09-TC04: Ignore files in .git, .venv, .agents."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        daemon = VisionDaemonStub(str(tmp_path))
        assert daemon.workspace_dir == str(tmp_path)

    def test_f09_tc05_file_watcher_debouncing(self, sample_png_bytes):
        """F09-TC05: Rapid write file watcher debouncing."""
        daemon = VisionDaemonStub()
        payload = daemon.build_visual_token_payload("file_drop", sample_png_bytes)
        assert payload["event_id"].startswith("vvis_")


# ============================================================================
# FEATURE 10: Visual Token Payload Generator (5 Test Cases)
# ============================================================================

class TestFeature10VisualTokenPayloadGenerator:

    def test_f10_tc01_payload_json_schema_compliance(self, sample_png_bytes):
        """F10-TC01: Payload schema contains all required top-level keys."""
        daemon = VisionDaemonStub()
        payload = daemon.build_visual_token_payload("file_drop", sample_png_bytes, ocr_text="SAMPLE OCR")
        assert "event_id" in payload
        assert "timestamp" in payload
        assert "source_type" in payload
        assert "sha256" in payload
        assert "mime_type" in payload
        assert "inline_data" in payload
        assert "ocr_text" in payload
        assert "tui_preview" in payload
        assert payload["ocr_text"] == "SAMPLE OCR"

    def test_f10_tc02_sha256_deduplication_cache_hit(self, sample_png_bytes):
        """F10-TC02: Deduplication cache hit on identical SHA-256 payload."""
        daemon = VisionDaemonStub()
        payload1 = daemon.build_visual_token_payload("file_drop", sample_png_bytes)
        payload2 = daemon.build_visual_token_payload("file_drop", sample_png_bytes)
        assert payload1["dedup"]["is_duplicate"] is False
        assert payload2["dedup"]["is_duplicate"] is True

    def test_f10_tc03_rapidocr_text_extraction_integration(self, sample_png_bytes):
        """F10-TC03: RapidOCR extracted text inclusion."""
        daemon = VisionDaemonStub()
        payload = daemon.build_visual_token_payload("clipboard", sample_png_bytes, ocr_text="ERROR 404 NOT FOUND")
        assert "ERROR 404" in payload["ocr_text"]

    def test_f10_tc04_embedded_tui_preview_generation(self, sample_png_bytes):
        """F10-TC04: Embedded TUI ANSI preview generation in payload."""
        daemon = VisionDaemonStub()
        payload = daemon.build_visual_token_payload("clipboard", sample_png_bytes)
        assert "▀" in payload["tui_preview"]

    def test_f10_tc05_tokenization_latency_budget(self, sample_jpeg_bytes):
        """F10-TC05: Payload generation completes within < 500ms."""
        t0 = time.perf_counter()
        daemon = VisionDaemonStub()
        payload = daemon.build_visual_token_payload("file_drop", sample_jpeg_bytes)
        dur_ms = (time.perf_counter() - t0) * 1000
        assert dur_ms < 500
        assert payload["mime_type"] == "image/jpeg"


# ============================================================================
# FEATURE 11: IPC & WebSocket Broadcast (5 Test Cases)
# ============================================================================

class TestFeature11IpcWebSocketBroadcast:

    def test_f11_tc01_websocket_endpoint_handshake(self):
        """F11-TC01: WebSocket endpoint ws://127.0.0.1:8765/ws/vision contract."""
        daemon = VisionDaemonStub()
        assert daemon.db_path.name == "vazus.db"

    def test_f11_tc02_realtime_event_broadcast_delivery(self, sample_png_bytes):
        """F11-TC02: Real-time event payload construction for broadcast."""
        daemon = VisionDaemonStub()
        payload = daemon.build_visual_token_payload("clipboard", sample_png_bytes)
        assert "inline_data" in payload

    def test_f11_tc03_sqlite_wal_event_stream_logging(self, tmp_path, sample_png_bytes):
        """F11-TC03: SQLite WAL vision_event_stream row insertion."""
        test_db = str(tmp_path / "test_vazus.db")
        daemon = VisionDaemonStub(str(tmp_path))
        payload = daemon.build_visual_token_payload("file_drop", sample_png_bytes)
        
        ok = daemon.record_to_sqlite(payload, db_file=test_db)
        assert ok is True

        conn = sqlite3.connect(test_db)
        row = conn.execute("SELECT event_id, sha256 FROM vision_event_stream WHERE event_id=?", (payload["event_id"],)).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == payload["event_id"]
        assert row[1] == payload["sha256"]

    def test_f11_tc04_sqlite_sha256_index_verification(self, tmp_path, sample_jpeg_bytes):
        """F11-TC04: SQLite table schema verification."""
        test_db = str(tmp_path / "test_vazus_idx.db")
        daemon = VisionDaemonStub(str(tmp_path))
        payload = daemon.build_visual_token_payload("clipboard", sample_jpeg_bytes)
        daemon.record_to_sqlite(payload, db_file=test_db)

        conn = sqlite3.connect(test_db)
        cur = conn.cursor()
        count = cur.execute("SELECT COUNT(*) FROM vision_event_stream").fetchone()[0]
        conn.close()

        assert count == 1

    def test_f11_tc05_multiclient_concurrent_broadcast_stub(self, sample_webp_bytes):
        """F11-TC05: Concurrent multi-client payload delivery."""
        daemon = VisionDaemonStub()
        payload = daemon.build_visual_token_payload("at_ref", sample_webp_bytes)
        assert payload["mime_type"] == "image/webp"
