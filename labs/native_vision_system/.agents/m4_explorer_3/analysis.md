# Tier 3 & Tier 4 E2E Test Case Specifications
**Project**: Native Terminal Multimodal Vision System (`antigravity-cli` / `vazus_core`)  
**Author**: M4 Explorer 3 (E2E Tier 3 & Tier 4 Real-World Scenario Specifier)  
**Date**: 2026-08-05  
**Target Output**: `C:\vazus\labs\native_vision_system\.agents\m4_explorer_3\analysis.md`  

---

## Executive Summary

This document establishes the exhaustive specification for **Tier 3 (Cross-Feature Interaction Integration Tests)** and **Tier 4 (Real-World Application Scenario & Zero-Bash Delivery E2E Tests)** for the Native Terminal Multimodal Vision System.

- **Tier 3 (10 Test Specifications)** focus on multi-module integration across the Real-Time Vision Daemon (`vazus_vision_daemon.py`), Multimodal Resolver (`vazus_core.multimodal_resolver`), TUI Preview Renderer (`vazus_core.tui_preview_renderer`), WebSocket IPC (`ws://127.0.0.1:8765/ws/vision`), and SQLite WAL event storage (`vision_event_stream` in `memory/vazus.db`).
- **Tier 4 (8 Test Specifications)** focus on end-to-end user application workflows: Win+Shift+S Windows clipboard capture, zero-bash direct vision payload delivery to `google.genai` Gemini 3.6 Flash model endpoint, real-time subagent context auto-injection, rapid screenshot burst deduplication, OCR text extraction integration, and offline mock-mode verification.

---

## Part 1: Tier 3 — Cross-Feature Interaction Specifications (TC-T3)

Tier 3 tests verify that independently unit-tested modules operate seamlessly together under complex async conditions, file system triggers, and IPC distribution channels.

### TC-T3-01: Workspace File Drop -> Resolver -> TUI Renderer End-to-End Pipeline
- **Test Objective**: Verify complete pipeline execution when an image is dropped into a watched workspace directory.
- **Components In Scope**: `vazus_vision_daemon.py` (`watchfiles`), `MultimodalResolver`, `TUIPreviewRenderer`.
- **Preconditions**:
  - Temporary workspace folder created (`tmp_workspace/drops/`).
  - Daemon started in background thread monitoring `tmp_workspace/drops/`.
- **Input Data**: Write 1920x1080 PNG image (`sample_drop.png`) into `tmp_workspace/drops/`.
- **Execution Steps**:
  1. Daemon detects file creation event via `watchfiles`.
  2. Daemon passes file path to `MultimodalResolver.resolve()`.
  3. Daemon passes resolved payload to `TUIPreviewRenderer.render()`.
  4. Daemon constructs `VisualTokenPayload` dictionary.
- **Assertion Criteria**:
  - Processing completed in `< 500 ms` from file write completion.
  - `mime_type` strictly equals `"image/png"`.
  - Base64 encoded payload matches SHA-256 of original file.
  - `tui_preview` contains half-block Unicode `▀` (`\u2580`) and ANSI 24-bit TrueColor sequences (`\x1b[38;2;...m`).
  - Output string dimensions fit default terminal boundaries (max 80 cols x 40 rows).

### TC-T3-02: Dual IPC Channel Broadcast (WebSocket + SQLite WAL Engine)
- **Test Objective**: Ensure generated visual token payloads are simultaneously delivered over WebSocket and recorded in SQLite WAL persistence.
- **Components In Scope**: `vazus_vision_daemon.py`, `websockets` server (`ws://127.0.0.1:8765/ws/vision`), SQLite WAL database (`memory/vazus.db`).
- **Preconditions**:
  - WebSocket client connected to test daemon endpoint.
  - SQLite test database initialized with `vision_event_stream` table schema.
- **Input Data**: Synthetic file drop event payload.
- **Execution Steps**:
  1. Trigger daemon payload generation pipeline.
  2. Receive WebSocket message on subscriber socket.
  3. Query SQLite table `vision_event_stream` for latest `event_id`.
- **Assertion Criteria**:
  - WebSocket message received in `< 50 ms` post-processing.
  - JSON payload schema validates: `event_id`, `timestamp`, `source_type`, `sha256`, `mime_type`, `inline_data`, `ocr_text`, `tui_preview`.
  - SQLite database record contains exact matching `sha256`, `mime_type`, and non-null `tui_preview`.

