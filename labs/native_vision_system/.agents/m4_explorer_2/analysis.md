# E2E Test Suite Specification: Tier 1 (Feature Coverage) & Tier 2 (Boundary & Corner Cases)

**Author**: M4 Explorer 2 (E2E Tier 1 & 2 Test Case Specifier)  
**Project**: Native Terminal Multimodal Vision System (`C:\vazus\labs\native_vision_system`)  
**Date**: 2026-08-05  

---

## 1. Executive Summary & Overview

This specification defines the exhaustive test case catalog for **Tier 1 (Feature Coverage, $\ge 5$ test cases per feature)** and **Tier 2 (Boundary & Corner Cases)** of the End-to-End (E2E) Test Suite for the Native Terminal Multimodal Vision System.

The vision system consists of three core functional modules:
1. **R1: Native Multimodal Image Resolver** (`vazus_core.multimodal_resolver`)
2. **R2: TUI Terminal Preview Renderer** (`vazus_core.tui_preview_renderer`)
3. **R3: Real-Time Vision Daemon** (`vazus_vision_daemon.py`)

This test specification covers **55 Tier 1 Test Cases** (spanning 11 distinct features across R1, R2, R3) and **30 Tier 2 Boundary Test Cases** (spanning 6 edge categories: empty inputs, zero/extreme dimensions, corrupt payloads, invalid `@` references, terminal viewport extremes, and rapid clipboard/IPC stress).

---

## 2. Architecture & Feature Mapping

```
+---------------------------------------------------------------------------------------------------+
|                                 E2E TEST HARNESS (Tiers 1 & 2)                                    |
+---------------------------------------------------------------------------------------------------+
                                                  |
         +----------------------------------------+----------------------------------------+
         |                                        |                                        |
         v                                        v                                        v
+----------------------------------+  +-----------------------------------+  +------------------------------------+
|  MODULE R1: Multimodal Resolver  |  |   MODULE R2: TUI Preview Renderer |  |   MODULE R3: Vision Daemon         |
|  - Feature 1: File Preprocessor  |  |   - Feature 4: TrueColor Renderer |  |   - Feature 8: Win32 Listener      |
|  - Feature 2: InlineData Encoder |  |   - Feature 5: ANSI RLE Buffer    |  |   - Feature 9: File Watcher        |
|  - Feature 3: @ Reference Resolver|  |   - Feature 6: Aspect Ratio Math  |  |   - Feature 10: Payload Generator  |
|                                  |  |   - Feature 7: Fallback ASCII/256 |  |   - Feature 11: IPC & WS Broadcast |
+----------------------------------+  +-----------------------------------+  +------------------------------------+
```

### Feature Inventory & Coverage Matrix

| Feature ID | Feature Name | Core Module | Target Subsystem | Tier 1 Count | Tier 2 Count |
|---|---|---|---|---|---|
| **F01** | Polymorphic File Preprocessor | `vazus_core.multimodal_resolver` | R1 Resolver | 5 | 5 |
| **F02** | InlineData Base64 Part Encoder | `vazus_core.multimodal_resolver` | R1 Resolver | 5 | 3 |
| **F03** | `@` Reference Resolver | `vazus_core.multimodal_resolver` | R1 Resolver | 5 | 5 |
| **F04** | TrueColor Half-Block Renderer | `vazus_core.tui_preview_renderer` | R2 Renderer | 5 | 2 |
| **F05** | ANSI RLE Double-Buffering | `vazus_core.tui_preview_renderer` | R2 Renderer | 5 | 2 |
| **F06** | Aspect Ratio & Bounding Box | `vazus_core.tui_preview_renderer` | R2 Renderer | 5 | 5 |
| **F07** | Fallback ASCII & 256-Color | `vazus_core.tui_preview_renderer` | R2 Renderer | 5 | 2 |
| **F08** | Win32 Clipboard Listener | `vazus_vision_daemon.py` | R3 Daemon | 5 | 3 |
| **F09** | Workspace File Watcher | `vazus_vision_daemon.py` | R3 Daemon | 5 | 2 |
| **F10** | Visual Token Payload Generator | `vazus_vision_daemon.py` | R3 Daemon | 5 | 2 |
| **F11** | IPC & WebSocket Broadcast | `vazus_vision_daemon.py` | R3 Daemon | 5 | 4 |
| **TOTAL** | **11 Core Features** | — | — | **55** | **30** |

---

## 3. Tier 1: Feature Coverage Specifications ($\ge 5$ per feature)

### 3.1 Feature 1: Polymorphic File Preprocessor (R1)

#### `TC-T1-F01-01`: Magic Byte PNG Ingestion
- **Target**: `MultimodalResolver.resolve()` & `MultimodalResolver.inspect_mime_type()`
- **Preconditions**: Valid 8-byte PNG header `\x89PNG\r\n\x1a\n` in sample image `test_sample.png`.
- **Input**: Path `Path("tests/assets/test_sample.png")`.
- **Execution**: Pass path to `MultimodalResolver.resolve(path)`.
- **Assertions**:
  - `payload.mime_type == "image/png"`
  - `payload.raw_bytes[:8] == b"\x89PNG\r\n\x1a\n"`
  - `payload.file_path` contains normalized string representation of path.

#### `TC-T1-F01-02`: Magic Byte JPEG Ingestion
- **Target**: `MultimodalResolver.inspect_mime_type()`
- **Preconditions**: Valid JPEG byte stream starting with `\xFF\xD8\xFF`.
- **Input**: Raw bytes of JPEG file `test_sample.jpg`.
- **Execution**: Pass `bytes` to `MultimodalResolver.resolve(bytes_data)`.
- **Assertions**:
  - `payload.mime_type == "image/jpeg"`
  - `payload.raw_bytes[:3] == b"\xFF\xD8\xFF"`

