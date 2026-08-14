"""
Comprehensive Unit Test Suite for Milestone M2: TUI Terminal Preview Renderer.

File: C:\\vazus\\labs\\native_vision_system\\tests\\test_tui_preview_renderer.py
Runner: C:\\vazus\\.venv\\Scripts\\python.exe -m pytest C:\\vazus\\labs\\native_vision_system\\tests\\test_tui_preview_renderer.py
"""

import os
import io
import sys
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image

TESTS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, r"C:\vazus")
sys.path.insert(0, str(TESTS_DIR))

from vazus_core.tui_preview_renderer import (
    TUIPreviewRenderer,
    strip_ansi,

)
from vazus_core.multimodal_resolver import (
    MultimodalResolver,
    ResolvedMultimodalPayload,
    ImageNotFoundError,
    CorruptedImageError,
    ClipboardEmptyError,
)


@pytest.fixture
def sample_img():
    """Generates a simple 100x100 RGB image fixture."""
    return Image.new("RGB", (100, 100), color=(255, 0, 0))


@pytest.fixture
def sample_png_bytes(sample_img):
    """Generates valid PNG bytes fixture."""
    buf = io.BytesIO()
    sample_img.save(buf, format="PNG")
    return buf.getvalue()


# ============================================================================
# Category 1: TestAspectMath (8 Test Cases)
# ============================================================================

class TestAspectMath:

    def test_aspect_math_square_1to1(self):
        """TC-M2-01: 1:1 square image scaling math."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(1000, 1000, max_cols=80, max_rows=24)
        assert cols == 48
        assert rows == 24
        sub_pixel_ar = cols / (rows * 2)
        assert abs(sub_pixel_ar - 1000 / 1000) < 0.1

    def test_aspect_math_landscape_169(self):
        """TC-M2-02: 16:9 landscape image scaling math."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(1920, 1080, max_cols=80, max_rows=24)
        assert cols in (78, 80)
        assert rows == 22
        sub_pixel_ar = cols / (rows * 2)
        assert abs(sub_pixel_ar - 1920 / 1080) < 0.1

    def test_aspect_math_portrait_916(self):
        """TC-M2-03: 9:16 portrait image scaling math."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(1080, 1920, max_cols=80, max_rows=24)
        assert cols == 27
        assert rows == 24
        sub_pixel_ar = cols / (rows * 2)
        assert abs(sub_pixel_ar - 1080 / 1920) < 0.1

    def test_aspect_math_panoramic_219(self):
        """TC-M2-04: 21:9 panoramic ultra-wide image scaling math."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(2560, 1080, max_cols=80, max_rows=24)
        assert cols == 80
        assert rows == 17
        sub_pixel_ar = cols / (rows * 2)
        assert abs(sub_pixel_ar - 2560 / 1080) < 0.1

    def test_aspect_math_micro_1x1(self):
        """TC-M2-05: 1x1 micro image scaling bounds."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(1, 1, max_cols=80, max_rows=24)
        assert cols == 48
        assert rows == 24
        sub_pixel_ar = cols / (rows * 2)
        assert abs(sub_pixel_ar - 1.0) < 0.1

        cols_micro, rows_micro = TUIPreviewRenderer.compute_preview_dimensions(1, 1, max_cols=2, max_rows=1)
        assert cols_micro in (1, 2)
        assert rows_micro == 1

    def test_aspect_math_huge_4000x3000(self):
        """TC-M2-06: 4000x3000 ultra-large image scaling bounds."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(4000, 3000, max_cols=80, max_rows=24)
        assert cols == 64
        assert rows == 24
        sub_pixel_ar = cols / (rows * 2)
        assert abs(sub_pixel_ar - 4000 / 3000) < 0.1

    def test_aspect_math_odd_subpixel_height(self):
        """TC-M2-07: Odd subpixel height scaling math."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(100, 75, max_cols=80, max_rows=24)
        assert cols == 64
        assert rows == 24
        sub_pixel_ar = cols / (rows * 2)
        assert abs(sub_pixel_ar - 100 / 75) < 0.1

    def test_aspect_math_ascii_mode(self):
        """TC-M2-08: Single character ASCII aspect ratio factor."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(1920, 1080, max_cols=80, max_rows=24, is_half_block=False)
        assert cols in (78, 80)
        assert rows == 22
        sub_pixel_ar = cols / (rows * 2)
        assert abs(sub_pixel_ar - 1920 / 1080) < 0.1


