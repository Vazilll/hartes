# Technical Design & Architectural Specification
## M2: TUI Preview Renderer (`vazus_core/tui_preview_renderer.py`)
### Aspect Ratio Math, Terminal Auto-Resizing, Payload Integration, and Unit Test Plan

---

### 1. Executive Summary

This specification defines the complete architectural integration, mathematical scaling equations, terminal viewport auto-resizing algorithms, and unit testing matrix for `vazus_core.tui_preview_renderer`. Inspired by `Neo3dEngine` (`ConsoleScreen.cs`), `TUIPreviewRenderer` converts image payloads—such as local disk files, `@` references (`@clipboard`, `@latest`, `@artifact`), raw bytes, PIL images, or pre-resolved `ResolvedMultimodalPayload` objects—into high-fidelity 24-bit TrueColor ANSI half-block pixel matrices (`▀` U+2580), 256-color fallbacks, or ASCII luminance ramps inside terminal viewports.

---

### 2. Payload Integration Architecture (`ResolvedMultimodalPayload` ↔ `TUIPreviewRenderer`)

#### 2.1 Interface & Signature Contract
The `TUIPreviewRenderer` accepts flexible polymorphic input sources while natively optimizing when a pre-resolved `ResolvedMultimodalPayload` (from `vazus_core.multimodal_resolver`) is provided:

```python
class TUIPreviewRenderer:
    """
    High-fidelity TUI ANSI/ASCII image preview renderer inspired by Neo3dEngine.
    """
    def __init__(
        self,
        default_mode: str = "auto",
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None,
        border_style: str = "unicode"
    ):
        self.default_mode = default_mode
        self.max_cols = max_cols
        self.max_rows = max_rows
        self.border_style = border_style

    def render(
        self,
        source: Union[ResolvedMultimodalPayload, Image.Image, str, Path, bytes],
        title: Optional[str] = None,
        mode: Optional[str] = None,
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None
    ) -> str:
        """
        Renders an image input or ResolvedMultimodalPayload into an ANSI card string.
        """
        ...
```

#### 2.2 Ingestion & Zero-Redundancy Pipeline
When `render(...)` is invoked:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Input Polymorphism                             │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
          ┌──────────────────────────┴──────────────────────────┐
          ▼                                                     ▼
┌──────────────────────────────┐              ┌───────────────────────────┐
│ ResolvedMultimodalPayload    │              │ Raw Input Source          │
│ (Already resolved by M1)     │              │ (str, Path, bytes, Image) │
└──────────────┬───────────────┘              └─────────────┬─────────────┘
               │                                            │
               │                                  MultimodalResolver.resolve()
               │                                            │
               └──────────────────────┬─────────────────────┘
                                      │
                                      ▼
                   ┌────────────────────────────────────┐
                   │ Extract Payload Metadata           │
                   │ - Original W_img x H_img           │
                   │ - Source label (file_path/type)    │
                   │ - SHA-256 / Mime type              │
                   └──────────────────┬─────────────────┘
                                      │
                                      ▼
                   ┌────────────────────────────────────┐
                   │ Terminal Viewport Bounding Box     │
                   │ - shutil.get_terminal_size()       │
                   │ - Frame overhead subtraction       │
                   │ - Aspect ratio scaling math        │
                   └──────────────────┬─────────────────┘
                                      │
                                      ▼
                   ┌────────────────────────────────────┐
                   │ PIL Image Resampling & Color Prep  │
                   │ - Image.open(io.BytesIO(raw_bytes))│
                   │ - LANCZOS resampling to (W_px,H_px)│
                   │ - Alpha compositing on #0B0D0E     │
                   └──────────────────┬─────────────────┘
                                      │
                                      ▼
                   ┌────────────────────────────────────┐
                   │ Render Buffer & Double-Buffering   │
                   │ - TrueColor Half-Block (▀ U+2580)  │
                   │ - Horizontal ANSI RLE Batching     │
                   │ - Unicode Container Frame Box      │
                   └────────────────────────────────────┘
