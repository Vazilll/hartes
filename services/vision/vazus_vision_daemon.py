"""
Milestone M3: Real-Time Vision & Clipboard Watcher Daemon for vazus SuperGraph OS.
File: C:\\vazus\\vazus_vision_daemon.py

Features:
1. Dual-channel real-time event monitoring:
   - Channel A: Win32 clipboard HWND listener (WM_CLIPBOARDUPDATE 0x031D) capturing RAM bitmap buffers.
   - Channel B: Workspace file watcher using watchfiles.awatch for .png, .jpg, .jpeg, .webp drops.
2. Deduplication LRU Cache (SHA-256 fingerprinting with TTL).
3. Payload Generator integrating MultimodalResolver, TUIPreviewRenderer, and RapidOCR.
4. Local IPC: WebSocket server (ws://127.0.0.1:8765/ws/vision) and SQLite WAL event logging.
5. CLI controls: --start, --stop, --status, --once, --test-clip, --test-drop.
"""

import sys
import os
import io
import time
import json
import uuid
import signal
import asyncio
import logging
import argparse
import threading
import collections
from pathlib import Path
from typing import Dict, Any, Optional, Set, List
from PIL import Image, ImageGrab

# --- Workspace Imports ---
sys.path.insert(0, r"C:\vazus")

from vazus_core.memory.multimodal_resolver import MultimodalResolver
from vazus_core.integrations.tui_preview_renderer import TUIPreviewRenderer
from vazus_core.memory.db import get_db_connection

# --- Optional External Dependencies ---
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

try:
    from watchfiles import awatch, Change
    HAS_WATCHFILES = True
except ImportError:
    HAS_WATCHFILES = False

try:
    import numpy as np
    from rapidocr import RapidOCR
    HAS_RAPIDOCR = True
except ImportError:
    HAS_RAPIDOCR = False

# Win32 GUI imports
if sys.platform == "win32":
    try:
        import win32gui
        import win32con
        import ctypes
        HAS_WIN32 = True
    except ImportError:
        HAS_WIN32 = False
else:
    HAS_WIN32 = False

# --- Configuration Constants ---
DEFAULT_WS_HOST = "127.0.0.1"
DEFAULT_WS_PORT = 8765
DEFAULT_WS_PATH = "/ws/vision"
DEFAULT_WORKSPACE_DIR = r"C:\vazus\labs\native_vision_system"
DEFAULT_DB_PATH = r"C:\vazus\services\memory\vazus.db"
PID_FILE_PATH = r"C:\vazus\services\memory\vision_daemon.pid"

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
IGNORED_DIRECTORIES = {".git", ".agents", "node_modules", "__pycache__", ".venv", "venv", "build", "dist", ".idea", ".vscode"}

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("VazusVisionDaemon")


# ==============================================================================
# 1. Deduplication LRU Cache
# ==============================================================================

class ImageDeduplicator:
    """LRU Cache for SHA-256 image fingerprinting with TTL expiration."""

    def __init__(self, max_size: int = 100, ttl_seconds: float = 300.0):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: collections.OrderedDict[str, float] = collections.OrderedDict()
        self._lock = threading.Lock()

    def is_duplicate(self, sha256_hash: str) -> bool:
        with self._lock:
            now = time.time()
            self._purge_expired(now)

            if sha256_hash in self.cache:
                self.cache.move_to_end(sha256_hash)
                return True

            self.cache[sha256_hash] = now
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
            return False

    def _purge_expired(self, now: float):
        expired = [h for h, ts in self.cache.items() if now - ts > self.ttl_seconds]
        for h in expired:
            del self.cache[h]


# ==============================================================================
# 2. Visual Token Payload Generator
# ==============================================================================