#### `TC-T1-F01-03`: Magic Byte WebP Ingestion
- **Target**: `MultimodalResolver.inspect_mime_type()`
- **Preconditions**: Valid WebP file header (bytes 0..3 `RIFF`, bytes 8..11 `WEBP`).
- **Input**: Path to `test_sample.webp`.
- **Execution**: Pass path to `MultimodalResolver.resolve(path)`.
- **Assertions**:
  - `payload.mime_type == "image/webp"`
  - `payload.raw_bytes[:4] == b"RIFF"`
  - `payload.raw_bytes[8:12] == b"WEBP"`

#### `TC-T1-F01-04`: Mismatched File Extension Resolution (Magic Bytes Precedence)
- **Target**: `MultimodalResolver.inspect_mime_type()`
- **Preconditions**: A PNG image file saved with `.jpg` extension (`renamed_png.jpg`).
- **Input**: File path `renamed_png.jpg`.
- **Execution**: Pass path to `MultimodalResolver.resolve("renamed_png.jpg")`.
- **Assertions**:
  - `payload.mime_type == "image/png"` (Magic byte inspection overrides `.jpg` extension hint).
  - Extension hint does not override byte signature.

#### `TC-T1-F01-05`: Tier 2 Pillow Metadata Fallback Resolution
- **Target**: `MultimodalResolver.inspect_mime_type()`
- **Preconditions**: Image format without standard 8-byte magic header (e.g. BMP or GIF) passed as byte stream.
- **Input**: Raw bytes of a valid BMP image (`b"BM..."`).
- **Execution**: Pass bytes to `MultimodalResolver.resolve(bmp_bytes)`.
- **Assertions**:
  - Magic byte primary check falls back to Tier 2 Pillow inspection (`PIL.Image.open(BytesIO)`).
  - `payload.mime_type` correctly resolves to `"image/bmp"` or converted PNG format.

---

### 3.2 Feature 2: InlineData Base64 Part Encoder (R1)

#### `TC-T1-F02-01`: `to_inline_data_dict()` Schema Compliance
- **Target**: `ResolvedMultimodalPayload.to_inline_data_dict()`
- **Preconditions**: `ResolvedMultimodalPayload` instantiated with sample PNG bytes.
- **Execution**: Call `payload.to_inline_data_dict()`.
- **Assertions**:
  - Returned dict contains top-level key `"inlineData"`.
  - `"inlineData"` dict contains keys `"mimeType"` and `"data"`.
  - `"mimeType" == "image/png"`.
  - `"data"` is valid Base64 encoded string matching `base64.b64encode(raw_bytes).decode("utf-8")`.

#### `TC-T1-F02-02`: `to_genai_part()` Instantiation
- **Target**: `ResolvedMultimodalPayload.to_genai_part()`
- **Preconditions**: `google.genai.types.Part` available.
- **Execution**: Call `payload.to_genai_part()`.
- **Assertions**:
  - Returned object is instance of `google.genai.types.Part`.
  - `part.inline_data.mime_type == payload.mime_type`.
  - `part.inline_data.data == payload.raw_bytes`.

#### `TC-T1-F02-03`: Base64 Round-Trip Integrity
- **Target**: `ResolvedMultimodalPayload`
- **Preconditions**: 100KB binary image byte array.
- **Execution**: Resolve payload, retrieve `base64_str`, decode via `base64.b64decode()`.
- **Assertions**:
  - Decoded bytes match original input bytes byte-for-byte (`decoded == raw_bytes`).
  - No trailing padding corruption or line-break insertion.

#### `TC-T1-F02-04`: SHA-256 Digest Calculation
- **Target**: `ResolvedMultimodalPayload.sha256`
- **Preconditions**: Known image file with expected SHA-256 checksum.
- **Execution**: Resolve payload and inspect `payload.sha256`.
- **Assertions**:
  - `payload.sha256 == hashlib.sha256(raw_bytes).hexdigest()`.
  - Length of `payload.sha256` is exactly 64 hexadecimal characters.

#### `TC-T1-F02-05`: Ingestion of `PIL.Image.Image` Objects
- **Target**: `MultimodalResolver.resolve()`
- **Preconditions**: Memory-created `PIL.Image.new("RGB", (100, 100), color="red")`.
- **Execution**: Pass `PIL.Image` instance directly to `MultimodalResolver.resolve(pil_img)`.
- **Assertions**:
  - Payload resolves without throwing disk read errors.
  - `payload.width == 100`, `payload.height == 100`.
  - `payload.mime_type` defaults to `"image/png"`.

---

### 3.3 Feature 3: `@` Reference Resolver (R1)

#### `TC-T1-F03-01`: Disk File Path Resolution (`str` and `Path`)
- **Target**: `MultimodalResolver.resolve()`
- **Preconditions**: Image file exists at `tests/assets/sample.png`.
- **Execution**: Call `MultimodalResolver.resolve("tests/assets/sample.png")`.
- **Assertions**:
  - Returns `ResolvedMultimodalPayload` with populated `file_path`.
  - Absolute path normalization matches `os.path.abspath("tests/assets/sample.png")`.

#### `TC-T1-F03-02`: `@clipboard` / `@clip` RAM Ingestion
- **Target**: `MultimodalResolver.resolve("@clipboard")`
- **Preconditions**: Windows clipboard loaded with a `PIL.Image` via mock/win32.
- **Execution**: Call `MultimodalResolver.resolve("@clipboard")`.
- **Assertions**:
  - Successfully retrieves bitmap from clipboard RAM without disk temporary file residue.
  - Returns `ResolvedMultimodalPayload` with `file_path == None` or `"RAM_CLIPBOARD"`.

#### `TC-T1-F03-03`: `@latest` / `@last` Workspace Resolution
- **Target**: `MultimodalResolver.resolve("@latest")`
- **Preconditions**: Workspace contains `img_1.png` (modified 10m ago) and `img_2.jpg` (modified 1s ago).
- **Execution**: Call `MultimodalResolver.resolve("@latest")`.
- **Assertions**:
  - Selects `img_2.jpg` based on latest `st_mtime`.
  - `payload.file_path` ends with `img_2.jpg`.

