#!/usr/bin/env python3
"""
TARS OS — File System Watchdog Service
========================================
Background daemon that watches C:/vazus/ for file changes.
On any .cpp/.rs/.zig/.py file write → triggers tars_hook_handler pipeline
without needing a git commit.

Run as background service:
  python C:/vazus/harness/autonomy/tars_watchdog.py

Stop with Ctrl+C.
"""

import sys
import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

VAZUS_ROOT = Path("C:/vazus")
HANDLER_SCRIPT = VAZUS_ROOT / "harness/autonomy/tars_hook_handler.py"
VENV_PYTHON = VAZUS_ROOT / ".venv/Scripts/python.exe"

WATCH_EXTENSIONS = {".cpp", ".rs", ".zig", ".py", ".md"}
IGNORE_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".mypy_cache"}
DEBOUNCE_SECONDS = 3.0  # wait 3s after last change before triggering

class TARSWatchdogHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._last_trigger: dict[str, float] = {}

    def _should_handle(self, path: str) -> bool:
        p = Path(path)
        if p.suffix.lower() not in WATCH_EXTENSIONS:
            return False
        for part in p.parts:
            if part in IGNORE_DIRS:
                return False
        return True

    def _debounced_trigger(self, path: str):
        import threading
        now = time.monotonic()
        self._last_trigger[path] = now

        def _delayed():
            time.sleep(DEBOUNCE_SECONDS)
            if self._last_trigger.get(path) == now:
                self._run_pipeline(path)

        t = threading.Thread(target=_delayed, daemon=True)
        t.start()

    def _run_pipeline(self, path: str):
        print(f"\n🔔 [Watchdog] Change detected: {path}")
        print("   → Running TARS memory snapshot pipeline...")
        try:
            result = subprocess.run(
                [str(VENV_PYTHON), str(HANDLER_SCRIPT), "--watchdog", path],
                cwd=str(VAZUS_ROOT),
                capture_output=False,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            print("   ⚠️  Pipeline timed out after 30s.")
        except Exception as e:
            print(f"   ❌ Pipeline error: {e}")

    def on_modified(self, event):
        if not event.is_directory and self._should_handle(event.src_path):
            self._debounced_trigger(event.src_path)

    def on_created(self, event):
        if not event.is_directory and self._should_handle(event.src_path):
            self._debounced_trigger(event.src_path)


def main():
    print("╔══════════════════════════════════════════════╗")
    print("║  👁️  TARS OS — Watchdog Service Starting...   ║")
    print("╚══════════════════════════════════════════════╝")
    print(f"  Watching: {VAZUS_ROOT}")
    print(f"  Triggers: {', '.join(sorted(WATCH_EXTENSIONS))}")
    print(f"  Debounce: {DEBOUNCE_SECONDS}s")
    print("  Press Ctrl+C to stop.\n")

    event_handler = TARSWatchdogHandler()
    observer = Observer()
    observer.schedule(event_handler, str(VAZUS_ROOT), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n🛑 TARS Watchdog stopped.")
    observer.join()


if __name__ == "__main__":
    main()
