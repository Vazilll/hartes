# Technical Analysis & Implementation Specification: R1 Native Multimodal Image Resolver (`vazus_core/multimodal_resolver.py`)

## 1. Executive Summary
This document provides the exhaustive technical architecture, formal interface contracts, and step-by-step implementation specification for **M1: Native Multimodal Image Resolver (`vazus_core/multimodal_resolver.py`)** in `vazus_core`.

The module acts as a zero-workaround, polymorphic preprocessor that standardizes any visual input—disk paths, raw bytes, Pillow images, Base64 data URIs, or terminal `@` references—into a validated `ResolvedMultimodalPayload` ready for direct execution against **Gemini 3.6 Flash** via `google.genai.types.Part.from_bytes` or `inlineData` REST JSON blocks.

---

## 2. Polymorphic Input Ingestion Specification

The `MultimodalResolver.resolve(source)` interface must polymorphically accept four distinct input types and convert them into raw binary image bytes (`bytes`) and metadata:

```
                                    +-----------------------------------------+
                                    | Polymorphic Input `source`              |
                                    +-----------------------------------------+
                                                         |
         +------------------------+----------------------+------------------------+------------------------+
         |                        |                      |                        |                        |
         v                        v                      v                        v                        v
+------------------+     +-----------------+    +------------------+     +-----------------+     +-------------------+
|  `str` / `Path`  |     |  `str` (@ ref)  |    | `str` (Base64)   |     |     `bytes`     |     | `PIL.Image.Image` |
| File Path        |     | @clipboard, etc |    | Data URI / Raw   |     | Raw Bytes       |     | In-Memory Image   |
+------------------+     +-----------------+    +------------------+     +-----------------+     +-------------------+
         |                        |                      |                        |                        |
         v                        v                      v                        |                        v
+------------------+     +-----------------+    +------------------+              |              +-------------------+
| Read File Bytes  |     | Resolve System  |    | Decode base64 to |              |              | `image.save()` to |
| (`open('rb')`)   |     | Source to Bytes |    | raw bytes        |              |              | `io.BytesIO()`    |
+------------------+     +-----------------+    +------------------+              |              +-------------------+
         |                        |                      |                        |                        |
         +------------------------+----------------------+------------------------+------------------------+
                                                         |
                                                         v
                                       +-----------------------------------+
                                       |  Raw Binary Bytes (`raw_bytes`)   |
                                       +-----------------------------------+
```

### 2.1 Supported Input Types & Behavior

| Input Type | Trigger Condition | Conversion Logic | Failure Mode |
|---|---|---|---|
| **Local File Path** (`str` or `Path`) | String/Path pointing to existing file on disk | `Path(source).expanduser().resolve()`; read binary content via `path.read_bytes()`. | `FileNotFoundError` if path does not exist. |
| **`@` Reference** (`str`) | Starts with `@` (e.g. `@clipboard`, `@latest`, `@artifact`) | Special resolver invocation:<br>• `@clipboard`: Uses `PIL.ImageGrab.grabclipboard()` to fetch clipboard image.<br>• `@latest`: Searches working directory for newest `.png`/`.jpg`/`.webp`.<br>• `@artifact`: Resolves newest image file in artifact directory. | `ValueError("No image found in clipboard")` or `FileNotFoundError("No recent image found")`. |
| **Base64 Data URI** (`str`) | Starts with `data:image/` | Strip prefix (e.g., `data:image/png;base64,`), parse remaining string using `base64.b64decode()`. | `ValueError("Invalid Base64 Data URI")` if decoding fails. |
| **Raw Base64 String** (`str`) | Valid base64 string, not a valid file path | Attempt `base64.b64decode(source)`. Validate if decoded bytes start with valid image magic bytes. | `ValueError("Invalid Base64 string payload")` if decoding/magic bytes check fails. |
| **Raw Bytes** (`bytes` or `bytearray`) | `isinstance(source, (bytes, bytearray))` | Direct pass-through of `bytes(source)`. | `ValueError("Empty byte array")` if `len(source) == 0`. |
| **Pillow Image** (`PIL.Image.Image`) | `isinstance(source, Image.Image)` | Write PIL image object into memory buffer using `io.BytesIO()`. Preserve `img.format` if set, otherwise export as PNG. | `ValueError` if Pillow fails to serialize image. |

---

## 3. 3-Tiered Format Inspection Architecture

To guarantee accuracy even when file extensions are incorrect, missing, or stripped, MIME type detection uses a 3-tiered fallback pipeline:

```
                                  +---------------------------------------+
                                  |         Raw Image Binary Bytes        |
                                  +---------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  | Tier 1: Magic Byte Signature Matching |
                                  +---------------------------------------+
                                                      |
                                      +---------------+---------------+
                                      | Match                         | No Match
                                      v                               v
                        +---------------------------+   +---------------------------+
                        | Return Validated MIME     |   | Tier 2: Pillow Inspection |
                        | (image/png, jpeg, webp)   |   | Image.open(io.BytesIO)    |
                        +---------------------------+   +---------------------------+
                                                                      |
                                                      +---------------+---------------+
                                                      | Success                       | Failure
                                                      v                               v
                                        +---------------------------+   +---------------------------+
                                        | Return Pillow Format MIME |   | Tier 3: Extension Hint    |
                                        +---------------------------+   | mimetypes.guess_type()    |
                                                                        +---------------------------+
```

### 3.1 Tier 1: Magic Byte Signature Table

Magic byte detection operates on the first 12 bytes of `raw_bytes`:

| Format | Magic Byte Sequence (Hex) | Offset / Condition | Output MIME Type |
|---|---|---|---|
| **PNG** | `89 50 4E 47 0D 0A 1A 0A` (`b'\x89PNG\r\n\x1a\n'`) | Starts at byte 0 (8 bytes) | `image/png` |
| **JPEG** | `FF D8 FF` (`b'\xff\xd8\xff'`) | Starts at byte 0 (3 bytes) | `image/jpeg` |
| **WEBP** | `52 49 46 46` (`b'RIFF'`) & `57 45 42 50` (`b'WEBP'`) | Bytes 0..3 == `b'RIFF'` AND Bytes 8..11 == `b'WEBP'` | `image/webp` |
| **GIF** | `47 49 46 38 37 61` or `47 49 46 38 39 61` (`b'GIF87a'` / `b'GIF89a'`) | Starts at byte 0 (6 bytes) | `image/gif` |
| **BMP** | `42 4D` (`b'BM'`) | Starts at byte 0 (2 bytes) | `image/bmp` |
| **TIFF** | `49 49 2A 00` (`b'II*\x00'`) or `4D 4D 00 2A` (`b'MM\x00*'`) | Starts at byte 0 (4 bytes) | `image/tiff` |

### 3.2 Tier 2: Pillow Metadata Inspection

If Tier 1 yields no match (e.g. novel or uncommon header):
1. Load `img = Image.open(io.BytesIO(raw_bytes))`.
2. Inspect `img.format` (e.g., `'PNG'`, `'JPEG'`, `'WEBP'`, `'GIF'`, `'BMP'`, `'TIFF'`).
3. Map format string to MIME type via lookup dict:
   `{'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp', 'GIF': 'image/gif', 'BMP': 'image/bmp', 'TIFF': 'image/tiff'}`.
4. Extract image resolution (`img.width`, `img.height`).

### 3.3 Tier 3: Extension Hint Fallback

If Tier 2 fails or raises `PIL.UnidentifiedImageError`:
1. Use `mimetypes.guess_type(hint_path)` if a file path hint was provided.
2. If unknown, default to `image/png` if bytes look like image data, or raise `ValueError("Unresolvable image format")`.

---

## 4. Payload Conversion Specifications

### 4.1 google.genai Native Part Conversion (`types.Part`)

For direct SDK interaction with `google.genai` (SDK v2.14.0+):

```python
from google.genai import types

part = types.Part.from_bytes(
    data=payload.raw_bytes,
    mime_type=payload.mime_type
)
```

This encapsulates the image blob without saving to disk or using external shell processes.

### 4.2 inlineData REST / JSON Dictionary Format

For IPC serialization (WebSocket broadcasts, SQLite WAL, subagent prompt injection):

```json
{
  "inlineData": {
    "mimeType": "image/png",
    "data": "iVBORw0KGgoAAAANSUhEUgAA..."
  }
}
```

---

## 5. Formal Data Structures & API Signatures

### 5.1 Data Structure: `ResolvedMultimodalPayload`

```python
@dataclass
class ResolvedMultimodalPayload:
    raw_bytes: bytes
    mime_type: str
    base64_data: str
    sha256: str
    width: int
    height: int
    file_path: Optional[str] = None
    source_type: str = "unknown"

    @property
    def genai_part(self) -> types.Part:
        """Returns google.genai types.Part object constructed from raw bytes."""
        return types.Part.from_bytes(data=self.raw_bytes, mime_type=self.mime_type)

    def to_genai_part(self) -> types.Part:
        """Explicit method alias for genai_part property."""
        return self.genai_part

    def to_inline_data_dict(self) -> Dict[str, Any]:
        """Returns JSON-compliant inlineData dictionary block."""
        return {
            "inlineData": {
                "mimeType": self.mime_type,
                "data": self.base64_data
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        """Returns full metadata dictionary representation."""
        return {
            "sha256": self.sha256,
            "mime_type": self.mime_type,
            "width": self.width,
            "height": self.height,
            "file_path": self.file_path,
            "source_type": self.source_type,
            "byte_size": len(self.raw_bytes),
            "inline_data": self.to_inline_data_dict()
        }
```