#### `TC-T1-F03-04`: `@artifact:<name>` Brain Artifact Resolution
- **Target**: `MultimodalResolver.resolve("@artifact:preview_chart")`
- **Preconditions**: Artifact PNG `preview_chart.png` exists in active artifact search directory.
- **Execution**: Call `MultimodalResolver.resolve("@artifact:preview_chart")`.
- **Assertions**:
  - Resolves target artifact file path.
  - `payload.mime_type == "image/png"`.

#### `TC-T1-F03-05`: `@` Path Prefix Stripping (`@C:\path\to\img.png`)
- **Target**: `MultimodalResolver.resolve("@C:/vazus/labs/native_vision_system/tests/assets/sample.png")`
- **Preconditions**: File exists at specified path.
- **Execution**: Pass `@` prefixed path to resolver.
- **Assertions**:
  - Resolver strips leading `@` character and resolves underlying disk path.
  - Returns valid `ResolvedMultimodalPayload`.

---

### 3.4 Feature 4: TrueColor Half-Block Renderer (R2)

#### `TC-T1-F04-01`: Half-Block Unicode Character Usage
- **Target**: `TUIPreviewRenderer.render()`
- **Preconditions**: Valid `ResolvedMultimodalPayload` or `PIL.Image`.
- **Execution**: `renderer.render(payload, mode="truecolor")`.
- **Assertions**:
  - Returned string contains Unicode upper half-block characters `▀` (`U+2580`).
  - Does not contain standard ASCII placeholder boxes unless in fallback mode.

#### `TC-T1-F04-02`: 24-Bit Escape Code Syntax (`\x1b[38;2;R;G;Bm` / `\x1b[48;2;R;G;Bm`)
- **Target**: `TUIPreviewRenderer.render()`
- **Preconditions**: TrueColor mode active.
- **Execution**: Render a 2x2 colored image.
- **Assertions**:
  - Output string contains foreground TrueColor codes matching regex `\x1b\[38;2;\d{1,3};\d{1,3};\d{1,3}m`.
  - Output string contains background TrueColor codes matching regex `\x1b\[48;2;\d{1,3};\d{1,3};\d{1,3}m`.

#### `TC-T1-F04-03`: Subpixel Top/Bottom Color Mapping
- **Target**: `TUIPreviewRenderer._render_half_block_matrix()`
- **Preconditions**: Image with top row Red `(255, 0, 0)` and bottom row Blue `(0, 0, 255)`.
- **Execution**: Render 1-column, 1-row cell (height 2 pixels).
- **Assertions**:
  - Cell top pixel (Red) maps to FG color `\x1b[38;2;255;0;0m`.
  - Cell bottom pixel (Blue) maps to BG color `\x1b[48;2;0;0;255m`.
  - Character rendered is `▀`.

#### `TC-T1-F04-04`: 2x2 Primary Colors Rendering
- **Target**: `TUIPreviewRenderer.render()`
- **Preconditions**: 2x2 PNG image with Red (top-left), Green (top-right), Blue (bottom-left), Yellow (bottom-right).
- **Execution**: Render with `max_cols=2, max_rows=1`.
- **Assertions**:
  - Cell 1: FG Red, BG Blue.
  - Cell 2: FG Green, BG Yellow.
  - Total rendered output consists of 1 line containing 2 half-block cells.

#### `TC-T1-F04-05`: Alpha Channel Background Compositing
- **Target**: `TUIPreviewRenderer.render()`
- **Preconditions**: RGBA image with 50% transparent pixels `(255, 255, 255, 128)`.
- **Execution**: Render with default dark background `#0B0D0E` `(11, 13, 14)`.
- **Assertions**:
  - Semi-transparent pixels are alpha-blended against `#0B0D0E`.
  - Evaluated RGB color values equal `round(255*0.5 + 11*0.5) == 133`.

---

### 3.5 Feature 5: ANSI RLE Double-Buffering (R2)

#### `TC-T1-F05-01`: RLE ANSI Payload Compression Efficiency
- **Target**: `TUIPreviewRenderer` RLE optimizer
- **Preconditions**: Solid color 80x40 image (all pixels Red `(255, 0, 0)`).
- **Execution**: Render with RLE enabled vs unoptimized per-pixel rendering.
- **Assertions**:
  - RLE output size is $>60\%$ smaller than unoptimized output size.
  - RLE string emits FG/BG ANSI codes only once per row instead of 80 times.

#### `TC-T1-F05-02`: Consecutive Horizontal Run Batching
- **Target**: `TUIPreviewRenderer._render_half_block_matrix()`
- **Preconditions**: Row of 10 identical blue half-block subpixel pairs followed by 10 red pairs.
- **Execution**: Inspect generated ANSI stream for row.
- **Assertions**:
  - Stream contains 1 Blue ANSI sequence -> 10 `▀` characters -> 1 Red ANSI sequence -> 10 `▀` characters.
  - No intermediate ANSI escape codes occur between identical characters.

#### `TC-T1-F05-03`: Color Transition Flush Logic
- **Target**: `TUIPreviewRenderer` RLE state machine
- **Preconditions**: Pattern alternating pixel colors `Red -> Blue -> Red -> Blue`.
- **Execution**: Render row.
- **Assertions**:
  - State machine correctly flushes previous run and updates current FG/BG state on every color change.
  - Rendered output visual appearance is identical to non-RLE output.

#### `TC-T1-F05-04`: Frame Double-Buffering Repaint Suppression
- **Target**: `TUIPreviewRenderer` double-buffer
- **Preconditions**: Two identical consecutive frames passed to renderer.
- **Execution**: Call `render()` on frame 1, then `render()` on frame 2 with double-buffering active.
- **Assertions**:
  - Frame 2 returns empty string `""` or minimal diff sequence indicating zero redraw required.

#### `TC-T1-F05-05`: Line End ANSI Reset Termination
- **Target**: `TUIPreviewRenderer.render()`
- **Preconditions**: Any image render output.
- **Execution**: Inspect each line ending in output string.
- **Assertions**:
  - Every row string ends with ANSI reset code `\x1b[0m` prior to `\n`.
  - Prevents terminal background color bleeding into subsequent CLI prompt lines.

