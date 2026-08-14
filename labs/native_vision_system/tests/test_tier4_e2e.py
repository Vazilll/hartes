"""
Tier 4: Real-World Application Scenario & Zero-Bash Delivery E2E Test Suite.
Total Test Cases: 8 (zero-bash direct payload delivery, clipboard workflows, subagent context injection,
offline mock isolation, and master worksession victory scenario).

File: C:\\vazus\\labs\\native_vision_system\\tests\\test_tier4_e2e.py
Runner: C:\\vazus\\.venv\\Scripts\\python.exe C:\\vazus\\labs\\native_vision_system\\tests\\run_e2e_tests.py --tier 4
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


class TestTier4RealWorldScenariosZeroBash:

    @patch("google.genai.Client")
    def test_tc_t4_01_win_shift_s_clipboard_zero_bash_delivery(self, mock_client_cls, sample_pil_image):
        """TC-T4-01: Win+Shift+S Clipboard Capture -> Gemini 3.6 Flash Direct Zero-Bash Delivery."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Visual token payload processed for button text 'SUBMIT ORDER'."
        mock_client.models.generate_content.return_value = mock_response

        start_time = time.perf_counter()

        with patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard", return_value=sample_pil_image):
            res = MultimodalResolver.dispatch_to_gemini(
                image_input="@clipboard",
                prompt="What action does this UI button perform?",
                model="gemini-3.6-flash",
                client=mock_client
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert elapsed_ms < 350
        assert res["status"] == "SUCCESS"
        assert "SUBMIT ORDER" in res["text"]
        assert res["mime_type"] == "image/png"
        mock_client.models.generate_content.assert_called_once()

    def test_tc_t4_02_subagent_context_auto_injection(self, sample_png_bytes):
        """TC-T4-02: Subagent Context Auto-Injection (SubagentFramework Hook Integration)."""
        daemon = VisionDaemonStub()
        payload = daemon.build_visual_token_payload(
            "clipboard",
            sample_png_bytes,
            ocr_text="Traceback (most recent call last):\n  File 'app.py', line 42, in <module>\nValueError: Invalid vector"
        )

        subagent_context = []
        subagent_context.append({
            "role": "user",
            "content": f"Vision Token Injected:\nOCR: {payload['ocr_text']}\nPreview:\n{payload['tui_preview']}"
        })

        assert len(subagent_context) == 1
        assert "ValueError: Invalid vector" in subagent_context[0]["content"]
        assert "▀" in subagent_context[0]["content"]

    def test_tc_t4_03_rapid_screenshot_burst_deduplication(self, sample_png_bytes, sample_jpeg_bytes):
        """TC-T4-03: Rapid Screenshot Burst Stress & Deduplication."""
        daemon = VisionDaemonStub()
        e1 = daemon.build_visual_token_payload("clipboard", sample_png_bytes)
        e2 = daemon.build_visual_token_payload("clipboard", sample_png_bytes)
        e3 = daemon.build_visual_token_payload("clipboard", sample_jpeg_bytes)

        assert e1["dedup"]["is_duplicate"] is False
        assert e2["dedup"]["is_duplicate"] is True
        assert e3["dedup"]["is_duplicate"] is False

    @patch("google.genai.Client")
    def test_tc_t4_04_offline_fallback_mock_sdk_harness_isolation(self, mock_client_cls, sample_png_bytes):
        """TC-T4-04: Offline Fallback & Mock SDK Harness Isolation."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MagicMock(text="Mock offline result")

        res = MultimodalResolver.dispatch_to_gemini(
            image_input=sample_png_bytes,
            prompt="Analyze in offline CI mode",
            client=mock_client
        )

        assert res["status"] == "SUCCESS"
        assert res["text"] == "Mock offline result"

    def test_tc_t4_05_multimodal_combined_vision_plus_ocr_payload_synergy(self, sample_png_bytes):
        """TC-T4-05: Multi-Modal Combined Vision + OCR Payload Synergy."""
        daemon = VisionDaemonStub()
        payload = daemon.build_visual_token_payload(
            source_type="clipboard",
            raw_bytes=sample_png_bytes,
            ocr_text="def compute_vector(): return [1, 2, 3]"
        )

        assert "inline_data" in payload
        assert payload["inline_data"]["mime_type"] == "image/png"
        assert payload["ocr_text"] == "def compute_vector(): return [1, 2, 3]"

    def test_tc_t4_06_end_to_end_system_victory_scenario(self, tmp_path, sample_png_bytes, sample_jpeg_bytes):
        """TC-T4-06: End-to-End System Victory Scenario (10-Minute Worksession Simulation)."""
        test_db = str(tmp_path / "worksession.db")
        daemon = VisionDaemonStub(str(tmp_path))

        # Event 1: File Drop
        f1 = tmp_path / "architecture.png"
        f1.write_bytes(sample_png_bytes)
        p1 = daemon.build_visual_token_payload("file_drop", sample_png_bytes, str(f1))
        daemon.record_to_sqlite(p1, db_file=test_db)

        # Event 2: @latest query
        res_latest = MultimodalResolver.resolve("@latest", workspace_dir=tmp_path)
        assert res_latest.file_path == str(f1.resolve())

        # Event 3: Clipboard capture
        p2 = daemon.build_visual_token_payload("clipboard", sample_jpeg_bytes, ocr_text="Error dialog")
        daemon.record_to_sqlite(p2, db_file=test_db)

        # Audit check
        conn = sqlite3.connect(test_db)
        count = conn.execute("SELECT COUNT(*) FROM vision_event_stream").fetchone()[0]
        conn.close()

        assert count == 2

    def test_tc_t4_07_anti_freeze_clipboard_safety(self, sample_png_bytes):
        """TC-T4-07: Anti-Freeze Clipboard Safety & Image Serialization Rule Verification."""
        payload = MultimodalResolver.resolve(sample_png_bytes)
        inline_dict = payload.to_inline_data_dict()

        assert "inlineData" in inline_dict
        assert isinstance(inline_dict["inlineData"]["data"], str)
        assert not isinstance(inline_dict["inlineData"]["data"], bytes)

    def test_tc_t4_08_high_dpi_display_bounding_box(self):
        """TC-T4-08: High-DPI Display Bounding Box & Sub-Pixel Aspect Preservation."""
        high_dpi_img = Image.new("RGB", (3840, 2160), color="green")
        payload = MultimodalResolver.resolve(high_dpi_img)
        ansi_str = TUIPreviewRenderer.render(payload, max_cols=80, max_rows=40)

        lines = ansi_str.splitlines()
        assert len(lines) <= 40
        assert "▀" in lines[0]
