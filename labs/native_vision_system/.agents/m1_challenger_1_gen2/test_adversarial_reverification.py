r"""
Adversarial Stress Test Suite - Re-verification of Iteration 2 Fixes
Target: vazus_core.multimodal_resolver
Location: C:\vazus\labs\native_vision_system\.agents\m1_challenger_1_gen2\test_adversarial_reverification.py
"""

import sys
import os
import io

import base64
import hashlib

import pytest
from unittest import mock

# Ensure C:\vazus is in sys.path
if r"C:\vazus" not in sys.path:
    sys.path.insert(0, r"C:\vazus")

from PIL import Image
from vazus_core.multimodal_resolver import (
    MultimodalResolver,
    ResolvedMultimodalPayload,
    CorruptedImageError,
    UnsupportedFormatError,
    ImageNotFoundError,
)


def create_corrupted_png_bytes() -> bytes:
    """
    Constructs a synthetic PNG with valid signature and valid IHDR header (16x16 px),
    but with corrupted IDAT payload bytes.
    """
    img = Image.new("RGB", (16, 16), color="green")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    valid_png = buf.getvalue()

    idat_idx = valid_png.find(b"IDAT")
    assert idat_idx != -1
    # Corrupt compressed IDAT payload bytes while preserving IHDR header
    corrupt_pixel_bytes = valid_png[:idat_idx + 4] + b"\x00" * 33 + valid_png[idat_idx + 4 + 33:]
    return corrupt_pixel_bytes


