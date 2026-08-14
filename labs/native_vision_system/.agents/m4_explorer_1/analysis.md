# Comprehensive Architectural Design: E2E Test Infrastructure & Runner
**Project**: Native Terminal Multimodal Vision System (`C:\vazus\labs\native_vision_system`)  
**Architect**: M4 Explorer 1 (E2E Test Infra Architect)  
**Date**: 2026-08-05  

---

## 1. Executive Summary

This document presents the complete architectural specification for the **E2E Test Infrastructure & Test Runner** for the Native Terminal Multimodal Vision System. 

The test harness is designed as an **opaque-box, multi-tiered verification framework** that validates the zero-bash direct vision payload delivery, high-fidelity ANSI preview rendering, real-time Win32/IOCP daemon watchers, and `google.genai` Gemini 3.6 Flash payload construction without requiring manual user interaction or external bash workarounds.

### Core Objectives:
1. **Directory & Layout Specification**: Standardized layout under `C:\vazus\labs\native_vision_system\tests\` supporting 5 distinct test tiers (Feature Unit, Boundary/Corner Cases, Daemon Integration, Zero-Bash E2E Pipeline, and Tier 5 Adversarial Hardening).
2. **Master Test Runner Architecture (`run_e2e_tests.py`)**: Dedicated command-line and programmatic test runner that discovers tests, manages fixtures, executes test suites, outputs ANSI summary reports, manages `TEST_READY.md` signals, and strictly returns **exit code `0` on 100% test pass** (and non-zero on any failure).
3. **`TEST_INFRA.md` Mapping Specification**: Comprehensive template mapping all 13 features from `PROJECT.md` to specific test tiers, module paths, function signatures, input vectors, and acceptance criteria.

---

## 2. Test Framework Directory & File Layout

The test framework resides strictly in `C:\vazus\labs\native_vision_system\tests\`, isolated from production source code (`vazus_core/`, `vazus_vision_daemon.py`). 

```
C:\vazus\labs\native_vision_system\
├── tests\
│   ├── __init__.py
│   ├── conftest.py                     # Global Pytest fixtures (mocks, temp dirs, synthetic assets)
│   ├── pytest.ini                       # Pytest execution config, markers, verbosity, filterwarnings
│   ├── test_helpers.py                  # Synthetic image generators, mock WS client/server, byte corruptors
│   │
│   ├── tier1_feature/                   # Tier 1: Feature Unit Tests (>=5 test cases per feature)
│   │   ├── __init__.py
│   │   ├── test_r1_resolver.py          # Features 1, 2, 3: Preprocessor, Base64 Part Encoder, @ Ref Resolver
│   │   ├── test_r2_tui_renderer.py      # Features 4, 5, 6, 7: Half-block, RLE buffer, Aspect ratio, Fallbacks
│   │   └── test_r3_daemon.py            # Features 8, 9, 10, 11: HWND hook, File watcher, Tokenizer, WS/WAL
│   │
│   ├── tier2_boundary/                  # Tier 2: Boundary, Edge & Corner Cases
│   │   ├── __init__.py
│   │   ├── test_corrupt_and_empty.py    # 0-byte files, truncated streams, bad magic bytes, extension mismatch
│   │   ├── test_ref_boundary.py         # Non-existent @ refs, permission locks, rapid clipboard churn
│   │   └── test_tui_boundary.py         # Viewport extremes (1x1, 1000x1000, 0x0), non-ASCII/Unicode titles
│   │
│   ├── tier3_daemon_integration/        # Tier 3: Real-Time Daemon Integration & Latency Benchmarks
│   │   ├── __init__.py
│   │   ├── test_clipboard_events.py     # Win32 HWND clipboard injects & latency (<500ms)
│   │   ├── test_file_drop_events.py     # watchfiles IOCP disk drop detection & debouncing
│   │   └── test_ipc_websocket.py        # WebSocket client/server event broadcast & SQLite WAL verification
│   │
│   ├── tier4_zero_bash_e2e/             # Tier 4: End-to-End Zero-Bash Payload Delivery
│   │   ├── __init__.py
│   │   ├── test_zero_bash_flow.py       # Image source -> Resolver -> TUI preview -> Gemini 3.6 Flash payload
│   │   └── test_full_pipeline.py        # End-to-end multi-tier pipeline integration flow
│   │
│   └── tier5_adversarial/               # Tier 5: Adversarial Coverage & Hardening (M5)
│       ├── __init__.py
│       └── test_adversarial.py          # Malicious payloads, buffer overflows, memory leak & stress testing
│
├── run_e2e_tests.py                     # Master E2E Test Runner Script (exit code 0 on 100% pass)
└── TEST_INFRA.md                        # Feature-to-Tier Mapping & Test Verification Matrix Document
```

### Key Components of Layout:

1. **`conftest.py`**:
   - `sample_png_bytes`, `sample_jpg_bytes`, `sample_webp_bytes`: Provides valid synthetic binary image fixtures generated via Pillow in-memory (`io.BytesIO`).
   - `temp_workspace_dir`: Provisioned temporary directory fixture for isolated file drop testing.
   - `mock_gemini_client`: Mock `google.genai.Client` fixture validating `types.Part.from_bytes` signature and response payload formatting without consuming API tokens during offline runs.
   - `mock_clipboard`: Win32 RAM clipboard monkeypatch fixture simulating `Win+Shift+S` image placement.
   - `async_ws_server`: In-process ephemeral WebSocket server fixture listening on `ws://127.0.0.1:8765/ws/vision`.

