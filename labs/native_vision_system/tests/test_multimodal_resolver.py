"""
Unit tests for vazus_core/multimodal_resolver.py
File: C:\\vazus\\labs\\native_vision_system\\tests\\test_multimodal_resolver.py
Runner: C:\\vazus\\.venv\\Scripts\\python.exe -m pytest C:\\vazus\\labs\\native_vision_system\\tests\\test_multimodal_resolver.py
"""

import os
import io
import time
import base64
import hashlib
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image

import sys
sys.path.insert(0, r"C:\vazus")

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
from google.genai import types


# --- Fixtures ---

@pytest.fixture
def sample_png_bytes():
    """Generates a valid 100x100 PNG image in memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color="red")
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_jpeg_bytes():
    """Generates a valid 100x100 JPEG image in memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def sample_webp_bytes():
    """Generates a valid 100x100 WEBP image in memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color="green")
    img.save(buf, format="WEBP")
    return buf.getvalue()


# --- Unit Tests ---

class TestMultimodalResolver:

    def test_inspect_mime_type_magic_bytes(self, sample_png_bytes, sample_jpeg_bytes, sample_webp_bytes):
        """TC-01..TC-06: Test magic byte MIME type detection for PNG, JPEG, WEBP."""
        assert MultimodalResolver.inspect_mime_type(sample_png_bytes) == "image/png"
        assert MultimodalResolver.inspect_mime_type(sample_jpeg_bytes) == "image/jpeg"
        assert MultimodalResolver.inspect_mime_type(sample_webp_bytes) == "image/webp"

    def test_inspect_mime_type_magic_bytes_precedence(self, sample_png_bytes):
        """TC-07, TC-08: Verify magic bytes take precedence over misleading file extension hints."""
        detected_mime = MultimodalResolver.inspect_mime_type(sample_png_bytes, hint_path="misleading_file.jpg")
        assert detected_mime == "image/png"

    def test_inspect_mime_type_corrupted_or_empty(self):
        """Test error handling for empty or corrupt bytes in inspect_mime_type."""
        with pytest.raises(ValueError):
            MultimodalResolver.inspect_mime_type(b"")

        with pytest.raises(ValueError):
            MultimodalResolver.inspect_mime_type(b"INVALID_NON_IMAGE_BYTES_PAYLOAD")

    def test_resolve_raw_bytes(self, sample_png_bytes, sample_jpeg_bytes, sample_webp_bytes):
        """TC-04, TC-05, TC-06: Verify resolve with raw image bytes."""
        payload_png = MultimodalResolver.resolve(sample_png_bytes)
        assert isinstance(payload_png, ResolvedMultimodalPayload)
        assert payload_png.mime_type == "image/png"
        assert payload_png.raw_bytes == sample_png_bytes
        assert payload_png.file_path is None
        assert payload_png.width == 100
        assert payload_png.height == 100
        assert payload_png.sha256 == hashlib.sha256(sample_png_bytes).hexdigest()
        assert payload_png.base64_data == base64.b64encode(sample_png_bytes).decode("utf-8")
        assert payload_png.base64_str == payload_png.base64_data

        payload_jpg = MultimodalResolver.resolve(sample_jpeg_bytes)
        assert payload_jpg.mime_type == "image/jpeg"

        payload_webp = MultimodalResolver.resolve(sample_webp_bytes)
        assert payload_webp.mime_type == "image/webp"

    def test_resolve_disk_files(self, tmp_path, sample_png_bytes, sample_jpeg_bytes, sample_webp_bytes):
        """TC-01, TC-02, TC-03: Verify resolve with disk file paths."""
        png_file = tmp_path / "test_image.png"
        png_file.write_bytes(sample_png_bytes)

        jpg_file = tmp_path / "test_image.jpg"
        jpg_file.write_bytes(sample_jpeg_bytes)

        webp_file = tmp_path / "test_image.webp"
        webp_file.write_bytes(sample_webp_bytes)

        payload_png = MultimodalResolver.resolve(str(png_file))
        assert payload_png.mime_type == "image/png"
        assert payload_png.file_path == str(png_file.resolve())

        payload_jpg = MultimodalResolver.resolve(jpg_file)
        assert payload_jpg.mime_type == "image/jpeg"

        payload_webp = MultimodalResolver.resolve(str(webp_file))
        assert payload_webp.mime_type == "image/webp"

    def test_resolve_at_reference_file(self, tmp_path, sample_png_bytes):
        """TC-12: Verify resolve with @ prefix file path."""
        png_file = tmp_path / "target.png"
        png_file.write_bytes(sample_png_bytes)

        payload = MultimodalResolver.resolve(f"@{png_file}")
        assert payload.mime_type == "image/png"
        assert payload.file_path == str(png_file.resolve())

    @patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard")
    def test_resolve_clipboard_image(self, mock_grab, sample_png_bytes):
        """Test @clipboard with PIL Image object."""
        img = Image.new("RGB", (80, 80), color="blue")
        mock_grab.return_value = img

        payload = MultimodalResolver.resolve("@clipboard")
        assert payload.mime_type == "image/png"
        assert payload.width == 80
        assert payload.height == 80
        assert payload.source_type == "clipboard"

    @patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard")
    def test_resolve_clipboard_file_list(self, mock_grab, tmp_path, sample_png_bytes):
        """Test @clip with list of file paths in clipboard."""
        png_file = tmp_path / "copied.png"
        png_file.write_bytes(sample_png_bytes)
        mock_grab.return_value = [str(png_file)]

        payload = MultimodalResolver.resolve("@clip")
        assert payload.mime_type == "image/png"
        assert payload.file_path == str(png_file.resolve())

    @patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard")
    def test_resolve_clipboard_empty(self, mock_grab):
        """Test @clipboard when clipboard is empty or contains non-image data."""
        mock_grab.return_value = None
        with pytest.raises(ClipboardEmptyError):
            MultimodalResolver.resolve("@clipboard")

    @patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard")
    def test_resolve_clipboard_locked(self, mock_grab):
        """Test @clipboard when clipboard API raises OSError."""
        mock_grab.side_effect = OSError("Clipboard locked by another process")
        with pytest.raises(ClipboardAccessError):
            MultimodalResolver.resolve("@clip")

    def test_resolve_latest(self, tmp_path, sample_png_bytes, sample_jpeg_bytes):
        """Test @latest image search in workspace."""
        file1 = tmp_path / "old.png"
        file1.write_bytes(sample_png_bytes)

        time.sleep(0.05)

        file2 = tmp_path / "new.jpg"
        file2.write_bytes(sample_jpeg_bytes)

        payload = MultimodalResolver.resolve("@latest", workspace_dir=tmp_path)
        assert payload.mime_type == "image/jpeg"
        assert payload.file_path == str(file2.resolve())

    def test_resolve_latest_empty(self, tmp_path):
        """Test @latest when no image files exist."""
        empty_dir = tmp_path / "empty_dir"
        empty_dir.mkdir()
        with pytest.raises(ImageNotFoundError):
            MultimodalResolver.resolve("@latest", workspace_dir=empty_dir, extra_search_dirs=[])

    def test_resolve_artifact(self, tmp_path, sample_png_bytes):
        """Test @artifact:<name> resolution."""
        agent_artifact_dir = tmp_path / ".agents" / "agent_1" / "artifacts"
        agent_artifact_dir.mkdir(parents=True)
        artifact_file = agent_artifact_dir / "mockup.png"
        artifact_file.write_bytes(sample_png_bytes)

        payload = MultimodalResolver.resolve("@artifact:mockup", workspace_dir=tmp_path)
        assert payload.mime_type == "image/png"
        assert payload.file_path == str(artifact_file.resolve())

    def test_resolve_artifact_not_found(self, tmp_path):
        """Test @artifact:<name> when artifact does not exist."""
        with pytest.raises(ArtifactNotFoundError):
            MultimodalResolver.resolve("@artifact:nonexistent_mockup", workspace_dir=tmp_path, extra_search_dirs=[])

    def test_resolve_pil_image(self):
        """TC-09: Verify resolve with PIL.Image object."""
        img = Image.new("RGB", (50, 50), color="yellow")
        payload = MultimodalResolver.resolve(img)
        assert isinstance(payload, ResolvedMultimodalPayload)
        assert payload.mime_type == "image/png"
        assert payload.width == 50
        assert payload.height == 50
        assert payload.source_type == "pil_image"

    def test_resolve_base64_data_uri(self, sample_png_bytes):
        """TC-10, TC-11: Verify resolve with Base64 Data URI string."""
        b64_data = base64.b64encode(sample_png_bytes).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64_data}"

        payload1 = MultimodalResolver.resolve(data_uri)
        assert payload1.mime_type == "image/png"
        assert payload1.raw_bytes == sample_png_bytes
        assert payload1.source_type == "base64_data_uri"

        payload2 = MultimodalResolver.resolve(b64_data)
        assert payload2.mime_type == "image/png"
        assert payload2.source_type == "base64_str"

    def test_genai_part_conversion(self, sample_png_bytes):
        """TC-13: Test conversion to google.genai types.Part."""
        payload = MultimodalResolver.resolve(sample_png_bytes)
        part = payload.to_genai_part()
        assert isinstance(part, types.Part)
        assert part.inline_data.mime_type == "image/png"
        assert part.inline_data.data == sample_png_bytes

        # Also test property access
        part_prop = payload.genai_part
        assert isinstance(part_prop, types.Part)
        assert part_prop.inline_data.mime_type == "image/png"

    def test_inline_data_dict_conversion(self, sample_png_bytes):
        """TC-14: Test conversion to inlineData dictionary."""
        payload = MultimodalResolver.resolve(sample_png_bytes)
        d = payload.to_inline_data_dict()
        assert "inlineData" in d
        assert d["inlineData"]["mimeType"] == "image/png"
        assert d["inlineData"]["data"] == payload.base64_data

        meta_dict = payload.to_dict()
        assert meta_dict["sha256"] == payload.sha256
        assert meta_dict["width"] == 100
        assert meta_dict["height"] == 100

    @patch("google.genai.Client")
    def test_dispatch_to_gemini_success(self, mock_client_cls, sample_png_bytes):
        """TC-15: Test dispatch_to_gemini with mocked genai Client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Gemini Flash vision output text"
        mock_client.models.generate_content.return_value = mock_response

        res = MultimodalResolver.dispatch_to_gemini(
            image_input=sample_png_bytes,
            prompt="Analyze this image",
            model="gemini-3.6-flash",
            client=mock_client
        )
        assert res["status"] == "SUCCESS"
        assert res["text"] == "Gemini Flash vision output text"
        assert res["mime_type"] == "image/png"
        mock_client.models.generate_content.assert_called_once()

    @patch("google.genai.Client")
    def test_dispatch_to_gemini_failure(self, mock_client_cls, sample_png_bytes):
        """TC-16: Test dispatch_to_gemini when API raises an exception."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("API rate limit exceeded")

        res = MultimodalResolver.dispatch_to_gemini(
            image_input=sample_png_bytes,
            prompt="Analyze this image",
            model="gemini-3.6-flash",
            client=mock_client
        )
        assert res["status"] == "ERROR"
        assert "API rate limit exceeded" in res["error"]

    def test_missing_file_error(self):
        """TC-17: Test error handling for non-existent file."""
        with pytest.raises((FileNotFoundError, ValueError)):
            MultimodalResolver.resolve(r"C:\non_existent_image_12345.png")

    def test_corrupted_bytes_error(self):
        """TC-18: Test error handling for invalid/corrupted binary data."""
        with pytest.raises(ValueError):
            MultimodalResolver.resolve(b"INVALID_NON_IMAGE_BYTES_PAYLOAD")

    def test_empty_bytes_error(self):
        """TC-19: Test error handling for empty byte input."""
        with pytest.raises(ValueError):
            MultimodalResolver.resolve(b"")

    def test_invalid_type_error(self):
        """TC-20: Test error handling for unsupported input type."""
        with pytest.raises((TypeError, ValueError)):
            MultimodalResolver.resolve(123456)

    @patch("google.genai.Client")
    def test_dispatch_to_gemini_missing_client_api_key(self, mock_client_cls, sample_png_bytes):
        """TC-21: Test dispatch_to_gemini catches Client init failure (e.g. missing API key) gracefully."""
        mock_client_cls.side_effect = ValueError("No API key was provided. Set GEMINI_API_KEY environment variable.")

        res = MultimodalResolver.dispatch_to_gemini(
            image_input=sample_png_bytes,
            prompt="Analyze this image",
            client=None
        )
        assert res["status"] == "ERROR"
        assert "No API key was provided" in res["error"]
        assert res["mime_type"] == "image/png"

    def test_strict_mode_pixel_corruption(self):
        """TC-22: Test strict mode pixel decoding catches corrupted pixel payload streams."""
        buf = io.BytesIO()
        img = Image.new("RGB", (16, 16), color="green")
        img.save(buf, format="PNG")
        valid_png = buf.getvalue()

        # Corrupt the IDAT compressed pixel stream payload while leaving IHDR header intact
        idat_idx = valid_png.find(b"IDAT")
        assert idat_idx != -1
        # Zero out 33 bytes of IDAT payload stream
        corrupt_pixel_bytes = valid_png[:idat_idx + 4] + b"\x00" * 33 + valid_png[idat_idx + 4 + 33:]

        # With strict=True (default), loading corrupted pixel stream raises CorruptedImageError
        with pytest.raises(CorruptedImageError):
            MultimodalResolver.resolve(corrupt_pixel_bytes, strict=True)

        # With strict=False, header parsing succeeds without loading pixels
        payload = MultimodalResolver.resolve(corrupt_pixel_bytes, strict=False)
        assert payload.width == 16
        assert payload.height == 16
        assert payload.mime_type == "image/png"

    def test_exception_inheritance(self):
        """Verify exception hierarchy rules."""
        assert issubclass(ClipboardEmptyError, ImageNotFoundError)
        assert issubclass(ClipboardEmptyError, ValueError)
        assert issubclass(ArtifactNotFoundError, ImageNotFoundError)
        assert issubclass(ImageNotFoundError, MultimodalResolverError)
        assert issubclass(ImageNotFoundError, FileNotFoundError)
        assert issubclass(UnsupportedFormatError, MultimodalResolverError)
        assert issubclass(UnsupportedFormatError, ValueError)
        assert issubclass(ClipboardAccessError, MultimodalResolverError)
        assert issubclass(ClipboardAccessError, OSError)
        assert issubclass(CorruptedImageError, MultimodalResolverError)
        assert issubclass(CorruptedImageError, ValueError)
        assert issubclass(MultimodalResolverError, Exception)