def create_corrupted_jpeg_bytes() -> bytes:
    """
    Constructs a synthetic JPEG with valid headers (32x32 px),
    but with corrupted scan entropy data after SOS marker.
    """
    img = Image.new("RGB", (32, 32), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    valid_jpg = buf.getvalue()
    
    sos_idx = valid_jpg.find(b"\xff\xda")
    assert sos_idx != -1
    # Zero out scan entropy data after SOS header block
    corrupt_jpg = valid_jpg[:sos_idx + 12] + b"\x00" * 50 + valid_jpg[sos_idx + 12 + 50:]
    return corrupt_jpg


class TestIssue1StrictPixelLoading:
    """
    Adversarial verification for Issue 1:
    Enforced strict mode pixel loading (img.load() when strict=True).
    Verify corrupted pixel stream payloads raise CorruptedImageError when strict=True,
    and pass header inspection when strict=False.
    """

    def test_corrupted_png_idat_strict_true(self):
        """Valid IHDR, zeroed IDAT -> strict=True MUST raise CorruptedImageError."""
        corrupt_png = create_corrupted_png_bytes()
        
        with pytest.raises(CorruptedImageError) as exc_info:
            MultimodalResolver.resolve(corrupt_png, strict=True)
        
        assert "Failed to parse image dimensions or verify pixel payload" in str(exc_info.value)

    def test_corrupted_png_idat_strict_false(self):
        """Valid IHDR, zeroed IDAT -> strict=False MUST succeed and return (16, 16)."""
        corrupt_png = create_corrupted_png_bytes()
        payload = MultimodalResolver.resolve(corrupt_png, strict=False)
        
        assert payload.width == 16
        assert payload.height == 16
        assert payload.mime_type == "image/png"

    def test_corrupted_jpeg_scan_strict_true(self):
        """Corrupted JPEG scan data -> strict=True MUST raise CorruptedImageError."""
        corrupt_jpg = create_corrupted_jpeg_bytes()
        
        with pytest.raises(CorruptedImageError):
            MultimodalResolver.resolve(corrupt_jpg, strict=True)

    def test_corrupted_jpeg_scan_strict_false(self):
        """Corrupted JPEG scan data -> strict=False returns header dimensions."""
        corrupt_jpg = create_corrupted_jpeg_bytes()
        payload = MultimodalResolver.resolve(corrupt_jpg, strict=False)
        
        assert payload.width == 32
        assert payload.height == 32
        assert payload.mime_type == "image/jpeg"

    def test_completely_invalid_random_bytes_strict_true(self):
        """Random bytes with invalid header -> strict=True raises UnsupportedFormatError or CorruptedImageError."""
        garbage = os.urandom(128)
        with pytest.raises((UnsupportedFormatError, CorruptedImageError)):
            MultimodalResolver.resolve(garbage, strict=True)

    def test_completely_invalid_random_bytes_strict_false(self):
        """Random bytes with invalid header -> strict=False raises UnsupportedFormatError or CorruptedImageError."""
        garbage = os.urandom(128)
        with pytest.raises((UnsupportedFormatError, CorruptedImageError)):
            MultimodalResolver.resolve(garbage, strict=False)

    def test_valid_image_strict_true_and_false(self):
        """Valid PNG image resolves cleanly in both strict=True and strict=False modes."""
        img = Image.new("RGB", (30, 40), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw_bytes = buf.getvalue()
        
        payload_strict = MultimodalResolver.resolve(raw_bytes, strict=True)
        payload_lazy = MultimodalResolver.resolve(raw_bytes, strict=False)
        
        assert payload_strict.width == 30 and payload_strict.height == 40
        assert payload_lazy.width == 30 and payload_lazy.height == 40
        assert payload_strict.sha256 == payload_lazy.sha256


class TestIssue2GeminiClientInitErrorHandling:
    """
    Adversarial verification for Issue 2:
    Wrap genai.Client() initialization inside try...except block in dispatch_to_gemini.
    Verify missing API key or client initialization failures return {"status": "ERROR", "error": ...}.
    """

    def test_dispatch_missing_api_key_client_none(self, monkeypatch):
        """
        When GEMINI_API_KEY is not set in environment and client=None,
        genai.Client() raises ValueError. dispatch_to_gemini MUST catch it and return status: ERROR.
        """
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        
        img = Image.new("RGB", (10, 10), color="green")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        valid_bytes = buf.getvalue()
        
        res = MultimodalResolver.dispatch_to_gemini(
            image_input=valid_bytes,
            prompt="Analyze this image",
            client=None
        )
        
        assert res["status"] == "ERROR"
        assert "API key" in res["error"] or "GEMINI_API_KEY" in res["error"] or "error" in res
        assert res["mime_type"] == "image/png"

    def test_dispatch_client_init_raises_custom_exception(self):
        """
        When genai.Client() raises any arbitrary exception during instantiation,
        dispatch_to_gemini catches it and returns status: ERROR.
        """
        img = Image.new("RGB", (10, 10), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        valid_bytes = buf.getvalue()
        
        with mock.patch("google.genai.Client", side_effect=RuntimeError("Custom Client connection failed")):
            res = MultimodalResolver.dispatch_to_gemini(
                image_input=valid_bytes,
                prompt="Analyze this image",
                client=None
            )
            
            assert res["status"] == "ERROR"
            assert res["error"] == "Custom Client connection failed"
            assert res["mime_type"] == "image/png"

    def test_dispatch_generate_content_failure(self):
        """
        When Client instantiates successfully but generate_content raises an exception,
        dispatch_to_gemini returns status: ERROR.
        """
        mock_client = mock.MagicMock()
        mock_client.models.generate_content.side_effect = Exception("Quota exceeded 429")
        
        img = Image.new("RGB", (10, 10), color="yellow")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        valid_bytes = buf.getvalue()
        
        res = MultimodalResolver.dispatch_to_gemini(
            image_input=valid_bytes,
            prompt="Analyze this image",
            client=mock_client
        )
        
        assert res["status"] == "ERROR"
        assert "Quota exceeded 429" in res["error"]

    def test_dispatch_success_path(self):
        """
        When Client succeeds, dispatch_to_gemini returns status: SUCCESS with text.
        """
        mock_client = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.text = "This is a red square."
        mock_client.models.generate_content.return_value = mock_response
        
        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        valid_bytes = buf.getvalue()
        
        res = MultimodalResolver.dispatch_to_gemini(
            image_input=valid_bytes,
            prompt="Analyze this image",
            client=mock_client
        )
        
        assert res["status"] == "SUCCESS"
        assert res["text"] == "This is a red square."
        assert res["mime_type"] == "image/png"
