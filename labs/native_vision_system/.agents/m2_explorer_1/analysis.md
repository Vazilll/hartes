# Technical Design & Architectural Specification
## M2: TUI Terminal Preview Renderer (`vazus_core/tui_preview_renderer.py`)

### 1. Executive Summary & Scope

This document presents the complete architectural specification, mathematical formulas, rendering pipelines, ANSI optimization algorithms, and implementation blueprint for `vazus_core/tui_preview_renderer.py` (Milestone M2: TUI Terminal Preview Renderer).

Inspired by `Neo3dEngine` (`ConsoleScreen.cs` / `ConsoleScreenAsync.cs`), `TUIPreviewRenderer` converts image files (`.png`, `.jpg`, `.jpeg`, `.webp`), PIL images, byte streams, `@` symbolic references (`@clipboard`, `@latest`, `@artifact:<name>`), and `ResolvedMultimodalPayload` objects into high-fidelity ANSI/ASCII terminal visual previews.

Key Features & Specifications:
1. **24-bit TrueColor Half-Block Matrix Renderer**: Uses Unicode upper half-block `▀` (`U+2580`) with top sub-pixel ANSI foreground (`\x1b[38;2;R;G;Bm`) and bottom sub-pixel ANSI background (`\x1b[48;2;R;G;Bm`), achieving a true $1:1$ square sub-pixel aspect ratio.
2. **Horizontal Run-Length Encoding (RLE) Batching**: Batches identical adjacent foreground/background color codes along horizontal rows, compressing terminal stdout output string size by >60% (up to 96% for solid blocks).
3. **Double-Buffering State Management**: Supports frame diffing against a front-buffer to suppress terminal repaints and cursor flickering in interactive CLI daemon workflows.
4. **256-Color RGB Quantization Fallback**: Quantizes 24-bit RGB values to 8-bit ANSI 256-color palette (`\x1b[38;5;{code}m` / `\x1b[48;5;{code}m`) using a 6x6x6 color cube and 24-step grayscale ramp.
5. **ASCII Luminance Ramps**: Provides 10-char standard, 17-char Neo3dEngine, and 70-char high-density ASCII luminance mapping modes for monochrome or legacy text terminals.
6. **Native Windows VT100 Setup**: Integrates `ctypes.windll.kernel32.SetConsoleMode` to enable `ENABLE_VIRTUAL_TERMINAL_PROCESSING` (0x0004) on Windows PowerShell and CMD hosts.

---

### 2. Class Architecture & Method Signatures

Target File: `C:\vazus\vazus_core\tui_preview_renderer.py`

