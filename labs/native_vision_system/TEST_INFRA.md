# E2E Test Infrastructure & Test Architecture Specification

**Project**: Native Terminal Multimodal Vision System (`C:\vazus\labs\native_vision_system`)  
**Author**: M4 Test Writer (E2E Test Suite & Infrastructure Creator)  
**Date**: 2026-08-05  

---

## 1. Test Philosophy & Core Principles

The End-to-End (E2E) Test Suite for the Native Terminal Multimodal Vision System is designed as an **opaque-box, multi-tiered verification framework**. It guarantees that image ingestion, TUI preview rendering, real-time daemon event processing, and `google.genai` Gemini 3.6 Flash payload construction work flawlessly without requiring manual bash workarounds or external intervention.

### Core Testing Pillars:
1. **Zero-Bash Direct Delivery**: Vision payloads must construct native `google.genai.types.Part` objects and inline Base64 data dictionaries directly in Python memory—bypassing intermediate shell scripts, bash executions, or disk dumps.
2. **Progressive Testability**: Features are tested against their concrete interfaces defined in `PROJECT.md`. Implemented modules (`vazus_core.multimodal_resolver`) run real business logic, while planned modules (M2 TUI Renderer, M3 Vision Daemon) are tested against strict interface contracts.
3. **Determinism & Isolation**: All test cases use isolated temporary directories (`tmp_path`), in-memory byte streams (`io.BytesIO`), and mock API clients to ensure reproducible test runs with zero side effects on host OS state.
4. **Strict Exit Code Guarantee**: The master test runner (`run_e2e_tests.py`) strictly enforces **exit code `0` on 100% test pass rate**, and returns exit code `1` on any failure or error.

---

## 2. Feature Inventory Matrix (Features 1 – 13)

Below is the authoritative mapping connecting all 13 features from `PROJECT.md` to target test tiers, test files, and verification methods.

| # | Feature Name | Core Module | Scope / Tier | Test File | Primary Verification Method & Assertion |
|---|--------------|-------------|--------------|-----------|------------------------------------------|
| 1 | Polymorphic File Preprocessor | `vazus_core.multimodal_resolver` | M1 / Tier 1, 2 | `test_tier1_feature.py`, `test_tier2_boundary.py` | Verify 3-tiered format inspection (Magic bytes `.png`/`.jpg`/`.webp`, Pillow, extension hints). Assert magic bytes override wrong file extensions. |
| 2 | InlineData Base64 Part Encoder | `vazus_core.multimodal_resolver` | M1 / Tier 1, 2 | `test_tier1_feature.py`, `test_tier2_boundary.py` | Assert `to_genai_part()` returns `types.Part` with valid `inline_data`. Assert Base64 round-trip binary equality and SHA-256 calculation. |
| 3 | `@` Reference Resolver | `vazus_core.multimodal_resolver` | M1 / Tier 1, 2 | `test_tier1_feature.py`, `test_tier2_boundary.py` | Resolve `@clipboard`, `@latest`, and `@artifact:<name>` references. Verify graceful handling of missing, empty, or locked resources. |
| 4 | TrueColor Half-Block Renderer | `vazus_core.tui_preview_renderer` | M2 / Tier 1, 3 | `test_tier1_feature.py`, `test_tier3_integration.py` | Verify ANSI output contains upper half-block `▀` (U+2580) and 24-bit TrueColor sequences (`\x1b[38;2;...m`, `\x1b[48;2;...m`). |
| 5 | ANSI RLE Double-Buffering | `vazus_core.tui_preview_renderer` | M2 / Tier 1, 3 | `test_tier1_feature.py`, `test_tier3_integration.py` | Assert RLE double-buffering compresses identical ANSI escape codes, achieving >60% payload size reduction compared to unoptimized streams. |
| 6 | Aspect Ratio & Bounding Box | `vazus_core.tui_preview_renderer` | M2 / Tier 1, 2 | `test_tier1_feature.py`, `test_tier2_boundary.py` | Verify grid dimensions preserve 1:1 sub-pixel square aspect ratio and stay within terminal bounds (`max_cols` x `max_rows`). |
| 7 | Fallback ASCII/256-Color Ramps | `vazus_core.tui_preview_renderer` | M2 / Tier 1, 3 | `test_tier1_feature.py`, `test_tier3_integration.py` | Validate `--mode=256` (8-bit ANSI codes) and `--mode=ascii` (17/70 char luminance ramps) without TrueColor sequences. |
| 8 | Win32 Clipboard Listener | `vazus_vision_daemon.py` | M3 / Tier 1, 3 | `test_tier1_feature.py`, `test_tier3_integration.py` | Test Win32 HWND message loop hook, `WM_CLIPBOARDUPDATE` (0x031D) event capture, and image bitmap extraction within <500ms. |
| 9 | Workspace File Watcher | `vazus_vision_daemon.py` | M3 / Tier 1, 3 | `test_tier1_feature.py`, `test_tier3_integration.py` | Test `watchfiles` disk drop detection for `.png`/`.jpg`/`.webp`, 100ms debouncing, and ignore-list filtering (`.git`, `.venv`). |
| 10 | Visual Token Payload Generator | `vazus_vision_daemon.py` | M3 / Tier 1, 4 | `test_tier1_feature.py`, `test_tier4_e2e.py` | Assert visual token payload JSON contains SHA-256, `mime_type`, `inline_data`, `tui_preview`, and `rapidocr` text extraction. |
| 11 | IPC & WebSocket Broadcast | `vazus_vision_daemon.py` | M3 / Tier 1, 3 | `test_tier1_feature.py`, `test_tier3_integration.py` | Verify WebSocket server endpoint (`ws://127.0.0.1:8765/ws/vision`) broadcasting and SQLite WAL table `vision_event_stream` insertion. |
| 12 | E2E Test Harness & Suite | `run_e2e_tests.py` | M4 / Tier 4 | `test_tier4_e2e.py`, `run_e2e_tests.py` | Execute complete test suite via `run_e2e_tests.py`, verify exit code 0, tier filtering, and zero-bash payload delivery. |
| 13 | E2E Hardening & Validation | `run_e2e_tests.py` | M5 / Tier 5 | `test_tier4_e2e.py` | Stress test daemon under high frequency events, corrupted payloads, 50MB images, and offline mock-mode isolation. |

