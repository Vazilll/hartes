"""
Adversarial Test Harness for MultimodalResolver (@ reference resolution & edge cases).
Location: C:\\vazus\\labs\\native_vision_system\\.agents\\m1_challenger_2\\test_adversarial_m1.py
Runner: C:\\vazus\\.venv\\Scripts\\python.exe -m pytest C:\\vazus\\labs\\native_vision_system\\.agents\\m1_challenger_2\\test_adversarial_m1.py -v
"""

import os
import io
import sys
import time
import base64
import hashlib
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image

sys.path.insert(0, r"C:\vazus")

from vazus_core.multimodal_resolver import (
    MultimodalResolver,
    ResolvedMultimodalPayload,
    MultimodalResolverError,
    UnsupportedFormatError,
    ImageNotFoundError,
    ClipboardEmptyError,
    ArtifactNotFoundError,
    ClipboardAccessError,
    CorruptedImageError
)


# --- Fixtures ---

@pytest.fixture
def valid_png_bytes():
    buf = io.BytesIO()
    img = Image.new("RGB", (64, 64), color="red")
    img.save(buf, format="PNG")
    return buf.getvalue()

@pytest.fixture
def valid_jpeg_bytes():
    buf = io.BytesIO()
    img = Image.new("RGB", (64, 64), color="blue")
    img.save(buf, format="JPEG")
    return buf.getvalue()


# --- 1. Artifact Resolution Adversarial Tests ---

class TestArtifactResolutionAdversarial:

    def test_artifact_nonexistent_name(self, tmp_path):
        """1.1: Non-existent artifact name raises ArtifactNotFoundError."""
        with pytest.raises(ArtifactNotFoundError) as exc_info:
            MultimodalResolver.resolve("@artifact:ghost_artifact_999", workspace_dir=tmp_path, extra_search_dirs=[])
        assert "ghost_artifact_999" in str(exc_info.value)
        assert exc_info.value.source == "@artifact:ghost_artifact_999"

    def test_artifact_empty_name(self, tmp_path):
        """1.2: Empty artifact reference @artifact: raises ArtifactNotFoundError."""
        with pytest.raises(ArtifactNotFoundError) as exc_info:
            MultimodalResolver.resolve("@artifact:", workspace_dir=tmp_path, extra_search_dirs=[])
        assert exc_info.value.source == "@artifact:"

    def test_artifact_bare_keyword_without_colon(self, tmp_path):
        """1.3: Bare @artifact without colon or slash falls back to path lookup and raises ImageNotFoundError."""
        with pytest.raises(ImageNotFoundError) as exc_info:
            MultimodalResolver.resolve("@artifact", workspace_dir=tmp_path)
        assert "artifact" in str(exc_info.value)

    def test_artifact_path_traversal_attempts(self, tmp_path):
        """1.4: Relative path traversal in @artifact reference fails with ArtifactNotFoundError."""
        secret_dir = tmp_path / "outside_dir"
        secret_dir.mkdir()
        secret_file = secret_dir / "secret.png"
        secret_file.write_bytes(b"FAKE_SECRET_BYTES")

        ws_dir = tmp_path / "workspace"
        ws_dir.mkdir()

        traversal_ref = "@artifact:../../outside_dir/secret.png"
        with pytest.raises(ArtifactNotFoundError):
            MultimodalResolver.resolve(traversal_ref, workspace_dir=ws_dir, extra_search_dirs=[])

    def test_artifact_subfolder_path_resolution(self, tmp_path, valid_png_bytes):
        """1.5: [KNOWN LIMITATION/BUG] Subfolder artifact path @artifact:subfolder/chart.png fails in current implementation."""
        artifacts_dir = tmp_path / "artifacts" / "subfolder"
        artifacts_dir.mkdir(parents=True)
        img_file = artifacts_dir / "chart.png"
        img_file.write_bytes(valid_png_bytes)

        # In current implementation, os.walk files list contains 'chart.png', not 'subfolder/chart.png'.
        # Therefore @artifact:subfolder/chart fails with ArtifactNotFoundError.
        with pytest.raises(ArtifactNotFoundError):
            MultimodalResolver.resolve("@artifact:subfolder/chart", workspace_dir=tmp_path, extra_search_dirs=[])

    def test_artifact_flat_name_nested_directory_resolution(self, tmp_path, valid_png_bytes):
        """1.6: Flat artifact name @artifact:chart resolves when chart.png is inside a subfolder under artifacts/."""
        artifacts_dir = tmp_path / "artifacts" / "deeply" / "nested"
        artifacts_dir.mkdir(parents=True)
        img_file = artifacts_dir / "chart.png"
        img_file.write_bytes(valid_png_bytes)

        payload = MultimodalResolver.resolve("@artifact:chart", workspace_dir=tmp_path, extra_search_dirs=[])
        assert payload.mime_type == "image/png"
        assert payload.file_path == str(img_file.resolve())

    def test_artifact_multiple_matches_newest_mtime(self, tmp_path, valid_png_bytes, valid_jpeg_bytes):
        """1.7: Newest artifact selected by mtime when multiple search roots contain matching file."""
        dir1 = tmp_path / "artifacts"
        dir1.mkdir(parents=True)
        old_art = dir1 / "diagram.png"
        old_art.write_bytes(valid_png_bytes)

        time.sleep(0.05)

        dir2 = tmp_path / ".agents" / "agent_1"
        dir2.mkdir(parents=True)
        new_art = dir2 / "diagram.png"
        new_art.write_bytes(valid_jpeg_bytes)

        payload = MultimodalResolver.resolve("@artifact:diagram", workspace_dir=tmp_path, extra_search_dirs=[])
        assert payload.mime_type == "image/jpeg"
        assert payload.file_path == str(new_art.resolve())


