# Handoff Report — M2: TUI Terminal Preview Renderer Architecture

## 1. Observation
- **Target Source Location**: `C:\vazus\vazus_core\tui_preview_renderer.py` (M2 milestone).
- **Existing Predecessor Module**: `C:\vazus\vazus_core\multimodal_resolver.py` (M1 milestone, verified complete with `ResolvedMultimodalPayload`, `inspect_mime_type`, and `@` reference resolution).
- **Reference & Prior Analysis**: `C:\vazus\labs\native_vision_system\.agents\survey_explorer_2\analysis.md` (Neo3dEngine `ConsoleScreen.cs` synthesis, TrueColor `▀` half-block matrix, 256-color fallback, 17-char ramp `" .:!/r(l1Z4H9W8$@"`, aspect ratio $11/24 \approx 0.5$).
- **Test Harness Verification**: `C:\vazus\labs\native_vision_system\tests\test_tier1_feature.py` contains 20 test cases dedicated to M2 features (Features 4, 5, 6, 7):
  - Feature 4: TrueColor Half-Block Renderer (`test_f04_tc01` to `test_f04_tc05`)
  - Feature 5: ANSI RLE Double-Buffering (`test_f05_tc01` to `test_f05_tc05`)
  - Feature 6: Aspect Ratio & Bounding Box (`test_f06_tc01` to `test_f06_tc05`)
  - Feature 7: Fallback ASCII/256-Color Ramps (`test_f07_tc01` to `test_f07_tc05`)
- **Interface Contract**: `TUIPreviewRenderer.render(payload_or_image, max_cols=80, max_rows=40, mode="truecolor")` and `TUIPreviewRenderer.compute_preview_dimensions(img_width, img_height, max_cols=80, max_rows=40, is_half_block=True) -> tuple[int, int]`.

## 2. Logic Chain
1. **Input Poly-resolution**: `TUIPreviewRenderer` must accept `ResolvedMultimodalPayload`, `PIL.Image.Image`, raw `bytes`, disk file paths (`str`, `Path`), and symbolic `@` references (`@clipboard`, `@latest`, `@artifact:<name>`). `MultimodalResolver.resolve(source)` in `vazus_core/multimodal_resolver.py` already handles all polymorphic formats cleanly; delegating input loading to `MultimodalResolver` ensures 100% architectural consistency across `vazus_core`.
2. **Aspect Ratio Preservation**: Standard monospace terminal cells have height $\approx 2 \times \text{width}$. Using upper half-block `▀` (`U+2580`) splits 1 cell into 2 vertical sub-pixels, resulting in sub-pixel aspect ratio $1.0$ (square sub-pixels). Downsampling to $(cols, rows \times 2)$ using `LANCZOS` preserves fine visual detail.
3. **ANSI RLE Compression**: Unoptimized output emits foreground and background ANSI escape sequences (~38 bytes) before every single half-block character. For an 80x40 grid, this generates ~125 KB of stdout string data. By statefully tracking `current_fg` and `current_bg` across each row and emitting color escape codes only when colors change, stdout buffer size is reduced by >60% (up to 96% for solid blocks).
4. **Quantization & ASCII Ramps**: When TrueColor is disabled or `--256` / `--ascii` is specified:
   - 256-color mode maps RGB to ANSI 8-bit palette via 6x6x6 color cube ($16 + 36 V_r + 6 V_g + V_b$) and 24-step grayscale ramp ($232 + \dots$).
   - ASCII modes map luminance $L = 0.299R + 0.587G + 0.114B$ to ramps: 10-char (`" .:-=+*#%@"`), 17-char Neo3dEngine (`" .:!/r(l1Z4H9W8$@"`), and 70-char high density.
5. **Windows VT100 Setup**: Calling `ctypes.windll.kernel32.SetConsoleMode(hOut, dwMode | 0x0004)` on module import / class initialization ensures ANSI escape sequences render natively without corruption in Windows PowerShell and CMD.

## 3. Caveats
- **Terminal Cell Font Variance**: Some custom terminal fonts (e.g. non-standard font height ratios or wide emojis) may exhibit slight aspect ratio variance. The default aspect ratio calculation assumes standard 1:2 cell font geometry ($0.5$).
- **Color Transparency Compositing**: Images with RGBA alpha channels are composited against a dark background (`#0B0D0E`) to avoid stdout transparency glitches.
- **Console Handle Redirection**: If stdout is redirected to a file or pipe (e.g. `python script.py > out.txt`), `GetStdHandle(-11)` may return a file handle where `GetConsoleMode` fails. `enable_vt100_support()` handles this gracefully by returning `False` without raising an exception.

## 4. Conclusion
The technical architecture, mathematical specifications, method signatures, ANSI RLE compression logic, double-buffering framework, and step-by-step implementation guide for `vazus_core/tui_preview_renderer.py` are fully designed, documented, and validated in `analysis.md`. The design is ready for immediate implementation by the Worker agent.

## 5. Verification Method
To independently verify the implementation after Worker code generation:
1. Run Tier 1 feature tests for Features 4, 5, 6, 7:
   `C:\vazus\.venv\Scripts\python.exe C:\vazus\labs\native_vision_system\tests\run_e2e_tests.py --tier 1`
2. Verify all test cases in `TestFeature04TrueColorRenderer`, `TestFeature05AnsiRleDoubleBuffering`, `TestFeature06AspectRatioBoundingBox`, and `TestFeature07FallbackAscii256Color` pass with 0 failures.
3. Verify RLE compression by running:
   `C:\vazus\.venv\Scripts\python.exe -c "from vazus_core.tui_preview_renderer import TUIPreviewRenderer; from PIL import Image; img = Image.new('RGB', (80, 40), 'red'); res = TUIPreviewRenderer.render(img); print(len(res))"`
   Expected output length should be < 5,000 bytes (compared to > 120,000 bytes unoptimized).