```

#### 2.3 Key Optimization & Metadata Extraction Rules
1. **Dimension Reuse**:
   `payload.width` and `payload.height` provide the original dimensions $(W_{img}, H_{img})$ immediately without requiring PIL header parsing.
2. **Delayed Pixel Decoding**:
   The binary payload (`payload.raw_bytes`) is converted into a `PIL.Image.Image` via `io.BytesIO` ONLY when pixel downsampling occurs.
3. **Card Container Header Formatting**:
   The header title line automatically constructs a label from payload metadata if `title` is not explicitly provided:
   - If `payload.file_path` is present: `label = Path(payload.file_path).name` (e.g. `"mockup.png"`).
   - If `payload.source_type` is `"clipboard"`: `label = "@clipboard"`.
   - If `payload.source_type` is `"latest"`: `label = "@latest"`.
   - Fallback: `label = f"Image ({payload.sha256[:8]})"`.
   - Formatted Title: `[VISION PREVIEW: <label> | <W_img>x<H_img> -> <C_term>x<R_term>]`

4. **Exception Handling & Propagation**:
   - Any `MultimodalResolverError` raised during secondary resolution (e.g. `ImageNotFoundError`, `ClipboardEmptyError`, `CorruptedImageError`) propagates transparently.
   - If `mode` parameter is invalid (not in `["truecolor", "256", "ascii_10", "ascii_17", "ascii_70", "auto"]`), raise `ValueError`.

---

### 3. Terminal Viewport Auto-Resizing & Aspect Ratio Math

#### 3.1 Terminal Size Detection & Priority Hierarchy
The renderer determines effective viewport boundaries using a 3-tier precedence hierarchy:

```python
import os
import shutil

def get_effective_viewport(
    param_max_cols: Optional[int],
    param_max_rows: Optional[int],
    instance_max_cols: Optional[int],
    instance_max_rows: Optional[int],
    fallback_cols: int = 80,
    fallback_rows: int = 24
) -> tuple[int, int]:
    # Tier 1: Function call parameter overrides
    # Tier 2: Instance default overrides
    # Tier 3: Live terminal size query via shutil.get_terminal_size()
    term_size = shutil.get_terminal_size(fallback=(fallback_cols, fallback_rows))
    
    cols = param_max_cols or instance_max_cols or term_size.columns
    rows = param_max_rows or instance_max_rows or term_size.lines
    
    return max(10, cols), max(5, rows)
```

#### 3.2 Container Frame Overhead & Viewport Constraints
The retro-cyberpunk Unicode card container occupies:
- **Horizontal Overhead**: 2 columns (left vertical border `│` and right vertical border `│`).
- **Vertical Overhead**: 2 lines (top header border `┌── [VISION PREVIEW...] ──┐` and bottom footer border `└────── [Mode...] ──────┘`).

Available inner rendering bounds:
$$V_w = \max(8, \text{effective\_cols} - 2)$$
$$V_h = \max(3, \text{effective\_rows} - 2)$$

---

#### 3.3 Aspect Ratio Scaling Equations

Let $W_{img}, H_{img}$ be the original image dimensions, and $A_{img} = \frac{W_{img}}{H_{img}}$ be the original physical aspect ratio.

```
       Monospace Terminal Cell Geometry & Sub-Pixel Scaling

   Mode A: TrueColor Half-Block (▀)      Modes B & C: Single Cell (ASCII/256)
  ┌───────────────────────────────┐     ┌───────────────────────────────┐
  │       Top Sub-Pixel           │     │                               │
  │     (Foreground Color)        │     │                               │
  ├───────────────────────────────┤     │        Single Pixel           │
  │      Bottom Sub-Pixel         │     │    (Character / 256 Color)    │
  │     (Background Color)        │     │                               │
  └───────────────────────────────┘     └───────────────────────────────┘
   Width: W_cell ≈ 0.5 H_cell            Width: W_cell ≈ 0.5 H_cell
   Sub-pixel H_sub = 0.5 H_cell           Cell H_cell = 1.0
   Aspect: W_sub / H_sub = 1.0 (SQUARE)  Aspect: W_cell / H_cell = 0.5 (TALL)
