# Handoff Report — Milestone M2 Empirical Challenge & Verification

**Agent**: m2_challenger_2 (empirical challenger / critic / specialist)  
**Working Directory**: `C:\vazus\labs\native_vision_system\.agents\m2_challenger_2`  
**Target File**: `C:\vazus\vazus_core\tui_preview_renderer.py`  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

### 1.1 Existing Test Suite Execution
- Running `pytest`:
  Command: `C:\vazus\.venv\Scripts\python.exe -m pytest C:\vazus\labs\native_vision_system\tests\test_tui_preview_renderer.py`
  Result: 39 passed in 1.29s (exit code 0).
- Running E2E test runner:
  Command: `C:\vazus\.venv\Scripts\python.exe C:\vazus\labs\native_vision_system\tests\run_e2e_tests.py`
  Result: 169 passed in 2.83s (exit code 0).

### 1.2 Empirical Test Harness Observations & Mathematical Defect
Executed custom empirical test harness (`C:\vazus\labs\native_vision_system\.agents\m2_challenger_2\test_harness.py`) evaluating `compute_preview_dimensions(img_width, img_height, max_cols=80, max_rows=24, is_half_block=True)`:

```
==========================================================================================
EMPIRICAL VERIFICATION 1 & 2: ASPECT RATIO SCALING MATH
==========================================================================================
Image Case         | Image Size  | Img AR  | Current (cols x rows)  | Current Sub AR | Correct (cols x rows)  | Correct Sub AR
------------------------------------------------------------------------------------------------------------------------
Square 1:1         | 1000x1000   |  1.0000 | cols=12, rows=24 (sub 12x48) |         0.2500 | cols=48, rows=24 (sub 48x48) |         1.0000
Landscape 16:9     | 1920x1080   |  1.7778 | cols=21, rows=24 (sub 21x48) |         0.4375 | cols=80, rows=22 (sub 80x44) |         1.8182
Portrait 9:16      | 1080x1920   |  0.5625 | cols= 7, rows=24 (sub  7x48) |         0.1458 | cols=27, rows=24 (sub 27x48) |         0.5625
Panoramic 21:9     | 2560x1080   |  2.3704 | cols=28, rows=24 (sub 28x48) |         0.5833 | cols=80, rows=17 (sub 80x34) |         2.3529
Micro 1x1          |    1x1      |  1.0000 | cols=12, rows=24 (sub 12x48) |         0.2500 | cols=48, rows=24 (sub 48x48) |         1.0000
Huge 4000x3000     | 4000x3000   |  1.3333 | cols=16, rows=24 (sub 16x48) |         0.3333 | cols=64, rows=24 (sub 64x48) |         1.3333
```

- **Line Inspection in `tui_preview_renderer.py`**:
  Lines 101-105:
  ```python
  101: char_aspect = 0.5 if is_half_block else 1.0
  102: target_aspect = (img_width / img_height) * char_aspect
  103:
  104: cols = max_cols
  105: rows = int(round(cols / target_aspect)) if target_aspect > 0 else max_rows
  ```

### 1.3 Card Container Visual Uniformity Observation
Executed `render_card` uniformity check across multiple image aspect ratios:
```
==========================================================================================
EMPIRICAL VERIFICATION 3: CARD CONTAINER VISUAL ALIGNMENT & UNIFORMITY
==========================================================================================
[PASS] Solid Red 100x100: Total lines=20, Visible widths={34}
[PASS] Gradient 200x100: Total lines=20, Visible widths={33}
[PASS] Tall 100x300: Total lines=20, Visible widths={31}

Card Container Uniform Width Result: 100% UNIFORM (PASS)
```

---

## 2. Logic Chain

1. **Derivation of Monospace Terminal Half-Block Geometry**:
   - Monospace font cell width $W_{cell} \approx 0.5 H_{cell}$ ($K_{cell} = 0.5$).
   - Upper half-block `▀` (`U+2580`) divides a character cell into 2 vertical sub-pixels:
     - Sub-pixel width: $W_{sub} = W_{cell} \approx 0.5 H_{cell}$.
     - Sub-pixel height: $H_{sub} = 0.5 H_{cell}$.
     - Sub-pixel aspect ratio: $R_{sub} = \frac{W_{sub}}{H_{sub}} = \frac{0.5 H_{cell}}{0.5 H_{cell}} = 1.0$ (**Exact 1:1 Square Sub-pixels**).
   - In terminal grid units:
     - Sub-pixel width $W_{px} = cols$.
     - Sub-pixel height $H_{px} = 2 \times rows$.
   - To match image aspect ratio $A_{img} = \frac{W_{img}}{H_{img}}$, the sub-pixel grid ratio must satisfy:
     $$\frac{W_{px}}{H_{px}} = \frac{cols}{2 \times rows} = A_{img} \implies \frac{cols}{rows} = 2.0 \times A_{img}$$