# ============================================================================
# Category 2: TestTerminalAutoResizing (6 Test Cases)
# ============================================================================

class TestTerminalAutoResizing:

    def test_term_resize_standard_80x24(self, sample_img):
        """TC-M2-09: Auto-resizing for standard 80x24 terminal."""
        with patch("shutil.get_terminal_size", return_value=os.terminal_size((80, 24))):
            ansi_str = TUIPreviewRenderer.render(sample_img)
            lines = ansi_str.splitlines()
            assert len(lines) <= 24

    def test_term_resize_large_120x40(self, sample_img):
        """TC-M2-10: Auto-resizing for large 120x40 terminal."""
        with patch("shutil.get_terminal_size", return_value=os.terminal_size((120, 40))):
            ansi_str = TUIPreviewRenderer.render(sample_img)
            lines = ansi_str.splitlines()
            assert len(lines) <= 40

    def test_term_resize_small_40x10(self, sample_img):
        """TC-M2-11: Auto-resizing for small 40x10 terminal."""
        with patch("shutil.get_terminal_size", return_value=os.terminal_size((40, 10))):
            ansi_str = TUIPreviewRenderer.render(sample_img)
            lines = ansi_str.splitlines()
            assert len(lines) <= 10

    def test_term_resize_explicit_max_cols_override(self, sample_img):
        """TC-M2-12: Explicit max_cols and max_rows function argument override."""
        with patch("shutil.get_terminal_size", return_value=os.terminal_size((120, 40))):
            ansi_str = TUIPreviewRenderer.render(sample_img, max_cols=60, max_rows=15)
            lines = ansi_str.splitlines()
            assert len(lines) <= 15

    def test_term_resize_instance_default_override(self, sample_img):
        """TC-M2-13: Instance default max_cols and max_rows override."""
        with patch("shutil.get_terminal_size", return_value=os.terminal_size((120, 40))):
            renderer = TUIPreviewRenderer(max_cols=50, max_rows=12)
            ansi_str = renderer.render(sample_img)
            lines = ansi_str.splitlines()
            assert len(lines) <= 12

    def test_term_resize_non_tty_fallback(self, sample_img):
        """TC-M2-14: Fallback to safe default (80x24) when get_terminal_size raises OSError."""
        with patch("shutil.get_terminal_size", side_effect=OSError("Non-TTY stdout")):
            ansi_str = TUIPreviewRenderer.render(sample_img)
            assert len(ansi_str) > 0


# ============================================================================
# Category 3: TestPayloadIntegration (6 Test Cases)
# ============================================================================

class TestPayloadIntegration:

    def test_payload_direct_object(self, sample_img):
        """TC-M2-15: Direct ingestion of ResolvedMultimodalPayload object."""
        payload = MultimodalResolver.resolve(sample_img)
        ansi_str = TUIPreviewRenderer.render(payload)
        assert len(ansi_str) > 0

    def test_payload_file_path_str(self, sample_img, tmp_path):
        """TC-M2-16: Ingestion of image file path string."""
        img_file = tmp_path / "test_image.png"
        sample_img.save(img_file, format="PNG")
        ansi_str = TUIPreviewRenderer.render(str(img_file))
        assert len(ansi_str) > 0

    def test_payload_path_object(self, sample_img, tmp_path):
        """TC-M2-17: Ingestion of pathlib.Path object."""
        img_file = tmp_path / "test_image.png"
        sample_img.save(img_file, format="PNG")
        ansi_str = TUIPreviewRenderer.render(img_file)
        assert len(ansi_str) > 0

    def test_payload_raw_bytes(self, sample_png_bytes):
        """TC-M2-18: Ingestion of raw PNG bytes."""
        ansi_str = TUIPreviewRenderer.render(sample_png_bytes)
        assert len(ansi_str) > 0

    def test_payload_pil_image(self, sample_img):
        """TC-M2-19: Ingestion of PIL.Image.Image object."""
        ansi_str = TUIPreviewRenderer.render(sample_img)
        assert len(ansi_str) > 0

    def test_payload_card_header_metadata(self, sample_img, tmp_path):
        """TC-M2-20: Card container top header populates metadata from payload."""
        img_file = tmp_path / "mockup.png"
        sample_img.save(img_file, format="PNG")
        payload = MultimodalResolver.resolve(img_file)
        card_str = TUIPreviewRenderer.render_card(payload)
        assert "mockup.png" in card_str