### TC-T3-03: Multi-File Batch Drop & LRU Deduplication
- **Test Objective**: Verify daemon handling of high-concurrency file drops and SHA-256 deduplication.
- **Components In Scope**: Daemon event queue, SHA-256 deduplication cache, `MultimodalResolver`.
- **Preconditions**: Empty workspace watched directory.
- **Input Data**: 5 files dropped simultaneously in parallel threads:
  1. `img1.png` (Valid 500x500 PNG)
  2. `img2.jpg` (Valid 800x600 JPEG)
  3. `img1_copy.png` (Identical bytes to `img1.png`)
  4. `img3.webp` (Valid WEBP image)
  5. `corrupt.png` (Invalid binary header `0x00112233`)
- **Execution Steps**:
  1. Write all 5 files concurrently into watched directory.
  2. Await event emission queue completion (timeout 2.0s).
- **Assertion Criteria**:
  - Exactly 3 valid unique events generated (`img1.png`, `img2.jpg`, `img3.webp`).
  - `img1_copy.png` suppressed by SHA-256 LRU cache (deduplicated).
  - `corrupt.png` handled gracefully with error log entry, without crashing daemon thread or stalling queue.

### TC-T3-04: File Locking & Incomplete Write Resilience
- **Test Objective**: Validate daemon behavior during slow file writes or file locking by external processes (e.g. browser downloads or screenshot editors).
- **Components In Scope**: `watchfiles` debounce engine, `MultimodalResolver` file reader.
- **Preconditions**: Daemon actively watching target directory.
- **Input Data**: Script opens `partial_write.png`, writes first 100 bytes, sleeps 150ms, writes remaining 50KB, closes handle.
- **Execution Steps**:
  1. Daemon receives initial IOCP directory notification.
  2. Debounce buffer waits for handle release / file modification idle state.
  3. Resolver invoked once file lock is released.
- **Assertion Criteria**:
  - Zero `PermissionError` or `IOError` raised.
  - Resolver receives complete 50KB payload.
  - Image MIME type correctly identified as `"image/png"`.
  - No partial zero-length payloads emitted.

### TC-T3-05: `@` Reference Resolution to TUI ANSI Preview
- **Test Objective**: Test resolution of `@clipboard`, `@latest`, and `@artifact:name` references followed by TUI Preview rendering.
- **Components In Scope**: `MultimodalResolver`, `TUIPreviewRenderer`.
- **Preconditions**:
  - 3 images created in workspace history (`art_01.png`, `art_02.jpg`, `art_03.webp`).
  - Windows clipboard populated with valid PIL Image.
- **Input Data**:
  - Query A: `@latest`
  - Query B: `@clipboard`
  - Query C: `@artifact:art_01`
- **Execution Steps**:
  1. Resolve Query A -> verify points to `art_03.webp`.
  2. Resolve Query B -> verify extracts clipboard image bytes.
  3. Resolve Query C -> verify extracts `art_01.png`.
  4. Pass each resolved payload to `TUIPreviewRenderer.render(payload)`.
- **Assertion Criteria**:
  - All 3 queries return valid `ResolvedMultimodalPayload` objects.
  - ANSI TUI strings successfully rendered for all 3 sources.
  - Total resolution + rendering time per query `< 40 ms`.

### TC-T3-06: Polymorphic Header Validation Under Misnamed Extension Drops
- **Test Objective**: Confirm multi-tiered format inspection (Magic Bytes -> Pillow -> Extension) when file extension contradicts file magic header.
- **Components In Scope**: Daemon watch pipeline, `MultimodalResolver.resolve()`.
- **Preconditions**: Watched workspace directory.
- **Input Data**: File named `photo.jpg` whose content starts with `\x89PNG\r\n\x1a\n` (actual PNG format).
- **Execution Steps**:
  1. Drop `photo.jpg` into watched directory.
  2. Daemon routes file to `MultimodalResolver`.
- **Assertion Criteria**:
  - `mime_type` resolved as `"image/png"` (magic bytes override `.jpg` extension).
  - Generated `google.genai.types.Part` has `mime_type="image/png"`.
  - TUI Preview renders cleanly without image decoding exception.