# --- 2. Clipboard Resolution Adversarial Tests ---

class TestClipboardResolutionAdversarial:

    @patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard")
    def test_clipboard_returns_none(self, mock_grab):
        """2.1: Clipboard returns None -> ClipboardEmptyError."""
        mock_grab.return_value = None
        with pytest.raises(ClipboardEmptyError) as exc_info:
            MultimodalResolver.resolve("@clipboard")
        assert exc_info.value.source == "@clipboard"

    @patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard")
    def test_clipboard_returns_empty_list(self, mock_grab):
        """2.2: Clipboard returns [] -> ClipboardEmptyError."""
        mock_grab.return_value = []
        with pytest.raises(ClipboardEmptyError) as exc_info:
            MultimodalResolver.resolve("@clipboard")
        assert exc_info.value.source == "@clipboard"

    @patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard")
    def test_clipboard_list_with_non_image_files(self, mock_grab, tmp_path):
        """2.3: Clipboard contains paths to non-image files (.txt, .py) -> ClipboardEmptyError."""
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("Hello world")
        py_file = tmp_path / "script.py"
        py_file.write_text("print(1)")

        mock_grab.return_value = [str(txt_file), str(py_file)]
        with pytest.raises(ClipboardEmptyError) as exc_info:
            MultimodalResolver.resolve("@clip")
        assert "none are valid existing image files" in str(exc_info.value)

    @patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard")
    def test_clipboard_list_with_nonexistent_files(self, mock_grab):
        """2.4: Clipboard contains paths to non-existent files -> ClipboardEmptyError."""
        mock_grab.return_value = [r"C:\non_existent_path_123.png"]
        with pytest.raises(ClipboardEmptyError):
            MultimodalResolver.resolve("@clip")

    @patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard")
    def test_clipboard_unexpected_data_types(self, mock_grab):
        """2.5: Clipboard returns integer, dict, or string -> ClipboardEmptyError."""
        mock_grab.return_value = 12345
        with pytest.raises(ClipboardEmptyError) as exc_info:
            MultimodalResolver.resolve("@clipboard")
        assert "Unsupported clipboard data format" in str(exc_info.value)

        mock_grab.return_value = "plain text string copied in Windows"
        with pytest.raises(ClipboardEmptyError):
            MultimodalResolver.resolve("@clipboard")

    @patch("vazus_core.multimodal_resolver.ImageGrab.grabclipboard")
    def test_clipboard_os_error_lock(self, mock_grab):
        """2.6: Clipboard API raises OSError -> ClipboardAccessError."""
        mock_grab.side_effect = OSError("PyWin32: OpenClipboard Failed (0x00000005)")
        with pytest.raises(ClipboardAccessError):
            MultimodalResolver.resolve("@clip")


# --- 3. Non-Image Files & @latest Edge Case Tests ---