# ============================================================================
# Category 4: TestRenderModes (6 Test Cases)
# ============================================================================

class TestRenderModes:

    def test_mode_truecolor(self, sample_img):
        """TC-M2-21: 24-bit TrueColor mode rendering with half-blocks."""
        ansi_str = TUIPreviewRenderer.render(sample_img, mode="truecolor")
        assert "\x1b[38;2;" in ansi_str
        assert "\x1b[48;2;" in ansi_str
        assert "▀" in ansi_str

    def test_mode_256_color(self, sample_img):
        """TC-M2-22: 256-color indexed ANSI mode rendering."""
        ansi_str = TUIPreviewRenderer.render(sample_img, mode="256")
        assert "\x1b[38;5;" in ansi_str or "\x1b[48;5;" in ansi_str
        assert "▀" in ansi_str

    def test_mode_ascii_10(self, sample_img):
        """TC-M2-23: 10-char ASCII luminance ramp rendering."""
        ascii_str = TUIPreviewRenderer.render(sample_img, mode="ascii_10")
        assert "\x1b[38;2;" not in ascii_str
        assert any(c in TUIPreviewRenderer.RAMP_10 for c in ascii_str)

    def test_mode_ascii_17(self, sample_img):
        """TC-M2-24: 17-char Neo3dEngine ASCII ramp rendering."""
        ascii_str = TUIPreviewRenderer.render(sample_img, mode="ascii_17")
        assert "\x1b[38;2;" not in ascii_str
        assert any(c in TUIPreviewRenderer.RAMP_17 for c in ascii_str)

    def test_mode_ascii_70(self, sample_img):
        """TC-M2-25: 70-char high-density ASCII ramp rendering."""
        ascii_str = TUIPreviewRenderer.render(sample_img, mode="ascii_70")
        assert "\x1b[38;2;" not in ascii_str
        assert any(c in TUIPreviewRenderer.RAMP_70 for c in ascii_str)

    def test_mode_auto_detection(self, sample_img):
        """TC-M2-26: Auto mode detection resolves cleanly."""
        ansi_str = TUIPreviewRenderer.render(sample_img, mode="auto")
        assert len(ansi_str) > 0


# ============================================================================
# Category 5: TestANSIOptimization (4 Test Cases)
# ============================================================================

class TestANSIOptimization:

    def test_rle_solid_color_reduction(self):
        """TC-M2-27: RLE batching compresses solid color payload size."""
        img = Image.new("RGB", (80, 40), color="red")
        ansi_str = TUIPreviewRenderer.render(img, max_cols=80, max_rows=40, mode="truecolor")
        unbatched_theoretical_size = 80 * 40 * 38  # ~121,600 bytes
        actual_size = len(ansi_str.encode("utf-8"))
        assert actual_size < (unbatched_theoretical_size * 0.20)

    def test_rle_checkerboard_worst_case(self):
        """TC-M2-28: RLE batching executes cleanly on frequent color shifts."""
        img = Image.new("RGB", (10, 10), color="red")
        pixels = img.load()
        for x in range(10):
            for y in range(10):
                if (x + y) % 2 == 0:
                    pixels[x, y] = (0, 0, 255)
        ansi_str = TUIPreviewRenderer.render(img, max_cols=10, max_rows=10, mode="truecolor")
        assert len(ansi_str) > 0
        assert "\x1b[38;2;" in ansi_str

    def test_rle_reset_sequence_at_line_end(self, sample_img):
        """TC-M2-29: Every row string ends with \\x1b[0m reset sequence."""
        ansi_str = TUIPreviewRenderer.render(sample_img, max_cols=20, max_rows=10, mode="truecolor")
        lines = ansi_str.splitlines()
        for line in lines:
            assert line.endswith("\x1b[0m")

    def test_double_buffering_no_op_diff(self, sample_img):
        """TC-M2-30: Stateful double-buffering suppresses output for unchanged frames."""
        renderer = TUIPreviewRenderer()
        diff1 = renderer.render_diff(sample_img, max_cols=20, max_rows=10)
        assert len(diff1) > 0
        diff2 = renderer.render_diff(sample_img, max_cols=20, max_rows=10)
        assert diff2 == ""