---

### 3.6 Feature 6: Aspect Ratio & Bounding Box (R2)

#### `TC-T1-F06-01`: 16:9 Landscape Aspect Ratio Scaling
- **Target**: `compute_preview_dimensions()`
- **Preconditions**: Image resolution 1920x1080 (16:9), terminal max bounds 80x40.
- **Execution**: Call `compute_preview_dimensions(1920, 1080, max_term_w=80, max_term_h=40, is_half_block=True)`.
- **Assertions**:
  - `cell_cols == 80`.
  - `cell_rows == 23` ($80 / (16/9) \approx 22.5 \rightarrow 23$).
  - Returned grid fits strictly within max bounds ($80 \le 80$, $23 \le 40$).

#### `TC-T1-F06-02`: 9:16 Portrait Aspect Ratio Scaling
- **Target**: `compute_preview_dimensions()`
- **Preconditions**: Image resolution 1080x1920 (9:16), terminal max bounds 80x40.
- **Execution**: Call `compute_preview_dimensions(1080, 1920, max_term_w=80, max_term_h=40, is_half_block=True)`.
- **Assertions**:
  - `cell_rows == 40` (height constrained).
  - `cell_cols == 23` ($40 \times (9/16) \approx 22.5 \rightarrow 23$).
  - Returned grid fits strictly within max bounds ($23 \le 80$, $40 \le 40$).

#### `TC-T1-F06-03`: 1:1 Square Subpixel Geometry Verification
- **Target**: `compute_preview_dimensions()`
- **Preconditions**: 1:1 square image (1000x1000 px).
- **Execution**: Compute half-block dimensions for 80x40 viewport.
- **Assertions**:
  - `cell_cols == 40`, `cell_rows == 40`.
  - Sampled pixel dimensions: `sampled_pixel_w == 40`, `sampled_pixel_h == 80`.
  - Ratio of sampled pixels $40 / 80 = 0.5$, which when combined with character aspect ratio 0.5 results in exact 1.0 square visual geometry.

#### `TC-T1-F06-04`: Viewport Bounding Box Clamp
- **Target**: `TUIPreviewRenderer.render()`
- **Preconditions**: Huge image 4000x4000 px, `max_cols=50`, `max_rows=20`.
- **Execution**: Render image preview.
- **Assertions**:
  - Output string row count is $\le 20$.
  - Output string maximum column width is $\le 50$.

#### `TC-T1-F06-05`: Small Image Dimension Handling
- **Target**: `compute_preview_dimensions()`
- **Preconditions**: Small image 20x10 px, max bounds 80x40.
- **Execution**: Compute preview dimensions.
- **Assertions**:
  - Retains original scale or scales up proportionally without throwing zero-division errors.
  - `cell_cols >= 1`, `cell_rows >= 1`.

---

### 3.7 Feature 7: Fallback ASCII & 256-Color Ramps (R2)

#### `TC-T1-F07-01`: 256-Color RGB Quantization Mapping
- **Target**: `TUIPreviewRenderer` 256-color quantizer
- **Preconditions**: RGB color `(255, 0, 0)` (Pure Red).
- **Execution**: Quantize RGB to 8-bit ANSI index.
- **Assertions**:
  - Maps to 6x6x6 cube index `196` ($16 + 36\times 5 + 6\times 0 + 0$).

#### `TC-T1-F07-02`: 256-Color Escape Syntax Generation
- **Target**: `TUIPreviewRenderer.render(mode="256")`
- **Preconditions**: Mode explicitly set to `"256"`.
- **Execution**: Render sample image.
- **Assertions**:
  - Generated ANSI stream contains `\x1b[38;5;{index}m` and `\x1b[48;5;{index}m`.
  - Does NOT contain 24-bit TrueColor sequences (`\x1b[38;2;...`).

#### `TC-T1-F07-03`: 10-Character ASCII Ramp Luminance Mapping
- **Target**: `TUIPreviewRenderer._render_ascii_matrix()`
- **Preconditions**: Ramp `" .:-=+*#%@"`.
- **Execution**: Test luminance values $L=0$ (black) and $L=255$ (white).
- **Assertions**:
  - $L=0$ maps to character `' '` (space).
  - $L=255$ maps to character `'@'`.
  - Mid luminance $L=128$ maps to mid character `'='` or `'*'`.

#### `TC-T1-F07-04`: 17-Character Neo3dEngine ASCII Ramp
- **Target**: `TUIPreviewRenderer._render_ascii_matrix()`
- **Preconditions**: Ramp `" .:!/r(l1Z4H9W8$@"`.
- **Execution**: Render grayscale gradient image.
- **Assertions**:
  - Correctly indexes across all 17 characters based on $L = 0.299R + 0.587G + 0.114B$.

#### `TC-T1-F07-05`: 70-Character High-Density ASCII Ramp
- **Target**: `TUIPreviewRenderer.render(mode="ascii_70")`
- **Preconditions**: 70-char ramp active.
- **Execution**: Render sample image.
- **Assertions**:
  - Uses full range of 70 ASCII characters.
  - Output string contains plain ASCII printable characters (ASCII range 32..126) with zero ANSI escape codes.

---

### 3.8 Feature 8: Win32 Clipboard Listener (R3)

#### `TC-T1-F08-01`: Win32 HWND Registration & Message Loop
- **Target**: `ClipboardListenerWindow` in `vazus_vision_daemon.py`
- **Preconditions**: Running on Windows OS environment (`win32gui` available).
- **Execution**: Instantiate `ClipboardListenerWindow` and start message pump.
- **Assertions**:
  - Creates valid `HWND_MESSAGE` window handle.
  - `AddClipboardFormatListener(hwnd)` returns non-zero success status.