### TC-T3-07: Double-Buffering & ANSI RLE Payload Compression Verification
- **Test Objective**: Verify that TUI preview renderer applies horizontal Run-Length Encoding (RLE) to ANSI escape strings generated from daemon file drops, achieving >60% payload size reduction.
- **Components In Scope**: Daemon drop handler, `TUIPreviewRenderer`.
- **Preconditions**: 800x600 solid color test image.
- **Input Data**: File drop of solid color PNG image.
- **Execution Steps**:
  1. Render ANSI string using naive per-character ANSI escape formatting.
  2. Render ANSI string using `TUIPreviewRenderer` with RLE double-buffering.
  3. Compare byte sizes of output strings.
- **Assertion Criteria**:
  - RLE rendered string size is at least 60% smaller than naive ANSI string.
  - Visual output when printed to terminal is 100% visually identical.

### TC-T3-08: 256-Color & ASCII Luminance Ramp Fallback Matrix
- **Test Objective**: Test cross-module behavior when renderer operating mode falls back from TrueColor to 256-color or ASCII luminance ramps.
- **Components In Scope**: `MultimodalResolver`, `TUIPreviewRenderer` (`mode="256color"`, `mode="ascii_17"`, `mode="ascii_70"`).
- **Preconditions**: High-contrast test gradient image.
- **Input Data**: Resolved payload passed to renderer with explicit mode overrides.
- **Execution Steps**:
  1. Render in `256color` mode -> check for `\x1b[38;5;...m` codes.
  2. Render in `ascii_17` mode -> check characters belong to `" .:!/r(l1Z4H9W8$@"`.
  3. Render in `ascii_70` mode -> check 70-character luminance ramp.
- **Assertion Criteria**:
  - All fallback modes execute without error.
  - No 24-bit TrueColor escape sequences present in 256-color/ASCII modes.
  - Character matrix dimensions remain strictly equal to `(max_cols, max_rows)`.

### TC-T3-09: Daemon Recovery & Reconnection Resiliency
- **Test Objective**: Verify daemon system stability when IPC clients (WebSocket or SQLite callers) disconnect or crash during payload transmission.
- **Components In Scope**: `vazus_vision_daemon.py` async event loop, IPC socket server.
- **Preconditions**: Daemon server running with 2 connected WebSocket clients.
- **Input Data**: Abruptly close socket client 1 mid-transmission during file drop event.
- **Execution Steps**:
  1. Trigger image drop.
  2. Force-close client 1 socket.
  3. Verify client 2 receives event.
  4. Trigger subsequent image drop.
- **Assertion Criteria**:
  - Daemon logs client disconnect error gracefully without unhandled exception.
  - Client 2 receives full event payload uninterrupted.
  - Subsequent image drops continue to process within `< 500 ms`.

### TC-T3-010: High-Resolution Image Memory & Performance Limits
- **Test Objective**: Ensure large images (e.g. 4K / 8K ultra-wide screenshots, 25MB JPEG) do not cause RAM memory leaks or rendering freezes.
- **Components In Scope**: `MultimodalResolver`, `TUIPreviewRenderer`, memory profiler.
- **Preconditions**: 7680x4320 high-res synthetic test image (20MB PNG).
- **Input Data**: Drop 8K image into daemon directory.
- **Execution Steps**:
  1. Record baseline RAM usage.
  2. Process 8K image drop through resolver and renderer downsampling.
  3. Record peak RAM usage and post-GC RAM.
- **Assertion Criteria**:
  - Resolution and rendering finish in `< 800 ms`.
  - Downsampled TUI buffer respects `max_cols=80`, `max_rows=40`.
  - Memory consumption returns to baseline (no PIL handle leaks).

---

## Part 2: Tier 4 — Real-World Application Scenario Specifications (TC-T4)

Tier 4 tests validate end-to-end user application workflows, ensuring zero-bash direct vision payload delivery to Gemini 3.6 Flash and seamless integration with Windows Win+Shift+S clipboard captures and subagent contexts.

### TC-T4-01: Win+Shift+S Clipboard Capture -> Gemini 3.6 Flash Direct Zero-Bash Delivery
- **Test Objective**: Complete end-to-end verification of Windows clipboard capture (`Win+Shift+S`), payload formatting, and direct delivery to Gemini 3.6 Flash without executing any bash commands or temp files.
- **Components In Scope**: Win32 Clipboard listener (`AddClipboardFormatListener` / `PIL.ImageGrab`), `MultimodalResolver`, `google.genai` SDK v2.14.0, Gemini 3.6 Flash model.
- **Preconditions**:
  - Valid `GEMINI_API_KEY` or test credentials available (or active mock mode).
  - Daemon clipboard listener active (`WM_CLIPBOARDUPDATE` hook enabled).