```python
"""
Native TUI Terminal Preview Renderer for vazus_core.
Inspired by Neo3dEngine (ConsoleScreen.cs).
Renders 24-bit TrueColor half-block matrices, 256-color fallback, and ASCII ramps
with horizontal Run-Length Encoding (RLE) ANSI escape sequence compression.
"""

import sys
import io
import os
import ctypes
from pathlib import Path
from typing import Union, Optional, Tuple, List, Dict, Any
from PIL import Image

from vazus_core.multimodal_resolver import MultimodalResolver, ResolvedMultimodalPayload


# --- VT100 Console Initialization ---

def enable_vt100_support() -> bool:
    """
    Enables VT100 ANSI escape code processing on Windows console stdout handle.
    Returns True if successfully enabled or running on non-Windows OS.
    """
    if sys.platform != "win32":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        STD_OUTPUT_HANDLE = -11
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

        hOut = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        if hOut == -1 or hOut == 0 or hOut is None:
            return False

        dwMode = ctypes.c_ulong()
        if not kernel32.GetConsoleMode(hOut, ctypes.byref(dwMode)):
            return False

        dwMode.value |= ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(kernel32.SetConsoleMode(hOut, dwMode))
    except Exception:
        return False


# --- Core TUIPreviewRenderer Class ---

class TUIPreviewRenderer:
    """
    High-fidelity terminal image matrix buffer visualizer.
    """

    # ASCII Luminance Ramps
    RAMP_10 = " .:-=+*#%@"
    RAMP_17 = " .:!/r(l1Z4H9W8$@"  # Direct from Neo3dEngine ConsoleScreen.cs line 12
    RAMP_70 = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "

    def __init__(self, default_mode: str = "truecolor", max_cols: int = 80, max_rows: int = 40):
        self.default_mode = default_mode
        self.max_cols = max_cols
        self.max_rows = max_rows
        self._front_buffer: Optional[List[List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]]] = None
        # Auto-enable Windows VT100 mode on instantiation
        enable_vt100_support()

    @staticmethod
    def compute_preview_dimensions(
        img_width: int,
        img_height: int,
        max_cols: int = 80,
        max_rows: int = 40,
        is_half_block: bool = True
    ) -> Tuple[int, int]:
        """
        Calculates optimal terminal grid dimensions (cols, rows) preserving image aspect ratio.
        
        Math:
        For half-block mode (is_half_block=True):
            1 character cell contains 2 vertical sub-pixels.
            Each cell has font width W_cell ~ 0.5 * H_cell.
            With 2 sub-pixels per cell, sub-pixel height H_sub = 0.5 * H_cell.
            Sub-pixel aspect ratio R_sub = W_cell / H_sub = 1.0 (Square sub-pixels!).
            Effective grid aspect ratio A_grid = cols / rows = img_width / img_height.

        For single-char ASCII mode (is_half_block=False):
            1 character cell contains 1 pixel (width ~ 0.5 * height).
            Effective grid aspect ratio A_grid = cols / rows = 2.0 * (img_width / img_height).
        """
        if img_width <= 0 or img_height <= 0 or max_cols <= 0 or max_rows <= 0:
            return (max(1, max_cols), max(1, max_rows))

        char_aspect = 0.5 if is_half_block else 1.0
        target_aspect = (img_width / img_height) * char_aspect

        cols = max_cols
        rows = int(round(cols / target_aspect))
        if rows > max_rows:
            rows = max_rows
            cols = int(round(rows * target_aspect))

        return (max(1, cols), max(1, rows))

    @classmethod
    def rgb_to_256_color(cls, r: int, g: int, b: int) -> int:
        """
        Quantizes 24-bit RGB (0-255) to 8-bit ANSI 256-color index (0-255).
        Uses 6x6x6 color cube (16-231) and 24-step grayscale ramp (232-255).
        """
        # Check grayscale case
        if abs(r - g) < 10 and abs(g - b) < 10:
            lum = int(round(0.299 * r + 0.587 * g + 0.114 * b))
            if lum < 8:
                return 16  # Pure black in cube
            if lum > 248:
                return 231 # Pure white in cube
            return 232 + int(round((lum - 8) / 247.0 * 23.0))

        # 6x6x6 Color Cube mapping
        vr = int(round(r / 255.0 * 5.0))
        vg = int(round(g / 255.0 * 5.0))
        vb = int(round(b / 255.0 * 5.0))
        return 16 + 36 * vr + 6 * vg + vb

    @classmethod
    def render(
        cls,
        payload_or_image: Union[ResolvedMultimodalPayload, Image.Image, str, Path, bytes],
        max_cols: int = 80,
        max_rows: int = 40,
        mode: str = "truecolor"
    ) -> str:
        """
        Main entrypoint. Ingests polymorphic image source and returns ANSI/ASCII string.
        """
        # 1. Image Ingestion & Resolution
        img = cls._load_pil_image(payload_or_image)

        # 2. Convert RGBA/P to RGB with dark background compositing
        if img.mode != "RGB":
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (11, 13, 14)) # Dark background #0B0D0E
                bg.paste(img, mask=img.split()[3])
                img = bg
            else:
                img = img.convert("RGB")

        # 3. Mode Dispatch
        norm_mode = mode.lower().strip()
        is_half_block = norm_mode in ("truecolor", "256", "256color")
        cols, rows = cls.compute_preview_dimensions(
            img.width, img.height, max_cols=max_cols, max_rows=max_rows, is_half_block=is_half_block
        )

        if norm_mode == "truecolor":
            return cls._render_truecolor_halfblock(img, cols, rows)
        elif norm_mode in ("256", "256color"):
            return cls._render_256color_halfblock(img, cols, rows)
        elif norm_mode.startswith("ascii"):
            return cls._render_ascii_ramp(img, cols, rows, mode=norm_mode)
        else:
            # Fallback to truecolor
            return cls._render_truecolor_halfblock(img, cols, rows)

    @classmethod
    def _load_pil_image(
        cls,
        source: Union[ResolvedMultimodalPayload, Image.Image, str, Path, bytes]
    ) -> Image.Image:
        if isinstance(source, ResolvedMultimodalPayload):
            return Image.open(io.BytesIO(source.raw_bytes))
        elif isinstance(source, Image.Image):
            return source
        elif isinstance(source, bytes):
            return Image.open(io.BytesIO(source))
        elif isinstance(source, (str, Path)):
            payload = MultimodalResolver.resolve(source)
            return Image.open(io.BytesIO(payload.raw_bytes))
        else:
            raise TypeError(f"Unsupported image input type: {type(source)}")
```

---

### 3. TrueColor Upper Half-Block (`▀` U+2580) Rendering Pipeline

#### 3.1 Sub-Pixel Downsampling Math
- Grid size: $cols$ columns by $rows$ rows in terminal cell units.
- Downsampled Image size:
  - Width: $cols$ pixels
  - Height: $rows \times 2$ pixels (since each cell row contains 2 vertical sub-pixels).