#### `TC-T1-F08-02`: `WM_CLIPBOARDUPDATE` (0x031D) Event Dispatch
- **Target**: `ClipboardListenerWindow._wnd_proc()`
- **Preconditions**: Listener active.
- **Execution**: Post synthetic `WM_CLIPBOARDUPDATE` message to HWND queue.
- **Assertions**:
  - `_wnd_proc` intercepts message code `0x031D`.
  - Dispatches async callback task to main `asyncio` event loop.

#### `TC-T1-F08-03`: RAM Clipboard Image Capture on `Win+Shift+S`
- **Target**: `vazus_vision_daemon.py` clipboard handler
- **Preconditions**: Copy PNG image to Windows clipboard.
- **Execution**: Trigger clipboard watcher callback.
- **Assertions**:
  - `PIL.ImageGrab.grabclipboard()` returns valid `PIL.Image` instance.
  - Event `source` identified as `"CLIPBOARD_RAM"`.

#### `TC-T1-F08-04`: Non-Image Clipboard Ignoration
- **Target**: `vazus_vision_daemon.py` clipboard handler
- **Preconditions**: Copy plain text `"Hello World"` to clipboard.
- **Execution**: Trigger clipboard watcher callback.
- **Assertions**:
  - `grabclipboard()` returns `None` or string.
  - Daemon ignores event and emits ZERO vision tokens.

#### `TC-T1-F08-05`: Clipboard Event Processing Latency (<5ms OS Catch)
- **Target**: `vazus_vision_daemon.py` latency tracker
- **Preconditions**: High-precision timer (`time.perf_counter()`).
- **Execution**: Post clipboard update and measure time until callback entry.
- **Assertions**:
  - OS event capture latency is $<5\text{ms}$.

---

### 3.9 Feature 9: Workspace File Watcher (R3)

#### `TC-T1-F09-01`: Disk Image Addition Detection
- **Target**: `WorkspaceImageFileFilter` & `watchfiles` integration
- **Preconditions**: Daemon watching `C:\vazus\labs\native_vision_system`.
- **Execution**: Create new file `test_drop.png` in workspace directory.
- **Assertions**:
  - `watchfiles` yields `Change.added` event for `test_drop.png`.
  - Event callback triggered.

#### `TC-T1-F09-02`: Disk Image Modification Detection
- **Target**: `WorkspaceImageFileFilter`
- **Preconditions**: File `test_drop.jpg` exists in workspace.
- **Execution**: Overwrite `test_drop.jpg` with updated image bytes.
- **Assertions**:
  - `watchfiles` yields `Change.modified` event.
  - Event callback triggered with updated path.

#### `TC-T1-F09-03`: Non-Image File Extension Filtering
- **Target**: `WorkspaceImageFileFilter`
- **Preconditions**: Daemon watching workspace.
- **Execution**: Create `script.py` and `notes.txt` in workspace.
- **Assertions**:
  - `WorkspaceImageFileFilter` returns `False`.
  - No vision processing triggered.

#### `TC-T1-F09-04`: Ignored System Directory Path Filtering
- **Target**: `WorkspaceImageFileFilter`
- **Preconditions**: Daemon watching workspace.
- **Execution**: Add `.png` image inside `.git/`, `.agents/`, or `.venv/`.
- **Assertions**:
  - Filter detects ignored path segments and returns `False`.
  - Prevents recursive daemon loops inside agent metadata dirs.

#### `TC-T1-F09-05`: File Watcher Debouncing (100ms Debounce)
- **Target**: `watch_workspace_images()`
- **Preconditions**: File write stream operating in 5KB chunks.
- **Execution**: Write file in 10 rapid chunks over 50ms.
- **Assertions**:
  - Debounce window merges chunks into a SINGLE file modification event.

---

### 3.10 Feature 10: Visual Token Payload Generator (R3)

#### `TC-T1-F10-01`: Payload JSON Schema Compliance
- **Target**: `vazus_vision_daemon.py` payload builder
- **Preconditions**: Sample PNG event processed.
- **Execution**: Build vision event payload dictionary.
- **Assertions**:
  - Dictionary contains required fields: `event_id`, `timestamp`, `source`, `dedup`, `image_metadata`, `visual_tokens`, `tui_preview`, `fast_ocr`.
  - `event_id` matches pattern `vvis_\d+_[a-f0-9]+`.

#### `TC-T1-F10-02`: SHA-256 Deduplication Cache Hit
- **Target**: `ImageDeduplicator` LRU cache
- **Preconditions**: Process image `A` (SHA-256 `hashA`).
- **Execution**: Process identical image `A` again within 300s TTL.
- **Assertions**:
  - Cache lookup returns `True`.
  - Payload sets `dedup.is_duplicate = True`.

#### `TC-T1-F10-03`: RapidOCR Text Extraction Integration
- **Target**: `fast_ocr` block in payload generator
- **Preconditions**: Image containing text `"ERROR 404 NOT FOUND"`.
- **Execution**: Pass image through daemon payload pipeline.
- **Assertions**:
  - `fast_ocr.engine == "rapidocr"`.
  - `fast_ocr.has_text == True`.
  - `fast_ocr.extracted_text` contains `"ERROR 404 NOT FOUND"`.

#### `TC-T1-F10-04`: Embedded TUI Preview Generation
- **Target**: `tui_preview` block in payload generator
- **Preconditions**: Valid image event.
- **Execution**: Inspect `tui_preview` payload fields.
- **Assertions**:
  - `tui_preview.ansi_string` contains valid 24-bit half-block ANSI sequence.
  - `tui_preview.ascii_matrix` populated.

#### `TC-T1-F10-05`: Total Tokenization Latency Budget (<500ms)
- **Target**: Full daemon pipeline execution
- **Preconditions**: 1920x1080 PNG image event.
- **Execution**: Measure total duration from event detection to payload completion.
- **Assertions**:
  - Total elapsed time is $<500\text{ms}$ (typical target $75\text{ms}-180\text{ms}$).

---

### 3.11 Feature 11: IPC & WebSocket Broadcast (R3)

