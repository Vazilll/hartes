# Handoff Report — M2 Explorer 2 (Aspect Math & Integration Specs)

## 1. Observation

Direct observations from codebase inspection:

1. **`vazus_core/multimodal_resolver.py` Payload Interface**:
   - `ResolvedMultimodalPayload` dataclass (`lines 72-120`) contains:
     - `raw_bytes: bytes`
     - `mime_type: str`
     - `base64_data: str`
     - `sha256: str`
     - `width: int`, `height: int`
     - `file_path: Optional[str]`
     - `source_type: str`
     - Methods: `to_genai_part()`, `to_inline_data_dict()`, `to_dict()`.
   - Exception hierarchy (`lines 26-68`): `MultimodalResolverError`, `UnsupportedFormatError`, `ImageNotFoundError`, `ClipboardEmptyError`, `ArtifactNotFoundError`, `ClipboardAccessError`, `CorruptedImageError`.

2. **Project Specification (`PROJECT.md`)**:
   - Feature 4: "TrueColor Half-Block Renderer — Renders ANSI 24-bit TrueColor previews with upper half-block `▀`"
   - Feature 5: "ANSI RLE Double-Buffering — Batches identical ANSI color codes to reduce TUI stdout size by >60%"
   - Feature 6: "Aspect Ratio & Bounding Box — Maintains 1:1 square sub-pixel aspect ratio within terminal bounds"
   - Feature 7: "Fallback ASCII/256-Color Ramps — Renders 256-color and 17/70 char ASCII fallback previews"
   - TUI Renderer API contract (`lines 62-65`): `TUIPreviewRenderer.render(payload_or_image: Union[ResolvedMultimodalPayload, Image.Image, str], max_cols: int = 80, max_rows: int = 40, mode: str = "truecolor") -> str`

3. **Existing Test Suite (`tests/test_multimodal_resolver.py`)**:
   - File location: `C:\vazus\labs\native_vision_system\tests\test_multimodal_resolver.py` (`lines 1-364`).
   - Runner command: `C:\vazus\.venv\Scripts\python.exe -m pytest C:\vazus\labs\native_vision_system\tests\test_multimodal_resolver.py`.
   - Test structure uses `pytest` class fixtures (`sample_png_bytes`, `sample_jpeg_bytes`, `sample_webp_bytes`) and mock objects (`unittest.mock.patch`).

4. **Neo3dEngine Principles (`survey_explorer_2/analysis.md`)**:
   - Monospace font cell ratio: $W_{cell} / H_{cell} \approx 11/24 \approx 0.5$.
   - Unicode half-block `▀` (`U+2580`) provides 2 vertical sub-pixels per character cell, yielding exact 1:1 square sub-pixel aspect ratio ($W_{sub} / H_{sub} = 1.0$).
   - Horizontal ANSI Run-Length Encoding (RLE) reduces escape sequence payload size by 60%–85%.

---

## 2. Logic Chain

1. **Payload Integration Logic**:
   - *From Observation 1*: `ResolvedMultimodalPayload` already holds image dimensions `width` and `height`, as well as `raw_bytes`, `file_path`, and `source_type`.
   - *Reasoning*: Passing `ResolvedMultimodalPayload` directly into `TUIPreviewRenderer.render()` eliminates redundant PIL `Image.open()` calls for dimension extraction. Pillow image loading is deferred until pixel downsampling occurs. Card container titles automatically consume `file_path` or `source_type` metadata.

2. **Aspect Ratio & Sub-Pixel Scaling Math Logic**:
   - *From Observation 2 & 4*: Monospace character cells are tall ($W_{cell} \approx 0.5 H_{cell}$).
   - *Reasoning*: In Mode A (TrueColor Half-Block `▀`), each cell contains 2 vertical sub-pixels (top half FG, bottom half BG). Height of each sub-pixel is $0.5 H_{cell}$, matching width $W_{cell} \approx 0.5 H_{cell}$. Thus, sub-pixel aspect ratio is $(0.5 H_{cell}) / (0.5 H_{cell}) = 1.0$ (Square!).
   - *Formula*: $W_{px} = C_{term}$, $H_{px} = 2 \times R_{term}$. To preserve image aspect ratio $A_{img} = W_{img} / H_{img}$, the ratio $\frac{W_{px}}{H_{px}} = A_{img}$ must be satisfied within terminal bounds $V_w \times (2 V_h)$.
   - In Modes B & C (single cell character/256-color), 1 cell = 1 pixel. Cell aspect ratio factor $K_{cell} = 0.5$ requires scaling by adjusted aspect ratio $A_{adj} = 2.0 \times A_{img}$.

3. **Terminal Auto-Resizing Logic**:
   - *From Observation 2*: Viewport bounds must dynamically adapt to terminal window resizing.
   - *Reasoning*: `shutil.get_terminal_size(fallback=(80, 24))` queries live terminal dimensions. Subtracting container frame overhead (2 columns, 2 rows) yields inner rendering bounds $V_w \times V_h$. Parameter overrides (`max_cols`, `max_rows`) take precedence over live queries to support custom embedding.

4. **Unit Test Matrix Logic**:
   - *From Observation 3*: The project test runner executes pytest suites located in `C:\vazus\labs\native_vision_system\tests\`.
   - *Reasoning*: Constructing a 39-test matrix in `tests/test_tui_preview_renderer.py` across 7 distinct categories (`TestAspectMath`, `TestTerminalAutoResizing`, `TestPayloadIntegration`, `TestRenderModes`, `TestANSIOptimization`, `TestCardContainer`, `TestErrorHandling`) guarantees robust validation and regression safety.

---

## 3. Caveats

- **Terminal Font Variations**: Monospace font cell aspect ratios can vary slightly across terminal emulators (e.g. 11/24 ≈ 0.458 vs 1/2 = 0.5). Sub-pixel geometry assumes standard 1:2 cell aspect ratio (1:1 square sub-pixels).
- **Windows Terminal ANSI Processing**: Legacy Windows `cmd.exe` requires `SetConsoleMode` with `ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004)` to enable ANSI escape colors. Windows Terminal and PowerShell 7+ support ANSI processing by default.

---

## 4. Conclusion

The specification for `vazus_core/tui_preview_renderer.py` is fully defined:
1. **Direct Payload Integration**: Native support for `ResolvedMultimodalPayload` with zero-redundancy metadata parsing and error propagation.
2. **Mathematical Precision**: 1:1 square sub-pixel aspect ratio math for TrueColor half-blocks (`▀` U+2580) and 2.0x adjusted aspect math for single-cell ASCII/256-color modes within dynamic `shutil.get_terminal_size()` viewports.
3. **Unit Test Blueprint**: A 39-test matrix specified for `tests/test_tui_preview_renderer.py` ready for M2 implementation and validation.

---

## 5. Verification Method

To verify the specifications and plan established in this report:

1. **Inspect Analysis Document**:
   - Read `C:\vazus\labs\native_vision_system\.agents\m2_explorer_2\analysis.md` for mathematical proofs, equations, data structures, and unit test matrix details.

2. **Verify Multimodal Resolver Interface**:
   - Run existing resolver tests: `C:\vazus\.venv\Scripts\python.exe -m pytest C:\vazus\labs\native_vision_system\tests\test_multimodal_resolver.py`.

3. **Future Test Suite Verification**:
   - Once `vazus_core/tui_preview_renderer.py` and `tests/test_tui_preview_renderer.py` are implemented, run:
     `C:\vazus\.venv\Scripts\python.exe -m pytest C:\vazus\labs\native_vision_system\tests\test_tui_preview_renderer.py`.