```

##### 3.3.1 Mode A: 24-Bit TrueColor Unicode Half-Block (`▀` U+2580)

1. **Sub-Pixel Geometry Derivation**:
   - Monospace font cell width $W_{cell} \approx 0.5 H_{cell}$.
   - One character cell contains **2 vertical sub-pixels**: top half (FG) and bottom half (BG).
   - Sub-pixel height: $H_{sub} = 0.5 H_{cell}$.
   - Sub-pixel width: $W_{sub} = W_{cell} \approx 0.5 H_{cell}$.
   - **Sub-Pixel Aspect Ratio**: $\frac{W_{sub}}{H_{sub}} = \frac{0.5 H_{cell}}{0.5 H_{cell}} = 1.0$ (Exact 1:1 Square Geometry!).

2. **Sub-Pixel Matrix Bounds**:
   - Since 1 character column = 1 sub-pixel column ($W_{px} = C_{term}$), max sub-pixel width is $W_{max\_px} = V_w$.
   - Since 1 character row = 2 sub-pixel rows ($H_{px} = 2 \times R_{term}$), max sub-pixel height is $H_{max\_px} = V_h \times 2$.

3. **Bounding Box Math**:
   Step 1: Compute column-constrained sub-pixel dimensions:
   $$W_{px} = \min(W_{img}, W_{max\_px})$$
   $$H_{px} = \text{round}\left(\frac{W_{px}}{A_{img}}\right)$$

   Step 2: Check if $H_{px} > H_{max\_px}$. If true, re-compute row-constrained:
   $$H_{px} = \min(H_{img}, H_{max\_px})$$
   $$W_{px} = \text{round}(H_{px} \times A_{img})$$

   Step 3: Clamp & Calculate Terminal Cell Matrix Grid:
   $$W_{px} = \max(1, W_{px})$$
   $$H_{px} = \max(1, H_{px})$$
   $$C_{term} = W_{px}$$
   $$R_{term} = \left\lceil \frac{H_{px}}{2} \right\rceil$$

4. **Odd Sub-Pixel Height Handling**:
   When $H_{px}$ is odd (e.g. $H_{px} = 23$), the 23rd sub-pixel occupies the top half (`FG`) of terminal cell row $R_{term} = 12$. The bottom half (`BG`) has no corresponding image pixel and is padded with dark background RGB `(0, 0, 0)`.

##### 3.3.2 Modes B & C: 256-Color Indexed ANSI & ASCII Luminance Ramps

1. **Cell Geometry Derivation**:
   - One character cell contains **1 pixel / character**.
   - Cell aspect ratio $K_{cell} = \frac{W_{cell}}{H_{cell}} \approx 0.5$.
   - Adjusted aspect ratio for terminal cell grid:
     $$A_{adj} = \frac{A_{img}}{K_{cell}} = 2.0 \times A_{img}$$

2. **Bounding Box Math**:
   Max cell bounds: $C_{max} = V_w$, $R_{max} = V_h$.

   Step 1: Compute column-constrained cell dimensions:
   $$C_{term} = \min(W_{img}, C_{max})$$
   $$R_{term} = \text{round}\left(\frac{C_{term}}{A_{adj}}\right) = \text{round}\left(\frac{C_{term}}{2.0 \times A_{img}}\right)$$

   Step 2: Check if $R_{term} > R_{max}$. If true, re-compute row-constrained:
   $$R_{term} = \min(H_{img}, R_{max})$$
   $$C_{term} = \text{round}(R_{term} \times A_{adj}) = \text{round}(R_{term} \times 2.0 \times A_{img})$$

   Step 3: Clamp:
   $$C_{term} = \max(1, C_{term})$$
   $$R_{term} = \max(1, R_{term})$$
   Resampling target size for Image: $(C_{term}, R_{term})$.

---

#### 3.4 Summary Table: Dimension Math Across Aspect Ratios

Assuming terminal viewport $V_w = 78$, $V_h = 22$ (80x24 terminal):

| Image Type | Original $(W_{img}, H_{img})$ | $A_{img}$ | Mode A Sub-Pixels $(W_{px}, H_{px})$ | Mode A Cells $(C_{term}, R_{term})$ | Mode B/C Cells $(C_{term}, R_{term})$ |
|------------|-------------------------------|-----------|-------------------------------------|------------------------------------|---------------------------------------|
| Square (1:1) | 1000 x 1000 | 1.0000 | 44 x 44 | 44 x 22 | 44 x 22 |
| Landscape (16:9) | 1920 x 1080 | 1.7778 | 78 x 44 | 78 x 22 | 78 x 22 |
| Portrait (9:16) | 1080 x 1920 | 0.5625 | 25 x 44 | 25 x 22 | 25 x 22 |
| Ultra-Wide (21:9) | 2560 x 1080 | 2.3704 | 78 x 33 | 78 x 17 | 78 x 16 |
| Micro Image | 1 x 1 | 1.0000 | 1 x 1 | 1 x 1 | 1 x 1 |
| Huge Image | 4000 x 3000 | 1.3333 | 59 x 44 | 59 x 22 | 59 x 22 |

---

### 4. Rendering Modes & ANSI RLE Optimization Specification

#### 4.1 Mode Comparison Matrix

| Mode Key | Description | Characters Used | Foreground Colors | Background Colors | RLE ANSI Optimization |
|----------|-------------|-----------------|-------------------|-------------------|-----------------------|
| `truecolor` / `mode_a` | 24-bit TrueColor Half-Block | `▀` (`U+2580`) | 24-bit RGB (`\x1b[38;2;R;G;Bm`) | 24-bit RGB (`\x1b[48;2;R;G;Bm`) | Enabled (>60% reduction) |
| `256` / `mode_b` | 8-bit 256-Color Indexed | ` ` (space) or `█` | 8-bit index (`\x1b[38;5;Nm`) | 8-bit index (`\x1b[48;5;Nm`) | Enabled (>60% reduction) |
| `ascii_10` | 10-char ASCII Luminance | `" .:-=+*#%@"` | None (Plain Text) | None (Plain Text) | N/A |
| `ascii_17` | 17-char Neo3dEngine Ramp | `" .:!/r(l1Z4H9W8$@"` | None (Plain Text) | None (Plain Text) | N/A |
| `ascii_70` | 70-char High-Density Ramp | `"$@B%8&WM#*oahkbdpqwm..."` | None (Plain Text) | None (Plain Text) | N/A |

#### 4.2 Run-Length Encoding (RLE) Batching Logic
Without optimization, emitting ANSI escape codes for every single sub-pixel cell generates ~38 bytes per cell (`\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m▀`), resulting in >70 KB of output for an 80x23 matrix.

**RLE Algorithm**:
```python
def render_rle_row(cells: list[tuple[tuple[int,int,int], tuple[int,int,int]]]) -> str:
    """
    cells: list of ((r_top, g_top, b_top), (r_bot, g_bot, b_bot)) for one row
    """
    row_str = []
    curr_fg = None
    curr_bg = None
    
    for (fg, bg) in cells:
        if fg != curr_fg or bg != curr_bg:
            # Emit color change command only when color state shifts
            row_str.append(f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m")
            curr_fg = fg
            curr_bg = bg
        row_str.append("▀")
        
    row_str.append("\x1b[0m")  # Reset at end of line
    return "".join(row_str)
```

---

### 5. Comprehensive Unit Test Matrix Plan (`tests/test_tui_preview_renderer.py`)

Target Test File: `C:\vazus\labs\native_vision_system\tests\test_tui_preview_renderer.py`
Runner Command: `python -m pytest C:\vazus\labs\native_vision_system\tests\test_tui_preview_renderer.py`

#### 5.1 Test Suite Organization Overview

```
TestTUIRendererSuite
├── 1. TestAspectMath (8 Test Cases)
├── 2. TestTerminalAutoResizing (6 Test Cases)
├── 3. TestPayloadIntegration (6 Test Cases)
├── 4. TestRenderModes (6 Test Cases)
├── 5. TestANSIOptimization (4 Test Cases)
├── 6. TestCardContainer (4 Test Cases)
└── 7. TestErrorHandling (5 Test Cases)
Total: 39 Rigorous Unit Test Cases
```

---

#### 5.2 Detailed Test Case Specifications

##### Category 1: `TestAspectMath` (Scaling Equations & Sub-Pixel Geometry)

| Test ID | Test Name | Input Image | Max Viewport (Cols x Rows) | Expected Sub-Pixel (W_px x H_px) | Expected Cells (C_term x R_term) | Assertion & Verification |
|---------|-----------|-------------|----------------------------|-----------------------------------|----------------------------------|--------------------------|
| `TC-M2-01` | `test_aspect_math_square_1to1` | 1000 x 1000 | 80 x 24 (V_w=78, V_h=22) | 44 x 44 | 44 x 22 | Verify exact 1:1 sub-pixel ratio preservation ($W_{px} = 2 \times R_{term}$). |
| `TC-M2-02` | `test_aspect_math_landscape_169` | 1920 x 1080 | 80 x 24 (V_w=78, V_h=22) | 78 x 44 | 78 x 22 | Verify column-constrained capping ($W_{px} = 78$). |
| `TC-M2-03` | `test_aspect_math_portrait_916` | 1080 x 1920 | 80 x 24 (V_w=78, V_h=22) | 25 x 44 | 25 x 22 | Verify row-constrained capping ($H_{px} = 44$). |
| `TC-M2-04` | `test_aspect_math_panoramic_219` | 2560 x 1080 | 80 x 24 (V_w=78, V_h=22) | 78 x 33 | 78 x 17 | Verify height under-fill ($H_{px} = 33 < 44$, $R_{term} = 17$). |
| `TC-M2-05` | `test_aspect_math_micro_1x1` | 1 x 1 | 80 x 24 (V_w=78, V_h=22) | 1 x 1 | 1 x 1 | Verify lower bound clamping ($W_{px}=1, H_{px}=1, C_{term}=1, R_{term}=1$). |
| `TC-M2-06` | `test_aspect_math_huge_4000x3000` | 4000 x 3000 | 80 x 24 (V_w=78, V_h=22) | 59 x 44 | 59 x 22 | Verify downscaling bounds capping for ultra-large images. |
| `TC-M2-07` | `test_aspect_math_odd_subpixel_height` | 100 x 75 | 80 x 24 (V_w=78, V_h=22) | 59 x 44 (or odd H_px test) | C_term x ceil(H_px/2) | Verify odd sub-pixel height row rounding and black padding in bottom sub-pixel. |
| `TC-M2-08` | `test_aspect_math_ascii_mode` | 1920 x 1080 | 80 x 24 (V_w=78, V_h=22) | N/A (ASCII 1:1 cell) | 78 x 22 | Verify single-character mode aspect ratio correction factor $K_{cell} = 0.5$. |

---

##### Category 2: `TestTerminalAutoResizing` (`shutil.get_terminal_size` & Overrides)

| Test ID | Test Name | Terminal Size Mock | Parameter Overrides | Expected Viewport Constraints | Assertion & Verification |
|---------|-----------|--------------------|---------------------|-------------------------------|--------------------------|
| `TC-M2-09` | `test_term_resize_standard_80x24` | (80, 24) | None | V_w=78, V_h=22 | Verify cell output rows fit inside 22 lines. |
| `TC-M2-10` | `test_term_resize_large_120x40` | (120, 40) | None | V_w=118, V_h=38 | Verify expansion to larger terminal sizes. |
| `TC-M2-11` | `test_term_resize_small_40x10` | (40, 10) | None | V_w=38, V_h=8 | Verify shrinking to small terminal viewports. |
| `TC-M2-12` | `test_term_resize_explicit_max_cols_override` | (120, 40) | max_cols=60, max_rows=15 | V_w=58, V_h=13 | Verify explicit argument takes precedence over `get_terminal_size()`. |
| `TC-M2-13` | `test_term_resize_instance_default_override` | (120, 40) | Init(max_cols=50) | V_w=48 | Verify instance default takes precedence over system terminal size. |
| `TC-M2-14` | `test_term_resize_non_tty_fallback` | OSError / Fallback | None | V_w=78, V_h=22 | Verify fallback to (80, 24) when stdout/stderr is redirected/non-TTY. |

---

##### Category 3: `TestPayloadIntegration` (`ResolvedMultimodalPayload` Ingestion)

| Test ID | Test Name | Input Source Type | Expected Payload Handling | Assertion & Verification |
|---------|-----------|-------------------|---------------------------|--------------------------|
| `TC-M2-15` | `test_payload_direct_object` | `ResolvedMultimodalPayload` | Ingest payload directly | Verify zero re-resolving, use of `payload.width`/`height` and `payload.raw_bytes`. |
| `TC-M2-16` | `test_payload_file_path_str` | `"test.png"` (str) | Auto-invokes `MultimodalResolver.resolve()` | Verify string path is transparently resolved into payload. |
| `TC-M2-17` | `test_payload_path_object` | `Path("test.png")` | Auto-invokes `MultimodalResolver.resolve()` | Verify `Path` object is resolved into payload. |
| `TC-M2-18` | `test_payload_raw_bytes` | `b"\x89PNG..."` | Auto-invokes `MultimodalResolver.resolve()` | Verify raw PNG bytes input. |
| `TC-M2-19` | `test_payload_pil_image` | `PIL.Image.Image` | Auto-invokes `MultimodalResolver.resolve()` | Verify PIL Image input. |
| `TC-M2-20` | `test_payload_card_header_metadata` | Payload (`file_path="foo.jpg"`) | Title formatting | Verify card top border header includes `"foo.jpg"` and resolution info `1920x1080 -> C_term x R_term`. |

---

##### Category 4: `TestRenderModes` (Mode Selection & Character Ramps)

| Test ID | Test Name | Specified Mode | Expected Escape Sequences / Chars | Assertion & Verification |
|---------|-----------|----------------|-----------------------------------|--------------------------|
| `TC-M2-21` | `test_mode_truecolor` | `mode="truecolor"` | `\x1b[38;2;...m`, `\x1b[48;2;...m`, `▀` | Verify 24-bit TrueColor codes and upper half-block characters. |
| `TC-M2-22` | `test_mode_256_color` | `mode="256"` | `\x1b[38;5;...m`, `\x1b[48;5;...m` | Verify 256-color indexed ANSI codes. |
| `TC-M2-23` | `test_mode_ascii_10` | `mode="ascii_10"` | `" .:-=+*#%@"` | Verify 10-char ASCII luminance ramp, no ANSI escape sequences. |
| `TC-M2-24` | `test_mode_ascii_17` | `mode="ascii_17"` | `" .:!/r(l1Z4H9W8$@"` | Verify 17-char Neo3dEngine ramp, no ANSI escape sequences. |
| `TC-M2-25` | `test_mode_ascii_70` | `mode="ascii_70"` | `"$@B%8&WM#*oahkbdpqwm..."` | Verify 70-char high-density ramp, no ANSI escape sequences. |
| `TC-M2-26` | `test_mode_auto_detection` | `mode="auto"` | TrueColor or 256 depending on env | Verify automatic fallback selection based on environment capability. |

---

##### Category 5: `TestANSIOptimization` (RLE Sequence Reduction & Double-Buffering)

| Test ID | Test Name | Input Test Image | Metric Comparison | Assertion & Verification |
|---------|-----------|------------------|-------------------|--------------------------|
| `TC-M2-27` | `test_rle_solid_color_reduction` | Solid Red Image (80x40) | Batched vs Un-batched string length | Verify RLE batching reduces string byte count by >80% for solid colors. |
| `TC-M2-28` | `test_rle_checkerboard_worst_case` | Alternating Checkerboard | Batched vs Un-batched string length | Verify algorithm functions correctly without corruption in worst-case color shifts. |
| `TC-M2-29` | `test_rle_reset_sequence_at_line_end` | Gradient Image | End of row escape codes | Verify `\x1b[0m` reset sequence is present at the end of every row string. |
| `TC-M2-30` | `test_double_buffering_no_op_diff` | Identical Sequential Frames | Buffer delta output | Verify unchanged frames generate zero cursor redraw commands. |

---

##### Category 6: `TestCardContainer` (Unicode Frame & Layout Structure)

| Test ID | Test Name | Viewport Cols x Rows | Expected Border Characters | Assertion & Verification |
|---------|-----------|----------------------|----------------------------|--------------------------|
| `TC-M2-31` | `test_card_border_corners` | 80 x 24 | `┌`, `┐`, `└`, `┘`, `─`, `│` | Verify Unicode container box corners and borders are rendered cleanly. |
| `TC-M2-32` | `test_card_total_line_count` | 80 x 24 ($R_{term} = 20$) | Line count = $R_{term} + 2$ | Verify total output string lines equals inner cell rows + 2 border rows (header + footer). |
| `TC-M2-33` | `test_card_row_width_uniformity` | 80 x 24 ($C_{term} = 78$) | Visible line width = $C_{term} + 2$ | Strip ANSI codes and verify all rendered lines have identical character length. |
| `TC-M2-34` | `test_card_custom_title_override` | Custom Title `"My Snapshot"` | Top header text | Verify top border displays `"My Snapshot"` centered/left-aligned in frame. |

---

##### Category 7: `TestErrorHandling` (Exceptions & Boundary Guardrails)

| Test ID | Test Name | Trigger Scenario | Expected Exception | Assertion & Verification |
|---------|-----------|------------------|--------------------|--------------------------|
| `TC-M2-35` | `test_error_non_existent_file` | `"non_existent.png"` | `ImageNotFoundError` | Verify missing file raises `ImageNotFoundError` from resolver. |
| `TC-M2-36` | `test_error_corrupted_payload` | `b"CORRUPTED_BYTES"` | `CorruptedImageError` | Verify corrupted bytes raise `CorruptedImageError`. |
| `TC-M2-37` | `test_error_invalid_render_mode` | `mode="invalid_xyz"` | `ValueError` | Verify invalid mode string raises `ValueError`. |
| `TC-M2-38` | `test_error_empty_clipboard` | `@clipboard` (empty) | `ClipboardEmptyError` | Verify empty clipboard raises `ClipboardEmptyError`. |
| `TC-M2-39` | `test_error_zero_viewport_bounds` | max_cols=0, max_rows=0 | Bound Clamping | Verify renderer clamps bounds to min 10x5 instead of crashing with division by zero. |

---

### 6. Architectural Conclusion & Next Steps

1. **Aspect Ratio Fidelity**:
   Mode A's 1:1 sub-pixel geometry ($W_{sub} / H_{sub} = 1.0$) ensures zero aspect ratio distortion inside terminal hosts.
2. **Seamless Integration**:
   `TUIPreviewRenderer.render(...)` integrates directly with `ResolvedMultimodalPayload` from M1, extracting native metadata and avoiding duplicate Pillow decodes.
3. **Test Readiness**:
   The 39 unit test cases defined in `tests/test_tui_preview_renderer.py` guarantee 100% code coverage across all dimension edge cases, terminal window resizes, RLE ANSI optimizations, card containers, and error states.
