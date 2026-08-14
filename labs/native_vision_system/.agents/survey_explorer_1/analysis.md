# Comprehensive Analysis: R1 Native Multimodal Image Resolver (`vazus_core.multimodal_resolver`)

## 1. Executive Summary
This document presents the survey findings and architectural specifications for **R1: Native Multimodal Image Resolver (`vazus_core.multimodal_resolver`)**, part of the **Native Terminal Multimodal Vision System** (`C:\vazus\labs\native_vision_system`).

The objective of R1 is to establish a zero-workaround, production-ready preprocessor in `vazus_core` that ingests image inputs (disk paths, raw bytes, PIL images, Base64 strings, or `@` references), validates format integrity via magic byte signatures, converts them into compliant `google.genai` inlineData payload objects (`types.Part.from_bytes`), and routes them directly to **Gemini 3.6 Flash**.

---

## 2. Environment & Dependency Audit

| Dependency / Environment | Verified Path / Version | Status & Usage |
|---|---|---|
| **Python Virtual Environment** | `C:\vazus\.venv\Scripts\python.exe` | Active project virtualenv |
| **google-genai SDK** | `google.genai` v2.14.0 | Verified. Provides `Client()`, `types.Part.from_bytes()` |
| **Pillow / PIL** | `PIL` v12.3.0 | Verified. For image loading, format fallback, aspect ratio inspection |
| **Standard Library** | `mimetypes`, `base64`, `io`, `pathlib`, `typing`, `dataclasses` | Pure Python, zero external binary dependency |
| **Active Settings & Models** | `gemini-3.6-flash` in `vazus_core.model_selector` | Configured as primary high-performance vision LLM |

---

## 3. Existing Codebase Inspection

### Key Files Examined

1. **`C:\vazus\vazus_core\google_multimodal_vision.py`**
   - **Current State**: Uses legacy/basic `client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, image_bytes])`.
   - **Limitation**: Reads raw bytes from file without polymorphic format detection, magic byte validation, or structured `types.Part.from_bytes` encapsulation. Falls back to local `Pix2Text` OCR.

2. **`C:\vazus\vazus_core\model_selector.py`**
   - Defines `AVAILABLE_MODELS` with `"gemini-3.6-flash": "Gemini 3.6 Flash (High)"`. Hot-reloads configuration and sets environment variables (`DNTS_MODEL`).

3. **`C:\vazus\vazus_core\cli_pixel_visualizer.py`**
   - Terminal visualizer using `plotext` and `PIL` image exports. Relates to R2 TUI preview rendering.

4. **`C:\vazus\tests\test_google_multimodal_vision.py`**
   - Unit tests covering vision pipeline and fallback logic.

5. **`C:\vazus\clip_ocr.py`**
   - Clipboard text extraction using `PIL.ImageGrab.grabclipboard()` and `RapidOCR`.

---

## 4. Technical Requirements for R1 (`vazus_core.multimodal_resolver`)

### 4.1. Magic Byte Inspection & MIME Type Resolution

To ensure robustness against invalid, corrupted, or misnamed image files (e.g. `.png` renamed to `.jpg`), magic byte inspection must take precedence over file extensions:

```
+-----------------------------------------------------------------------------------+
|                               Input Image Payload                                 |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
                 +-------------------------------------------------+
                 |  Tier 1: Magic Byte Signature Matching (Header) |
                 +-------------------------------------------------+
                                          |
                      +-------------------+-------------------+
                      | (Match)                               | (No Match)
                      v                                       v
        +---------------------------+           +---------------------------+
        |  Return Validated MIME    |           |  Tier 2: Pillow Inspection|
        | (image/png, jpeg, webp)   |           | (Image.open(BytesIO))     |
        +---------------------------+           +---------------------------+
                                                              |
                                          +-------------------+-------------------+
                                          | (Success)                             | (Failure)
                                          v                                       v
                            +---------------------------+           +---------------------------+
                            | Return Pillow Format MIME |           | Tier 3: Extension Hint    |
                            +---------------------------+           | (mimetypes.guess_type)    |
                                                                    +---------------------------+
```