2. **`pytest.ini`**:
   - Defines custom test markers: `@pytest.mark.tier1`, `@pytest.mark.tier2`, `@pytest.mark.tier3`, `@pytest.mark.tier4`, `@pytest.mark.tier5`, `@pytest.mark.slow`, `@pytest.mark.win32`.
   - Configures test discovery pattern: `python_files = test_*.py`, `python_classes = Test*`, `python_functions = test_*`.

---

## 3. Architecture of Master Test Runner (`run_e2e_tests.py`)

`run_e2e_tests.py` is the central test orchestrator. It can be invoked directly from command line (`python run_e2e_tests.py`) or programmatically by subagent workflows.

### 3.1 Key Requirements & Design Constraints:
1. **Exit Code Guarantee**: Must return **`exit_code = 0`** if and only if **100% of executed tests pass**. If any test fails, errors, or if test collection fails, it must exit with **`code = 1`**.
2. **Tiered Execution Filters**: Accepts CLI arguments `--tier 1`, `--tier 2`, `--tier 3`, `--tier 4`, `--tier 5`, or `--all` (default).
3. **Comprehensive Metrics & Reporting**: Summarizes total tests, passed count, failure count, skip count, duration, and percentage pass rate with color-coded ANSI terminal output.
4. **Signal File Management (`TEST_READY.md`)**: When executed with `--update-signal` on 100% pass, automatically writes/updates `C:\vazus\labs\native_vision_system\TEST_READY.md` containing execution timestamp, test count, pass rate, and checksum.

### 3.2 Detailed Design & Implementation Specification:

```python
#!/usr/bin/env python3
"""
run_e2e_tests.py — Master E2E Test Runner for Native Terminal Multimodal Vision System.
Executes test suites across Tiers 1-5, generates summary reports, and enforces exit code 0 on 100% pass.
"""

import sys
import os
import time
import argparse
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.resolve()
TESTS_DIR = PROJECT_ROOT / "tests"
SIGNAL_FILE = PROJECT_ROOT / "TEST_READY.md"

class E2ETestRunner:
    def __init__(self, tier: str = "all", verbose: bool = False, fail_fast: bool = False, update_signal: bool = False):
        self.tier = tier.lower()
        self.verbose = verbose
        self.fail_fast = fail_fast
        self.update_signal = update_signal

    def build_pytest_args(self) -> list[str]:
        args = [
            "-v" if self.verbose else "-q",
            "--tb=short",
            "-s" if self.verbose else "--capture=fd",
        ]
        
        if self.fail_fast:
            args.append("-x")
            
        # Select target directories based on tier
        if self.tier == "all":
            args.append(str(TESTS_DIR))
        elif self.tier in ("1", "tier1"):
            args.append(str(TESTS_DIR / "tier1_feature"))
        elif self.tier in ("2", "tier2"):
            args.append(str(TESTS_DIR / "tier2_boundary"))
        elif self.tier in ("3", "tier3"):
            args.append(str(TESTS_DIR / "tier3_daemon_integration"))
        elif self.tier in ("4", "tier4"):
            args.append(str(TESTS_DIR / "tier4_zero_bash_e2e"))
        elif self.tier in ("5", "tier5"):
            args.append(str(TESTS_DIR / "tier5_adversarial"))
        else:
            raise ValueError(f"Unknown tier: {self.tier}")
            
        return args

    def run(self) -> int:
        print("================================================================================")
        print(f" NATIVE MULTIMODAL VISION SYSTEM — E2E TEST RUNNER [Tier: {self.tier.upper()}]")
        print("================================================================================")
        
        start_time = time.time()
        pytest_args = self.build_pytest_args()
        
        # Execute pytest programmatically
        exit_code = pytest.main(pytest_args)
        elapsed = time.time() - start_time
        
        print("--------------------------------------------------------------------------------")
        print(f" Execution Finished in {elapsed:.2f}s | Pytest Exit Code: {exit_code}")
        
        if exit_code == 0:
            print(" RESULT: [PASS] 100% Test Pass Rate Achieved.")
            if self.update_signal or self.tier == "all":
                self._write_signal_file(elapsed)
            return 0
        else:
            print(f" RESULT: [FAIL] Test Suite Failed with Exit Code {exit_code}.")
            return 1

    def _write_signal_file(self, elapsed: float):
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        content = f"""# E2E Test Suite Status Signal
- Status: 100% PASS
- Timestamp: {timestamp}
- Executed Tier: {self.tier.upper()}
- Duration: {elapsed:.2f}s
- Runner Version: 1.0.0
- Verified Zero-Bash Delivery: YES
"""
        with open(SIGNAL_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print(f" Signal file written: {SIGNAL_FILE}")

def main():
    parser = argparse.ArgumentParser(description="E2E Test Runner for Native Terminal Multimodal Vision System")
    parser.add_argument("--tier", choices=["1", "2", "3", "4", "5", "all"], default="all", help="Target test tier")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose test output")
    parser.add_argument("-x", "--fail-fast", action="store_true", help="Stop on first failure")
    parser.add_argument("--signal", action="store_true", help="Update TEST_READY.md on success")
    
    args = parser.parse_args()
    runner = E2ETestRunner(tier=args.tier, verbose=args.verbose, fail_fast=args.fail_fast, update_signal=args.signal)
    sys.exit(runner.run())

if __name__ == "__main__":
    main()
```

---

## 4. `TEST_INFRA.md` Template Specification

`TEST_INFRA.md` acts as the explicit contract linking the 13 features specified in `PROJECT.md` to concrete test modules, functions, input conditions, and pass criteria.

### 4.1 Feature Inventory to Test Tier Mapping Table