---

## 3. Test Architecture & Directory Structure

```
C:\vazus\labs\native_vision_system\
├── TEST_INFRA.md                       # Comprehensive Test Architecture & Feature Matrix (This File)
├── TEST_READY.md                       # E2E Test Suite Status Signal & Readiness Declaration
└── tests\
    ├── __init__.py                     # Package initialization
    ├── conftest.py                     # Global Pytest fixtures (sample images, mocks, contract stubs)
    ├── test_tier1_feature.py           # Tier 1: Feature Coverage (>=5 test cases per feature for F01-F11)
    ├── test_tier2_boundary.py          # Tier 2: Boundary, Edge & Corner Cases (30 test cases)
    ├── test_tier3_integration.py       # Tier 3: Cross-Feature Integration Tests (10 test cases)
    ├── test_tier4_e2e.py               # Tier 4: Real-World Scenarios & Zero-Bash Delivery (8 test cases)
    └── run_e2e_tests.py                # Master E2E Test Runner Script (Exit Code 0 on 100% pass)
```

### Tier Definitions:

- **Tier 1 (Feature Coverage Unit Tests)**: Verifies core functionality of every feature (Features 1–11) with $\ge 5$ explicit test cases per feature (55+ total test cases).
- **Tier 2 (Boundary & Corner Case Tests)**: Tests extreme conditions, empty files, corrupt headers, invalid `@` references, micro/macro viewports, and rapid event bursts (30 test cases).
- **Tier 3 (Cross-Feature Integration Tests)**: Validates multi-module pipelines combining Resolver, Renderer, Daemon, WebSocket IPC, and SQLite WAL logging (10 test cases).
- **Tier 4 (End-to-End Real-World Scenario Tests)**: Simulates zero-bash delivery to Gemini 3.6 Flash, Win+Shift+S clipboard captures, subagent context injection, combined vision+OCR payloads, and worksession workflows (8 test cases).

---

## 4. Master Test Runner Architecture (`run_e2e_tests.py`)

`run_e2e_tests.py` is the central test orchestrator. It executes Pytest programmatically, captures execution duration, formats colorized ANSI summary output, updates `TEST_READY.md`, and enforces exit code rules.

### CLI Invocation:
```powershell
# Run all test tiers (Tiers 1-4)
C:\vazus\.venv\Scripts\python.exe C:\vazus\labs\native_vision_system\tests\run_e2e_tests.py

# Run specific tier with verbose output and signal file update
C:\vazus\.venv\Scripts\python.exe C:\vazus\labs\native_vision_system\tests\run_e2e_tests.py --tier 1 -v --signal
```

### Exit Code Rules:
- **`0`**: Returned if and only if **100% of executed tests pass**.
- **`1`**: Returned if any test fails, errors, or if test collection fails.

---

## 5. Coverage Thresholds & Performance Latency SLAs

| Metric / SLA | Required Threshold | Verification Method |
|--------------|-------------------|---------------------|
| **Tier 1 Feature Coverage** | $\ge 5$ test cases per feature (F01-F11) | `test_tier1_feature.py` suite |
| **Tier 2 Boundary Coverage** | $\ge 30$ corner/edge test cases | `test_tier2_boundary.py` suite |
| **Tier 3 Integration Coverage** | $\ge 10$ cross-module interaction tests | `test_tier3_integration.py` suite |
| **Tier 4 E2E Coverage** | $\ge 8$ real-world scenario tests | `test_tier4_e2e.py` suite |
| **Test Suite Pass Rate** | **100% (0 failures allowed)** | `run_e2e_tests.py` execution |
| **Multimodal Resolver Latency** | $< 40\text{ ms}$ per resolution | `test_tier3_integration.py` |
| **TUI Preview Renderer Latency** | $< 20\text{ ms}$ per render | `test_tier3_integration.py` |
| **Daemon Event Latency** | $< 500\text{ ms}$ end-to-end | `test_tier3_integration.py` |
| **Zero-Bash Payload Delivery** | **0 subprocess / shell calls** | `test_tier4_e2e.py` |
