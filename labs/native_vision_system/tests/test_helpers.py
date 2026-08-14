"""
Test Helpers and Contract Stubs for Native Terminal Multimodal Vision System test suite.

File: C:\\vazus\\labs\\native_vision_system\\tests\\test_helpers.py
"""

import io
import time
import base64
import hashlib
import sqlite3
from pathlib import Path
from PIL import Image

# --- Contract Stubs & Fallbacks for M2 (Renderer) and M3 (Daemon) ---

try:
    from vazus_core.tui_preview_renderer import TUIPreviewRenderer
except ImportError:
    class TUIPreviewRenderer:
        """
        Contract-compliant stub for M2 TUI Preview Renderer.
        Follows PROJECT.md § Architecture & Interface Contracts.
        """

        @staticmethod
        def compute_preview_dimensions(
            img_width: int,
            img_height: int,
            max_cols: int = 80,
            max_rows: int = 40,
            is_half_block: bool = True
        ) -> tuple[int, int]:
            if img_width <= 0 or img_height <= 0 or max_cols <= 0 or max_rows <= 0:
                return (max(1, max_cols), max(1, max_rows))

            char_aspect = 0.5 if is_half_block else 1.0
            target_aspect = (img_width / img_height) * char_aspect

            cols = max_cols
            rows = int(cols / target_aspect)
            if rows > max_rows:
                rows = max_rows
                cols = int(rows * target_aspect)

            return (max(1, cols), max(1, rows))

        @classmethod
        def render(
            cls,
            payload_or_image,
            max_cols: int = 80,
            max_rows: int = 40,
            mode: str = "truecolor"
        ) -> str:
            if max_cols <= 0:
                max_cols = 80
            if max_rows <= 0:
                max_rows = 40

            if hasattr(payload_or_image, "raw_bytes"):
                img_bytes = payload_or_image.raw_bytes
                img = Image.open(io.BytesIO(img_bytes))
            elif isinstance(payload_or_image, Image.Image):
                img = payload_or_image
            elif isinstance(payload_or_image, (str, Path)):
                img = Image.open(str(payload_or_image))
            else:
                img = Image.new("RGB", (10, 10), color="blue")

            w, h = img.size
            cols, rows = cls.compute_preview_dimensions(w, h, max_cols, max_rows)

            lines = []
            if mode == "truecolor":
                for r in range(rows):
                    line_parts = []
                    for c in range(cols):
                        fg_code = f"\x1b[38;2;255;0;0m"
                        bg_code = f"\x1b[48;2;0;0;255m"
                        line_parts.append(f"{fg_code}{bg_code}▀")
                    line_parts.append("\x1b[0m")
                    lines.append("".join(line_parts))
            elif mode in ("256", "256color"):
                for r in range(rows):
                    line_parts = []
                    for c in range(cols):
                        line_parts.append(f"\x1b[38;5;196m\x1b[48;5;21m▀")
                    line_parts.append("\x1b[0m")
                    lines.append("".join(line_parts))
            elif mode.startswith("ascii"):
                ramp = " .:!/r(l1Z4H9W8$@" if mode == "ascii_17" else " .:-=+*#%@"
                for r in range(rows):
                    lines.append(ramp[-1] * cols)
            else:
                for r in range(rows):
                    lines.append("▀" * cols)

            return "\n".join(lines)





class VisionDaemonStub:
    """
    Contract-compliant stub for M3 Real-Time Vision Daemon.
    Follows PROJECT.md § Architecture & Interface Contracts.
    """

    def __init__(self, workspace_dir: str = r"C:\vazus"):
        self.workspace_dir = workspace_dir
        self.running = False
        self.dedup_cache = set()
        self.db_path = Path(workspace_dir) / "memory" / "vazus.db"

    def build_visual_token_payload(
        self,
        source_type: str,
        raw_bytes: bytes,
        file_path: str = None,
        ocr_text: str = ""
    ) -> dict:
        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        b64_data = base64.b64encode(raw_bytes).decode("utf-8")

        mime_type = "image/png"
        if raw_bytes.startswith(b"\xff\xd8\xff"):
            mime_type = "image/jpeg"
        elif raw_bytes.startswith(b"RIFF") and raw_bytes[8:12] == b"WEBP":
            mime_type = "image/webp"

        is_dup = sha256 in self.dedup_cache
        if not is_dup:
            self.dedup_cache.add(sha256)

        try:
            tui_preview = TUIPreviewRenderer.render(
                payload_or_image=raw_bytes,
                max_cols=80,
                max_rows=40,
                mode="truecolor"
            )
        except Exception:
            tui_preview = ""

        return {
            "event_id": f"vvis_{int(time.time()*1000)}_{sha256[:8]}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source_type": source_type,
            "sha256": sha256,
            "mime_type": mime_type,
            "inline_data": {
                "mime_type": mime_type,
                "data": b64_data
            },
            "ocr_text": ocr_text,
            "tui_preview": tui_preview,
            "dedup": {
                "is_duplicate": is_dup
            }
        }

    def record_to_sqlite(self, payload: dict, db_file: str = None) -> bool:
        """Simulates writing event payload to SQLite WAL vision_event_stream table."""
        target_db = db_file or str(self.db_path)
        Path(target_db).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(target_db)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vision_event_stream (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT,
                source_type TEXT,
                sha256 TEXT,
                mime_type TEXT,
                ocr_text TEXT,
                tui_preview TEXT
            )
        """)
        cur.execute("""
            INSERT OR REPLACE INTO vision_event_stream 
            (event_id, timestamp, source_type, sha256, mime_type, ocr_text, tui_preview)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            payload["event_id"],
            payload["timestamp"],
            payload["source_type"],
            payload["sha256"],
            payload["mime_type"],
            payload.get("ocr_text", ""),
            payload.get("tui_preview", "")
        ))
        conn.commit()
        conn.close()
        return True

