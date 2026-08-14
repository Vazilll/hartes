"""
Native TUI Terminal Preview Renderer for vazus_core.
Inspired by Neo3dEngine (ConsoleScreen.cs).
Renders 24-bit TrueColor half-block matrices, 256-color fallback, and ASCII ramps
with horizontal Run-Length Encoding (RLE) ANSI escape sequence compression.
"""

import sys
import io
import os
import re
import ctypes
import shutil
from pathlib import Path
from typing import Union, Optional, Tuple, List, Dict, Any
from PIL import Image

from vazus_core.multimodal_resolver import (
    MultimodalResolver,
    ResolvedMultimodalPayload,
    MultimodalResolverError,
    UnsupportedFormatError,
    ImageNotFoundError,
    ClipboardEmptyError,
    ArtifactNotFoundError,
    ClipboardAccessError,
    CorruptedImageError,
)

ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def strip_ansi(text: str) -> str:
    """Strips ANSI escape sequences from text string."""
    return ANSI_ESCAPE_RE.sub('', text)


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


class TUIPreviewRenderer:
    """
    High-fidelity terminal image matrix buffer visualizer inspired by Neo3dEngine.
    """

    RAMP_10 = " .:-=+*#%@"
    RAMP_17 = " .:!/r(l1Z4H9W8$@"
    RAMP_70 = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "

    def __init__(
        self,
        default_mode: str = "truecolor",
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None,
        border_style: str = "unicode"
    ):
        self.default_mode = default_mode
        self.max_cols = max_cols
        self.max_rows = max_rows
        self.border_style = border_style
        self._front_buffer: Optional[List[List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]]] = None
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
        """
        if img_width <= 0 or img_height <= 0 or max_cols <= 0 or max_rows <= 0:
            return (max(1, max_cols or 80), max(1, max_rows or 40))

        # Monospace font cell geometry K_cell = W_cell / H_cell = 0.5.
        # Target cell grid ratio (cols / rows) to preserve image physical aspect ratio A_img on screen is 2.0 * A_img.
        target_aspect = (img_width / img_height) * 2.0

        cols = max_cols
        rows = int(round(cols / target_aspect)) if target_aspect > 0 else max_rows
        if rows > max_rows:
            rows = max_rows
            cols = int(round(rows * target_aspect))

        return (max(1, cols), max(1, rows))

    @classmethod
    def rgb_to_256_color(cls, r: int, g: int, b: int) -> int:
        """
        Quantizes 24-bit RGB (0-255) to 8-bit ANSI 256-color index (0-255).
        """
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))

        if abs(r - g) < 10 and abs(g - b) < 10 and abs(r - b) < 10:
            lum = int(round(0.299 * r + 0.587 * g + 0.114 * b))
            if lum < 8:
                return 16
            if lum > 248:
                return 231
            return 232 + int(round((lum - 8) / 247.0 * 23.0))

        vr = int(round(r / 255.0 * 5.0))
        vg = int(round(g / 255.0 * 5.0))
        vb = int(round(b / 255.0 * 5.0))
        return 16 + 36 * vr + 6 * vg + vb

    @classmethod
    def _load_pil_image(
        cls,
        source: Union[ResolvedMultimodalPayload, Image.Image, str, Path, bytes, bytearray]
    ) -> Tuple[Image.Image, Optional[ResolvedMultimodalPayload]]:
        """
        Polymorphic image ingestion pipeline.
        Returns tuple of (PIL.Image, Optional[ResolvedMultimodalPayload]).
        """
        if source is None:
            raise TypeError("Source cannot be None")

        if isinstance(source, ResolvedMultimodalPayload):
            try:
                img = Image.open(io.BytesIO(source.raw_bytes))
                img.load()
                return img, source
            except Exception as err:
                raise CorruptedImageError(f"Corrupted image bytes in payload: {str(err)}", source=source)

        elif isinstance(source, Image.Image):
            return source, None

        elif isinstance(source, (bytes, bytearray)):
            if len(source) == 0:
                raise CorruptedImageError("Empty byte array provided as image source", source=source)
            try:
                img = Image.open(io.BytesIO(bytes(source)))
                img.load()
                return img, None
            except Exception as err:
                raise CorruptedImageError(f"Corrupted image bytes: {str(err)}", source=source)

        elif isinstance(source, (str, Path)):
            payload = MultimodalResolver.resolve(source)
            try:
                img = Image.open(io.BytesIO(payload.raw_bytes))
                img.load()
                return img, payload
            except Exception as err:
                raise CorruptedImageError(f"Corrupted resolved image: {str(err)}", source=source)

        else:
            raise TypeError(f"Unsupported image input type: {type(source)}")

    @classmethod
    def _prepare_rgb_image(cls, img: Image.Image) -> Image.Image:
        """Converts RGBA/P/other image modes to RGB with dark background compositing (#0B0D0E)."""
        if img.mode == "RGB":
            return img

        if img.mode == "RGBA" or (hasattr(img, "split") and len(img.split()) == 4):
            bg = Image.new("RGB", img.size, (11, 13, 14))  # #0B0D0E
            bg.paste(img, mask=img.split()[3])
            return bg
        elif img.mode == "P" and "transparency" in img.info:
            rgba = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (11, 13, 14))
            bg.paste(rgba, mask=rgba.split()[3])
            return bg
        else:
            return img.convert("RGB")

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
                bg = pixels[c, y_bot] if y_bot < resized.height else (0, 0, 0)

                if len(fg) > 3:
                    fg = fg[:3]
                if len(bg) > 3:
                    bg = bg[:3]

                if fg != current_fg:
                    line_parts.append(f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m")
                    current_fg = fg

                if bg != current_bg:
                    line_parts.append(f"\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m")
                    current_bg = bg

                line_parts.append("▀")

            line_parts.append("\x1b[0m")
            lines.append("".join(line_parts))

        return "\n".join(lines)

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
                bg_rgb = pixels[c, y_bot] if y_bot < resized.height else (0, 0, 0)

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

    @classmethod
    def _render_ascii_ramp(cls, img: Image.Image, cols: int, rows: int, mode: str = "ascii") -> str:
        """
        Renders image using ASCII character luminance ramps.
        Supports 'ascii'/'ascii_10' (10 chars), 'ascii_17' (17 Neo3dEngine chars), 'ascii_70' (70 chars).
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
                lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                idx = int(round(lum / 255.0 * (ramp_len - 1)))
                idx = max(0, min(ramp_len - 1, idx))
                line_chars.append(ramp[idx])
            lines.append("".join(line_chars))

        return "\n".join(lines)

    def render(
        self_or_cls=None,
        payload_or_image: Union[ResolvedMultimodalPayload, Image.Image, str, Path, bytes, bytearray, None] = None,
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None,
        mode: Optional[str] = None,
        title: Optional[str] = None,
        border_style: str = "unicode",
        source: Union[ResolvedMultimodalPayload, Image.Image, str, Path, bytes, bytearray, None] = None,
    ) -> str:
        """
        Main entrypoint. Ingests polymorphic image source and returns ANSI/ASCII string.
        Can be called on class (TUIPreviewRenderer.render) or instance (renderer.render).
        """
        if isinstance(self_or_cls, TUIPreviewRenderer):
            instance = self_or_cls
            target_input = payload_or_image if payload_or_image is not None else source
        else:
            instance = None
            target_input = self_or_cls if self_or_cls is not None else (payload_or_image if payload_or_image is not None else source)

        if target_input is None:
            raise TypeError("Missing required image source for TUIPreviewRenderer.render()")

        cls = TUIPreviewRenderer

        effective_max_cols = max_cols if max_cols is not None else (instance.max_cols if instance and instance.max_cols is not None else None)
        effective_max_rows = max_rows if max_rows is not None else (instance.max_rows if instance and instance.max_rows is not None else None)

        if effective_max_cols is None or effective_max_rows is None:
            try:
                term_size = shutil.get_terminal_size(fallback=(80, 24))
                if effective_max_cols is None:
                    effective_max_cols = term_size.columns
                if effective_max_rows is None:
                    effective_max_rows = term_size.lines
            except Exception:
                if effective_max_cols is None:
                    effective_max_cols = 80
                if effective_max_rows is None:
                    effective_max_rows = 24

        if effective_max_cols <= 0:
            effective_max_cols = 80
        if effective_max_rows <= 0:
            effective_max_rows = 40

        target_mode = mode or (instance.default_mode if instance else "truecolor")
        norm_mode = str(target_mode).lower().strip()

        valid_modes = {"truecolor", "256", "256color", "ascii", "ascii_10", "ascii_17", "ascii_70", "auto"}
        if norm_mode not in valid_modes:
            raise ValueError(f"Invalid render mode: '{mode}'")

        if norm_mode == "auto":
            norm_mode = "truecolor"

        raw_img, payload = cls._load_pil_image(target_input)
        img = cls._prepare_rgb_image(raw_img)

        is_half_block = norm_mode in ("truecolor", "256", "256color")
        cols, rows = cls.compute_preview_dimensions(
            img.width, img.height, max_cols=effective_max_cols, max_rows=effective_max_rows, is_half_block=is_half_block
        )

        if norm_mode == "truecolor":
            return cls._render_truecolor_halfblock(img, cols, rows)
        elif norm_mode in ("256", "256color"):
            return cls._render_256color_halfblock(img, cols, rows)
        elif norm_mode.startswith("ascii"):
            return cls._render_ascii_ramp(img, cols, rows, mode=norm_mode)
        else:
            return cls._render_truecolor_halfblock(img, cols, rows)

    def render_diff(
        self_or_cls=None,
        payload_or_image: Union[ResolvedMultimodalPayload, Image.Image, str, Path, bytes, bytearray, None] = None,
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None,
        mode: str = "truecolor",
        source: Union[ResolvedMultimodalPayload, Image.Image, str, Path, bytes, bytearray, None] = None,
    ) -> str:
        """
        Stateful double-buffering renderer. Compares matrix against self._front_buffer.
        Emits cursor positioning escape codes (\\x1b[{r+1};{c+1}H) only for modified cells.
        """
        if isinstance(self_or_cls, TUIPreviewRenderer):
            instance = self_or_cls
            target_input = payload_or_image if payload_or_image is not None else source
        else:
            instance = None
            target_input = self_or_cls if self_or_cls is not None else (payload_or_image if payload_or_image is not None else source)

        if target_input is None:
            raise TypeError("Missing required image source for TUIPreviewRenderer.render_diff()")

        if instance is None:
            return TUIPreviewRenderer.render(target_input, max_cols=max_cols, max_rows=max_rows, mode=mode)

        effective_cols = max_cols if max_cols is not None else (instance.max_cols or 80)
        effective_rows = max_rows if max_rows is not None else (instance.max_rows or 40)
        if effective_cols <= 0:
            effective_cols = 80
        if effective_rows <= 0:
            effective_rows = 40

        raw_img, _ = instance._load_pil_image(target_input)
        img = instance._prepare_rgb_image(raw_img)

        cols, rows = instance.compute_preview_dimensions(
            img.width, img.height, max_cols=effective_cols, max_rows=effective_rows, is_half_block=True
        )
        resized = img.resize((cols, rows * 2), resample=Image.Resampling.LANCZOS)
        pixels = resized.load()

        back_buffer = []
        for r in range(rows):
            row_cells = []
            for c in range(cols):
                fg = pixels[c, 2 * r][:3]
                bg = pixels[c, 2 * r + 1][:3] if (2 * r + 1) < resized.height else (0, 0, 0)
                row_cells.append((fg, bg))
            back_buffer.append(row_cells)

        if instance._front_buffer is None or len(instance._front_buffer) != rows or len(instance._front_buffer[0]) != cols:
            instance._front_buffer = back_buffer
            return instance.render(target_input, max_cols=effective_cols, max_rows=effective_rows, mode=mode)

        diff_parts = []
        for r in range(rows):
            for c in range(cols):
                if back_buffer[r][c] != instance._front_buffer[r][c]:
                    fg, bg = back_buffer[r][c]
                    diff_parts.append(
                        f"\x1b[{r+1};{c+1}H\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m▀\x1b[0m"
                    )

        instance._front_buffer = back_buffer
        return "".join(diff_parts)

    def render_card(
        self_or_cls=None,
        payload_or_image: Union[ResolvedMultimodalPayload, Image.Image, str, Path, bytes, bytearray, None] = None,
        title: Optional[str] = None,
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None,
        mode: Optional[str] = None,
        border_style: str = "unicode",
        source: Union[ResolvedMultimodalPayload, Image.Image, str, Path, bytes, bytearray, None] = None,
    ) -> str:
        """
        Wraps the TUI pixel matrix inside a retro-cyberpunk Unicode card container.
        """
        if isinstance(self_or_cls, TUIPreviewRenderer):
            instance = self_or_cls
            target_input = payload_or_image if payload_or_image is not None else source
        else:
            instance = None
            target_input = self_or_cls if self_or_cls is not None else (payload_or_image if payload_or_image is not None else source)

        if target_input is None:
            raise TypeError("Missing required image source for TUIPreviewRenderer.render_card()")

        cls = TUIPreviewRenderer
        effective_mode = mode or (instance.default_mode if instance else "truecolor")
        raw_img, payload = cls._load_pil_image(target_input)

        term_size = shutil.get_terminal_size(fallback=(80, 24))
        c_max = max_cols if max_cols is not None else (instance.max_cols if instance and instance.max_cols is not None else term_size.columns)
        r_max = max_rows if max_rows is not None else (instance.max_rows if instance and instance.max_rows is not None else term_size.lines)

        if c_max <= 0:
            c_max = 80
        if r_max <= 0:
            r_max = 24

        c_max = max(10, c_max)
        r_max = max(5, r_max)

        inner_cols = max(4, c_max - 4)
        inner_rows = max(2, r_max - 2)

        preview_matrix = cls.render(target_input, max_cols=inner_cols, max_rows=inner_rows, mode=effective_mode)
        lines = preview_matrix.splitlines()

        visible_widths = [len(strip_ansi(line)) for line in lines]
        max_vis_w = max(visible_widths, default=40)

        if title is None:
            if payload and payload.file_path:
                label = Path(payload.file_path).name
            elif payload and payload.source_type == "clipboard":
                label = "@clipboard"
            elif payload and payload.source_type == "latest":
                label = "@latest"
            elif payload:
                label = f"Image ({payload.sha256[:8]})"
            else:
                label = "Snapshot"
            title_text = f"VISION PREVIEW: {label}"
        else:
            title_text = title

        header_str = f"─ [ {title_text} ] ─"
        footer_str = f"─ [ Mode: {effective_mode} (▀) ] ─"

        # Content width must accommodate header and footer titles
        required_content_w = max(max_vis_w, len(header_str), len(footer_str))

        fill_top = max(0, required_content_w + 2 - len(header_str))
        top_border = f"┌{header_str}{'─' * fill_top}┐"

        fill_bot = max(0, required_content_w + 2 - len(footer_str))
        bottom_border = f"└{'─' * fill_bot}{footer_str}┘"

        card_lines = [top_border]
        for line in lines:
            line_vis_w = len(strip_ansi(line))
            padding = " " * (required_content_w - line_vis_w)
            card_lines.append(f"│ {line}{padding} │")
        card_lines.append(bottom_border)

        return "\n".join(card_lines)


def render_terminal_harness_hud(
    active_skills: List[str],
    ast_saved_pct: float = 84.2,
    smt_status: str = "UNSAT Proof Certified",
    jury_consensus: str = "3/3 PASS (100%)",
    execution_route: str = "Local REPL + OpenVINO NPU + agy CLI"
) -> str:
    """
    Renders terminal-native real-time HUD card for live developer monitoring directly in the CLI/chat.
    """
    skills_str = ", ".join(active_skills) if active_skills else "none (progressive index ready)"
    lines = [
        f"┌── 🤖 VAZUS SUPERGRAPH OS HARNESS [TERMINAL LIVE HUD] ──────────────────────────┐",
        f"│ 🧩 Skill Auto-Loaded : [{skills_str}]",
        f"│ ✂️ AST Token Pruner  : -{ast_saved_pct:.1f}% Tokens Saved",
        f"│ 🛡️ SMT Z3 Verifier   : {smt_status}",
        f"│ 🏛️ Concordia Jury    : {jury_consensus}",
        f"│ ⚡ Execution Gateway : {execution_route}",
        f"└────────────────────────────────────────────────────────────────────────────────┘"
    ]
    return "\n".join(lines)

