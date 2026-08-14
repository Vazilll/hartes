import sys
from pathlib import Path
sys.path.insert(0, r"C:\vazus")

from vazus_core.tui_preview_renderer import TUIPreviewRenderer, strip_ansi
from PIL import Image

def compute_correct_dimensions(img_width: int, img_height: int, max_cols: int = 80, max_rows: int = 40, is_half_block: bool = True) -> tuple[int, int]:
    """
    Calculates terminal grid dimensions (cols, rows) preserving physical image aspect ratio on monospace terminals.
    
    Monospace terminal font cell geometry:
    - Width W_cell approx 0.5 * H_cell (K_cell = 0.5).
    
    For half-block mode (is_half_block=True):
    - 1 character cell has width W_cell and height H_cell, containing 2 vertical subpixels (top & bottom).
    - Subpixel width W_sub = W_cell.
    - Subpixel height H_sub = 0.5 * H_cell.
    - Subpixel aspect ratio R_sub = W_sub / H_sub = W_cell / (0.5 * H_cell) = 1.0 (Exact 1:1 Square Subpixels!).
    - Subpixel grid size: W_px = cols, H_px = 2 * rows.
    - Subpixel grid aspect ratio: W_px / H_px = cols / (2 * rows).
    - Setting W_px / H_px = A_img (img_width / img_height) gives:
        cols / (2 * rows) = A_img => cols / rows = 2.0 * A_img.
        
    For single-char ASCII mode (is_half_block=False):
    - 1 character cell contains 1 pixel (width W_cell, height H_cell).
    - Visual aspect ratio on screen: (cols * W_cell) / (rows * H_cell) = (cols / rows) * K_cell = (cols / rows) * 0.5.
    - Setting visual aspect ratio = A_img gives:
        (cols / rows) * 0.5 = A_img => cols / rows = 2.0 * A_img.
        
    Therefore, for BOTH half-block and ASCII modes on monospace terminals (K_cell = 0.5),
    the required terminal grid aspect ratio cols / rows is target_aspect = 2.0 * (img_width / img_height).
    """
    if img_width <= 0 or img_height <= 0 or max_cols <= 0 or max_rows <= 0:
        return (max(1, max_cols or 80), max(1, max_rows or 40))

    target_aspect = (img_width / img_height) * 2.0

    cols = max_cols
    rows = int(round(cols / target_aspect)) if target_aspect > 0 else max_rows
    if rows > max_rows:
        rows = max_rows
        cols = int(round(rows * target_aspect))

    return (max(1, cols), max(1, rows))


def run_math_verification():
    cases = [
        ("Square 1:1", 1000, 1000),
        ("Landscape 16:9", 1920, 1080),
        ("Portrait 9:16", 1080, 1920),
        ("Panoramic 21:9", 2560, 1080),
        ("Micro 1x1", 1, 1),
        ("Huge 4000x3000", 4000, 3000),
    ]

    print("==========================================================================================")
    print("EMPIRICAL VERIFICATION 1 & 2: ASPECT RATIO SCALING MATH")
    print("==========================================================================================")
    print(f"{'Image Case':18} | {'Image Size':11} | {'Img AR':7} | {'Current (cols x rows)':22} | {'Current Sub AR':14} | {'Correct (cols x rows)':22} | {'Correct Sub AR':14}")
    print("-" * 120)

    for name, w, h in cases:
        img_ar = w / h
        # Current implementation
        cur_c, cur_r = TUIPreviewRenderer.compute_preview_dimensions(w, h, max_cols=80, max_rows=24, is_half_block=True)
        cur_sub_ar = cur_c / (cur_r * 2)

        # Correct math
        cor_c, cor_r = compute_correct_dimensions(w, h, max_cols=80, max_rows=24, is_half_block=True)
        cor_sub_ar = cor_c / (cor_r * 2)

        print(f"{name:18} | {w:4}x{h:<6} | {img_ar:7.4f} | cols={cur_c:2}, rows={cur_r:2} (sub {cur_c:2}x{cur_r*2:<2}) | {cur_sub_ar:14.4f} | cols={cor_c:2}, rows={cor_r:2} (sub {cor_c:2}x{cor_r*2:<2}) | {cor_sub_ar:14.4f}")


def run_card_uniformity_verification():
    print("\n==========================================================================================")
    print("EMPIRICAL VERIFICATION 3: CARD CONTAINER VISUAL ALIGNMENT & UNIFORMITY")
    print("==========================================================================================")

    test_imgs = [
        ("Solid Red 100x100", Image.new("RGB", (100, 100), color="red")),
        ("Gradient 200x100", Image.new("RGB", (200, 100), color="blue")),
        ("Tall 100x300", Image.new("RGB", (100, 300), color="green")),
    ]

    all_uniform = True
    for label, img in test_imgs:
        card_str = TUIPreviewRenderer.render_card(img, title=f"Test {label}", max_cols=60, max_rows=20, mode="truecolor")
        lines = card_str.splitlines()
        visible_lengths = [len(strip_ansi(line)) for line in lines]
        unique_widths = set(visible_lengths)

        is_uniform = len(unique_widths) == 1
        if not is_uniform:
            all_uniform = False

        print(f"[{'PASS' if is_uniform else 'FAIL'}] {label}: Total lines={len(lines)}, Visible widths={unique_widths}")
        if not is_uniform:
            for idx, (line, width) in enumerate(zip(lines, visible_lengths)):
                print(f"   Line {idx:2}: len={width:3} | {line[:40]}...")

    print(f"\nCard Container Uniform Width Result: {'100% UNIFORM (PASS)' if all_uniform else 'NON-UNIFORM (FAIL)'}")

if __name__ == "__main__":
    run_math_verification()
    run_card_uniformity_verification()