- **Input Data**:
  - Synthetic Win32 clipboard update containing PIL Image (UI button screenshot with text `"SUBMIT ORDER"`).
  - User prompt: `"What action does this UI button perform?"`
- **Execution Steps**:
  1. Inject image into Win32 clipboard (simulating Win+Shift+S).
  2. Daemon catches `WM_CLIPBOARDUPDATE` within `< 50 ms`.
  3. Daemon extracts PIL Image via `PIL.ImageGrab.grabclipboard()`.
  4. Daemon invokes `MultimodalResolver.resolve(clipboard_img)` -> `ResolvedMultimodalPayload`.
  5. Construct `google.genai.types.Part.from_bytes(data=payload.base64_bytes, mime_type="image/png")`.
  6. Dispatch directly to Gemini 3.6 Flash API:
     `client.models.generate_content(model="gemini-3.6-flash", contents=[prompt, genai_part])`
- **Assertion Criteria**:
  - **Zero-Bash Enforcement**: 0 subprocess calls, 0 `.sh` or `.bat` script generations, 0 intermediate disk file writes.
  - Total end-to-end processing time from clipboard event to API dispatch `< 350 ms`.
  - `genai_part.inline_data.mime_type` equals `"image/png"`.
  - Gemini API returns valid HTTP 200 response containing text analyzing the `"SUBMIT ORDER"` button.

### TC-T4-02: Subagent Context Auto-Injection (`SubagentFramework` Hook Integration)
- **Test Objective**: Verify that when a user captures a snippet, visual token payload automatically injects into active subagent context (`rlm_code_engineer` or `open_deep_researcher`).
- **Components In Scope**: `vazus_vision_daemon.py`, `vazus_core.subagent_framework.SubagentHookRegistry`.
- **Preconditions**:
  - Active `SubagentContext` running in subagent session.
  - Daemon registered with `SubagentHookRegistry`.
- **Input Data**: Clipboard capture of python stack trace screenshot.
- **Execution Steps**:
  1. Trigger clipboard capture.
  2. Daemon generates `VisualTokenPayload` (includes `ocr_text`, `inline_data`, `tui_preview`).
  3. Daemon triggers `on_vision_token` subagent hook.
  4. Subagent appends visual token to its internal conversation history.
- **Assertion Criteria**:
  - Subagent context updated within `< 100 ms` of capture.
  - Subagent history contains inline `Part` plus extracted `ocr_text` stack trace.
  - ANSI TUI string rendered in terminal UI feedback window.

### TC-T4-03: Rapid Screenshot Burst Stress & Deduplication
- **Test Objective**: Simulate user taking 3 screenshots in rapid succession (burst capture during live debugging session).
- **Components In Scope**: Win32 clipboard listener, SHA-256 deduplicator, rate limiter.
- **Preconditions**: Daemon active.
- **Input Data**: 3 clipboard events within 1500 ms window:
  - Event 1 (t=0ms): Snippet A (Code Editor)
  - Event 2 (t=400ms): Snippet A (Duplicate capture of same region)
  - Event 3 (t=900ms): Snippet B (Terminal Error Output)
- **Execution Steps**:
  1. Inject Snippet A into clipboard.
  2. Re-inject Snippet A into clipboard 400ms later.
  3. Inject Snippet B into clipboard 500ms after that.
- **Assertion Criteria**:
  - Event 1 generates full API payload.
  - Event 2 recognized as duplicate via SHA-256 hash match -> suppressed without calling Gemini API (saving API tokens).
  - Event 3 generates new API payload.
  - System CPU load during burst remains `< 1.0%`.

### TC-T4-04: Offline Fallback & Mock SDK Harness Isolation
- **Test Objective**: Ensure test suite runs reliably in offline CI/CD environments using a mock `google.genai` SDK client without external internet access.
- **Components In Scope**: E2E test harness runner (`run_e2e_tests.py`), `MultimodalResolver`, Mock `google.genai.Client`.
- **Preconditions**: Network interface disabled / `GEMINI_API_KEY` set to `"mock_key_test"`.
- **Input Data**: Mock response object returning pre-canned vision evaluation.
- **Execution Steps**:
  1. Initialize test runner with `--mock-genai` flag.
  2. Execute Win+Shift+S capture workflow.
  3. Intercept `client.models.generate_content()` call args.
