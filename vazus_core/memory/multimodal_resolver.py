"""
Native Multimodal Image Resolver for vazus_core.
Polymorphic preprocessor for .png, .jpg, .jpeg, .webp images.
Converts disk files, @ references (@clipboard, @latest, @artifact), raw bytes, Base64, and PIL images
into google.genai inlineData Base64 parts and ResolvedMultimodalPayload objects.
"""

import os
import io
import base64
import hashlib
import mimetypes
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Union, Dict, Any, Optional, Tuple, List
from PIL import Image, ImageGrab

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


# --- Custom Exception Hierarchy ---

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


class UnsupportedFormatError(MultimodalResolverError, ValueError):
    """Raised when file extension, magic bytes, or image format is unsupported or invalid."""
    pass


class ImageNotFoundError(MultimodalResolverError, FileNotFoundError):
    """Base class raised when a requested image file, path, or reference cannot be located."""
    pass


class ClipboardEmptyError(ImageNotFoundError, ValueError):
    """Raised when Windows clipboard does not contain any image data or image file paths."""
    pass


class ArtifactNotFoundError(ImageNotFoundError):
    """Raised when a specified artifact reference (@artifact:<name>) cannot be resolved."""
    pass


class ClipboardAccessError(MultimodalResolverError, OSError):
    """Raised when reading from OS/Windows clipboard fails due to OS lock or permission errors."""
    pass


class CorruptedImageError(MultimodalResolverError, ValueError):
    """Raised when an image file header or bytes are corrupted, truncated, or unparseable by Pillow."""
    pass


# --- Payload Data Structure ---