2. **Derivation of Single-Character ASCII Geometry**:
   - Monospace font cell aspect ratio $K_{cell} = \frac{W_{cell}}{H_{cell}} \approx 0.5$.
   - Visual aspect ratio on screen:
     $$\frac{\text{Visual Width}}{\text{Visual Height}} = \frac{cols \times W_{cell}}{rows \times H_{cell}} = \frac{cols}{rows} \times K_{cell} = \frac{cols}{rows} \times 0.5 = A_{img} \implies \frac{cols}{rows} = 2.0 \times A_{img}$$

3. **Flaw Analysis of Current Implementation**:
   - `tui_preview_renderer.py` line 101 sets `char_aspect = 0.5 if is_half_block else 1.0` and `target_aspect = A_{img} * char_aspect`.
   - For half-block mode (`is_half_block=True`), `target_aspect = 0.5 * A_{img}`.
   - This sets `rows = cols / target_aspect = 2 * cols / A_{img}` $\implies \frac{cols}{rows} = 0.5 A_{img}$.
   - The resulting sub-pixel grid aspect ratio becomes:
     $$A_{sub\_grid} = \frac{cols}{2 \times rows} = \frac{0.5 A_{img}}{2} = 0.25 A_{img}$$
   - **Consequence**: Every rendered half-block preview is squished horizontally by a factor of 4! A 1:1 square image is rendered as a 1:4 tall skinny rectangle (`12x48` sub-pixels).
   - For ASCII mode (`is_half_block=False`), `char_aspect = 1.0` $\implies \frac{cols}{rows} = A_{img} \implies \text{Visual AR} = 0.5 A_{img}$.
   - **Consequence**: Every ASCII preview is squished horizontally by a factor of 2!

4. **Why Unit Tests Passed**:
   - `TestAspectMath` in `test_tui_preview_renderer.py` only checked `assert cols <= 80` and `assert rows <= 24` without verifying the actual calculated aspect ratio `cols / (rows * 2)` or `cols / rows`.

5. **Card Container Verification**:
   - `render_card` correctly measures maximum visible width taking ANSI escape codes into account (`strip_ansi`), generating 100% uniform line lengths across top border, preview lines, and bottom border.

---

## 3. Caveats

No uninvestigated areas. The mathematical error in `compute_preview_dimensions` was verified empirically and reproduced across all required aspect ratio categories (1:1 square, 16:9 landscape, 9:16 portrait, 21:9 panoramic, micro 1x1, 4000x3000).

---

## 4. Conclusion

**VERDICT: REQUEST_CHANGES**

- **Critical Mathematical Bug**: `compute_preview_dimensions` in `vazus_core/tui_preview_renderer.py` severely distorts image previews (squishing half-block by 4x and ASCII by 2x).
- **Required Fix**:
  In `tui_preview_renderer.py` (lines 101-102), replace:
  ```python
  char_aspect = 0.5 if is_half_block else 1.0
  target_aspect = (img_width / img_height) * char_aspect
  ```
  with:
  ```python
  # Monospace font cell geometry K_cell = W_cell / H_cell = 0.5.
  # Target cell grid ratio (cols / rows) to preserve image physical aspect ratio A_img on screen is 2.0 * A_img.
  target_aspect = (img_width / img_height) * 2.0
  ```
- **Required Unit Test Enhancement**:
  Update `test_tui_preview_renderer.py` `TestAspectMath` test cases to assert exact target sub-pixel aspect ratios (`abs(cols / (rows * 2) - img_w / img_h) < 0.1`) instead of trivial upper bounds checks.
- **Card Container**: `render_card` is 100% compliant and produces uniform line lengths.

---

## 5. Verification Method

1. Run empirical test harness:
   ```powershell
   C:\vazus\.venv\Scripts\python.exe C:\vazus\labs\native_vision_system\.agents\m2_challenger_2\test_harness.py
   ```
   *Expected after fix*: `Square 1:1` produces `cols=48, rows=24` (sub-pixel grid `48x48`), `Correct Sub AR = 1.0000`.

2. Run Pytest unit test suite:
   ```powershell
   C:\vazus\.venv\Scripts\python.exe -m pytest C:\vazus\labs\native_vision_system\tests\test_tui_preview_renderer.py
   ```

3. Run E2E test suite:
   ```powershell
   C:\vazus\.venv\Scripts\python.exe C:\vazus\labs\native_vision_system\tests\run_e2e_tests.py
   ```