- Image Resampling: `img.resize((cols, rows * 2), resample=Image.Resampling.LANCZOS)`.

#### 3.2 Pixel Grid Traversal
For cell row $r \in [0, rows - 1]$:
- Top sub-pixel row index in resized image: $y_{top} = 2 \times r$
- Bottom sub-pixel row index in resized image: $y_{bot} = 2 \times r + 1$
- For cell col $c \in [0, cols - 1]$:
  - Top sub-pixel RGB: $P_{top}(c, y_{top}) = (R_{top}, G_{top}, B_{top})$
  - Bottom sub-pixel RGB: $P_{bot}(c, y_{bot}) = (R_{bot}, G_{bot}, B_{bot})$
  - Character: `▀` (`U+2580`)
  - Top ANSI Foreground Sequence: `\x1b[38;2;R_top;G_top;B_topm`
  - Bottom ANSI Background Sequence: `\x1b[48;2;R_bot;G_bot;B_botm`

---

### 4. Horizontal Run-Length Encoding (RLE) Batching Algorithm

#### 4.1 Concept & Execution State
Without RLE, every single cell emits ~38 bytes of ANSI escape codes (`\x1b[38;2;...m\x1b[48;2;...m▀`), producing huge payload sizes (~125 KB for an 80x40 preview).
With RLE batching, we maintain `current_fg` and `current_bg` states per row. Escape codes are ONLY emitted when the top sub-pixel foreground or bottom sub-pixel background color changes!

#### 4.2 Detailed Pseudocode / Implementation Signature

```python
@classmethod
def _render_truecolor_halfblock(cls, img: Image.Image, cols: int, rows: int) -> str:
    """
    Renders image using 24-bit TrueColor upper half-blocks (▀) with horizontal RLE ANSI batching.
    """
    resized = img.resize((cols, rows * 2), resample=Image.Resampling.LANCZOS)
    pixels = resized.load()

    lines = []
    for r in range(rows):
        y_top = 2 * r
        y_bot = 2 * r + 1

        line_parts = []
        current_fg: Optional[Tuple[int, int, int]] = None
        current_bg: Optional[Tuple[int, int, int]] = None

        for c in range(cols):
            fg = pixels[c, y_top]
            bg = pixels[c, y_bot]

            # Emit foreground color change sequence if changed
            if fg != current_fg:
                line_parts.append(f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m")
                current_fg = fg

            # Emit background color change sequence if changed
            if bg != current_bg:
                line_parts.append(f"\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m")
                current_bg = bg

            line_parts.append("▀")

        # Every row must be terminated with an ANSI color reset sequence \x1b[0m
        line_parts.append("\x1b[0m")
        lines.append("".join(line_parts))

    return "\n".join(lines)
```

#### 4.3 Double-Buffering Frame Repaint Suppression
For interactive updates or streaming previews (e.g. in `vazus_vision_daemon.py`), `TUIPreviewRenderer` supports stateful double-buffering:

```python
def render_diff(
    self,
    payload_or_image: Union[ResolvedMultimodalPayload, Image.Image, str, Path, bytes],
    mode: str = "truecolor"
) -> str:
    """
    Stateful double-buffering renderer. Compares newly computed cell matrix against self._front_buffer.
    Emits cursor positioning escape codes (\x1b[{r+1};{c+1}H) only for modified cells.
    """
    img = self._load_pil_image(payload_or_image)
    if img.mode != "RGB":
        img = img.convert("RGB")

    cols, rows = self.compute_preview_dimensions(
        img.width, img.height, max_cols=self.max_cols, max_rows=self.max_rows, is_half_block=True
    )
    resized = img.resize((cols, rows * 2), resample=Image.Resampling.LANCZOS)
    pixels = resized.load()

    back_buffer = []
    for r in range(rows):
        row_cells = []
        for c in range(cols):
            fg = pixels[c, 2 * r]
            bg = pixels[c, 2 * r + 1]
            row_cells.append((fg, bg))
        back_buffer.append(row_cells)

    if self._front_buffer is None or len(self._front_buffer) != rows or len(self._front_buffer[0]) != cols:
        self._front_buffer = back_buffer
        return self.render(payload_or_image, max_cols=self.max_cols, max_rows=self.max_rows, mode=mode)

    # Differential rendering
    diff_parts = []
    for r in range(rows):
        for c in range(cols):
            if back_buffer[r][c] != self._front_buffer[r][c]:
                fg, bg = back_buffer[r][c]
                # Cursor position 1-indexed: \x1b[{row};{col}H
                diff_parts.append(f"\x1b[{r+1};{c+1}H\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m▀\x1b[0m")

    self._front_buffer = back_buffer
    return "".join(diff_parts)
```

---

### 5. 256-Color Fallback & ASCII Luminance Ramps

#### 5.1 256-Color (8-Bit Indexed) ANSI Fallback