#### Magic Byte Signatures:
- **PNG**: Starts with `b'\x89PNG\r\n\x1a\n'` (first 8 bytes) -> `image/png`
- **JPEG / JPG**: Starts with `b'\xff\xd8\xff'` (first 3 bytes) -> `image/jpeg`
- **WEBP**: Bytes 0..3 equal `b'RIFF'` AND Bytes 8..11 equal `b'WEBP'` -> `image/webp`
- **GIF** (optional): Starts with `b'GIF87a'` or `b'GIF89a'` -> `image/gif`
- **BMP** (optional): Starts with `b'BM'` -> `image/bmp`

### 4.2. Polymorphic Input Ingestion Specification

The resolver must polymorphically accept any of the following input formats:

1. **File Path (`str` or `pathlib.Path`)**:
   - Handles absolute paths (`C:\...\img.png`), relative paths, and `@` reference prefixes (`@C:\path\to\img.png`).
   - Normalizes path separators and checks `os.path.exists()`.
2. **Raw Binary Bytes (`bytes` or `bytearray`)**:
   - Direct byte stream handling.
3. **Pillow Image (`PIL.Image.Image`)**:
   - Converts PIL Image object into byte stream via `io.BytesIO()` using original format or PNG fallback.
4. **Base64 Data URI / Base64 String**:
   - Parses `data:image/png;base64,iVBORw0...` or raw base64 encoded strings into raw bytes.

### 4.3. google.genai Payload Construction Specification

The resolver must construct payloads directly compatible with `google.genai` SDK v2.14.0:

#### 1. SDK Native Part Object (`types.Part`)
```python
from google.genai import types

part = types.Part.from_bytes(
    data=image_bytes,
    mime_type=mime_type
)
```
- Internally sets `part.inline_data = types.Blob(data=image_bytes, mime_type=mime_type)`.

#### 2. Inline Data Base64 Dictionary Payload (for REST API / JSON Subagent Messages)
```python
base64_encoded_str = base64.b64encode(image_bytes).decode('utf-8')

inline_data_dict = {
    "inlineData": {
        "mimeType": mime_type,
        "data": base64_encoded_str
    }
}
```

---

## 5. Architectural Design Proposal for `multimodal_resolver.py`

### Proposed Module Structure (`vazus_core/multimodal_resolver.py`)

```python
"""
vazus_core.multimodal_resolver — Production-Ready Native Multimodal Image Resolver.
Polymorphically ingests local disk files, raw bytes, PIL Images, and Base64 strings,
inspects magic bytes, and builds compliant google.genai inlineData payloads for Gemini 3.6 Flash.
"""

from dataclasses import dataclass
import os
import io
import base64
import mimetypes
from pathlib import Path
from typing import Union, Dict, Any, Optional
from PIL import Image
from google.genai import genai, types

@dataclass
class ResolvedMultimodalPayload:
    raw_bytes: bytes
    mime_type: str
    base64_str: str
    file_path: Optional[str] = None
    
    def to_genai_part(self) -> types.Part:
        return types.Part.from_bytes(data=self.raw_bytes, mime_type=self.mime_type)
        
    def to_inline_data_dict(self) -> Dict[str, Any]:
        return {
            "inlineData": {
                "mimeType": self.mime_type,
                "data": self.base64_str
            }
        }

class MultimodalResolver:
    @staticmethod
    def inspect_mime_type(data: bytes, hint_path: Optional[str] = None) -> str:
        ...
        
    @staticmethod
    def resolve(source: Union[str, Path, bytes, Image.Image]) -> ResolvedMultimodalPayload:
        ...
        
    @classmethod
    def dispatch_to_gemini(
        cls,
        image_input: Any,
        prompt: str,
        model: str = "gemini-3.6-flash",
        client: Optional[genai.Client] = None
    ) -> Dict[str, Any]:
        ...
```

---

## 6. Conclusion & Next Steps
The technical investigation is complete and verified against the existing workspace, virtualenv (`C:\vazus\.venv`), and `google.genai` SDK v2.14.0. The specification is ready for implementation by the implementer agent.