#### `TC-T1-F11-01`: WebSocket Server Endpoint Handshake
- **Target**: `vazus_vision_daemon.py` WebSocket server
- **Preconditions**: Daemon active on `ws://127.0.0.1:8765/ws/vision`.
- **Execution**: Connect client via `websockets.connect()`.
- **Assertions**:
  - Connection accepted with HTTP status 101 Switching Protocols.

#### `TC-T1-F11-02`: Real-Time Event Broadcast Delivery
- **Target**: WebSocket broadcast loop
- **Preconditions**: 1 client connected to `ws://127.0.0.1:8765/ws/vision`.
- **Execution**: Emit new vision payload from daemon.
- **Assertions**:
  - Connected client receives JSON payload message in $<2\text{ms}$.
  - Parsed JSON matches emitted payload.

#### `TC-T1-F11-03`: SQLite WAL Event Stream Logging
- **Target**: `vision_event_stream` table in `memory/vazus.db`
- **Preconditions**: SQLite DB connection in WAL mode.
- **Execution**: Emit vision payload.
- **Assertions**:
  - Row inserted into `vision_event_stream`.
  - `SELECT * FROM vision_event_stream WHERE event_id = ?` returns matching record.

#### `TC-T1-F11-04`: SQLite SHA-256 Index Verification
- **Target**: `idx_vision_event_sha256` index
- **Preconditions**: 1000 event rows in DB.
- **Execution**: Query event by SHA-256 digest using `EXPLAIN QUERY PLAN`.
- **Assertions**:
  - Query plan indicates `USING INDEX idx_vision_event_sha256`.

#### `TC-T1-F11-05`: Multi-Client Concurrent Broadcast
- **Target**: WebSocket server manager
- **Preconditions**: 5 subagent clients connected simultaneously.
- **Execution**: Emit vision event.
- **Assertions**:
  - All 5 clients receive identical event payload concurrently without dropped frames or server exceptions.

---

## 4. Tier 2: Boundary & Corner Case Specifications (30 Edge Cases)

### 4.1 Category A: Empty Files & References (5 Cases)

#### `TC-T2-EMP-01`: 0-Byte Disk Image File (`empty.png`)
- **Category**: Empty Input Handling
- **Target**: `MultimodalResolver.resolve()`
- **Preconditions**: Create empty 0-byte file `tests/assets/empty.png`.
- **Execution**: Call `MultimodalResolver.resolve("tests/assets/empty.png")`.
- **Expected Behavior**: Catches `EmptyFileError` / `ValueError`, returns structured error payload `{"status": "error", "code": "EMPTY_FILE", "message": "File is 0 bytes"}` without unhandled crash.

#### `TC-T2-EMP-02`: Empty Byte Array (`b""`) Ingestion
- **Category**: Empty Input Handling
- **Target**: `MultimodalResolver.resolve(b"")`
- **Execution**: Pass empty `bytes` object to resolver.
- **Expected Behavior**: Raises `ValueError("Cannot resolve empty byte stream")` caught by payload wrapper.

#### `TC-T2-EMP-03`: Whitespace / Empty String Path (`"   "`)
- **Category**: Empty Input Handling
- **Target**: `MultimodalResolver.resolve("   ")`
- **Execution**: Pass whitespace path to resolver.
- **Expected Behavior**: Raises `FileNotFoundError` or `ValueError("Invalid path")` gracefully.

#### `TC-T2-EMP-04`: `@clipboard` Resolution with Empty Clipboard
- **Category**: Empty Input Handling
- **Target**: `MultimodalResolver.resolve("@clipboard")`
- **Preconditions**: Windows clipboard cleared (0 bytes, no image/text).
- **Execution**: Resolve `@clipboard`.
- **Expected Behavior**: Catches `ClipboardEmptyError`, returns payload indicating `"clipboard_empty": true`.

#### `TC-T2-EMP-05`: `@latest` Reference in Empty Workspace Directory
- **Category**: Empty Input Handling
- **Target**: `MultimodalResolver.resolve("@latest")`
- **Preconditions**: Target directory contains 0 `.png`/`.jpg`/`.webp` files.
- **Execution**: Resolve `@latest`.
- **Expected Behavior**: Raises `NoImagesFoundError("No image files present in workspace directory")`.

---

### 4.2 Category B: Zero-Size & Extreme Dimensions (5 Cases)

#### `TC-T2-DIM-01`: 1x1 Single Pixel Image Ingestion
- **Category**: Dimension Boundaries
- **Target**: `MultimodalResolver` & `TUIPreviewRenderer`
- **Preconditions**: Valid 1x1 PNG image.
- **Execution**: Resolve payload and render preview.
- **Expected Behavior**: Resolves successfully. Render outputs exactly 1 half-block character cell without index array out of bounds.

#### `TC-T2-DIM-02`: 0x0 Pixel Pillow Header Image
- **Category**: Dimension Boundaries
- **Target**: `TUIPreviewRenderer.render()` & `compute_preview_dimensions()`
- **Preconditions**: Corrupt image header with width=0 or height=0.
- **Execution**: Pass to `compute_preview_dimensions(0, 0)`.
- **Expected Behavior**: Sanitizes input dimensions, prevents ZeroDivisionError ($\text{aspect} = 0/0$), returns minimum 1x1 grid or raises `InvalidDimensionsError`.

#### `TC-T2-DIM-03`: Ultra-Wide Aspect Ratio Image (10000x1 px)
- **Category**: Dimension Boundaries
- **Target**: `compute_preview_dimensions()`
- **Preconditions**: Image 10000 px wide, 1 px tall.
- **Execution**: Compute preview bounds for 80x40 viewport.
- **Expected Behavior**: Clamps columns to `max_cols == 80`, sets rows to minimum `1`. Aspect ratio calculation does not buffer overflow.

#### `TC-T2-DIM-04`: Ultra-Tall Aspect Ratio Image (1x10000 px)
- **Category**: Dimension Boundaries
- **Target**: `compute_preview_dimensions()`
- **Preconditions**: Image 1 px wide, 10000 px tall.
- **Execution**: Compute preview bounds for 80x40 viewport.
- **Expected Behavior**: Clamps rows to `max_rows == 40`, sets columns to minimum `1`.

