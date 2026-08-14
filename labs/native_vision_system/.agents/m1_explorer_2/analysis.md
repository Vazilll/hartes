# Technical Analysis: `@` Reference Resolution & Robust Error Handling for `vazus_core/multimodal_resolver.py`

## 1. Executive Summary

This document specifies the technical architecture, parsing algorithms, search strategies, and exception hierarchy for **`@` Reference Resolution** and **Error Handling** within `vazus_core/multimodal_resolver.py` (Milestone M1).

The objective is to enable `MultimodalResolver.resolve()` to seamlessly ingest symbolic `@` references alongside standard file paths, raw bytes, and PIL Images while providing structured, diagnostic-rich exceptions when resolution fails.

Key capabilities specified:
1. **Clipboard Resolution (`@clipboard`, `@clip`)**: Ingests image data or file drops from the Windows RAM clipboard via `PIL.ImageGrab.grabclipboard()`.
2. **Latest Image Resolution (`@latest`, `@last`)**: Scans workspace directories, user temporary dumps, and system screenshots to resolve the most recently modified image file.
3. **Artifact Reference Resolution (`@artifact:<name>`)**: Resolves agent artifacts from `.agents/**/artifacts/`, global user stores (`~/.gemini/antigravity-cli/artifacts/`), and workspace `artifacts/`.
4. **Structured Exception Hierarchy**: Inherits from `MultimodalResolverError`, ensuring detailed diagnostic metadata (`source`, `message`, `details`).

---

## 2. `@` Reference Parsing & Resolution Specification

### 2.1. Reference Classification & Dispatch Logic

When `MultimodalResolver.resolve(source)` receives a string input, it inspects whether the string starts with `@` or matches known symbolic keywords.

```
                                  +-----------------------------+
                                  | Input String (source: str)  |
                                  +-----------------------------+
                                                 |
                                                 v
                                  +-----------------------------+
                                  | Strip whitespace & check @  |
                                  +-----------------------------+
                                                 |
         +---------------------------------------+---------------------------------------+
         |                                       |                                       |
         v                                       v                                       v
+-------------------+                   +-------------------+                   +-------------------+
| Clipboard Keyword |                   | Latest Keyword    |                   | Artifact Keyword  |
| @clipboard / @clip|                   | @latest / @last   |                   | @artifact:<name>  |
+-------------------+                   +-------------------+                   +-------------------+
         |                                       |                                       |
         v                                       v                                       v
+-------------------+                   +-------------------+                   +-------------------+
|  resolve_clip()   |                   | resolve_latest()  |                   | resolve_artifact()|
+-------------------+                   +-------------------+                   +-------------------+
```

---

### 2.2. Clipboard Reference Resolution (`@clipboard`, `@clip`)

#### Triggers
- `@clipboard`, `@clip`, `clipboard`, `clip` (case-insensitive).

#### Windows RAM Clipboard Integration (`PIL.ImageGrab.grabclipboard()`)
On Windows (Win32), `PIL.ImageGrab.grabclipboard()` returns one of three types:

1. **`PIL.Image.Image` object**:
   - Direct bitmap in RAM (e.g. copied screenshot via `Win+Shift+S`).
   - **Processing**:
     - Inspect `img.mode`. If `RGBA`, preserve transparency or convert to `RGB` if saving JPEG. Default export to `PNG` byte stream via `io.BytesIO()`.
     - Standardize MIME type to `image/png`.
     - Extract dimensions `(width, height)`.
     - Calculate SHA-256 hash over raw binary payload.

2. **`list` of file paths** (`List[str]`):
   - Occurs when files are copied in Windows File Explorer (`CF_HDROP`).
   - **Processing**:
     - Filter paths ending with allowed image extensions (`.png`, `.jpg`, `.jpeg`, `.webp`).
     - Pick the first valid image path that exists on disk.
     - Delegate resolution to file path preprocessor (magic byte check + disk read).

3. **`None` or Non-Image Object**:
   - Clipboard contains plain text, HTML, rich text, or is empty.
   - **Processing**:
     - Raise `ClipboardEmptyError("No image data or valid image file found in Windows clipboard.", source=source)`.

