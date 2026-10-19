# Forwarder for backward compatibility with user rules & external callers
import sys
from pathlib import Path

target = Path(__file__).resolve().parent / "tools" / "clip_ocr.py"
if target.exists():
    with open(target, "rb") as f:
        code = compile(f.read(), str(target), "exec")
        exec(code, {"__name__": "__main__", "__file__": str(target)})
else:
    sys.exit(f"Target not found: {target}")
