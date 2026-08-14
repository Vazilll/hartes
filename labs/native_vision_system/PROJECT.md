# Project: Native Terminal Multimodal Vision System

## Architecture
The Native Terminal Multimodal Vision System integrates seamlessly into `vazus_core` and `antigravity-cli` on Windows. It consists of 3 core functional modules and a dual-track E2E verification test harness:

1. **Multimodal Image Resolver (`vazus_core.multimodal_resolver`)**:
   - Polymorphic preprocessor for `.png`, `.jpg`, `.jpeg`, `.webp` images.
   - Converts disk files, `@` references (`@clipboard`, `@latest`, `@artifact`), raw bytes, and PIL images into `google.genai` compliant `inlineData` Base64 parts.
   - Performs 3-tiered format validation (Magic Byte headers, Pillow metadata, Extension hints).

2. **TUI Preview Renderer (`vazus_core.tui_preview_renderer`)**:
   - High-fidelity terminal pixel matrix buffer visualizer inspired by `Neo3dEngine` (`ConsoleScreen.cs`).
   - Supports 24-bit TrueColor using `▀` (U+2580) half-block characters (1:1 sub-pixel aspect ratio), double-buffering, and horizontal Run-Length Encoding (RLE) ANSI sequence optimization.
   - Features 256-color fallback, 17/70 char ASCII luminance ramps, and Windows VT100 console mode setup (`SetConsoleMode`).

3. **Real-Time Vision Daemon (`vazus_vision_daemon.py`)**:
   - Background watcher monitoring Win32 clipboard (`AddClipboardFormatListener` / `Win+Shift+S`) and workspace image file drops (`watchfiles==1.2.0`).
   - Generates visual token payloads (<500ms latency, <0.1% CPU load) containing SHA-256 deduplicated metadata, `inlineData`, rapidocr text extraction, and TUI ANSI strings.
   - Broadcasts events via WebSocket (`ws://127.0.0.1:8765/ws/vision`) and SQLite WAL table (`vision_event_stream` in `memory/vazus.db`).

4. **E2E Testing Suite**:
   - Opaque-box test suite verifying zero-bash direct vision payload delivery, ANSI preview rendering, clipboard detection, and Gemini 3.6 Flash payload formatting.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Polymorphic File Preprocessor | Inspects magic bytes & extensions for .png, .jpg, .jpeg, .webp | M1 | survey |
| 2 | InlineData Base64 Part Encoder | Converts image bytes to google.genai inlineData dict/Part | M1 | survey |
| 3 | @ Reference Resolver | Resolves @clipboard, @latest, and @artifact references | M1 | survey |
| 4 | TrueColor Half-Block Renderer | Renders ANSI 24-bit TrueColor previews with upper half-block `▀` | M2 | survey |
| 5 | ANSI RLE Double-Buffering | Batches identical ANSI color codes to reduce TUI stdout size by >60% | M2 | survey |
| 6 | Aspect Ratio & Bounding Box | Maintains 1:1 square sub-pixel aspect ratio within terminal bounds | M2 | survey |
| 7 | Fallback ASCII/256-Color Ramps | Renders 256-color and 17/70 char ASCII fallback previews | M2 | survey |
| 8 | Win32 Clipboard Listener | Monitors Win+Shift+S clipboard events using Win32 HWND hook | M3 | survey |
| 9 | Workspace File Watcher | Monitors disk drops for .png/.jpg/.jpeg/.webp via watchfiles | M3 | survey |
| 10 | Visual Token Payload Generator | Builds payload with metadata, inlineData, rapidocr text, & TUI string | M3 | survey |
| 11 | IPC & WebSocket Broadcast | Publishes events over WebSocket (ws://127.0.0.1:8765) and SQLite WAL | M3 | survey |
| 12 | E2E Test Harness & Suite | Comprehensive tests (Tiers 1-4) verifying zero-bash delivery | M4 | dual-track |
| 13 | E2E Hardening & Validation | Final 100% test validation and Tier 5 adversarial coverage hardening | M5 | dual-track |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Native Multimodal Image Resolver | Implement `vazus_core/multimodal_resolver.py` | none | DONE |
| M2 | TUI Terminal Preview Renderer | Implement `vazus_core/tui_preview_renderer.py` | M1 | DONE |
| M3 | Real-Time Vision Daemon | Implement `vazus_vision_daemon.py` | M1, M2 | DONE |
| M4 | E2E Test Suite Creation | Create test runner & test cases (Tiers 1-4) | none | DONE |
| M5 | Integration & Final E2E Validation | Pass 100% E2E tests and Tier 5 hardening | M1, M2, M3, M4 | DONE |

## Interface Contracts

### Multimodal Resolver ↔ TUI Renderer & Daemon
- `MultimodalResolver.resolve(source: Union[str, bytes, Image.Image, Path]) -> ResolvedMultimodalPayload`
- `ResolvedMultimodalPayload`:
  - `mime_type: str` ("image/png", "image/jpeg", "image/webp")
  - `base64_data: str`
  - `genai_part: Part` (`google.genai.types.Part.from_bytes(...)`)
  - `sha256: str`
  - `width: int`, `height: int`
  - `to_inline_data_dict() -> Dict[str, Any]`

### TUI Renderer API
- `TUIPreviewRenderer.render(payload_or_image: Union[ResolvedMultimodalPayload, Image.Image, str], max_cols: int = 80, max_rows: int = 40, mode: str = "truecolor") -> str`
- Returns ANSI escape string ready for direct terminal print.

### Vision Daemon IPC API
- WebSocket endpoint: `ws://127.0.0.1:8765/ws/vision`
- SQLite WAL table: `vision_event_stream` in `C:\vazus\memory\vazus.db`
- Event Payload JSON schema:
  ```json
  {
    "event_id": "evt_...",
    "timestamp": "ISO-8601",
    "source_type": "clipboard | file_drop | at_ref",
    "sha256": "...",
    "mime_type": "image/png",
    "inline_data": {"mime_type": "image/png", "data": "base64..."},
    "ocr_text": "...",
    "tui_preview": "\\x1b[38;2;..."
  }
  ```

## Code Layout
Target file paths:
- `C:\vazus\vazus_core\multimodal_resolver.py` (M1)
- `C:\vazus\vazus_core\tui_preview_renderer.py` (M2)
- `C:\vazus\vazus_vision_daemon.py` (M3)
- `C:\vazus\labs\native_vision_system\tests\` (M4 & M5)
- `C:\vazus\labs\native_vision_system\TEST_READY.md` (M4 output signal)