#### `TC-T2-DIM-05`: Extreme Resolution Image (16384x16384 px)
- **Category**: Dimension Boundaries & Memory Safety
- **Target**: `MultimodalResolver` & `TUIPreviewRenderer`
- **Preconditions**: 16K x 16K PNG file (uncompressed ~768MB RAM).
- **Execution**: Process image through resolver and renderer.
- **Expected Behavior**: Downsamples safely using draft/thumbnail mode in PIL (`img.thumbnail((80, 80))`), maintaining peak RAM consumption $<50\text{MB}$.

---

### 4.3 Category C: Corrupt Bytes & Partial Writes (5 Cases)

#### `TC-T2-COR-01`: Truncated PNG Header (4 Bytes `\x89PNG`)
- **Category**: Malformed Payload Handling
- **Target**: `MultimodalResolver.inspect_mime_type()`
- **Preconditions**: File containing only first 4 bytes of PNG header.
- **Execution**: Resolve file.
- **Expected Behavior**: Magic byte inspection passes Tier 1 check but Tier 2 Pillow check fails. Throws `CorruptImageError`, caught cleanly.

#### `TC-T2-COR-02`: Random Noise / Garbage Bytes (`os.urandom(1024)`)
- **Category**: Malformed Payload Handling
- **Target**: `MultimodalResolver.resolve()`
- **Preconditions**: File containing 1024 random binary bytes named `fake.png`.
- **Execution**: Resolve file.
- **Expected Behavior**: Magic byte check fails, Pillow check fails. Throws `UnsupportedFormatError("File does not contain valid image data")`.

#### `TC-T2-COR-03`: Malformed JPEG EXIF Metadata Payload
- **Category**: Malformed Payload Handling
- **Target**: `MultimodalResolver.resolve()`
- **Preconditions**: Valid JPEG image with corrupted/malformed EXIF header metadata block.
- **Execution**: Resolve file.
- **Expected Behavior**: Ignores corrupted EXIF metadata warnings/exceptions, extracts raw image pixel stream successfully.

#### `TC-T2-COR-04`: Mid-Write Partial Disk File Drop
- **Category**: Concurrent I/O Stress
- **Target**: `vazus_vision_daemon.py` file watcher
- **Preconditions**: Large 20MB image being copied to workspace in slow chunks.
- **Execution**: File watcher catches `Change.added` event while file is only 20% written.
- **Expected Behavior**: Debounce (100ms) or retry loop (`try_open_with_lock`) waits until file write completes before processing, avoiding truncated image read exceptions.

#### `TC-T2-COR-05`: Polyglot WebP / Script Payload Injection
- **Category**: Security Boundaries
- **Target**: `MultimodalResolver`
- **Preconditions**: File containing WebP header followed by embedded shell script payload.
- **Execution**: Resolve file.
- **Expected Behavior**: Strict PIL binary decoding validates pixel payload, ignoring non-image execution chunks.

---

### 4.4 Category D: Malformed & Non-Existent `@` References (5 Cases)

#### `TC-T2-REF-01`: Unknown `@` Reference Tag (`@invalid_reference_tag`)
- **Category**: Syntax & Schema Validation
- **Target**: `MultimodalResolver.resolve()`
- **Preconditions**: Input string `"@invalid_reference_tag"`.
- **Execution**: Pass to resolver.
- **Expected Behavior**: Throws `InvalidReferenceError("Unknown @ reference schema: @invalid_reference_tag")`.

#### `TC-T2-REF-02`: Non-Existent Brain Artifact (`@artifact:missing_chart`)
- **Category**: Missing Resource Resolution
- **Target**: `MultimodalResolver.resolve()`
- **Preconditions**: Artifact `missing_chart.png` does not exist.
- **Execution**: Resolve `@artifact:missing_chart`.
- **Expected Behavior**: Throws `ArtifactNotFoundError` with path search details.

#### `TC-T2-REF-03`: Path Traversal Attack in `@` Reference
- **Category**: Security Sandboxing
- **Target**: `MultimodalResolver.resolve()`
- **Preconditions**: Path input `"@../../../../Windows/System32/config/SAM"`.
- **Execution**: Resolve path.
- **Expected Behavior**: Canonical path checker (`Path.resolve()`) detects path escaping allowed workspace sandbox, raises `SecurityAccessDeniedError`.

#### `TC-T2-REF-04`: Malformed `@` Syntax (`@@@`, `@:`, `@clipboard:arg`)
- **Category**: Syntax Validation
- **Target**: `MultimodalResolver.resolve()`
- **Preconditions**: Inputs `@@@` or `@:`.
- **Execution**: Pass malformed reference strings.
- **Expected Behavior**: Regex parser rejects malformed reference, raises `InvalidRefSyntaxError`.

#### `TC-T2-REF-05`: Exclusively Locked File Access (`@C:\locked_img.png`)
- **Category**: OS I/O Boundaries
- **Target**: `MultimodalResolver.resolve()`
- **Preconditions**: Image file opened with exclusive OS write lock (`win32file.LOCKFILE_EXCLUSIVE_LOCK`).
- **Execution**: Attempt to resolve locked file.
- **Expected Behavior**: Catches `PermissionError`, executes exponential backoff retry (3 attempts over 50ms) before returning `FileLockedError`.

---

### 4.5 Category E: Terminal Viewport Boundaries (5 Cases)

#### `TC-T2-VWP-01`: Micro Viewport Dimensions (1x1 Terminal Cell)
- **Category**: Viewport Boundaries
- **Target**: `TUIPreviewRenderer.render()`
- **Preconditions**: `max_cols=1, max_rows=1`.
- **Execution**: Render sample image preview.
- **Expected Behavior**: Renders exactly 1 character cell without formatting exception or string bounds panic.

#### `TC-T2-VWP-02`: Zero Viewport Dimensions (`max_cols=0`, `max_rows=0`)
- **Category**: Viewport Boundaries
- **Target**: `TUIPreviewRenderer.render()`
- **Preconditions**: `max_cols=0, max_rows=0`.
- **Execution**: Pass zero viewport parameters.
- **Expected Behavior**: Automatically clamps zero dimensions to minimum safe fallback `max_cols=1, max_rows=1`.