class TestLatestResolutionAdversarial:

    def test_latest_no_images_only_text_and_code(self, tmp_path):
        """3.1: Workspace contains only text/code files -> ImageNotFoundError."""
        (tmp_path / "doc.txt").write_text("text content")
        (tmp_path / "code.py").write_text("def foo(): pass")
        (tmp_path / "data.json").write_text('{"key": "value"}')

        with pytest.raises(ImageNotFoundError) as exc_info:
            MultimodalResolver.resolve("@latest", workspace_dir=tmp_path, extra_search_dirs=[])
        assert "No recent image file" in str(exc_info.value)

    def test_latest_zero_byte_image_file_skipped(self, tmp_path, valid_png_bytes):
        """3.2: 0-byte .png file is newer than valid .png file -> 0-byte file is skipped."""
        old_valid = tmp_path / "old_valid.png"
        old_valid.write_bytes(valid_png_bytes)

        time.sleep(0.05)

        new_zero = tmp_path / "new_zero.png"
        new_zero.write_bytes(b"")

        payload = MultimodalResolver.resolve("@latest", workspace_dir=tmp_path, extra_search_dirs=[])
        assert payload.file_path == str(old_valid.resolve())

    def test_latest_corrupted_image_file_behavior(self, tmp_path, valid_png_bytes):
        """3.3: [FINDING] Newest file matching .png extension is corrupted text; resolve("@latest") raises CorruptedImageError or UnsupportedFormatError."""
        old_valid = tmp_path / "valid.png"
        old_valid.write_bytes(valid_png_bytes)

        time.sleep(0.05)

        new_corrupt = tmp_path / "corrupt_latest.png"
        new_corrupt.write_text("THIS IS NOT AN IMAGE FILE BUT HAS PNG EXTENSION")

        # _resolve_latest picks corrupt_latest.png because of extension and mtime.
        # inspect_mime_type falls back to tier 3 extension hint ('image/png').
        # Dimension extraction fails in Pillow, raising CorruptedImageError.
        with pytest.raises((CorruptedImageError, UnsupportedFormatError)):
            MultimodalResolver.resolve("@latest", workspace_dir=tmp_path, extra_search_dirs=[])

    def test_latest_directory_named_with_image_extension(self, tmp_path, valid_png_bytes):
        """3.4: Directory named 'fake_folder.png' is ignored by @latest scanner."""
        fake_dir = tmp_path / "fake_folder.png"
        fake_dir.mkdir()

        valid_img = tmp_path / "real.png"
        valid_img.write_bytes(valid_png_bytes)

        payload = MultimodalResolver.resolve("@latest", workspace_dir=tmp_path, extra_search_dirs=[])
        assert payload.file_path == str(valid_img.resolve())

    def test_latest_skip_directories(self, tmp_path, valid_png_bytes):
        """3.5: Images inside .git, .venv, node_modules are skipped."""
        venv_img = tmp_path / ".venv" / "lib" / "site-packages" / "test.png"
        venv_img.parent.mkdir(parents=True)
        venv_img.write_bytes(valid_png_bytes)

        with pytest.raises(ImageNotFoundError):
            MultimodalResolver.resolve("@latest", workspace_dir=tmp_path, extra_search_dirs=[])


# --- 4. Path Traversal & Boundary Tests ---

class TestPathTraversalAdversarial:

    def test_path_traversal_to_non_image_file(self, tmp_path):
        """4.1: Reading non-image text file via @ path traversal raises UnsupportedFormatError or CorruptedImageError."""
        secret_txt = tmp_path / "secret.txt"
        secret_txt.write_text("CONFIDENTIAL_DATA=12345")

        sub_dir = tmp_path / "sub"
        sub_dir.mkdir()

        ref = f"@{sub_dir / '../secret.txt'}"
        with pytest.raises((UnsupportedFormatError, CorruptedImageError)):
            MultimodalResolver.resolve(ref, workspace_dir=sub_dir)

    def test_path_traversal_nonexistent_file(self, tmp_path):
        """4.2: Non-existent relative path traversal raises ImageNotFoundError."""
        ref = "@../../non_existent_file_xyz.png"
        with pytest.raises(ImageNotFoundError) as exc_info:
            MultimodalResolver.resolve(ref, workspace_dir=tmp_path)
        assert exc_info.value.source == ref

    def test_path_traversal_valid_image_outside_workspace(self, tmp_path, valid_png_bytes):
        """4.3: Valid image path outside workspace_dir resolves (Resolver permits external file access)."""
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_img = outside_dir / "external.png"
        outside_img.write_bytes(valid_png_bytes)

        ws_dir = tmp_path / "workspace"
        ws_dir.mkdir()

        ref = f"@{ws_dir / '../outside/external.png'}"
        payload = MultimodalResolver.resolve(ref, workspace_dir=ws_dir)
        assert payload.mime_type == "image/png"
        assert payload.file_path == str(outside_img.resolve())

    def test_whitespace_padded_reference(self, tmp_path, valid_png_bytes):
        """4.4: Whitespace padded reference strings are stripped and resolved."""
        img = tmp_path / "valid.png"
        img.write_bytes(valid_png_bytes)

        payload = MultimodalResolver.resolve(f"  @{img}   ")
        assert payload.mime_type == "image/png"


# --- 5. Polyglot & Mime Header Tests ---

class TestPolyglotAndMimeAdversarial:

    def test_magic_byte_override_misleading_extension(self, tmp_path, valid_jpeg_bytes):
        """5.1: JPEG bytes stored in file named 'fake.png' correctly identified as image/jpeg."""
        fake_png = tmp_path / "fake.png"
        fake_png.write_bytes(valid_jpeg_bytes)

        payload = MultimodalResolver.resolve(fake_png)
        assert payload.mime_type == "image/jpeg"

    def test_corrupted_header_bytes(self, tmp_path):
        """5.2: Corrupted PNG magic header bytes raise CorruptedImageError or UnsupportedFormatError."""
        bad_png = tmp_path / "corrupt.png"
        bad_png.write_bytes(b"\x89PNG\r\n\x1a\nTRUNCATED_AND_CORRUPTED_HEADER")

        with pytest.raises((CorruptedImageError, UnsupportedFormatError)):
            MultimodalResolver.resolve(bad_png)