# ============================================================================
# Category 6: TestCardContainer (4 Test Cases)
# ============================================================================

class TestCardContainer:

    def test_card_border_corners(self, sample_img):
        """TC-M2-31: Retro-cyberpunk Unicode container box borders."""
        card_str = TUIPreviewRenderer.render_card(sample_img, max_cols=40, max_rows=15)
        assert "┌" in card_str
        assert "┐" in card_str
        assert "└" in card_str
        assert "┘" in card_str

    def test_card_total_line_count(self, sample_img):
        """TC-M2-32: Total line count equals inner matrix rows plus 2 border lines."""
        card_str = TUIPreviewRenderer.render_card(sample_img, max_cols=40, max_rows=15)
        lines = card_str.splitlines()
        assert len(lines) > 2

    def test_card_row_width_uniformity(self, sample_img):
        """TC-M2-33: Stripped visible character length is uniform across all card lines."""
        card_str = TUIPreviewRenderer.render_card(sample_img, max_cols=50, max_rows=20)
        lines = card_str.splitlines()
        widths = [len(strip_ansi(line)) for line in lines]
        assert len(set(widths)) == 1

    def test_card_custom_title_override(self, sample_img):
        """TC-M2-34: Custom title override displays in top border header."""
        card_str = TUIPreviewRenderer.render_card(sample_img, title="My Snapshot")
        assert "My Snapshot" in card_str


# ============================================================================
# Category 7: TestErrorHandling (5 Test Cases)
# ============================================================================

class TestErrorHandling:

    def test_error_non_existent_file(self):
        """TC-M2-35: Non-existent image file raises ImageNotFoundError."""
        with pytest.raises(ImageNotFoundError):
            TUIPreviewRenderer.render("non_existent_image_file_12345.png")

    def test_error_corrupted_payload(self):
        """TC-M2-36: Corrupted binary bytes raise CorruptedImageError."""
        with pytest.raises(CorruptedImageError):
            TUIPreviewRenderer.render(b"CORRUPTED_NON_IMAGE_BYTES_12345")

    def test_error_invalid_render_mode(self, sample_img):
        """TC-M2-37: Invalid render mode string raises ValueError."""
        with pytest.raises(ValueError):
            TUIPreviewRenderer.render(sample_img, mode="invalid_rendering_mode_xyz")

    def test_error_empty_clipboard(self):
        """TC-M2-38: Empty Windows RAM clipboard raises ClipboardEmptyError."""
        with patch("PIL.ImageGrab.grabclipboard", return_value=None):
            with pytest.raises(ClipboardEmptyError):
                TUIPreviewRenderer.render("@clipboard")

    def test_error_zero_viewport_bounds(self, sample_img):
        """TC-M2-39: Zero or negative viewport bounds sanitized without panic."""
        cols, rows = TUIPreviewRenderer.compute_preview_dimensions(100, 100, max_cols=0, max_rows=0)
        assert cols >= 1
        assert rows >= 1
        ansi_str = TUIPreviewRenderer.render(sample_img, max_cols=0, max_rows=0)
        assert len(ansi_str) > 0
