"""
Empirical Stress Test Harness for TUIPreviewRenderer (M2)
Location: C:\\vazus\\labs\\native_vision_system\\.agents\\m2_challenger_1\\empirical_stress_test.py
"""

import sys
import os
sys.path.insert(0, r"C:\vazus")
import io
import re
from PIL import Image, ImageDraw
from vazus_core.tui_preview_renderer import TUIPreviewRenderer, strip_ansi
from vazus_core.multimodal_resolver import MultimodalResolver, ResolvedMultimodalPayload

def unbatched_render_truecolor(img: Image.Image, cols: int, rows: int) -> str:
    """Computes reference unbatched output size where every cell emits FG and BG sequences."""
    resized = img.resize((cols, rows * 2), resample=Image.Resampling.LANCZOS)
    pixels = resized.load()
    lines = []
    for r in range(rows):
        y_top = 2 * r
        y_bot = 2 * r + 1
        line_parts = []
        for c in range(cols):
            fg = pixels[c, y_top][:3]
            bg = pixels[c, y_bot][:3] if y_bot < resized.height else (0, 0, 0)
            line_parts.append(f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m▀")
        line_parts.append("\x1b[0m")
        lines.append("".join(line_parts))
    return "\n".join(lines)


def unbatched_render_256color(img: Image.Image, cols: int, rows: int) -> str:
    """Computes reference unbatched 256-color output size."""
    resized = img.resize((cols, rows * 2), resample=Image.Resampling.LANCZOS)
    pixels = resized.load()
    lines = []
    for r in range(rows):
        y_top = 2 * r
        y_bot = 2 * r + 1
        line_parts = []
        for c in range(cols):
            fg = pixels[c, y_top][:3]
            bg = pixels[c, y_bot][:3] if y_bot < resized.height else (0, 0, 0)
            fg_code = TUIPreviewRenderer.rgb_to_256_color(fg[0], fg[1], fg[2])
            bg_code = TUIPreviewRenderer.rgb_to_256_color(bg[0], bg[1], bg[2])
            line_parts.append(f"\x1b[38;5;{fg_code}m\x1b[48;5;{bg_code}m▀")
        line_parts.append("\x1b[0m")
        lines.append("".join(line_parts))
    return "\n".join(lines)


def run_rle_compression_tests():
    print("=== TEST 1: RLE ANSI Compression Rates ===")
    
    # 1. Solid Red Image (80x40)
    solid_red = Image.new("RGB", (400, 400), (255, 0, 0))
    unbatched_red = unbatched_render_truecolor(solid_red, 80, 40)
    rle_red = TUIPreviewRenderer.render(solid_red, max_cols=80, max_rows=40, mode="truecolor")
    red_reduction = (1 - len(rle_red.encode('utf-8')) / len(unbatched_red.encode('utf-8'))) * 100
    print(f"Solid Red (80x40): Unbatched={len(unbatched_red.encode('utf-8'))} B, RLE={len(rle_red.encode('utf-8'))} B -> Reduction = {red_reduction:.2f}%")
    assert red_reduction > 60.0, f"Solid red reduction {red_reduction}% < 60%"

    # 2. Horizontal Gradient Image (80x40)
    grad_h = Image.new("RGB", (400, 400))
    draw_h = ImageDraw.Draw(grad_h)
    for y in range(400):
        for x in range(400):
            grad_h.putpixel((x, y), (int(x / 400 * 255), 100, int(y / 400 * 255)))
    unbatched_gh = unbatched_render_truecolor(grad_h, 80, 40)
    rle_gh = TUIPreviewRenderer.render(grad_h, max_cols=80, max_rows=40, mode="truecolor")
    gh_reduction = (1 - len(rle_gh.encode('utf-8')) / len(unbatched_gh.encode('utf-8'))) * 100
    print(f"Horizontal Gradient (80x40): Unbatched={len(unbatched_gh.encode('utf-8'))} B, RLE={len(rle_gh.encode('utf-8'))} B -> Reduction = {gh_reduction:.2f}%")

    # 3. Vertical Gradient Image (80x40) - Solid per row
    grad_v = Image.new("RGB", (400, 400))
    for y in range(400):
        c = int(y / 400 * 255)
        for x in range(400):
            grad_v.putpixel((x, y), (c, c, c))
    unbatched_gv = unbatched_render_truecolor(grad_v, 80, 40)
    rle_gv = TUIPreviewRenderer.render(grad_v, max_cols=80, max_rows=40, mode="truecolor")
    gv_reduction = (1 - len(rle_gv.encode('utf-8')) / len(unbatched_gv.encode('utf-8'))) * 100
    print(f"Vertical Solid Gradient (80x40): Unbatched={len(unbatched_gv.encode('utf-8'))} B, RLE={len(rle_gv.encode('utf-8'))} B -> Reduction = {gv_reduction:.2f}%")
    assert gv_reduction > 60.0, f"Vertical gradient reduction {gv_reduction}% < 60%"

    # 4. 256-color Solid Green (80x40)
    solid_green = Image.new("RGB", (200, 200), (0, 255, 0))
    unbatched_256 = unbatched_render_256color(solid_green, 80, 40)
    rle_256 = TUIPreviewRenderer.render(solid_green, max_cols=80, max_rows=40, mode="256")
    reduction_256 = (1 - len(rle_256.encode('utf-8')) / len(unbatched_256.encode('utf-8'))) * 100
    print(f"256-color Solid Green (80x40): Unbatched={len(unbatched_256.encode('utf-8'))} B, RLE={len(rle_256.encode('utf-8'))} B -> Reduction = {reduction_256:.2f}%")
    assert reduction_256 > 60.0, f"256-color reduction {reduction_256}% < 60%"
    print("PASS: RLE ANSI Compression Test\n")


def run_line_reset_tests():
    print("=== TEST 2: Line Reset \\x1b[0m Conformance ===")
    modes = ["truecolor", "256", "256color"]
    test_img = Image.new("RGB", (100, 100), (128, 64, 32))
    
    for m in modes:
        output = TUIPreviewRenderer.render(test_img, max_cols=40, max_rows=20, mode=m)
        lines = output.splitlines()
        for idx, line in enumerate(lines):
            assert line.endswith("\x1b[0m"), f"Mode {m} line {idx} does not end with \\x1b[0m: {repr(line[-10:])}"
        print(f"Mode '{m}': All {len(lines)} lines end with \\x1b[0m")
    
    print("PASS: Line Reset Conformance Test\n")


def run_double_buffering_tests():
    print("=== TEST 3: Double-Buffering Repaint Suppression ===")
    renderer = TUIPreviewRenderer(max_cols=60, max_rows=30)
    img1 = Image.new("RGB", (200, 200), (10, 20, 30))
    img2 = Image.new("RGB", (200, 200), (200, 100, 50))

    # Frame 1: initial render returns full frame
    frame1 = renderer.render_diff(img1)
    assert len(frame1) > 0, "Initial frame_diff should return full matrix"

    # Frame 1 repeated: should return empty string ""
    frame1_repeat = renderer.render_diff(img1)
    assert frame1_repeat == "", f"Identical consecutive frame emitted output of length {len(frame1_repeat)}"
    print("Frame 1 -> Frame 1 repeat: Emitted 0 bytes (zero repaints)")

    # Frame 1 repeated again: should return empty string ""
    frame1_repeat2 = renderer.render_diff(img1)
    assert frame1_repeat2 == "", "Frame 1 repeat #2 should emit empty string"

    # Frame 2 (different): should emit diff
    frame2 = renderer.render_diff(img2)
    assert len(frame2) > 0, "Different frame should emit diff"
    print(f"Frame 1 -> Frame 2: Emitted diff of length {len(frame2)}")

    # Frame 2 repeated: should return empty string ""
    frame2_repeat = renderer.render_diff(img2)
    assert frame2_repeat == "", "Frame 2 repeat should emit empty string"
    print("Frame 2 -> Frame 2 repeat: Emitted 0 bytes (zero repaints)")

    # Frame 2 with 1 pixel changed
    img2_mod = img2.copy()
    img2_mod.putpixel((0, 0), (255, 255, 255))
    diff_single_pixel = renderer.render_diff(img2_mod)
    assert len(diff_single_pixel) > 0 and "\x1b[1;1H" in diff_single_pixel, "Single pixel change should update cell (1,1)"
    print(f"Single Pixel Change: Emitted targeted diff update: {repr(diff_single_pixel)}")

    # Modified repeated: 0 bytes
    assert renderer.render_diff(img2_mod) == "", "Modified frame repeat should emit 0 bytes"
    print("PASS: Double-Buffering Repaint Suppression Test\n")


def run_edge_cases_and_robustness_tests():
    print("=== TEST 4: Edge Cases & Robustness ===")

    # 1. Micro 1x1 image
    img_1x1 = Image.new("RGB", (1, 1), (100, 150, 200))
    out_1x1_scaled = TUIPreviewRenderer.render(img_1x1, max_cols=80, max_rows=40)
    assert len(out_1x1_scaled.splitlines()) <= 40, "1x1 scaled image should fit max_rows"
    out_1x1_exact = TUIPreviewRenderer.render(img_1x1, max_cols=2, max_rows=1)
    assert len(out_1x1_exact.splitlines()) == 1, "1x1 exact image should produce 1 line"

    # 2. Extreme narrow 1x1000 image
    img_narrow = Image.new("RGB", (1, 1000), (50, 50, 50))
    out_narrow = TUIPreviewRenderer.render(img_narrow, max_cols=80, max_rows=40)
    assert len(out_narrow.splitlines()) <= 40, "Narrow image should cap at max_rows"

    # 3. Extreme wide 1000x1 image
    img_wide = Image.new("RGB", (1000, 1), (50, 50, 50))
    out_wide = TUIPreviewRenderer.render(img_wide, max_cols=80, max_rows=40)
    assert len(out_wide.splitlines()) == 1, f"1000x1 image should produce 1 line, got {len(out_wide.splitlines())}"

    # 4. Zero / negative max_cols / max_rows
    out_zero_cols = TUIPreviewRenderer.render(img_1x1, max_cols=0, max_rows=0)
    assert len(out_zero_cols) > 0, "Zero bounds should clamp gracefully without error"
    out_neg_cols = TUIPreviewRenderer.render(img_1x1, max_cols=-10, max_rows=-5)
    assert len(out_neg_cols) > 0, "Negative bounds should clamp gracefully without error"

    # 5. RGBA image with transparency
    img_rgba = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
    out_rgba = TUIPreviewRenderer.render(img_rgba, max_cols=40, max_rows=20)
    assert len(out_rgba) > 0, "RGBA image rendering should succeed"

    # 6. Palette image P mode
    img_p = Image.new("P", (100, 100))
    img_p.putpalette([i for i in range(256)] * 3)
    out_p = TUIPreviewRenderer.render(img_p, max_cols=40, max_rows=20)
    assert len(out_p) > 0, "Palette P mode image rendering should succeed"

    # 7. Card container uniformity
    card_out = TUIPreviewRenderer.render_card(img_1x1, title="Test Card", max_cols=80, max_rows=24)
    card_lines = card_out.splitlines()
    widths = [len(strip_ansi(l)) for l in card_lines]
    assert len(set(widths)) == 1, f"Card lines should have 100% uniform visible width, got widths: {set(widths)}"
    print(f"Card container uniform visible line width: {widths[0]} chars across {len(card_lines)} lines")

    print("PASS: Edge Cases & Robustness Test\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    run_rle_compression_tests()
    run_line_reset_tests()
    run_double_buffering_tests()
    run_edge_cases_and_robustness_tests()
    print("ALL EMPIRICAL STRESS TESTS PASSED SUCCESSFULLY!")
