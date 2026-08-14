## 2026-08-05T02:18:52Z
<USER_REQUEST>
You are M2 Worker Iteration 2 (m2_worker_2).
Working directory: C:\vazus\labs\native_vision_system\.agents\m2_worker_2

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Objective:
Fix two specific issues identified by M2 Reviewer 1 and M2 Challenger 2 during Gate verification.

Target Files to Edit:
1. `C:\vazus\vazus_core\multimodal_resolver.py`
2. `C:\vazus\vazus_core\tui_preview_renderer.py`
3. `C:\vazus\labs\native_vision_system\tests\test_tui_preview_renderer.py`

Read reports first:
- `C:\vazus\labs\native_vision_system\.agents\m2_reviewer_1\handoff.md` (pytest temp dir pollution in @latest)
- `C:\vazus\labs\native_vision_system\.agents\m2_challenger_2\handoff.md` (aspect ratio math formula fix)

Fix Details:
1. `vazus_core/multimodal_resolver.py`:
   - In `skip_dirs` during directory scanning for `@latest` image resolution (around line 273), ensure `pytest-` and `pytest-of-` directories are ignored (e.g. `d.name.startswith("pytest-")` or `d.name.startswith("pytest-of-")` or adding to `skip_dirs`), so `%TEMP%` pytest directories from previous test runs do not pollute `@latest` image resolution.

2. `vazus_core/tui_preview_renderer.py`:
   - In `compute_preview_dimensions`:
     Change:
     ```python
     char_aspect = 0.5 if is_half_block else 1.0
     target_aspect = (img_width / img_height) * char_aspect
     ```
     to:
     ```python
     # Monospace font cell geometry K_cell = W_cell / H_cell = 0.5.
     # Target cell grid ratio (cols / rows) to preserve image physical aspect ratio A_img on screen is 2.0 * A_img.
     target_aspect = (img_width / img_height) * 2.0
     ```

3. `tests/test_tui_preview_renderer.py`:
   - Update `TestAspectMath` test cases (TC-M2-01 to TC-M2-08) to assert exact aspect ratio scaling:
     - Square 1000x1000 at max (80, 24) -> cols=48, rows=24 (sub-pixel grid 48x48, sub-pixel AR = 1.0000).
     - Landscape 1920x1080 -> cols=78 (or 80), rows=22.
     - Portrait 1080x1920 -> cols=27, rows=24.
     - Micro 1x1 -> cols=2 (or clamped min 1), rows=1.
     Verify `abs(cols / (rows * 2) - img_width / img_height) < 0.1` for half-blocks.

Verification:
- Run `C:\vazus\.venv\Scripts\python.exe -m pytest C:\vazus\labs\native_vision_system\tests\test_tui_preview_renderer.py`
- Run `C:\vazus\.venv\Scripts\python.exe C:\vazus\labs\native_vision_system\tests\run_e2e_tests.py` twice consecutively to ensure zero cross-run test pollution and 100% pass rate.

Write your report to `C:\vazus\labs\native_vision_system\.agents\m2_worker_2\handoff.md` and send a message back.
</USER_REQUEST>