class VisionPayloadGenerator:
    """Generates structured visual token event JSON payloads."""

    @staticmethod
    def extract_ocr(img: Image.Image) -> Dict[str, Any]:
        """Extracts text using RapidOCR if available."""
        if not HAS_RAPIDOCR:
            return {"engine": "none", "has_text": False, "extracted_text": "", "confidence": 0.0}

        try:
            engine = RapidOCR()
            img_rgb = img.convert("RGB")
            img_np = np.array(img_rgb)
            result, _ = engine(img_np)

            if result:
                lines = [item[1] for item in result if len(item) >= 2]
                scores = [float(item[2]) for item in result if len(item) >= 3]
                avg_score = float(np.mean(scores)) if scores else 1.0
                return {
                    "engine": "rapidocr",
                    "has_text": len(lines) > 0,
                    "extracted_text": "\n".join(lines),
                    "confidence": round(avg_score, 4)
                }
        except Exception as e:
            logger.debug(f"RapidOCR extraction failed: {e}")

        return {"engine": "rapidocr_fallback", "has_text": False, "extracted_text": "", "confidence": 0.0}

    @classmethod
    def generate(
        cls,
        source_input: Any,
        source_type: str = "clipboard",
        file_path: Optional[str] = None,
        deduper: Optional[ImageDeduplicator] = None
    ) -> Dict[str, Any]:
        """Resolves source, constructs preview & OCR, and formats JSON payload."""
        payload = MultimodalResolver.resolve(source_input)
        
        is_dup = False
        if deduper:
            is_dup = deduper.is_duplicate(payload.sha256)

        # Load PIL Image for OCR pass
        try:
            pil_img = Image.open(io.BytesIO(payload.raw_bytes))
        except Exception:
            pil_img = None

        ocr_info = cls.extract_ocr(pil_img) if pil_img else {"engine": "none", "has_text": False, "extracted_text": "", "confidence": 0.0}
        tui_str = TUIPreviewRenderer.render(payload, max_cols=80, max_rows=30, mode="truecolor")

        event_id = f"vvis_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        return {
            "event_id": event_id,
            "timestamp": timestamp,
            "source": source_type,
            "file_path": file_path or payload.file_path,
            "dedup": {
                "sha256": payload.sha256,
                "is_duplicate": is_dup
            },
            "image_metadata": {
                "width": payload.width,
                "height": payload.height,
                "format": payload.mime_type.split("/")[-1].upper(),
                "mode": pil_img.mode if pil_img else "RGB",
                "size_bytes": len(payload.raw_bytes)
            },
            "visual_tokens": {
                "mime_type": payload.mime_type,
                "base64_data": payload.base64_data,
                "genai_inline_part": payload.to_inline_data_dict()
            },
            "tui_preview": tui_str,
            "fast_ocr": ocr_info,
            "subagent_targets": ["subagent_rlm_bridge", "verifier_worker", "open_deep_researcher"]
        }


# ==============================================================================
# 3. Dual Channel Event Listeners
# ==============================================================================

class ClipboardListener:
    """Channel A: Win32 HWND clipboard listener with polling fallback."""

    def __init__(self, loop: asyncio.AbstractEventLoop, callback):
        self.loop = loop
        self.callback = callback
        self.running = False
        self.thread = None
        self.hwnd = None
        self._last_sequence = None

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == 0x031D:  # WM_CLIPBOARDUPDATE
            if self.running:
                asyncio.run_coroutine_threadsafe(self.callback(), self.loop)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _win32_loop(self):
        try:
            wc = win32gui.WNDCLASS()
            wc.lpfnWndProc = self._wnd_proc
            wc.lpszClassName = f"VazusClipboardListener_{uuid.uuid4().hex[:6]}"
            wc.hInstance = win32gui.GetModuleHandle(None)

            try:
                class_atom = win32gui.RegisterClass(wc)
            except Exception:
                class_atom = wc.lpszClassName

            self.hwnd = win32gui.CreateWindow(
                class_atom, "VazusClipboardWindow", 0, 0, 0, 0, 0,
                win32con.HWND_MESSAGE, 0, wc.hInstance, None
            )
            ctypes.windll.user32.AddClipboardFormatListener(self.hwnd)
            self.running = True
            win32gui.PumpMessages()
        except Exception as e:
            logger.warning(f"Win32 HWND creation failed ({e}); falling back to polling loop.")
            self._polling_loop()

    def _polling_loop(self):
        self.running = True
        while self.running:
            try:
                if HAS_WIN32:
                    seq = ctypes.windll.user32.GetClipboardSequenceNumber()
                    if self._last_sequence is not None and seq != self._last_sequence:
                        asyncio.run_coroutine_threadsafe(self.callback(), self.loop)
                    self._last_sequence = seq
            except Exception:
                pass
            time.sleep(0.25)

    def start(self):
        if HAS_WIN32:
            self.thread = threading.Thread(target=self._win32_loop, daemon=True)
        else:
            self.thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if HAS_WIN32 and self.hwnd:
            try:
                ctypes.windll.user32.RemoveClipboardFormatListener(self.hwnd)
                win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass


class WorkspaceWatcher:
    """Channel B: Workspace file watcher using watchfiles.awatch."""

    def __init__(self, workspace_dir: str, callback):
        self.workspace_dir = Path(workspace_dir)
        self.callback = callback

    def _watch_filter(self, _change: Any, path_str: str) -> bool:
        path = Path(path_str)
        if any(ignored in path.parts for ignored in IGNORED_DIRECTORIES):
            return False
        return path.suffix.lower() in ALLOWED_EXTENSIONS

    async def run(self):
        if not HAS_WATCHFILES:
            logger.warning("watchfiles not installed; WorkspaceWatcher disabled.")
            return

        if not self.workspace_dir.exists():
            self.workspace_dir.mkdir(parents=True, exist_ok=True)

        async for changes in awatch(self.workspace_dir, watch_filter=self._watch_filter, debounce=100, step=50):
            for change_type, file_path in changes:
                if change_type in (Change.added, Change.modified):
                    if asyncio.iscoroutinefunction(self.callback):
                        await self.callback(file_path)
                    else:
                        self.callback(file_path)


# ==============================================================================
# 4. IPC & SQLite Persistence Server
# ==============================================================================

class VisionDaemonIPC:
    """WebSocket broadcast server and SQLite WAL event log persister."""

    def __init__(self, host: str = DEFAULT_WS_HOST, port: int = DEFAULT_WS_PORT, db_path: str = DEFAULT_DB_PATH):
        self.host = host
        self.port = port
        self.db_path = db_path
        self.clients: Set[Any] = set()
        self._init_db()

    def _init_db(self):
        conn = get_db_connection(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vision_event_stream (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    file_path TEXT,
                    sha256 TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vision_event_sha256 ON vision_event_stream(sha256);")
            conn.commit()
        finally:
            conn.close()

    def log_event_to_db(self, payload: Dict[str, Any]):
        conn = get_db_connection(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO vision_event_stream
                (event_id, timestamp, source, file_path, sha256, mime_type, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                payload["event_id"],
                payload["timestamp"],
                payload["source"],
                payload.get("file_path"),
                payload["dedup"]["sha256"],
                payload["visual_tokens"]["mime_type"],
                json.dumps(payload)
            ))
            conn.commit()
        finally:
            conn.close()

    async def register_client(self, websocket: Any):
        self.clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            self.clients.discard(websocket)

    async def broadcast(self, payload: Dict[str, Any]):
        self.log_event_to_db(payload)

        if not HAS_WEBSOCKETS or not self.clients:
            return

        message = json.dumps(payload)
        to_remove = set()

        for client in self.clients:
            try:
                await client.send(message)
            except Exception:
                to_remove.add(client)

        self.clients -= to_remove

    async def start_server(self):
        if not HAS_WEBSOCKETS:
            logger.warning("websockets not installed; WebSocket server disabled.")
            return None

        async def handler(websocket, path=None):
            await self.register_client(websocket)

        return await websockets.serve(handler, self.host, self.port)


# ==============================================================================
# 5. Main Daemon Orchestrator & CLI Controls
# ==============================================================================

class VazusVisionDaemon:
    """Master daemon orchestrator linking dual-channel listeners, deduplicator, and IPC."""

    def __init__(self, workspace_dir: str = DEFAULT_WORKSPACE_DIR, db_path: str = DEFAULT_DB_PATH):
        self.workspace_dir = workspace_dir
        self.db_path = db_path
        self.deduper = ImageDeduplicator()
        self.ipc = VisionDaemonIPC(db_path=db_path)
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.clip_listener: Optional[ClipboardListener] = None
        self.ws_watcher: Optional[WorkspaceWatcher] = None

    async def handle_clipboard_event(self):
        try:
            clip_img = ImageGrab.grabclipboard()
            if clip_img is None:
                return

            if isinstance(clip_img, Image.Image):
                payload = VisionPayloadGenerator.generate(
                    source_input=clip_img,
                    source_type="clipboard",
                    deduper=self.deduper
                )
                if not payload["dedup"]["is_duplicate"]:
                    logger.info(f"Clipboard image captured: {payload['event_id']} ({payload['image_metadata']['width']}x{payload['image_metadata']['height']})")
                    await self.ipc.broadcast(payload)
        except Exception as e:
            logger.error(f"Clipboard handling error: {e}")

    async def handle_file_drop_event(self, file_path: str):
        try:
            payload = VisionPayloadGenerator.generate(
                source_input=file_path,
                source_type="file_drop",
                file_path=file_path,
                deduper=self.deduper
            )
            if not payload["dedup"]["is_duplicate"]:
                logger.info(f"Workspace file drop captured: {file_path}")
                await self.ipc.broadcast(payload)
        except Exception as e:
            logger.error(f"File drop handling error for {file_path}: {e}")

    async def run(self):
        self.loop = asyncio.get_running_loop()

        # Write PID file
        Path(PID_FILE_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(PID_FILE_PATH, "w") as f:
            f.write(str(os.getpid()))

        # Start WebSocket Server
        ws_server = await self.ipc.start_server()
        if ws_server:
            logger.info(f"WebSocket server listening at ws://{DEFAULT_WS_HOST}:{DEFAULT_WS_PORT}{DEFAULT_WS_PATH}")

        # Start Channel A (Clipboard)
        self.clip_listener = ClipboardListener(self.loop, self.handle_clipboard_event)
        self.clip_listener.start()
        logger.info("Channel A: Clipboard Listener initialized.")

        # Start Channel B (Workspace Watcher)
        self.ws_watcher = WorkspaceWatcher(self.workspace_dir, self.handle_file_drop_event)
        asyncio.create_task(self.ws_watcher.run())
        logger.info(f"Channel B: Workspace Watcher monitoring {self.workspace_dir}")

        logger.info("Real-Time Vision Daemon fully operational. Press Ctrl+C to terminate.")

        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            self.stop()

    def stop(self):
        if self.clip_listener:
            self.clip_listener.stop()
        if os.path.exists(PID_FILE_PATH):
            try:
                os.remove(PID_FILE_PATH)
            except Exception:
                pass
        logger.info("Real-Time Vision Daemon stopped.")


# ==============================================================================
# 6. CLI Management Entrypoint
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Vazus Real-Time Vision Daemon Control Utility")
    parser.add_argument("--start", action="store_true", help="Start the vision daemon process")
    parser.add_argument("--stop", action="store_true", help="Stop the running vision daemon process")
    parser.add_argument("--status", action="store_true", help="Check the status of the vision daemon")
    parser.add_argument("--once", action="store_true", help="Run a single scan pass across clipboard and workspace drops")
    parser.add_argument("--test-clip", action="store_true", help="Test clipboard capture and print generated JSON payload")
    parser.add_argument("--test-drop", type=str, metavar="PATH", help="Test file drop ingestion for specified file path")

    args = parser.parse_args()

    if args.stop:
        if os.path.exists(PID_FILE_PATH):
            try:
                with open(PID_FILE_PATH, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                print(f"Daemon process {pid} stopped.")
            except Exception as e:
                print(f"Failed to kill daemon process: {e}")
        else:
            print("No PID file found. Daemon is not running.")
        return

    if args.status:
        if os.path.exists(PID_FILE_PATH):
            try:
                with open(PID_FILE_PATH, "r") as f:
                    pid = int(f.read().strip())
                print(f"Daemon RUNNING (PID: {pid}).")
            except Exception:
                print("Daemon STOPPED.")
        else:
            print("Daemon STOPPED.")
        return

    if args.test_clip:
        try:
            clip_data = ImageGrab.grabclipboard()
        except Exception:
            clip_data = None

        if clip_data is None:
            print("NO_IMAGE_IN_CLIPBOARD")
        else:
            payload = VisionPayloadGenerator.generate(clip_data, source_type="clipboard")
            print(json.dumps(payload, indent=2))
        return

    if args.test_drop:
        payload = VisionPayloadGenerator.generate(args.test_drop, source_type="file_drop")
        print(json.dumps(payload, indent=2))
        return

    if args.once:
        print("Executing single scan pass...")
        try:
            clip_data = ImageGrab.grabclipboard()
        except Exception:
            clip_data = None

        if clip_data:
            payload = VisionPayloadGenerator.generate(clip_data, source_type="clipboard")
            print(f"[Clipboard] {payload['event_id']} ({payload['image_metadata']['width']}x{payload['image_metadata']['height']})")
        else:
            print("[Clipboard] No image found.")
        return

    if args.start or len(sys.argv) == 1:
        daemon = VazusVisionDaemon()
        asyncio.run(daemon.run())


if __name__ == "__main__":
    main()