- **Assertion Criteria**:
  - Intercepted `contents` parameter contains exact expected `types.Part` object.
  - `Part.inline_data.data` matches Base64 image payload.
  - Test passes with exit code 0 under offline environment.

### TC-T4-05: Multi-Modal Combined Vision + OCR Payload Synergy
- **Test Objective**: Validate hybrid visual token construction where screenshot contains both graphical elements and text, verifying combined OCR and image payload delivery.
- **Components In Scope**: `vazus_vision_daemon.py`, `rapidocr`, `MultimodalResolver`.
- **Preconditions**: Image containing printed code snippet: `"def compute_vector(): return [1, 2, 3]"`.
- **Input Data**: Clipboard capture of code snippet image.
- **Execution Steps**:
  1. Daemon receives clipboard image.
  2. Daemon runs `rapidocr.detect_and_recognize(img)`.
  3. Daemon runs `MultimodalResolver.resolve(img)`.
  4. Daemon constructs hybrid payload containing both Base64 `inlineData` part and structured text field `ocr_text`.
- **Assertion Criteria**:
  - `ocr_text` contains string `"def compute_vector(): return [1, 2, 3]"`.
  - `inline_data` contains complete valid Base64 PNG string.
  - Combined payload allows Gemini 3.6 Flash to receive both spatial vision tensor and exact OCR text.

### TC-T4-06: End-to-End System Victory Scenario (10-Minute Worksession Simulation)
- **Test Objective**: Master integration test verifying 10-minute continuous developer session involving multiple drops, clipboard captures, `@` references, and Gemini API queries.
- **Components In Scope**: Entire Native Vision System (Daemon + Resolver + Renderer + IPC + SDK).
- **Preconditions**: Clean test workspace environment.
- **Input Data**: Sequential event log:
  1. Drop `architecture_diagram.png`.
  2. Query `@latest`.
  3. Capture clipboard snippet of error dialog (`Win+Shift+S`).
  4. Resolve `@clipboard`.
  5. Drop `updated_diagram.jpg`.
  6. Dispatch 5 consecutive zero-bash calls to Gemini 3.6 Flash.
- **Execution Steps**: Execute sequence sequentially with realistic 500ms delays.
- **Assertion Criteria**:
  - 100% of events process with zero errors.
  - All 5 Gemini API requests return successful visual evaluations.
  - Zero bash commands executed throughout entire session.
  - SQLite `vision_event_stream` records all 5 events with complete audit trails.
  - Peak memory remains strictly `< 120 MB`.

### TC-T4-07: Anti-Freeze Clipboard Safety & Image Serialization Rule Verification
- **Test Objective**: Validate that system prevents calling `view_file` or binary string serialization on raw image files in agent communication channels, preventing API stream freezes.
- **Components In Scope**: `vazus_vision_daemon.py`, `clip_ocr.py`, subagent messaging protocol.
- **Preconditions**: Clipboard containing 10MB bitmap image.
- **Input Data**: Win+Shift+S capture.
- **Execution Steps**:
  1. Process clipboard image.
  2. Verify daemon payload outputs Base64 `inlineData` structure rather than raw binary file serialization.
  3. Verify image paths are referenced via path string rather than raw binary view.
- **Assertion Criteria**:
  - Payload serialization uses JSON-compliant Base64 strings.
  - Zero binary payload stream stalls or empty generation loops (`content: ""`).

### TC-T4-08: High-DPI Display Bounding Box & Sub-Pixel Aspect Preservation
- **Test Objective**: Test clipboard screenshots captured from 4K High-DPI Windows displays (e.g. 250% scaling, 3840x2160) to ensure aspect ratios and terminal TUI bounds are perfectly maintained.
- **Components In Scope**: `MultimodalResolver`, `TUIPreviewRenderer`.
- **Preconditions**: High-DPI synthetic screenshot image (3840x2160 pixels, aspect ratio 1.777).
- **Input Data**: High-DPI clipboard capture.
- **Execution Steps**:
  1. Resolve image payload.
  2. Render ANSI preview for terminal screen (80 cols x 40 rows).
  3. Measure rendered character buffer aspect ratio.