#### Concurrency & Win32 Lock Exception Handling
- Accessing the Windows clipboard can fail if another process locks `OpenClipboard` (e.g. Snipping Tool, Office apps).
- Wrap call in `try...except (OSError, RuntimeError, Exception) as err`:
  - Raise `ClipboardAccessError(f"Failed to access Windows RAM clipboard: {str(err)}", source=source, details={"os_error": str(err)})`.

---

### 2.3. Latest Image Resolution (`@latest`, `@last`)

#### Triggers
- `@latest`, `@last`, `latest`, `last` (case-insensitive).

#### Search Algorithm & Prioritized Paths
1. **Workspace Directory**: Search active workspace (`CWD` or configured project root).
   - Recurse through subdirectories up to max depth 3.
   - **Exclusions**: Skip hidden or build folders (`.git`, `.venv`, `__pycache__`, `node_modules`, `build`, `dist`).
2. **User Temp Directory**:
   - `os.environ.get("TEMP")`, `os.environ.get("TMP")`, or `tempfile.gettempdir()`.
3. **System Pictures / Screenshots Directory**:
   - Windows default: `Path(os.environ["USERPROFILE"]) / "Pictures" / "Screenshots"` and `Path(os.environ["USERPROFILE"]) / "Pictures"`.
   - Linux/macOS fallback: `~/Pictures/Screenshots`.

#### Candidate Filtering & Sorting
- Candidate files must match valid image extensions (`.png`, `.jpg`, `.jpeg`, `.webp`).
- Filter out 0-byte uninitialized files (`os.path.getsize(p) > 0`).
- For each file `p`, retrieve modification time: `mtime = os.path.getmtime(p)`.
- Sort candidate files descending by `mtime`.
- Select the candidate with the highest `mtime`.

#### Failure Mode
- If candidate list is empty across all search locations:
  - Raise `ImageNotFoundError("No recent image file (.png, .jpg, .jpeg, .webp) found in workspace, temp, or screenshots directories.", source=source, details={"searched_dirs": [...]})`.

---

### 2.4. Artifact Reference Resolution (`@artifact:<name>`)

#### Triggers
- `@artifact:<name>`, `@artifact/<name>`, `artifact:<name>`, `artifact/<name>` (case-insensitive prefix).

#### Name Parsing & Extension Candidate Generation
- Extract target `<name>` (e.g. `@artifact:dashboard_mockup` -> `dashboard_mockup`).
- If `<name>` lacks a valid image extension:
  - Generate candidate filenames: `[f"{name}.png", f"{name}.jpg", f"{name}.jpeg", f"{name}.webp", name]`.
- If `<name>` already includes an extension (e.g. `mockup.png`):
  - Candidates: `[name]`.

