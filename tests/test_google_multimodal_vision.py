"""
Unit tests for vazus_core/google_multimodal_vision.py
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.append(r"C:\vazus")
sys.path.append(r"C:\vazus\vazus_core")

from vazus_core.google_multimodal_vision import (
    analyze_lab_report_image,
    parse_with_pix2text,
    _get_pix2text
)

class TestGoogleMultimodalVision(unittest.TestCase):

    def test_missing_image_file_returns_standard_error_status(self):
        fake_path = r"C:\vazus\non_existent_lab_image_999.png"
        res = analyze_lab_report_image(fake_path)
        self.assertEqual(res.get("status"), "ERROR")
        self.assertEqual(res.get("engine"), "none")
        self.assertEqual(res.get("analysis_text"), "")
        self.assertIn("Image file not found", res.get("message", ""))
        self.assertEqual(res.get("image"), fake_path)

    def test_missing_image_file_pix2text_returns_error_status(self):
        fake_path = r"C:\vazus\non_existent_pix2text_image_999.png"
        res = parse_with_pix2text(fake_path)
        self.assertEqual(res.get("status"), "ERROR")
        self.assertEqual(res.get("engine"), "pix2text")
        self.assertEqual(res.get("analysis_text"), "")
        self.assertIn("Image file not found", res.get("message", ""))
        self.assertEqual(res.get("image"), fake_path)

    @patch("google.genai.Client")
    def test_gemini_vision_success_mock(self, mock_client_cls):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Гемоглобин: 145 г/л (Норма), Эритроциты: 4.8 х10^12/л"
        mock_client.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_client

        dummy_path = r"C:\vazus\test_dummy_lab_report.png"
        with open(dummy_path, "wb") as f:
            f.write(b"fake_image_bytes_lab_report")

        try:
            res = analyze_lab_report_image(dummy_path, user_prompt="Analyze blood test")
            self.assertEqual(res.get("status"), "SUCCESS")
            self.assertEqual(res.get("engine"), "gemini-2.5-flash")
            self.assertIn("Гемоглобин", res.get("analysis_text", ""))
            self.assertEqual(res.get("image"), dummy_path)
        finally:
            if os.path.exists(dummy_path):
                os.remove(dummy_path)

    @patch("vazus_core.google_multimodal_vision._get_pix2text")
    def test_pix2text_fallback_tier1_success(self, mock_get_p2t):
        mock_p2t = MagicMock()
        mock_page = MagicMock()
        mock_page.to_markdown.return_value = "| Test | Value |\n|---|---|\n| Hb | 145 |"
        mock_p2t.recognize_page.return_value = mock_page
        mock_get_p2t.return_value = mock_p2t

        dummy_path = r"C:\vazus\test_dummy_ocr.png"
        with open(dummy_path, "wb") as f:
            f.write(b"fake_ocr_bytes")

        try:
            res = parse_with_pix2text(dummy_path, extract_layout=True)
            self.assertEqual(res.get("status"), "PIX2TEXT_SUCCESS")
            self.assertEqual(res.get("engine"), "pix2text-1.1.6-full")
            self.assertIn("Hb", res.get("analysis_text", ""))
            self.assertEqual(res.get("image"), dummy_path)
        finally:
            if os.path.exists(dummy_path):
                os.remove(dummy_path)

    @patch("vazus_core.google_multimodal_vision._get_pix2text")
    @patch("pix2text.Pix2Text.from_config")
    def test_pix2text_fallback_tier2_success(self, mock_from_config, mock_get_p2t):
        mock_p2t_tier1 = MagicMock()
        mock_p2t_tier1.recognize_page.side_effect = Exception("Page layout model failure")
        mock_get_p2t.return_value = mock_p2t_tier1

        mock_p2t_tier2 = MagicMock()
        mock_p2t_tier2.recognize_text.return_value = "Plain text OCR fallback result"
        mock_from_config.return_value = mock_p2t_tier2

        dummy_path = r"C:\vazus\test_dummy_ocr_tier2.png"
        with open(dummy_path, "wb") as f:
            f.write(b"fake_ocr_bytes_2")

        try:
            res = parse_with_pix2text(dummy_path, extract_layout=True)
            self.assertEqual(res.get("status"), "PIX2TEXT_SUCCESS")
            self.assertEqual(res.get("engine"), "pix2text-1.1.6-fast")
            self.assertEqual(res.get("analysis_text"), "Plain text OCR fallback result")
            self.assertEqual(res.get("image"), dummy_path)
        finally:
            if os.path.exists(dummy_path):
                os.remove(dummy_path)

    def test_pix2text_singleton_cache(self):
        with patch("pix2text.Pix2Text.from_config") as mock_from_config:
            mock_inst = MagicMock()
            mock_from_config.return_value = mock_inst
            
            import vazus_core.google_multimodal_vision as gmv
            gmv._P2T_INSTANCE = None

            inst1 = _get_pix2text()
            inst2 = _get_pix2text()
            self.assertIs(inst1, inst2)
            mock_from_config.assert_called_once()

if __name__ == "__main__":
    unittest.main()
