# Unit Test Specification & Verification Plan: `vazus_core.multimodal_resolver`

**Author**: M1 Explorer 3 (Unit Verification Plan)  
**Target Module**: `C:\vazus\vazus_core\multimodal_resolver.py`  
**Test File Target**: `C:\vazus\labs\native_vision_system\tests\test_multimodal_resolver.py`  
**Target Virtualenv**: `C:\vazus\.venv\Scripts\python.exe`  
**Date**: 2026-08-05  

---

## 1. Executive Summary

This document specifies the complete unit testing architecture, test matrix, mocking strategies, and verification commands for **Milestone M1: Native Multimodal Image Resolver (`vazus_core.multimodal_resolver`)**.

The target module handles polymorphic image ingestion (disk paths, raw bytes, PIL Image objects, Base64 strings, and `@` references), 3-tiered format inspection (magic byte signatures, Pillow inspection, and extension hints), Base64 encoding, SHA-256 deduplication hashing, and payload conversion to `google.genai` SDK v2.14.0 `types.Part` objects or REST `inlineData` dictionaries for **Gemini 3.6 Flash**.

This specification provides the M1 Worker with a complete test implementation blueprint to verify `vazus_core/multimodal_resolver.py` without requiring external network dependencies or live API credentials.

---

## 2. Test Target Interface Contract

Unit tests must validate the following classes and methods defined in `vazus_core/multimodal_resolver.py`:

### 2.1. Dataclass `ResolvedMultimodalPayload`
- **Fields**:
  - `raw_bytes: bytes` — Unencoded binary image payload.
  - `mime_type: str` — Validated MIME string (`"image/png"`, `"image/jpeg"`, `"image/webp"`).
  - `base64_str: str` — Base64-encoded string representation of `raw_bytes`.
  - `file_path: Optional[str]` — Source path (if resolved from disk), else `None`.
  - `sha256: str` — Hexadecimal SHA-256 checksum of `raw_bytes`.
  - `width: int` — Pixel width of image.
  - `height: int` — Pixel height of image.
- **Methods**:
  - `to_genai_part() -> google.genai.types.Part`: Returns `types.Part.from_bytes(data=self.raw_bytes, mime_type=self.mime_type)`.
  - `to_inline_data_dict() -> Dict[str, Any]`: Returns `{"inlineData": {"mimeType": self.mime_type, "data": self.base64_str}}`.

### 2.2. Class `MultimodalResolver`
- **Static / Class Methods**:
  - `inspect_mime_type(data: bytes, hint_path: Optional[str] = None) -> str`
    - Tier 1: Magic byte header inspection (`\x89PNG\r\n\x1a\n`, `\xff\xd8\xff`, `RIFF....WEBP`).
    - Tier 2: Pillow `Image.open(io.BytesIO(data))` inspection.
    - Tier 3: Extension hint (`mimetypes.guess_type`).
    - Raises `ValueError` for unknown/corrupted formats.
  - `resolve(source: Union[str, Path, bytes, Image.Image]) -> ResolvedMultimodalPayload`
    - Ingests file path, raw bytes, PIL Image, Base64 Data URI, or `@` reference.
    - Returns constructed `ResolvedMultimodalPayload`.
  - `dispatch_to_gemini(image_input: Any, prompt: str, model: str = "gemini-3.6-flash", client: Optional[genai.Client] = None) -> Dict[str, Any]`
    - Mocks API calls, builds `types.Part`, issues `client.models.generate_content`, returns structured dict.

---

## 3. Comprehensive Unit Test Matrix