### 5.2 Core Class: `MultimodalResolver`

```python
class MultimodalResolver:
    """
    Production-grade polymorphic image preprocessor for Gemini 3.6 Flash.
    """

    @staticmethod
    def inspect_mime_type(data: bytes, hint_path: Optional[str] = None) -> str:
        """
        Executes 3-tiered MIME type detection:
        Tier 1: Magic byte header inspection
        Tier 2: Pillow metadata inspection
        Tier 3: Extension hint via mimetypes
        """
        ...

    @staticmethod
    def resolve_at_reference(at_ref: str) -> Tuple[bytes, str, str]:
        """
        Resolves @ references (@clipboard, @latest, @artifact, @<path>).
        Returns (raw_bytes, source_type, file_path_or_identifier).
        """
        ...

    @classmethod
    def resolve(cls, source: Union[str, Path, bytes, bytearray, Image.Image]) -> ResolvedMultimodalPayload:
        """
        Main entrypoint. Ingests polymorphic image source, validates format integrity,
        computes SHA-256, extracts dimensions, and returns ResolvedMultimodalPayload.
        """
        ...

    @classmethod
    def dispatch_to_gemini(
        cls,
        image_input: Union[str, Path, bytes, Image.Image, ResolvedMultimodalPayload],
        prompt: str,
        model: str = "gemini-3.6-flash",
        client: Optional[genai.Client] = None
    ) -> Dict[str, Any]:
        """
        Resolves image and dispatches directly to Gemini 3.6 Flash via google.genai Client.
        """
        ...
```

---

## 6. Step-by-Step Implementation Guide for Implementer

1. **File Location**: `C:\vazus\vazus_core\multimodal_resolver.py`
2. **Imports Required**:
   ```python
   import os
   import sys
   import io
   import base64
   import hashlib
   import mimetypes
   from pathlib import Path
   from dataclasses import dataclass
   from typing import Union, Dict, Any, Optional, Tuple
   from PIL import Image, ImageGrab
   from google.genai import genai, types
   ```

3. **Magic Byte Checker (`_inspect_magic_bytes`)**:
   - Check `data[:8]` against `b'\x89PNG\r\n\x1a\n'`.
   - Check `data[:3]` against `b'\xff\xd8\xff'`.
   - Check `data[:4] == b'RIFF'` and `data[8:12] == b'WEBP'`.
   - Check `data[:6]` in `(b'GIF87a', b'GIF89a')`.
   - Check `data[:2] == b'BM'`.
   - Check `data[:4]` in `(b'II*\x00', b'MM\x00*')`.

4. **Dimensions & SHA-256 Extraction**:
   - Use `hashlib.sha256(raw_bytes).hexdigest()`.
   - Use `Image.open(io.BytesIO(raw_bytes))` to get `(width, height)`.

5. **`@` Reference Resolvers**:
   - `@clipboard`: Call `ImageGrab.grabclipboard()`. If result is `Image.Image`, convert to PNG bytes. If result is list of filenames, take first image path. If `None`, raise `ValueError("No image data in clipboard")`.
   - `@latest`: Search `os.getcwd()` for files matching `*.png`, `*.jpg`, `*.jpeg`, `*.webp`. Sort by `os.path.getmtime`, return newest.
   - `@artifact`: Search `C:\Users\Vaz\.gemini\antigravity-cli\brain` or workspace artifacts for newest image file.

6. **Base64 / Data URI Resolution**:
   - If `source.startswith("data:image/")`, split by `,`, decode payload.
   - Else if string is not an existing file path, attempt `base64.b64decode`. If successful and magic bytes match, accept as raw bytes.

---

## 7. Verification & Invalidation Conditions

- **Independent Verification Method**:
  Run pytest on `C:\vazus\labs\native_vision_system\tests\test_multimodal_resolver.py` using `C:\vazus\.venv\Scripts\python.exe -m pytest`.
- **Invalidation Conditions**:
  - Failure to correctly identify a `.png` file renamed to `.jpg`.
  - Failure to decode a Base64 data URI string into `inlineData`.
  - Missing `sha256`, `width`, or `height` fields in `ResolvedMultimodalPayload`.
  - `to_inline_data_dict()` returning invalid schema for `google.genai`.
