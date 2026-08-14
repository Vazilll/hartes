# Technical Design & Architectural Specification
## R2: TUI ASCII/ANSI Terminal Preview Renderer (Neo3dEngine Integration)

### 1. Executive Summary
This document defines the complete architectural design, mathematical algorithms, character encoding specifications, and integration interfaces for **R2: TUI ASCII/ANSI Terminal Preview Renderer**. Inspired by `Neo3dEngine` (`ConsoleScreen.cs` / `ConsoleScreenAsync.cs`), this component renders instant, high-fidelity visual preview matrices inside Windows PowerShell and standard ANSI terminal hosts whenever an image path or `@` reference (such as `@clipboard`, `@latest`, `@artifact:name`) is processed.

---

### 2. Neo3dEngine Architectural Principles & Synthesis

#### 2.1 Double-Buffering & Run-Length Encoding (RLE) Optimization
`ConsoleScreen.cs` and `ConsoleScreenAsync.cs` demonstrate two critical techniques for smooth terminal rendering:
1. **Character & Color Matrix Double-Buffering**:
   - Maintain a contiguous memory representation of the frame (`char_buffer`, `fg_color_buffer`, `bg_color_buffer`).
   - Compare frame buffers to eliminate unnecessary terminal repaints and cursor moves.
2. **Run-Length Color Sequence Batching**:
   - Instead of emitting ANSI escape codes before every single character cell (which bloats output by ~38 bytes per pixel), contiguous horizontal runs of pixels sharing identical foreground/background states are grouped together into a single write block.
   - **Formula / Pseudocode**:
     ```python
     run_chars = []
     current_fg, current_bg = None, None
     for cell in frame:
         if cell.fg != current_fg or cell.bg != current_bg:
             flush_run(run_chars, current_fg, current_bg)
             current_fg, current_bg = cell.fg, cell.bg
         run_chars.append(cell.char)
     flush_run(run_chars, current_fg, current_bg)
     ```
   - This optimization reduces ANSI string byte overhead by 60%–85% for typical downsampled image previews.

#### 2.2 Monospace Character Aspect Ratio Correction
Standard monospace terminal fonts (Consolas, Cascadia Code, Lucida Console, Menlo) have a non-square cell geometry:
- Width-to-Height Ratio $R_{cell} = \frac{W_{cell}}{H_{cell}} \approx \frac{11}{24} \approx 0.4583 \approx 0.5$.
- As observed in `ConsoleScreen.cs` line 11: `_pixelAspect = 11.0f / 24.0f`.
- Uncorrected 1:1 pixel mapping leads to extreme vertical stretching (images appear twice as tall).

---

### 3. Rendering Modes & Character Set Selection

The TUI Renderer provides three distinct rendering tiers automatically selected based on terminal capability detection:

```
+-------------------------------------------------------------------------+
|                        TUI Rendering Pipeline                           |
+-------------------------------------------------------------------------+
| Input Image / @ Reference                                               |
|   ├── Direct File Path (.png, .jpg, .webp, .bmp)                        |
|   ├── @clipboard / @clip (RAM Clipboard Payload)                        |
|   └── @latest / @artifact:name (Workspace Drop)                         |
+-------------------------------------------------------------------------+
                                  │
                                  ▼
                   ┌──────────────────────────────┐
                   │ Image Downsampler & Aspect   │
                   │ Ratio Normalizer             │
                   └──────────────┬───────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ Mode A:          │    │ Mode B:          │    │ Mode C:          │
│ 24-Bit TrueColor │    │ 256-Color ANSI   │    │ Pure ASCII       │
│ Unicode Half-Block│    │ Fallback Matrix  │    │ Luminance Ramp   │
│ (▀ U+2580)       │    │ (8-Bit Indexed)  │    │ (10 / 70 Ramp)   │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

#### 3.1 Mode A: 24-Bit TrueColor Half-Block Matrix (`▀` U+2580) [Default]
- **Mechanism**: Each terminal character cell displays **two vertical sub-pixels** using the Unicode upper half-block character `▀` (`U+2580`).
  - **Top Sub-Pixel**: Foreground color `\x1b[38;2;R_top;G_top;B_topm`
  - **Bottom Sub-Pixel**: Background color `\x1b[48;2;R_bot;G_bot;B_botm`
- **Aspect Ratio Equivalence**:
  - Because one character cell (height $H_{cell}$, width $W_{cell} \approx 0.5 H_{cell}$) contains 2 vertical pixels, each half-block pixel has height $0.5 H_{cell}$ and width $W_{cell} \approx 0.5 H_{cell}$.
  - **Resulting Sub-Pixel Aspect Ratio is $1.0$ (Square Pixels)!**
  - Sampling resolution for target cell grid $(W_{term}, H_{term})$ requires resizing image to exact resolution $(W_{term}, 2 \times H_{term})$.

#### 3.2 Mode B: 256-Color (8-Bit) Indexed ANSI Fallback
- Used when terminal environment lacks 24-bit TrueColor support or explicit `--256` flag is passed.
- **Escape Sequences**: `\x1b[38;5;{code}m` (FG) and `\x1b[48;5;{code}m` (BG).
- **RGB-to-256 Color Quantization Formula**:
  - For color component $C \in \{R, G, B\}$, map to 6-level cube: $V_c = \text{round}\left(\frac{C}{255} \times 5\right)$
  - 6x6x6 Color Index: $I_{cube} = 16 + 36 V_r + 6 V_g + V_b$
  - Grayscale Index (for $R \approx G \approx B$): $I_{gray} = 232 + \text{round}\left(\frac{L - 8}{247} \times 23\right)$ where $L = 0.299R + 0.587G + 0.114B$.
  - Euclidean distance selects minimum error index between $I_{cube}$ and $I_{gray}$.

#### 3.3 Mode C: Pure ASCII Luminance Ramp
- Used for plain text logs, serial output, or zero-ANSI fallback modes (`--ascii`).
- **Gradient Ramps**:
  - **Standard Ramp (10 chars)**: `" .:-=+*#%@"`
  - **Neo3dEngine Ramp (17 chars)**: `" .:!/r(l1Z4H9W8$@"` (Direct from `ConsoleScreen.cs` line 12)
  - **High-Density Ramp (70 chars)**: `"$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "`
- **Luminance Mapping**:
  $$L = 0.299 R + 0.587 G + 0.114 B$$
  $$\text{Index} = \text{clamp}\left(\left\lfloor \frac{L}{255} \times (\text{len(ramp)} - 1) \right\rfloor, 0, \text{len(ramp)} - 1\right)$$
- **Aspect Ratio Compensation for ASCII**:
  - Image is downsampled to resolution $(W_{term}, \text{round}(W_{term} \times 0.5 \times \frac{H_{img}}{W_{img}}))$.

---

### 4. Image Downsampling & Bounding Box Math

#### 4.1 Bounding Box Calculation Algorithm
Given:
- Input Image dimensions: $(W_{img}, H_{img})$
- Target maximum terminal viewport constraints: $(T_{w\_max}, T_{h\_max})$ (Default: $T_{w\_max} = 80$, $T_{h\_max} = 30$)
- Character cell aspect ratio factor $K_{cell}$:
  - For Half-Block Mode: $K_{cell} = 1.0$ (since 1 cell row = 2 pixel rows)
  - For Single-Char/ASCII Mode: $K_{cell} = 0.5$ (since 1 cell row = 1 pixel row, half as wide)

**Algorithm**:
```python
def compute_preview_dimensions(
    img_w: int,
    img_h: int,
    max_term_w: int = 80,
    max_term_h: int = 30,
    is_half_block: bool = True
) -> tuple[int, int, int, int]:
    """
    Returns (cell_cols, cell_rows, sampled_pixel_w, sampled_pixel_h)
    preserving image aspect ratio within maximum terminal bounding box.
    """
    aspect = img_w / img_h
    
    if is_half_block:
        # Effective aspect ratio in terminal grid:
        # Each cell has 2 vertical pixels, so 1 cell col x 1 cell row is square in pixel space!
        # Target cell grid:
        target_cell_w = min(img_w, max_term_w)
        target_cell_h = round(target_cell_w / aspect)
        
        if target_cell_h > max_term_h:
            target_cell_h = max_term_h
            target_cell_w = round(target_cell_h * aspect)
            
        sampled_pixel_w = max(1, target_cell_w)
        sampled_pixel_h = max(2, target_cell_h * 2)  # 2 pixels per row
        cell_cols = sampled_pixel_w
        cell_rows = target_cell_h
    else:
        # ASCII / Single Char mode: cell aspect ratio ~ 0.5
        adj_aspect = aspect / 0.5  # 2.0 * aspect
        cell_cols = min(img_w, max_term_w)
        cell_rows = round(cell_cols / adj_aspect)
        
        if cell_rows > max_term_h:
            cell_rows = max_term_h
            cell_cols = round(cell_rows * adj_aspect)
            
        cell_cols = max(1, cell_cols)
        cell_rows = max(1, cell_rows)
        sampled_pixel_w = cell_cols
        sampled_pixel_h = cell_rows
        
    return cell_cols, cell_rows, sampled_pixel_w, sampled_pixel_h
```

#### 4.2 Resampling Filter Selection
- **Interpolation**: `PIL.Image.Resampling.LANCZOS` (or `BICUBIC`) for sharp downsampling without moiré patterns or jagged pixel artifacts.
- **Color Space**: Perform downsampling in `RGB` / `RGBA` color space (convert `RGBA` transparent pixels against a dark background `#0B0D0E` or checkerboard).

---

### 5. Input Reference Resolution (@ Handlers)

The preview renderer must support seamless input targets:

| Reference Format | Source Resolution Logic |
|------------------|--------------------------|
| `C:\path\to\file.png` | Direct disk read via PIL |
| `@clipboard` / `@clip` | Reads Windows RAM clipboard via `PIL.ImageGrab.grabclipboard()`. If image exists, save temporary memory buffer. If text path in clipboard, parse path. |
| `@latest` / `@last` | Scans workspace directory `C:\vazus\labs\native_vision_system` for most recently modified `.png`, `.jpg`, `.jpeg`, `.webp` file. |
| `@artifact:<name>` | Searches `C:\Users\Vaz\.gemini\antigravity-cli\brain\...` artifact folders for matching PNG preview images. |

---

### 6. Card Frame & Terminal UI Container Specification

To integrate with `vazus_core` CLI aesthetic, previews are enclosed in a high-tech retro-cyberpunk Unicode card container:

```
┌── [VISION PREVIEW: screenshot_2026-08-05.png | 1920x1080 -> 80x24] ─────────────────┐
│ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀ │
│ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀ │
│ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀ │
│ ...                                                                                │
└─────────────────────────────────────────────── [Mode: 24-bit TrueColor (▀)] ──────┘
```

#### Border Character Set
- Top-Left: `┌` (`U+250C`)
- Top-Right: `┐` (`U+2510`)
- Bottom-Left: `└` (`U+2514`)
- Bottom-Right: `┘` (`U+2518`)
- Horizontal: `─` (`U+2500`)
- Vertical: `│` (`U+2502`)

#### Windows PowerShell VT100 Initialization
```python
import sys
import ctypes

def enable_vt_processing():
    """Enables ANSI escape sequences in Windows PowerShell / Command Prompt."""
    if sys.platform == 'win32':
        kernel32 = ctypes.windll.kernel32
        # STD_OUTPUT_HANDLE = -11
        hOut = kernel32.GetStdHandle(-11)
        if hOut != -1 and hOut != 0:
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(hOut, ctypes.byref(mode)):
                # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                mode.value |= 0x0004
                kernel32.SetConsoleMode(hOut, mode)
```

---

### 7. Module Interface & Implementation Contract

Proposed module path: `vazus_core/tui_preview_renderer.py`

```python
class TUIPreviewRenderer:
    """
    High-fidelity TUI ANSI/ASCII image preview renderer inspired by Neo3dEngine.
    """
    def __init__(self, default_mode: str = "auto", max_width: int = 80, max_height: int = 30):
        self.default_mode = default_mode
        self.max_width = max_width
        self.max_height = max_height

    def render_preview(
        self,
        source: str | Path | Image.Image,
        title: str | None = None,
        mode: str | None = None,
        max_w: int | None = None,
        max_h: int | None = None
    ) -> str:
        ...

    def resolve_source(self, source: str | Path | Image.Image) -> tuple[Image.Image, str]:
        ...

    def _render_half_block_matrix(self, img: Image.Image, cell_w: int, cell_h: int) -> str:
        ...

    def _render_ascii_matrix(self, img: Image.Image, cell_w: int, cell_h: int, ramp: str) -> str:
        ...
```

---

### 8. Verification & Test Plan

1. **Unit Verification**:
   - Resampling dimension test: Verify `compute_preview_dimensions(1920, 1080, 80, 30, True)` returns exact square pixel counts.
   - RLE sequence reduction test: Verify run-length batching reduces ANSI string output length compared to un-batched rendering.
2. **Terminal Host Verification**:
   - Test in Windows PowerShell 7+, Windows Terminal, and standard Windows `cmd.exe`.
3. **Input Handler Verification**:
   - Verify `@clipboard` extracts PNG image data when an image is copied to clipboard.
   - Verify `@latest` detects the newest file in `C:\vazus\labs\native_vision_system`.