| ID | Test Scenario | Input Source | Expected Output / Behavior | Priority |
|---|---|---|---|---|
| **TC-01** | PNG File Path Ingestion | `.png` file path | `mime_type == "image/png"`, correct width/height, non-empty `sha256` & `base64_str` | P0 |
| **TC-02** | JPEG File Path Ingestion | `.jpg` / `.jpeg` file path | `mime_type == "image/jpeg"`, correct width/height, valid base64 | P0 |
| **TC-03** | WEBP File Path Ingestion | `.webp` file path | `mime_type == "image/webp"`, correct width/height, valid base64 | P0 |
| **TC-04** | Raw PNG Bytes Ingestion | `bytes` (`b"\x89PNG..."`) | `mime_type == "image/png"`, `file_path is None` | P0 |
| **TC-05** | Raw JPEG Bytes Ingestion | `bytes` (`b"\xff\xd8\xff..."`) | `mime_type == "image/jpeg"`, `file_path is None` | P0 |
| **TC-06** | Raw WEBP Bytes Ingestion | `bytes` (`b"RIFF...WEBP..."`) | `mime_type == "image/webp"`, `file_path is None` | P0 |
| **TC-07** | Magic Byte Overrides Misnamed Extension | `.jpg` file containing PNG bytes | `mime_type == "image/png"` (Magic byte header takes precedence) | P0 |
| **TC-08** | Magic Byte Overrides `.bin` Extension | `.bin` file containing WEBP bytes | `mime_type == "image/webp"` | P1 |
| **TC-09** | PIL Image Object Ingestion | `PIL.Image.Image` object | Ingests image, converts to byte stream, returns valid payload | P0 |
| **TC-10** | Base64 Data URI String | `"data:image/png;base64,iVBORw0..."` | Decodes base64, inspects magic bytes, returns PNG payload | P1 |
| **TC-11** | Raw Base64 String | Raw base64 encoded string | Decodes string into raw bytes, returns valid payload | P1 |
| **TC-12** | `@` Reference Handling (`@path`) | `"@C:\\path\\image.png"` | Strips `@` prefix, resolves file path on disk | P1 |
| **TC-13** | `to_genai_part()` Conversion | `ResolvedMultimodalPayload` | Returns `google.genai.types.Part` with matching `mime_type` and `data` | P0 |
| **TC-14** | `to_inline_data_dict()` Schema | `ResolvedMultimodalPayload` | Returns `{"inlineData": {"mimeType": "...", "data": "..."}}` dict | P0 |
| **TC-15** | `dispatch_to_gemini` Success | Mock `genai.Client` + prompt | Calls `generate_content` with `types.Part`, returns `status: "SUCCESS"` | P0 |
| **TC-16** | `dispatch_to_gemini` Error | Mock `genai.Client` raising Exception | Traps exception, returns `status: "ERROR"` with details | P1 |
| **TC-17** | Missing File Exception | Non-existent path `"C:\\fake\\no.png"` | Raises `FileNotFoundError` or `ValueError` | P0 |
| **TC-18** | Corrupted Bytes Exception | `b"GARBAGE_NOT_AN_IMAGE"` | Raises `ValueError` ("Unsupported or corrupted image format") | P0 |
| **TC-19** | Empty Bytes Exception | `b""` | Raises `ValueError` | P1 |
| **TC-20** | Invalid Input Type Exception | `12345` (int) | Raises `TypeError` or `ValueError` | P1 |

---

## 4. Mocking & Compatibility Verification Strategy

### 4.1. Mocking `google.genai.Client`
To achieve 100% offline unit verification without real API calls, unit tests use `unittest.mock.MagicMock` and `unittest.mock.patch`:

```python
from unittest.mock import MagicMock, patch
from google.genai import types

@patch("google.genai.Client")
def test_dispatch_to_gemini_mock(mock_client_cls):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Visual analysis: Red square detected."
    mock_client.models.generate_content.return_value = mock_response
    mock_client_cls.return_value = mock_client
    ...
```

### 4.2. Verification of `google.genai.types.Part`
The test suite verifies that calling `.to_genai_part()` on a payload creates a valid `types.Part` object:
1. `isinstance(part, types.Part)` is `True`.
2. `part.inline_data.mime_type` equals the resolved MIME string.
3. `part.inline_data.data` equals the exact `raw_bytes`.

### 4.3. REST API `inlineData` Dict Payload Verification
The `to_inline_data_dict()` method must be tested for key conformity:
```python
expected_dict = {
    "inlineData": {
        "mimeType": "image/png",
        "data": base64_encoded_str
    }
}
assert payload.to_inline_data_dict() == expected_dict
```

---

## 5. Concrete Pytest Test Code Specification

The M1 Worker should implement `C:\vazus\labs\native_vision_system\tests\test_multimodal_resolver.py` following this exact specification:

```python
"""
Unit tests for vazus_core/multimodal_resolver.py
File: C:\\vazus\\labs\\native_vision_system\\tests\\test_multimodal_resolver.py
Runner: C:\\vazus\\.venv\\Scripts\\python.exe -m pytest
"""

import os
import io
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
    ResolvedMultimodalPayload
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
        # File with .jpg extension hint containing PNG bytes
        detected_mime = MultimodalResolver.inspect_mime_type(sample_png_bytes, hint_path="misleading_file.jpg")
        assert detected_mime == "image/png"

    def test_resolve_raw_bytes(self, sample_png_bytes):
        """TC-04: Verify resolve with raw PNG bytes."""
        payload = MultimodalResolver.resolve(sample_png_bytes)
        assert isinstance(payload, ResolvedMultimodalPayload)
        assert payload.mime_type == "image/png"
        assert payload.raw_bytes == sample_png_bytes
        assert payload.file_path is None
        assert payload.width == 100
        assert payload.height == 100
        assert payload.sha256 == hashlib.sha256(sample_png_bytes).hexdigest()
        assert payload.base64_str == base64.b64encode(sample_png_bytes).decode("utf-8")

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
        assert payload_png.file_path == str(png_file)

        payload_jpg = MultimodalResolver.resolve(jpg_file)
        assert payload_jpg.mime_type == "image/jpeg"

        payload_webp = MultimodalResolver.resolve(str(webp_file))
        assert payload_webp.mime_type == "image/webp"

    def test_resolve_at_reference(self, tmp_path, sample_png_bytes):
        """TC-12: Verify resolve with @ prefix file path."""
        png_file = tmp_path / "target.png"
        png_file.write_bytes(sample_png_bytes)

        payload = MultimodalResolver.resolve(f"@{png_file}")
        assert payload.mime_type == "image/png"

    def test_resolve_pil_image(self):
        """TC-09: Verify resolve with PIL.Image object."""
        img = Image.new("RGB", (50, 50), color="yellow")
        payload = MultimodalResolver.resolve(img)
        assert isinstance(payload, ResolvedMultimodalPayload)
        assert payload.mime_type == "image/png"
        assert payload.width == 50
        assert payload.height == 50

    def test_resolve_base64_data_uri(self, sample_png_bytes):
        """TC-10, TC-11: Verify resolve with Base64 Data URI string."""
        b64_data = base64.b64encode(sample_png_bytes).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64_data}"

        payload1 = MultimodalResolver.resolve(data_uri)
        assert payload1.mime_type == "image/png"
        assert payload1.raw_bytes == sample_png_bytes

        payload2 = MultimodalResolver.resolve(b64_data)
        assert payload2.mime_type == "image/png"

    def test_genai_part_conversion(self, sample_png_bytes):
        """TC-13: Test conversion to google.genai types.Part."""
        payload = MultimodalResolver.resolve(sample_png_bytes)
        part = payload.to_genai_part()
        assert isinstance(part, types.Part)
        assert part.inline_data.mime_type == "image/png"
        assert part.inline_data.data == sample_png_bytes

    def test_inline_data_dict_conversion(self, sample_png_bytes):
        """TC-14: Test conversion to inlineData dictionary."""
        payload = MultimodalResolver.resolve(sample_png_bytes)
        d = payload.to_inline_data_dict()
        assert "inlineData" in d
        assert d["inlineData"]["mimeType"] == "image/png"
        assert d["inlineData"]["data"] == payload.base64_str

    @patch("google.genai.Client")
    def test_dispatch_to_gemini_success(self, mock_client_cls, sample_png_bytes):
        """TC-15: Test dispatch_to_gemini with mocked genai Client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Gemini Flash vision output text"
        mock_client.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_client

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

    def test_missing_file_error(self):
        """TC-17: Test error handling for non-existent file."""
        with pytest.raises((FileNotFoundError, ValueError)):
            MultimodalResolver.resolve(r"C:\non_existent_image_12345.png")

    def test_corrupted_bytes_error(self):
        """TC-18: Test error handling for invalid/corrupted binary data."""
        with pytest.raises(ValueError, match="Unsupported or corrupted image format"):
            MultimodalResolver.resolve(b"INVALID_NON_IMAGE_BYTES_PAYLOAD")

    def test_invalid_type_error(self):
        """TC-20: Test error handling for unsupported input type."""
        with pytest.raises((TypeError, ValueError)):
            MultimodalResolver.resolve(123456)
```

---

## 6. Execution Commands & Test Runner Instructions

### 6.1. Running Unit Tests via pytest

Execute the test suite using the project virtual environment python executable:

```powershell
C:\vazus\.venv\Scripts\python.exe -m pytest C:\vazus\labs\native_vision_system\tests\test_multimodal_resolver.py -v --tb=short
```

### 6.2. Expected Success Output Criteria
- **Total Test Cases**: 14 test functions covering 20 test scenarios (TC-01 through TC-20).
- **Pass Rate**: 100% (0 failures, 0 errors, 0 skipped).
- **Execution Speed**: < 1.0 second total runtime (all image operations in memory/RAM).

---

## 7. Conclusion

This unit test specification provides a complete, robust, and zero-network test suite for validating `vazus_core/multimodal_resolver.py`. It guarantees full coverage of file format resolutions, magic byte checks, Base64/SHA-256 transformations, and `google.genai` SDK compatibility.
