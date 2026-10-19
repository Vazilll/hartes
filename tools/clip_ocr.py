#!/usr/bin/env python3
"""Launcher redirecting to canonical services/vision/clip_ocr.py."""
import runpy
from pathlib import Path

target = Path(r"/home/tarhes/Проекты/vazus/services/vision/clip_ocr.py")
if target.exists():
    runpy.run_path(str(target), run_name="__main__")
else:
    raise FileNotFoundError(f"Canonical OCR script not found at {target}")
