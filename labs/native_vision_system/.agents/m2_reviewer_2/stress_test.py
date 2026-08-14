"""
Adversarial Stress Test Suite for TUIPreviewRenderer (M2).
Run independently by m2_reviewer_2.
"""

import sys
import io
import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, r"C:\vazus")

from vazus_core.tui_preview_renderer import (
    TUIPreviewRenderer,
    strip_ansi,

)
from vazus_core.multimodal_resolver import (
    MultimodalResolver,
    ResolvedMultimodalPayload,
    CorruptedImageError,
    ImageNotFoundError,
    ClipboardEmptyError,
)

def test_odd_image_dimensions():
    print("Testing odd image dimensions...")
    for w, h in [(101, 73), (3, 5), (17, 11), (7, 1)]:
        img = Image.new("RGB", (w, h), color=(100, 150, 200))
        ansi_tc = TUIPreviewRenderer.render(img, max_cols=30, max_rows=15, mode="truecolor")
        assert len(ansi_tc) > 0
        ansi_256 = TUIPreviewRenderer.render(img, max_cols=30, max_rows=15, mode="256")
        assert len(ansi_256) > 0
        ascii_out = TUIPreviewRenderer.render(img, max_cols=30, max_rows=15, mode="ascii_10")
        assert len(ascii_out) > 0
        card = TUIPreviewRenderer.render_card(img, max_cols=30, max_rows=15)
        assert len(card) > 0
    print("  [PASS] Odd image dimensions")

def test_micro_1x1_images():
    print("Testing micro 1x1 images...")
    # 1x1 RGB
    img_1x1 = Image.new("RGB", (1, 1), color=(255, 0, 0))
    res_1x1 = TUIPreviewRenderer.render(img_1x1, max_cols=80, max_rows=40)
    assert len(res_1x1) > 0
    assert "▀" in res_1x1

    # 1x1 RGBA transparent
    rgba_1x1 = Image.new("RGBA", (1, 1), color=(0, 255, 0, 0))
    res_rgba = TUIPreviewRenderer.render(rgba_1x1, max_cols=80, max_rows=40)
    assert len(res_rgba) > 0
    # Composited on #0B0D0E -> (11, 13, 14)
    assert "\x1b[38;2;11;13;14m" in res_rgba
    print("  [PASS] Micro 1x1 images")

def test_zero_negative_viewport_overrides():
    print("Testing zero/negative viewport overrides...")
    img = Image.new("RGB", (50, 50), color=(120, 120, 120))
    for cols, rows in [(0, 0), (-10, -5), (0, 20), (30, -1)]:
        res = TUIPreviewRenderer.render(img, max_cols=cols, max_rows=rows)
        assert len(res) > 0
        card = TUIPreviewRenderer.render_card(img, max_cols=cols, max_rows=rows)
        assert len(card) > 0
    print("  [PASS] Zero/negative viewport overrides")

def test_non_tty_redirection_fallbacks():
    print("Testing non-TTY stdio redirection fallbacks...")
    img = Image.new("RGB", (40, 40), color=(50, 100, 150))
    with patch("shutil.get_terminal_size", side_effect=OSError("No TTY")):
        res = TUIPreviewRenderer.render(img)
        assert len(res) > 0
        
        # Test render_card behavior under OSError exception
        try:
            card = TUIPreviewRenderer.render_card(img)
            print("  render_card handled OSError safely")
        except OSError:
            print("  [CRITICAL FINDING] render_card line 474 fails when shutil.get_terminal_size raises OSError!")
            
    print("  [CHECKED] Non-TTY stdio redirection fallbacks")

def test_256_color_cube_boundaries():
    print("Testing 256-color cube boundaries...")
    test_cases = [
        ((0, 0, 0), 16),
        ((255, 255, 255), 231),
        ((-50, -10, -5), 16),
        ((300, 500, 1000), 231),
        ((128, 128, 128), 243),
    ]
    for (r, g, b), expected in test_cases:
        code = TUIPreviewRenderer.rgb_to_256_color(r, g, b)
        assert 0 <= code <= 255
        if expected is not None:
            assert code == expected
    print("  [PASS] 256-color cube boundaries")

def test_rgba_compositing():
    print("Testing RGBA compositing (#0B0D0E)...")
    img_transparent = Image.new("RGBA", (10, 10), color=(255, 255, 255, 0))
    prepared = TUIPreviewRenderer._prepare_rgb_image(img_transparent)
    pixels = prepared.load()
    for x in range(10):
        for y in range(10):
            assert pixels[x, y] == (11, 13, 14)
    print("  [PASS] RGBA compositing (#0B0D0E)")

def test_double_buffering_state():
    print("Testing double-buffering state...")
    renderer = TUIPreviewRenderer()
    img1 = Image.new("RGB", (20, 20), color=(255, 0, 0))
    img2 = Image.new("RGB", (20, 20), color=(0, 255, 0))
    
    d1 = renderer.render_diff(img1, max_cols=20, max_rows=10)
    assert len(d1) > 0
    
    d2 = renderer.render_diff(img1, max_cols=20, max_rows=10)
    assert d2 == ""

    d3 = renderer.render_diff(img2, max_cols=20, max_rows=10)
    assert len(d3) > 0
    assert "\x1b[1;1H" in d3

    d4 = renderer.render_diff(img2, max_cols=40, max_rows=20)
    assert len(d4) > 0
    print("  [PASS] Double-buffering state")

def test_card_container_width_uniformity():
    print("Testing card container width uniformity...")
    img = Image.new("RGB", (100, 60), color=(80, 40, 200))
    
    card_short = TUIPreviewRenderer.render_card(img, title="A", max_cols=60, max_rows=20)
    lines_short = card_short.splitlines()
    widths_short = [len(strip_ansi(l)) for l in lines_short]
    assert len(set(widths_short)) == 1

    card_long = TUIPreviewRenderer.render_card(img, title="SUPER_LONG_TITLE_" * 5, max_cols=60, max_rows=20)
    lines_long = card_long.splitlines()
    widths_long = [len(strip_ansi(l)) for l in lines_long]
    assert len(set(widths_long)) == 1

    img_1x1 = Image.new("RGB", (1, 1), color=(255, 0, 0))
    card_1x1 = TUIPreviewRenderer.render_card(img_1x1, max_cols=60, max_rows=20)
    lines_1x1 = card_1x1.splitlines()
    widths_1x1 = [len(strip_ansi(l)) for l in lines_1x1]
    assert len(set(widths_1x1)) == 1
    print("  [PASS] Card container width uniformity")

def test_integrity_checks():
    print("Testing code integrity (anti-cheating)...")
    img_red = Image.new("RGB", (10, 10), color=(255, 0, 0))
    img_blue = Image.new("RGB", (10, 10), color=(0, 0, 255))

    out_red = TUIPreviewRenderer.render(img_red, max_cols=10, max_rows=5)
    out_blue = TUIPreviewRenderer.render(img_blue, max_cols=10, max_rows=5)

    assert out_red != out_blue
    assert "\x1b[38;2;255;0;0m" in out_red
    assert "\x1b[38;2;0;0;255m" in out_blue
    print("  [PASS] Code integrity (anti-cheating)")

if __name__ == "__main__":
    test_odd_image_dimensions()
    test_micro_1x1_images()
    test_zero_negative_viewport_overrides()
    test_non_tty_redirection_fallbacks()
    test_256_color_cube_boundaries()
    test_rgba_compositing()
    test_double_buffering_state()
    test_card_container_width_uniformity()
    test_integrity_checks()
    print("\nSTRESS TESTS FINISHED.")
