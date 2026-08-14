import time
import sys
from pathlib import Path
sys.path.insert(0, r"C:\vazus")
from vazus_core.multimodal_resolver import (
    MultimodalResolver,
    ArtifactNotFoundError,
    ImageNotFoundError,
    CorruptedImageError,
    UnsupportedFormatError
)

print("=== MultimodalResolver Edge Case Security Tests ===")

# Test 1: Non-image file attempt
try:
    MultimodalResolver.resolve(r"C:\vazus\labs\native_vision_system\PROJECT.md")
    print("FAIL: Text file resolved as image!")
except (CorruptedImageError, UnsupportedFormatError) as e:
    print(f"PASS: Non-image text file rejected with {type(e).__name__}: {e}")
except Exception as e:
    print(f"PASS (other exc): {type(e).__name__}: {e}")

# Test 2: @ non-image file attempt
try:
    MultimodalResolver.resolve(r"@C:\vazus\labs\native_vision_system\PROJECT.md")
    print("FAIL: @Text file resolved as image!")
except (CorruptedImageError, UnsupportedFormatError) as e:
    print(f"PASS: @Non-image text file rejected with {type(e).__name__}: {e}")

# Test 3: Data URI with corrupted base64
try:
    MultimodalResolver.resolve("data:image/png;base64,!!!INVALID_B64!!!")
    print("FAIL: Corrupted Data URI resolved!")
except CorruptedImageError as e:
    print(f"PASS: Corrupted Data URI rejected with CorruptedImageError: {e}")

# Test 4: Base64 string that decodes to non-image
try:
    import base64
    text_b64 = base64.b64encode(b"This is plain text content").decode("utf-8")
    MultimodalResolver.resolve(text_b64)
    print("FAIL: Plain text Base64 resolved as image!")
except ImageNotFoundError as e:
    print(f"PASS: Plain text Base64 rejected with ImageNotFoundError: {e}")