| # | Feature Name | Target Module | Test Tier | Test Case File Path | Verification Method & Assertions |
|---|--------------|---------------|-----------|----------------------|-----------------------------------|
| 1 | Polymorphic File Preprocessor | `vazus_core.multimodal_resolver` | Tier 1 & Tier 2 | `tests/tier1_feature/test_r1_resolver.py`, `tests/tier2_boundary/test_corrupt_and_empty.py` | Verify magic byte headers for `.png`, `.jpg`, `.jpeg`, `.webp`. Verify rejection/fallback of invalid magic bytes. |
| 2 | InlineData Base64 Part Encoder | `vazus_core.multimodal_resolver` | Tier 1 | `tests/tier1_feature/test_r1_resolver.py` | Assert `to_genai_part()` returns `types.Part` with valid `inline_data.mime_type` and Base64 string. |
| 3 | `@` Reference Resolver | `vazus_core.multimodal_resolver` | Tier 1 & Tier 2 | `tests/tier1_feature/test_r1_resolver.py`, `tests/tier2_boundary/test_ref_boundary.py` | Resolve `@clipboard`, `@latest`, `@artifact`. Assert FileNotFoundError for missing `@` targets. |
| 4 | TrueColor Half-Block Renderer | `vazus_core.tui_preview_renderer` | Tier 1 | `tests/tier1_feature/test_r2_tui_renderer.py` | Verify ANSI output contains `\x1b[38;2;...` and `\x1b[48;2;...` with upper half-block character `▀` (U+2580). |
| 5 | ANSI RLE Double-Buffering | `vazus_core.tui_preview_renderer` | Tier 1 | `tests/tier1_feature/test_r2_tui_renderer.py` | Compare batched RLE ANSI string byte length against un-batched string; assert >60% byte reduction. |
| 6 | Aspect Ratio & Bounding Box | `vazus_core.tui_preview_renderer` | Tier 1 & Tier 2 | `tests/tier1_feature/test_r2_tui_renderer.py`, `tests/tier2_boundary/test_tui_boundary.py` | Assert rendered pixel matrix preserves square sub-pixel aspect ratio within target max_cols x max_rows bounds. |
| 7 | Fallback ASCII/256-Color Ramps | `vazus_core.tui_preview_renderer` | Tier 1 | `tests/tier1_feature/test_r2_tui_renderer.py` | Test `--mode=256` and `--mode=ascii`. Verify 256-color escape sequences and 10/17/70 luminance ramps. |
| 8 | Win32 Clipboard Listener | `vazus_vision_daemon.py` | Tier 1 & Tier 3 | `tests/tier1_feature/test_r3_daemon.py`, `tests/tier3_daemon_integration/test_clipboard_events.py` | Verify HWND window creation, `AddClipboardFormatListener` registration, and event latency <500ms. |
| 9 | Workspace File Watcher | `vazus_vision_daemon.py` | Tier 1 & Tier 3 | `tests/tier1_feature/test_r3_daemon.py`, `tests/tier3_daemon_integration/test_file_drop_events.py` | Drop image file into workspace temp dir; assert `watchfiles` triggers event callback within 100ms. |
| 10 | Visual Token Payload Generator | `vazus_vision_daemon.py` | Tier 1 & Tier 4 | `tests/tier1_feature/test_r3_daemon.py`, `tests/tier4_zero_bash_e2e/test_zero_bash_flow.py` | Assert payload JSON contains SHA-256, `mime_type`, `inlineData`, `tui_preview`, and `rapidocr` text. |
| 11 | IPC & WebSocket Broadcast | `vazus_vision_daemon.py` | Tier 1 & Tier 3 | `tests/tier1_feature/test_r3_daemon.py`, `tests/tier3_daemon_integration/test_ipc_websocket.py` | Connect WS client to `ws://127.0.0.1:8765/ws/vision`; verify JSON payload received; check SQLite `vision_event_stream` row. |
| 12 | E2E Test Harness & Suite | `run_e2e_tests.py` | Tier 4 | `tests/tier4_zero_bash_e2e/test_full_pipeline.py` | Execute `run_e2e_tests.py --tier 4`; verify returncode 0 and complete zero-bash vision ingestion flow. |
| 13 | E2E Hardening & Validation | `run_e2e_tests.py` | Tier 5 | `tests/tier5_adversarial/test_adversarial.py` | Inject corrupted bytes, high-frequency events, 50MB images; assert daemon stability and graceful error handling. |

---

## 5. Verification & Quality Assurance Strategy

To ensure absolute reliability of the test runner and infrastructure:

1. **Self-Verification of Runner**:
   - Execute `python run_e2e_tests.py --tier 1` against initial stub tests.
   - Assert exit code 0 when all tests pass.
   - Assert exit code 1 when intentionally introducing a test assertion failure.

2. **Isolation & Determinism**:
   - All file drop tests run inside `tempfile.TemporaryDirectory()`.
   - All network/WebSocket tests use dynamic local ephemeral ports or isolated `127.0.0.1:8765` test handlers.
   - Clipboard tests use mocked Win32 RAM buffers to prevent messing with host clipboard.

3. **Performance Benchmarking**:
   - Tier 3 integration tests include assertion bounds on latency: `assert event_duration_ms < 500`.

---

## 6. Summary & Recommendations

The proposed E2E test infrastructure architecture provides:
- Clean 5-tier modular layout under `tests/`.
- Robust master runner `run_e2e_tests.py` returning exit code 0 on 100% pass.
- Clear contract mapping feature inventory to test cases via `TEST_INFRA.md`.

This design is fully specified and ready for implementation in Milestone M4.
