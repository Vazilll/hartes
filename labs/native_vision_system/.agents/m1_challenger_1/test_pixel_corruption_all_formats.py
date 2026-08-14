"""
Expanded Pixel Corruption Verification Script
Location: C:\\vazus\\labs\\native_vision_system\\.agents\\m1_challenger_1\\test_pixel_corruption_all_formats.py
"""

import sys
import io
import os
import tempfile
from pathlib import Path
from PIL import Image

sys.path.insert(0, r"C:\vazus")

from vazus_core.multimodal_resolver import MultimodalResolver, CorruptedImageError

def test_corrupted_pixels():
    formats = ["PNG", "JPEG", "WEBP", "GIF", "BMP", "TIFF"]

    results = []

    for fmt in formats:
        buf = io.BytesIO()
        img = Image.new("RGB", (32, 32), color="red")
        img.save(buf, format=fmt)
        valid_bytes = buf.getvalue()

        # Corrupt the last 40% of the byte array
        cutoff = int(len(valid_bytes) * 0.6)
        corrupted_bytes = valid_bytes[:cutoff] + (b"\x00" * (len(valid_bytes) - cutoff))

        passed_resolve = False
        load_failed = False
        error_msg = ""

        try:
            payload = MultimodalResolver.resolve(corrupted_bytes)
            passed_resolve = True

            # Now test if Pillow img.verify() or img.load() fails
            try:
                with Image.open(io.BytesIO(payload.raw_bytes)) as test_img:
                    test_img.load()
            except Exception as e:
                load_failed = True
                error_msg = str(e)
        except CorruptedImageError as e:
            passed_resolve = False
            error_msg = f"Caught CorruptedImageError: {e}"
        except Exception as e:
            passed_resolve = False
            error_msg = f"Caught unexpected {type(e).__name__}: {e}"

        results.append({
            "format": fmt,
            "passed_resolve": passed_resolve,
            "load_failed": load_failed,
            "error_msg": error_msg
        })

    print("FORMAT PIXEL CORRUPTION RESULTS:")
    for r in results:
        print(f"Format: {r['format']:<6} | Resolve Allowed Corrupted Payload: {r['passed_resolve']!s:<5} | Downstream load() Crashes: {r['load_failed']!s:<5} | Msg: {r['error_msg']}")

if __name__ == "__main__":
    test_corrupted_pixels()
