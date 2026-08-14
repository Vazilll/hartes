# Hard Handoff Report: E2E Tier 3 & Tier 4 Specification
**Agent**: M4 Explorer 3 (E2E Tier 3 & 4 Real-World Scenario Specifier)  
**Working Directory**: `C:\vazus\labs\native_vision_system\.agents\m4_explorer_3`  
**Target Milestone**: M4 E2E Test Suite Creation  
**Date**: 2026-08-05T02:02:07Z  

---

## 1. Observation

- **Original User Request**: `C:\vazus\labs\native_vision_system\.agents\ORIGINAL_REQUEST.md` lines 20-27 require an opaque-box E2E test suite verifying zero-bash direct vision payload delivery to Gemini 3.6 Flash, real-time watcher detection (<500ms), and ANSI terminal previews.
- **Project Architecture & Inventory**: `C:\vazus\labs\native_vision_system\PROJECT.md` lines 16-23 & lines 38-39 specify R1 (`MultimodalResolver`), R2 (`TUIPreviewRenderer`), R3 (`vazus_vision_daemon.py`), dual IPC channels (`ws://127.0.0.1:8765/ws/vision` & SQLite `vision_event_stream` in `memory/vazus.db`), and Milestones M4/M5 dual-track test harness.
- **Sibling Explorer Specifications**:
  - `m4_explorer_1`: Defined overall E2E test infrastructure architecture, pytest runner framework (`run_e2e_tests.py`), and test directory layout in `tests/`.
  - `m4_explorer_2`: Defined Tier 1 (Feature coverage >=5 per feature) and Tier 2 (Boundary and corner cases).
- **Environment & SDK Capability**: Python 3.12 virtualenv (`C:\vazus\.venv`) contains `google.genai` (v2.14.0), `Pillow` (12.3.0), `watchfiles` (1.2.0), `rapidocr`, `websockets`, and `pywin32`.

---

## 2. Logic Chain

1. **Observation**: `PROJECT.md` defines 3 core functional components (Resolver, Renderer, Daemon) operating across local file systems, Win32 clipboards, IPC sockets, and Google GenAI SDK calls.
2. **Logic Step 1 (Tier 3 Integration)**: Testing individual modules in isolation is insufficient for verifying system stability. Tier 3 must explicitly test cross-feature interactions: file drops triggering daemon events -> invoking resolver -> generating ANSI previews -> broadcasting across WebSocket and SQLite WAL concurrently.
3. **Logic Step 2 (Tier 3 Concurrency & Resilience)**: Real-world file systems exhibit file locks, partial writes, corrupted byte drops, and client crashes. Tier 3 test specifications must include file write debouncing, multi-file batch drops, SHA-256 deduplication, and socket crash recovery.
4. **Logic Step 3 (Tier 4 Real-World Workflows)**: The core goal of the project is eliminating bash workarounds and manual file conversion when supplying vision input to Gemini 3.6 Flash. Tier 4 must model exact user workflows: pressing `Win+Shift+S`, capturing screenshots directly into Python RAM via `PIL.ImageGrab`, formatting `google.genai.types.Part.from_bytes()`, and calling `client.models.generate_content()` with zero temporary bash scripts or disk file artifacts.
5. **Logic Step 4 (Tier 4 Ecosystem Integration)**: Developers utilize subagents (`rlm_code_engineer`, `open_deep_researcher`) and offline CI/CD test runners. Tier 4 specifications must test auto-injection into `SubagentContext`, hybrid OCR + visual token generation (`rapidocr`), high-DPI aspect ratio scaling (3840x2160), and mock SDK isolation.
6. **Conclusion**: An exhaustive suite of 10 Tier 3 integration test specifications (`TC-T3-01` through `TC-T3-10`) and 8 Tier 4 real-world scenario specifications (`TC-T4-01` through `TC-T4-08`) provides complete coverage for cross-feature interactions and zero-bash Gemini 3.6 Flash delivery.

---

## 3. Caveats

- **Live vs Mock Gemini API Credentials**: Running live Tier 4 E2E tests against Gemini 3.6 Flash requires a valid `GEMINI_API_KEY` set in the OS environment. Offline CI/CD test runs use the mocked SDK harness specified in `TC-T4-04`.
- **Win32 Message Loop Execution**: Win32 clipboard tests (`TC-T4-01`, `TC-T4-03`) require a Windows OS environment with an active user session for GUI clipboard handle access. Headless Linux CI runners fallback to `TC-T4-04` mock clipboard injections.
- **Read-Only Scope Enforcement**: No source code files in `vazus_core/` or project `src/` were edited during this specification task. All outputs are strictly maintained within `C:\vazus\labs\native_vision_system\.agents\m4_explorer_3\`.

---

## 4. Conclusion

1. **Tier 3 Integration Suite (10 Test Specs)**: Fully specifies daemon-resolver-renderer pipeline flow, WebSocket/SQLite IPC dual-channel delivery, multi-file batching, slow file write debouncing, `@` reference resolution, magic byte header precedence, RLE ANSI string compression (>60%), fallback color ramps, socket crash recovery, and 8K image memory limits.
2. **Tier 4 Real-World Suite (8 Test Specs)**: Fully specifies Win+Shift+S clipboard capture to direct zero-bash Gemini 3.6 Flash payload delivery, subagent context auto-injection, screenshot burst deduplication, offline mock SDK harness isolation, hybrid vision+OCR payload synergy, anti-freeze binary safety, 4K High-DPI aspect preservation, and master 10-minute session victory scenario.
3. **Completeness**: Detailed specifications, assertion criteria, latency thresholds (<500ms), and execution steps are fully documented in `C:\vazus\labs\native_vision_system\.agents\m4_explorer_3\analysis.md`.

---

## 5. Verification Method

To verify the deliverables of M4 Explorer 3:

1. **Inspect Analysis Report**:
   `C:\vazus\labs\native_vision_system\.agents\m4_explorer_3\analysis.md`
2. **Inspect Handoff Report**:
   `C:\vazus\labs\native_vision_system\.agents\m4_explorer_3\handoff.md`
3. **Environment Command Verification**:
   ```powershell
   C:\vazus\.venv\Scripts\python.exe -c "import PIL, watchfiles, rapidocr, websockets, google.genai; print('Environment readiness for Tier 3 & Tier 4 E2E implementation verified!')"
   ```
