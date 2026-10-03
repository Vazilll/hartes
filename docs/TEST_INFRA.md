# E2E Test Infra: RTU MIREA Academic Truth & Verification Engine

## 1. Test Philosophy
- **Opaque-box, Requirement-Driven**: Derived strictly from `ORIGINAL_REQUEST.md` (2026-09-20T14:02:32Z) and `C:\vazus\.agents\orchestrator_4\PROJECT.md`.
- **Zero-Trust & Zero-Stub**: Prohibition of fake data or synthetic mock universities (`ИКБО-01-23`, `api.mirea.ninja`). Enforces fail-closed behavior when credentials or cache are absent.
- **Fail-Closed Safety Invariant**: Strict interception of mutating HTTP verbs (`POST`, `PUT`, `DELETE`, `PATCH`) and dangerous quiz attempt GETs against `*.mirea.ru`.
- **Methodology**: 4-Tier Verification Hierarchy (Category-Partition + Boundary Value Analysis + Cross-Feature Combinatorial Pipelines + Real-World Workloads & AST Tamper Defense).

---

## 2. Feature Inventory & Coverage Mapping

| # | Feature | Scope / Requirement | Tier 1 (Coverage) | Tier 2 (Boundary) | Tier 3 (Cross) | Tier 4 (Real-World) |
|---|---------|---------------------|:-----------------:|:-----------------:|:--------------:|:-------------------:|
| 1 | Student Profile Model & Sync | ORIGINAL_REQUEST §R1 | `test_tier1_05` | `test_tier2_07` | `test_tier3_01`, `test_tier3_05` | `test_tier4_03` |
| 2 | 18 Academic Debts Stage 1 Deadline | ORIGINAL_REQUEST §R1 | `test_tier1_06` | - | `test_tier3_01`, `test_tier3_04` | `test_tier4_03` |
| 3 | Keycloak SSO Auth & 2FA Extraction | ORIGINAL_REQUEST §R1 | `test_tier1_01..04` | `test_tier2_03` | `test_tier3_01` | - |
| 4 | Official Schedule API Resolution | ORIGINAL_REQUEST §R2 | `test_tier1_07..08` | `test_tier2_01`, `test_tier2_06` | `test_tier3_01` | - |
| 5 | RFC 5545 iCal Parsing & SQLite Sync | ORIGINAL_REQUEST §R2 | `test_tier1_09..11` | `test_tier2_02` | `test_tier3_01`, `test_tier3_05` | `test_tier4_01` |
| 6 | Moodle 4 AJAX Course & Quiz Discovery | ORIGINAL_REQUEST §R3 | `test_tier1_12..14` | `test_tier2_08` | `test_tier3_01`, `test_tier3_04` | - |
| 7 | Strict Read-Only Safety Guardrail | ORIGINAL_REQUEST §R4 | `test_tier1_15..17` | `test_tier2_04` | `test_tier3_03` | `test_tier4_02` |
| 8 | Dead Code & Stub Scrubber | ORIGINAL_REQUEST §R5 | `test_tier1_18..20` | `test_tier2_05` | `test_tier3_02` | `test_tier4_03..04` |

---

## 3. Test Architecture & Runner Infrastructure

- **Primary Runner**: `pytest 9.1.1` inside virtualenv:
  ```powershell
  C:\vazus\.venv\Scripts\python.exe -m pytest tests/test_academic_truth_engine.py -q
  ```
- **Test File**: `tests/test_academic_truth_engine.py` (37 tests across 4 tiers).
- **Isolation Guarantees**:
  - **Isolated SQLite Storage**: `tmp_db` pytest fixture provides a sandboxed temporary SQLite database per test run.
  - **Deterministic Offline Mocks**: Uses `unittest.mock` to simulate Keycloak HTML responses, RFC 5545 iCal feeds, and Moodle 4 AJAX payloads without live network calls.
  - **Progressive Testability**: Features from yet-to-be-implemented milestones (M2–M4) skip gracefully until implemented by worker subagents, preventing collection or runtime breakage.

---

## 4. Real-World Application & Tamper Detection (Tier 4)

| # | Scenario | Invariant Asserted | Threshold | Status |
|---|----------|--------------------|-----------|--------|
| 1 | Full-Semester 87 KB iCal Workload | Fast parsing latency & Moscow time slot resolution | $< 150\text{ ms}$ | **PASS** |
| 2 | Adversarial Subagent Intercept | Intercepts rogue mutating HTTP POST/DELETE/PATCH | 100% blocked | **SKIPPED (M4)** |
| 3 | Zero Synthetic Constants Leak Audit | Zero `ИКБО-01-23` or `api.mirea.ninja` in output records | 0 matches | **PASS** |
| 4 | Zero-Stub AST Audit | Absence of `DEFAULT_SEED_SCHEDULE` or dummy fallbacks | 0 stubs | **PASS** |

---

## 5. Execution Summary
- **Total Test Cases**: 37 tests
- **Active Implemented & Passing**: 15 tests (Milestone M1 & Schema/AST/Benchmark layer)
- **Pending Milestones**: 22 tests (Gracefully skipped pending Worker M2, M3, M4 implementations)
- **Regressions / Failures**: 0 failures
- **Exit Code**: 0