```python
@classmethod
def _render_256color_halfblock(cls, img: Image.Image, cols: int, rows: int) -> str:
    """
    Renders image using 256-color ANSI half-blocks with horizontal RLE sequence batching.
    """
    resized = img.resize((cols, rows * 2), resample=Image.Resampling.LANCZOS)
    pixels = resized.load()

    lines = []
    for r in range(rows):
        y_top = 2 * r
        y_bot = 2 * r + 1

        line_parts = []
        current_fg_code: Optional[int] = None
        current_bg_code: Optional[int] = None

        for c in range(cols):
            fg_rgb = pixels[c, y_top]
            bg_rgb = pixels[c, y_bot]

            fg_code = cls.rgb_to_256_color(fg_rgb[0], fg_rgb[1], fg_rgb[2])
            bg_code = cls.rgb_to_256_color(bg_rgb[0], bg_rgb[1], bg_rgb[2])

            if fg_code != current_fg_code:
                line_parts.append(f"\x1b[38;5;{fg_code}m")
                current_fg_code = fg_code

            if bg_code != current_bg_code:
                line_parts.append(f"\x1b[48;5;{bg_code}m")
                current_bg_code = bg_code

            line_parts.append("▀")

        line_parts.append("\x1b[0m")
        lines.append("".join(line_parts))

    return "\n".join(lines)
```

#### 5.2 ASCII Luminance Ramp Renderer

```python
@classmethod
def _render_ascii_ramp(cls, img: Image.Image, cols: int, rows: int, mode: str = "ascii") -> str:
    """
    Renders image using ASCII character luminance ramps.
    Supports 'ascii' (10 chars), 'ascii_17' (17 Neo3dEngine chars), 'ascii_70' (70 chars).
    """
    if mode == "ascii_17":
        ramp = cls.RAMP_17
    elif mode == "ascii_70":
        ramp = cls.RAMP_70
    else:
        ramp = cls.RAMP_10

    ramp_len = len(ramp)
    resized = img.resize((cols, rows), resample=Image.Resampling.LANCZOS)
    pixels = resized.load()

    lines = []
    for r in range(rows):
        line_chars = []
        for c in range(cols):
            rgb = pixels[c, r]
            # Standard ITU-R BT.601 luminance formula
            lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
            idx = int(round(lum / 255.0 * (ramp_len - 1)))
            idx = max(0, min(ramp_len - 1, idx))
            line_chars.append(ramp[idx])
        lines.append("".join(line_chars))

    return "\n".join(lines)
```

---

### 6. Card Frame & TUI Container Specification

For CLI presentation (as illustrated in `survey_explorer_2`), `TUIPreviewRenderer` includes a decorator method `render_card()`:

```python
@classmethod
def render_card(
    cls,
    source: Union[ResolvedMultimodalPayload, Image.Image, str, Path, bytes],
    title: str = "VISION PREVIEW",
    max_cols: int = 80,
    max_rows: int = 30,
    mode: str = "truecolor"
) -> str:
    """
    Wraps the TUI pixel matrix inside a Unicode card container with title header and footer.
    """
    preview_matrix = cls.render(source, max_cols=max_cols - 4, max_rows=max_rows - 4, mode=mode)
    lines = preview_matrix.splitlines()

    actual_cols = max((len(line) for line in lines), default=max_cols - 4)
    # Strip ANSI escape codes to compute visible character length
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    visible_widths = [len(ansi_escape.sub('', line)) for line in lines]
    max_vis_w = max(visible_widths, default=40)

    header_text = f"─ [ {title} ] ─"
    fill_len = max(0, max_vis_w - len(header_text) + 2)
    top_border = f"┌{header_text}{'─' * fill_len}┐"
    footer_text = f"─ [ Mode: {mode} (▀) ] ─"
    footer_fill = max(0, max_vis_w - len(footer_text) + 2)
    bottom_border = f"└{'─' * footer_fill}{footer_text}┘"

    card_lines = [top_border]
    for line in lines:
        card_lines.append(f"│ {line} │")
    card_lines.append(bottom_border)

    return "\n".join(card_lines)
```

---

### 7. Implementation Checklist for Worker / Implementer

1. Create `C:\vazus\vazus_core\tui_preview_renderer.py` with all methods specified above.
2. Ensure imports resolve: `from vazus_core.multimodal_resolver import MultimodalResolver, ResolvedMultimodalPayload`.
3. Verify `TUIPreviewRenderer.compute_preview_dimensions` matches test signature in `tests/test_helpers.py` and `tests/test_tier1_feature.py`.
4. Run test suite using `C:\vazus\.venv\Scripts\python.exe C:\vazus\labs\native_vision_system\tests\run_e2e_tests.py` to confirm Features 4, 5, 6, and 7 pass 100%.