- **Assertion Criteria**:
  - Rendered matrix uses upper half-block `▀` characters.
  - Effective sub-pixel ratio is 1:1 square aspect ratio.
  - Rendered width/height ratio matches 1.777 (+/- 2% terminal cell discretization tolerance).

---

## Part 3: Test Matrix & Coverage Summary

| Test ID | Tier | Target Module(s) | Primary Input | Expected Latency | Core Invariants Verified |
|---|---|---|---|---|---|
| **TC-T3-01** | Tier 3 | Daemon + Resolver + Renderer | 1080p PNG Drop | < 500ms | Pipeline drop -> Base64 + ANSI preview |
| **TC-T3-02** | Tier 3 | WebSocket + SQLite WAL | Synthetic Payload | < 50ms | Dual IPC delivery & DB WAL logging |
| **TC-T3-03** | Tier 3 | Daemon Queue + Deduplicator | 5 Concurrent Files | < 1000ms | Concurrency, SHA-256 deduplication, error isolation |
| **TC-T3-04** | Tier 3 | Watchfiles Debouncer | Slow/Locked Write | < 400ms | Lock resilience, no zero-byte payloads |
| **TC-T3-05** | Tier 3 | `@` Resolver + Renderer | `@latest`, `@clipboard` | < 40ms | `@` syntax resolution & TUI output |
| **TC-T3-06** | Tier 3 | Polymorphic Validator | `photo.jpg` (PNG bytes) | < 30ms | Magic byte header override |
| **TC-T3-07** | Tier 3 | ANSI RLE Optimizer | Solid Color Image | < 20ms | >60% payload size compression |
| **TC-T3-08** | Tier 3 | Fallback Ramps Renderer | High-Contrast Image | < 20ms | 256-color & ASCII luminance ramps |
| **TC-T3-09** | Tier 3 | Daemon IPC Server | Client Crash Event | < 10ms | Socket crash resilience & recovery |
| **TC-T3-10** | Tier 3 | Resolver + Renderer | 8K PNG (20MB) | < 800ms | Memory stability & no handles leak |
| **TC-T4-01** | Tier 4 | Clipboard + SDK + Gemini 3.6 | Win+Shift+S Capture | < 350ms | **Zero-bash delivery to Gemini 3.6 Flash** |
| **TC-T4-02** | Tier 4 | Daemon + Subagent Framework | Stack trace screenshot | < 100ms | Auto-injection into subagent context |
| **TC-T4-03** | Tier 4 | Win32 Listener + Deduplicator | 3 Rapid Screenshots | < 500ms | Burst handling & duplicate API call suppression |
| **TC-T4-04** | Tier 4 | E2E Harness + Mock SDK | Mocked Win+Shift+S | < 50ms | Offline CI/CD zero-bash test isolation |
| **TC-T4-05** | Tier 4 | Vision + RapidOCR Engine | Code snippet image | < 150ms | Combined visual Part + OCR text payload |
| **TC-T4-06** | Tier 4 | Full Vision System | 10-Min Session Log | < 500ms/evt | Master victory scenario (100% pass) |
| **TC-T4-07** | Tier 4 | Anti-Freeze Safety Engine | 10MB Bitmap | < 100ms | Base64 safety & no stream freezes |
| **TC-T4-08** | Tier 4 | Aspect & Scaling Engine | 4K High-DPI Screenshot | < 50ms | 1:1 sub-pixel aspect preservation |

---

## Part 4: Verification Method & Execution Commands

To independently verify these specifications:

1. **Verify Artifact Existence**:
   - `C:\vazus\labs\native_vision_system\.agents\m4_explorer_3\analysis.md`
   - `C:\vazus\labs\native_vision_system\.agents\m4_explorer_3\handoff.md`

2. **Run Environment Prerequisite Checks**:
   ```powershell
   C:\vazus\.venv\Scripts\python.exe -c "import PIL, watchfiles, rapidocr, websockets, google.genai; print('Python 3.12 Venv & Libraries Verified for Tier 3/4 Testing!')"
   ```

3. **Target Test Layout Mapping**:
   - Tier 3 pytest file: `C:\vazus\labs\native_vision_system\tests\test_tier3_cross_feature.py`
   - Tier 4 pytest file: `C:\vazus\labs\native_vision_system\tests\test_tier4_real_world.py`