#### `TC-T2-VWP-03`: Extreme Ultra-Wide Viewport (500x20 Cells)
- **Category**: Viewport Boundaries
- **Target**: `TUIPreviewRenderer.render()`
- **Preconditions**: `max_cols=500, max_rows=20`.
- **Execution**: Render 16:9 image.
- **Expected Behavior**: Constrained by `max_rows=20`, sets `cols = 20 * (16/9) = 36`. Does NOT force wide expansion to 500 cols.

#### `TC-T2-VWP-04`: Extreme Ultra-Tall Viewport (20x500 Cells)
- **Category**: Viewport Boundaries
- **Target**: `TUIPreviewRenderer.render()`
- **Preconditions**: `max_cols=20, max_rows=500`.
- **Execution**: Render 16:9 image.
- **Expected Behavior**: Constrained by `max_cols=20`, sets `rows = 20 / (16/9) = 11`. Does NOT expand to 500 rows.

#### `TC-T2-VWP-05`: Negative Viewport Parameters (`max_cols=-10`, `max_rows=-5`)
- **Category**: Viewport Boundaries & Input Sanitization
- **Target**: `TUIPreviewRenderer.render()`
- **Preconditions**: `max_cols=-10, max_rows=-5`.
- **Execution**: Render preview.
- **Expected Behavior**: Sanitizes negative inputs to default standard dimensions `max_cols=80, max_rows=40`.

---

### 4.6 Category F: Rapid Clipboard & Concurrent IPC Stress (5 Cases)

#### `TC-T2-STR-01`: Rapid Clipboard Event Burst (50 Events in 500ms)
- **Category**: Stress & Concurrency
- **Target**: `vazus_vision_daemon.py` clipboard queue
- **Preconditions**: Script fires 50 synthetic `WM_CLIPBOARDUPDATE` messages in 500ms.
- **Execution**: Monitor daemon queue and memory footprint.
- **Expected Behavior**: Queue throttles/debounces burst, processing only latest state. System memory remains stable, zero thread deadlocks or crashes.

#### `TC-T2-STR-02`: Interleaved Non-Image Clipboard Types Burst
- **Category**: Stress & Filtering
- **Target**: `vazus_vision_daemon.py`
- **Preconditions**: Rapidly alternate clipboard content: `Text -> PNG -> HTML -> PNG -> RTF -> PNG` in 1 second.
- **Execution**: Monitor emitted vision payloads.
- **Expected Behavior**: Emits payloads ONLY for the 3 PNG states. Filters out Text, HTML, RTF without latency lag.

#### `TC-T2-STR-03`: Win32 Clipboard Lock Contention
- **Category**: OS Concurrency
- **Target**: `PIL.ImageGrab.grabclipboard()` handler
- **Preconditions**: External process holds `OpenClipboard()` lock for 30ms.
- **Execution**: Daemon catches `WM_CLIPBOARDUPDATE` during lock.
- **Expected Behavior**: Retries `grabclipboard()` with exponential backoff (10ms, 20ms, 40ms) up to 3 times before timing out gracefully.

#### `TC-T2-STR-04`: WebSocket Client Disconnection Mid-Broadcast
- **Category**: Network IPC Boundaries
- **Target**: `vazus_vision_daemon.py` WebSocket broadcast server
- **Preconditions**: 3 subagents connected. 1 client forcefully drops connection (`TCP RST`) during active payload JSON stream.
- **Execution**: Emit broadcast payload.
- **Expected Behavior**: Catches `websockets.exceptions.ConnectionClosedError`, removes dead socket handle, completes broadcast to remaining 2 active clients.

#### `TC-T2-STR-05`: Concurrent SQLite WAL Write/Read Contention
- **Category**: Database Concurrency
- **Target**: `vision_event_stream` table in `vazus.db`
- **Preconditions**: Daemon writing 10 vision event rows per second while subagent executes continuous `SELECT` queries.
- **Execution**: Run concurrent write and read loop for 10 seconds.
- **Expected Behavior**: SQLite WAL mode allows concurrent readers and single writer without throwing `sqlite3.OperationalError: database is locked`.

---

## 5. Test Execution & Assertion Summary Table

| Category | Tier 1 Specs | Tier 2 Specs | Total Specifications | Key Assertion Engine |
|---|---|---|---|---|
| **R1 Multimodal Resolver** | 15 | 13 | 28 | `pytest` + `google.genai` payload validator |
| **R2 TUI Renderer** | 20 | 9 | 29 | ANSI escape sequence parser + PIL aspect checker |
| **R3 Vision Daemon** | 20 | 8 | 28 | `asyncio` test runner + `websockets` mock client |
| **TOTAL** | **55** | **30** | **85** | **Dual-Track E2E Test Suite** |

---

## 6. Verification Method for Test Implementer

To independently verify all specified test cases once implemented:

1. **Environment Setup**:
   - Python environment: `C:\vazus\.venv\Scripts\python.exe`
   - Test framework: `pytest`

2. **Test Execution Command**:
   ```powershell
   & C:\vazus\.venv\Scripts\python.exe -m pytest C:\vazus\labs\native_vision_system\tests\test_tier1_features.py C:\vazus\labs\native_vision_system\tests\test_tier2_boundaries.py -v
   ```

3. **Coverage Command**:
   ```powershell
   & C:\vazus\.venv\Scripts\python.exe -m pytest --cov=vazus_core.multimodal_resolver --cov=vazus_core.tui_preview_renderer --cov=vazus_vision_daemon C:\vazus\labs\native_vision_system\tests\
   ```

4. **Invalidation Criteria**:
   - Any Tier 1 feature with $<5$ verified passing unit/integration test cases.
   - Any unhandled exception (e.g. `ZeroDivisionError`, `IndexError`, `UnboundLocalError`) on Tier 2 boundary inputs.