#### Prioritized Artifact Search Locations
1. **Subagent / Agent Artifacts**: `.agents/**/` within workspace (e.g. `C:\vazus\labs\native_vision_system\.agents\**\`).
2. **Workspace Artifact Directory**: `<workspace>/artifacts/` or `<workspace>/.artifacts/`.
3. **Global Antigravity Store**: `C:\Users\Vaz\.gemini\antigravity-cli\artifacts\` and `C:\Users\Vaz\.gemini\artifacts\`.
4. **Direct Workspace Match**: Relative path search within `<workspace>/`.

#### Resolution & Conflict Handling
- Search all candidate paths across the artifact search locations.
- If multiple matching artifact files are found:
  - Select the file with the newest modification timestamp (`mtime`).
- Delegate file loading and validation to standard disk resolver.

#### Failure Mode
- If no candidate match is found:
  - Raise `ArtifactNotFoundError(f"Artifact reference '{name}' could not be resolved in artifact directories.", source=source, details={"searched_artifact_paths": [...]})`.

---

## 3. Exception Hierarchy Specification

All exceptions inherit from `MultimodalResolverError` to provide diagnostic clarity.

```python
class MultimodalResolverError(Exception):
    """Base exception for all multimodal resolver failures."""
    def __init__(
        self,
        message: str,
        source: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.source = source
        self.details = details or {}

class UnsupportedFormatError(MultimodalResolverError):
    """Raised when file extension, magic bytes, or image format is unsupported or invalid."""
    pass

class ImageNotFoundError(MultimodalResolverError):
    """Base class raised when a requested image file, path, or reference cannot be located."""
    pass

class ClipboardEmptyError(ImageNotFoundError):
    """Raised when Windows clipboard does not contain any image data or image file paths."""
    pass

class ArtifactNotFoundError(ImageNotFoundError):
    """Raised when a specified artifact reference (@artifact:<name>) cannot be resolved."""
    pass

class ClipboardAccessError(MultimodalResolverError):
    """Raised when reading from OS/Windows clipboard fails due to OS lock or permission errors."""
    pass

class CorruptedImageError(MultimodalResolverError):
    """Raised when an image file header or bytes are corrupted, truncated, or unparseable by Pillow."""
    pass
```

### Exception Detail Payloads

| Exception | Typical Trigger | `source` | `details` Keys |
|---|---|---|---|
| `UnsupportedFormatError` | Unknown extension or magic bytes | `"file.pdf"` / `b'\x25\x50\x44\x46'` | `magic_bytes_hex`, `detected_extension`, `supported_mime_types` |
| `ImageNotFoundError` | Non-existent disk path or `@latest` | `"@latest"` / `"missing.png"` | `searched_dirs`, `attempted_paths` |
| `ClipboardEmptyError` | Clipboard contains text or empty | `"@clipboard"` | `clipboard_type` (`None`, `text`, etc.) |
| `ArtifactNotFoundError` | Non-existent artifact name | `"@artifact:chart"` | `artifact_name`, `searched_artifact_paths` |
| `ClipboardAccessError` | Win32 clipboard API locked | `"@clip"` | `os_error_code`, `exception_str` |
| `CorruptedImageError` | Truncated JPEG / corrupt bytes | `Path("corrupt.png")` | `pillow_error_str`, `file_size_bytes` |

---

## 4. Integration Contract with `MultimodalResolver`

### Method Signature Proposal

```python
class MultimodalResolver:
    @classmethod
    def resolve(
        cls,
        source: Union[str, Path, bytes, Image.Image],
        workspace_dir: Optional[Union[str, Path]] = None,
        extra_search_dirs: Optional[List[Union[str, Path]]] = None,
        strict: bool = True
    ) -> ResolvedMultimodalPayload:
        """
        Polymorphically resolves image inputs into a google.genai compatible payload.
        
        Supports:
        - Symbolic references: '@clipboard', '@clip', '@latest', '@last', '@artifact:<name>'
        - Disk file paths (absolute, relative, string or Path)
        - Raw binary bytes / bytearray
        - PIL Image instances
        - Base64 strings / Data URIs
        """
        ...
```

---

## 5. Verification & Test Case Design

To verify `@` reference resolution and exception handling, the test harness must execute:

1. **Clipboard Unit Test**:
   - Mock `PIL.ImageGrab.grabclipboard()` returning:
     a) A 100x100 RGB `PIL.Image.Image` -> Expect `ResolvedMultimodalPayload` with MIME `image/png`.
     b) A list `["C:\\test\\valid.png"]` -> Expect resolution of `valid.png`.
     c) `None` -> Expect `ClipboardEmptyError`.
     d) `OSError("Clipboard locked")` -> Expect `ClipboardAccessError`.

2. **Latest Image Search Test**:
   - Create temporary directory with files `img_1.png` (mtime T-10s) and `img_2.jpg` (mtime T-1s).
   - Call `resolve("@latest", workspace_dir=temp_dir)` -> Expect `img_2.jpg`.
   - Test empty directory -> Expect `ImageNotFoundError`.

3. **Artifact Reference Resolution Test**:
   - Create temporary artifact directory `.agents/subagent_1/artifacts/mockup.png`.
   - Call `resolve("@artifact:mockup")` -> Expect successful payload resolution.
   - Call `resolve("@artifact:nonexistent")` -> Expect `ArtifactNotFoundError`.

4. **Exception Hierarchy Inheritance Verification**:
   - Verify `issubclass(ClipboardEmptyError, ImageNotFoundError)` is `True`.
   - Verify `issubclass(ImageNotFoundError, MultimodalResolverError)` is `True`.
