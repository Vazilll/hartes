#!/usr/bin/env python3
"""
scripts/unified_system_orchestrator.py — Parallel Services Orchestrator for vazus SuperGraph OS v0.1.1-beta.

Supervises:
1. 🌐 Raytsystem Public OS Visual Control Center (http://127.0.0.1:8765 & /universe)
2. 📱 2-Way Google Calendar & Tasks Sync Engine (Obsidian Vault -> Google Cloud)
3. 🧠 SuperGraph Vector Linker & AST Topology Watcher

vazus SuperGraph OS Ecosystem
"""

import sys
import time
import subprocess
import threading
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
DASHBOARD_SERVER = PROJECT_ROOT / "scripts" / "raytsystem_dashboard_server.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.google_sync_engine import GoogleSyncEngine


def run_google_sync_loop(interval_sec: int = 30):
    """Background loop that periodically syncs Obsidian markdown tasks to Google Calendar & Tasks."""
    print("📱 [Orchestrator] Старт фонового демона Google Calendar & Tasks Sync...", flush=True)
    engine = GoogleSyncEngine()
    while True:
        try:
            _res = engine.scan_and_sync()
            # Silent background status
        except Exception as e:
            sys.stderr.write(f"⚠️ [Google Sync Loop Warning]: {e}\n")
        time.sleep(interval_sec)


def is_port_in_use(port: int = 8765) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def launch_dashboard_server():
    """Launches the Raytsystem Web Server process."""
    if is_port_in_use(8765):
        print("🌐 [Orchestrator] Raytsystem Visual Control Center уже запущен на http://127.0.0.1:8765", flush=True)
        return

    print(f"🌐 [Orchestrator] Запуск Raytsystem Visual Control Center (http://127.0.0.1:8765)...", flush=True)
    cmd = [str(VENV_PYTHON), str(DASHBOARD_SERVER)]
    proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))
    proc.wait()


def main():
    print("=" * 75)
    print("🚀 vazus SuperGraph OS v0.1.1-beta — Единый оркестратор системных сервисов")
    print("=" * 75)
    print("1. 🌐 Web Control Center & 3D Universe: http://127.0.0.1:8765/universe")
    print("2. 📝 Хранилище заметок Obsidian: C:/vazus/services/memory/semantic/wiki")
    print("3. 📱 Двухсторонняя синхронизация задач: Google Calendar API & Google Tasks API")
    print("=" * 75)

    # Start Google Sync in background thread
    t_sync = threading.Thread(target=run_google_sync_loop, daemon=True)
    t_sync.start()

    # Launch Web Server in main process
    try:
        launch_dashboard_server()
    except KeyboardInterrupt:
        print("\n🛑 Остановка оркестратора системных сервисов.")


if __name__ == "__main__":
    main()