@dataclass
class ResolvedMultimodalPayload:
    raw_bytes: bytes
    mime_type: str
    base64_data: str
    sha256: str
    width: int
    height: int
    file_path: Optional[str] = None
    source_type: str = "unknown"

    @property
    def base64_str(self) -> str:
        """Alias for base64_data."""
        return self.base64_data

    @property
    def genai_part(self) -> Any:
        """Returns google.genai types.Part object constructed from raw bytes."""
        if types is None:
            raise RuntimeError("google.genai package is not installed.")
        return types.Part.from_bytes(data=self.raw_bytes, mime_type=self.mime_type)

    def to_genai_part(self) -> Any:
        """Explicit method alias for genai_part property."""
        return self.genai_part

    def to_inline_data_dict(self) -> Dict[str, Any]:
        """Returns JSON-compliant inlineData dictionary block."""
        return {
            "inlineData": {
                "mimeType": self.mime_type,
                "data": self.base64_data
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        """Returns full metadata dictionary representation."""
        return {
            "sha256": self.sha256,
            "mime_type": self.mime_type,
            "width": self.width,
            "height": self.height,
            "file_path": self.file_path,
            "source_type": self.source_type,
            "byte_size": len(self.raw_bytes),
            "base64_data": self.base64_data,
            "inline_data": self.to_inline_data_dict()
        }


# --- Core MultimodalResolver Class ---

class MultimodalResolver:
    """
    Production-grade polymorphic image preprocessor for Gemini 3.6 Flash.
    """

    @staticmethod
    def _inspect_magic_bytes(data: bytes) -> Optional[str]:
        """Inspects magic byte headers of the raw binary payload."""
        if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
            return "image/jpeg"
        if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image/webp"
        if len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        if len(data) >= 2 and data[:2] == b"BM":
            return "image/bmp"
        if len(data) >= 4 and data[:4] in (b"II*\x00", b"MM\x00*"):
            return "image/tiff"
        return None

    @staticmethod
    def inspect_mime_type(data: bytes, hint_path: Optional[str] = None) -> str:
        """
        Executes 3-tiered MIME type detection:
        Tier 1: Magic byte header inspection
        Tier 2: Pillow metadata inspection
        Tier 3: Extension hint via mimetypes
        """
        if not data or len(data) == 0:
            raise CorruptedImageError("Empty byte array provided for MIME inspection", source=data)

        # Tier 1: Magic byte header inspection
        magic_mime = MultimodalResolver._inspect_magic_bytes(data)
        if magic_mime:
            return magic_mime

        # Tier 2: Pillow inspection
        try:
            with Image.open(io.BytesIO(data)) as img:
                fmt = img.format
                if fmt:
                    fmt_upper = fmt.upper()
                    format_map = {
                        "PNG": "image/png",
                        "JPEG": "image/jpeg",
                        "JPG": "image/jpeg",
                        "WEBP": "image/webp",
                        "GIF": "image/gif",
                        "BMP": "image/bmp",
                        "TIFF": "image/tiff",
                    }
                    if fmt_upper in format_map:
                        return format_map[fmt_upper]
        except Exception:
            pass

        # Tier 3: Extension hint fallback
        if hint_path:
            guessed_type, _ = mimetypes.guess_type(str(hint_path))
            if guessed_type and guessed_type.startswith("image/"):
                return guessed_type

        raise UnsupportedFormatError(
            "Unsupported or corrupted image format.",
            source=data[:16] if data else None,
            details={"hint_path": hint_path, "header_hex": data[:16].hex() if data else ""}
        )

    @staticmethod
    def _resolve_clipboard(at_ref: str) -> Tuple[bytes, str, Optional[str]]:
        """Resolves image from Windows RAM clipboard via PIL.ImageGrab."""
        try:
            clip_data = ImageGrab.grabclipboard()
        except (OSError, RuntimeError, Exception) as err:
            raise ClipboardAccessError(
                f"Failed to access Windows RAM clipboard: {str(err)}",
                source=at_ref,
                details={"error_str": str(err)}
            )

        if clip_data is None:
            raise ClipboardEmptyError(
                "No image data or valid image file found in Windows clipboard.",
                source=at_ref,
                details={"clipboard_type": None}
            )

        if isinstance(clip_data, Image.Image):
            buf = io.BytesIO()
            clip_data.save(buf, format="PNG")
            return (buf.getvalue(), "clipboard", "clipboard")

        elif isinstance(clip_data, list):
            valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"}
            for item in clip_data:
                item_path = Path(str(item))
                if item_path.suffix.lower() in valid_exts and item_path.exists() and item_path.is_file():
                    return (item_path.read_bytes(), "clipboard", str(item_path.resolve()))
            raise ClipboardEmptyError(
                "Clipboard contains file paths, but none are valid existing image files.",
                source=at_ref,
                details={"clipboard_paths": clip_data}
            )
        else:
            raise ClipboardEmptyError(
                f"Unsupported clipboard data format: {type(clip_data)}",
                source=at_ref,
                details={"clipboard_type": str(type(clip_data))}
            )

    @staticmethod
    def _resolve_latest(
        at_ref: str,
        workspace_dir: Optional[Union[str, Path]] = None,
        extra_search_dirs: Optional[List[Union[str, Path]]] = None
    ) -> Tuple[bytes, str, Optional[str]]:
        """Scans workspace, temp, and screenshots directories for the newest image file."""
        valid_exts = {".png", ".jpg", ".jpeg", ".webp"}
        search_dirs = []

        root_dir = Path(workspace_dir).resolve() if workspace_dir else Path.cwd().resolve()
        search_dirs.append(root_dir)

        if extra_search_dirs is not None:
            for d in extra_search_dirs:
                if d:
                    search_dirs.append(Path(d).resolve())
        else:
            temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()
            if temp_dir:
                search_dirs.append(Path(temp_dir).resolve())

            user_profile = os.environ.get("USERPROFILE") or os.environ.get("HOME")
            if user_profile:
                pics = Path(user_profile) / "Pictures"
                if (pics / "Screenshots").exists():
                    search_dirs.append((pics / "Screenshots").resolve())
                if pics.exists():
                    search_dirs.append(pics.resolve())

        candidates = []
        skip_dirs = {".git", ".venv", "__pycache__", "node_modules", "build", "dist"}

        for s_dir in search_dirs:
            if not s_dir.exists() or not s_dir.is_dir():
                continue
            try:
                for root, dirs, files in os.walk(s_dir, topdown=True):
                    dirs[:] = [
                        d for d in dirs
                        if d not in skip_dirs
                        and not d.startswith(".")
                        and not d.startswith("pytest-")
                        and not d.startswith("pytest_")
                    ]

                    try:
                        rel = Path(root).relative_to(s_dir)
                        if len(rel.parts) > 3:
                            dirs[:] = []
                            continue
                    except ValueError:
                        pass

                    for f in files:
                        f_path = Path(root) / f
                        if f_path.suffix.lower() in valid_exts:
                            try:
                                st = f_path.stat()
                                if st.st_size > 0:
                                    candidates.append((st.st_mtime, f_path))
                            except Exception:
                                pass
            except Exception:
                pass

        if not candidates:
            raise ImageNotFoundError(
                "No recent image file (.png, .jpg, .jpeg, .webp) found in workspace, temp, or screenshots directories.",
                source=at_ref,
                details={"searched_dirs": [str(d) for d in search_dirs]}
            )

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_file = candidates[0][1]
        return (best_file.read_bytes(), "latest", str(best_file.resolve()))

    @staticmethod
    def _resolve_artifact(
        at_ref: str,
        artifact_name: str,
        workspace_dir: Optional[Union[str, Path]] = None,
        extra_search_dirs: Optional[List[Union[str, Path]]] = None
    ) -> Tuple[bytes, str, Optional[str]]:
        """Resolves image artifacts from .agents, artifacts/, and global stores."""
        valid_exts = [".png", ".jpg", ".jpeg", ".webp"]
        name_path = Path(artifact_name)

        if name_path.suffix.lower() in valid_exts:
            candidate_names = [artifact_name]
        else:
            candidate_names = [f"{artifact_name}{ext}" for ext in valid_exts] + [artifact_name]

        root_dir = Path(workspace_dir).resolve() if workspace_dir else Path.cwd().resolve()

        search_roots = []
        agents_dir = root_dir / ".agents"
        if agents_dir.exists():
            search_roots.append(agents_dir)

        ws_artifacts = root_dir / "artifacts"
        if ws_artifacts.exists():
            search_roots.append(ws_artifacts)

        ws_dot_artifacts = root_dir / ".artifacts"
        if ws_dot_artifacts.exists():
            search_roots.append(ws_dot_artifacts)

        if extra_search_dirs is not None:
            for d in extra_search_dirs:
                if d and Path(d).exists():
                    search_roots.append(Path(d).resolve())
        else:
            user_home = os.environ.get("USERPROFILE") or os.environ.get("HOME")
            if user_home:
                g1 = Path(user_home) / ".gemini" / "antigravity-cli" / "artifacts"
                if g1.exists():
                    search_roots.append(g1)
                g2 = Path(user_home) / ".gemini" / "artifacts"
                if g2.exists():
                    search_roots.append(g2)

        search_roots.append(root_dir)

        found_candidates = []
        for s_root in search_roots:
            if not s_root.exists():
                continue
            try:
                for root, dirs, files in os.walk(s_root):
                    for c_name in candidate_names:
                        if c_name in files:
                            f_path = Path(root) / c_name
                            try:
                                st = f_path.stat()
                                if st.st_size > 0:
                                    found_candidates.append((st.st_mtime, f_path))
                            except Exception:
                                pass
            except Exception:
                pass

        if not found_candidates:
            raise ArtifactNotFoundError(
                f"Artifact reference '{artifact_name}' could not be resolved in artifact directories.",
                source=at_ref,
                details={"artifact_name": artifact_name, "searched_roots": [str(r) for r in search_roots]}
            )

        found_candidates.sort(key=lambda x: x[0], reverse=True)
        best_artifact = found_candidates[0][1]
        return (best_artifact.read_bytes(), "artifact", str(best_artifact.resolve()))

    @staticmethod
    def resolve_at_reference(
        at_ref: str,
        workspace_dir: Optional[Union[str, Path]] = None,
        extra_search_dirs: Optional[List[Union[str, Path]]] = None
    ) -> Tuple[bytes, str, Optional[str]]:
        """
        Resolves symbolic @ references (@clipboard, @latest, @artifact:<name>, @<path>).
        Returns (raw_bytes, source_type, file_path_or_identifier).
        """
        ref_str = at_ref.strip()
        clean_ref = ref_str[1:] if ref_str.startswith("@") else ref_str
        clean_lower = clean_ref.lower()

        if clean_lower in ("clipboard", "clip"):
            return MultimodalResolver._resolve_clipboard(at_ref)
        elif clean_lower in ("latest", "last"):
            return MultimodalResolver._resolve_latest(at_ref, workspace_dir, extra_search_dirs)
        elif clean_lower.startswith("artifact:") or clean_lower.startswith("artifact/"):
            artifact_name = clean_ref[len("artifact:"):] if clean_lower.startswith("artifact:") else clean_ref[len("artifact/"):]
            return MultimodalResolver._resolve_artifact(at_ref, artifact_name.strip(), workspace_dir, extra_search_dirs)
        else:
            target_path = Path(clean_ref).expanduser()
            if not target_path.is_absolute() and workspace_dir:
                target_path = Path(workspace_dir) / target_path

            target_path = target_path.resolve()
            if target_path.exists() and target_path.is_file():
                return (target_path.read_bytes(), "file", str(target_path))
            else:
                raise ImageNotFoundError(
                    f"Image file specified in reference '{at_ref}' not found at {target_path}",
                    source=at_ref,
                    details={"resolved_path": str(target_path)}
                )

    @classmethod
    def resolve(
        cls,
        source: Union[str, Path, bytes, bytearray, Image.Image],
        workspace_dir: Optional[Union[str, Path]] = None,
        extra_search_dirs: Optional[List[Union[str, Path]]] = None,
        strict: bool = True
    ) -> ResolvedMultimodalPayload:
        """
        Main entrypoint. Ingests polymorphic image source, validates format integrity,
        computes SHA-256, extracts dimensions, and returns ResolvedMultimodalPayload.
        """
        if source is None:
            raise TypeError("Source cannot be None")

        raw_bytes: bytes = b""
        source_type: str = "unknown"
        file_path: Optional[str] = None

        if isinstance(source, (bytes, bytearray)):
            if len(source) == 0:
                raise CorruptedImageError("Empty byte array provided as image source", source=source)
            raw_bytes = bytes(source)
            source_type = "bytes"
            file_path = None

        elif isinstance(source, Image.Image):
            buf = io.BytesIO()
            fmt = source.format if source.format in ("PNG", "JPEG", "WEBP", "GIF", "BMP", "TIFF") else "PNG"
            try:
                source.save(buf, format=fmt)
            except Exception:
                buf = io.BytesIO()
                source.convert("RGB").save(buf, format="PNG")
            raw_bytes = buf.getvalue()
            source_type = "pil_image"
            file_path = None

        elif isinstance(source, (str, Path)):
            str_src = str(source).strip()
            if not str_src:
                raise ValueError("Empty string source provided")

            str_lower = str_src.lower()
            is_at_ref = (
                str_src.startswith("@") or
                str_lower in ("clipboard", "clip", "latest", "last") or
                str_lower.startswith("artifact:") or str_lower.startswith("artifact/")
            )

            if is_at_ref:
                raw_bytes, source_type, file_path = cls.resolve_at_reference(
                    str_src, workspace_dir=workspace_dir, extra_search_dirs=extra_search_dirs
                )
            elif str_src.startswith("data:image/") or str_src.startswith("data:"):
                # Data URI
                source_type = "base64_data_uri"
                file_path = None
                try:
                    header, b64_payload = str_src.split(",", 1) if "," in str_src else ("", str_src)
                    raw_bytes = base64.b64decode(b64_payload)
                except Exception as err:
                    raise CorruptedImageError(f"Invalid Base64 Data URI string: {str(err)}", source=str_src)
            else:
                # File path or raw Base64 string
                path_obj = Path(str_src).expanduser()
                if path_obj.exists() and path_obj.is_file():
                    raw_bytes = path_obj.read_bytes()
                    source_type = "file"
                    file_path = str(path_obj.resolve())
                else:
                    # Attempt base64 decode if not a valid file path
                    try:
                        decoded = base64.b64decode(str_src, validate=True)
                        magic_mime = cls._inspect_magic_bytes(decoded)
                        if magic_mime:
                            raw_bytes = decoded
                            source_type = "base64_str"
                            file_path = None
                        else:
                            # Check Pillow open
                            try:
                                with Image.open(io.BytesIO(decoded)) as test_img:
                                    test_img.verify()
                                raw_bytes = decoded
                                source_type = "base64_str"
                                file_path = None
                            except Exception:
                                raise ImageNotFoundError(
                                    f"File path does not exist on disk and string is not a valid base64 image: {str_src}",
                                    source=str_src
                                )
                    except Exception:
                        raise ImageNotFoundError(
                            f"Image file not found on disk: {str_src}",
                            source=str_src
                        )
        else:
            raise TypeError(f"Unsupported source type: {type(source)}")

        # 3-Tier MIME type inspection
        mime_type = cls.inspect_mime_type(raw_bytes, hint_path=file_path)

        # Extract dimensions using Pillow (and verify pixel payload stream if strict=True)
        try:
            with Image.open(io.BytesIO(raw_bytes)) as img:
                width, height = img.size
                if strict:
                    img.load()
        except Exception as err:
            raise CorruptedImageError(
                f"Failed to parse image dimensions or verify pixel payload: {str(err)}",
                source=source
            )

        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        base64_data = base64.b64encode(raw_bytes).decode("utf-8")

        return ResolvedMultimodalPayload(
            raw_bytes=raw_bytes,
            mime_type=mime_type,
            base64_data=base64_data,
            sha256=sha256,
            width=width,
            height=height,
            file_path=file_path,
            source_type=source_type
        )

    @classmethod
    def dispatch_to_gemini(
        cls,
        image_input: Union[str, Path, bytes, Image.Image, ResolvedMultimodalPayload],
        prompt: str,
        model: str = "gemini-3.6-flash",
        client: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Resolves image input and dispatches directly to Gemini 3.6 Flash via google.genai Client.
        """
        if isinstance(image_input, ResolvedMultimodalPayload):
            payload = image_input
        else:
            payload = cls.resolve(image_input)

        try:
            if client is None:
                client = genai.Client()
            part = payload.to_genai_part()
            response = client.models.generate_content(
                model=model,
                contents=[prompt, part]
            )
            return {
                "status": "SUCCESS",
                "text": getattr(response, "text", str(response)),
                "mime_type": payload.mime_type,
                "sha256": payload.sha256,
                "payload": payload
            }
        except Exception as err:
            return {
                "status": "ERROR",
                "error": str(err),
                "mime_type": payload.mime_type,
                "sha256": payload.sha256,
                "payload": payload
            }
