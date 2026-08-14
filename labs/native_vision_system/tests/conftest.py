"""
Global Pytest fixtures and synthetic image assets for the Native Terminal Multimodal Vision System test suite.

File: C:\\vazus\\labs\\native_vision_system\\tests\\conftest.py
"""

import os
import io
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image

# Ensure C:\vazus and tests directory are in sys.path
PROJECT_ROOT = Path(r"C:\vazus")
TESTS_DIR = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))


# --- Image Asset Fixtures ---

@pytest.fixture
def sample_png_bytes():
    """Generates a valid 100x100 PNG image byte payload in memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_jpeg_bytes():
    """Generates a valid 100x100 JPEG image byte payload in memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(0, 0, 255))
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def sample_webp_bytes():
    """Generates a valid 100x100 WEBP image byte payload in memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(0, 255, 0))
    img.save(buf, format="WEBP")
    return buf.getvalue()


@pytest.fixture
def sample_pil_image():
    """Generates a sample 120x80 RGB PIL Image instance."""
    return Image.new("RGB", (120, 80), color=(255, 255, 0))


@pytest.fixture
def temp_workspace_dir(tmp_path):
    """Provides an isolated temporary workspace directory fixture."""
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


# --- Mock API Fixtures ---

@pytest.fixture
def mock_gemini_client():
    """Mocks google.genai Client for offline API testing."""
    client = MagicMock()
    response = MagicMock()
    response.text = "Gemini 3.6 Flash: Visual token payload successfully analyzed."
    client.models.generate_content.return_value = response
    return client
