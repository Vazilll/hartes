import sys
try:
    if sys.stdout:
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr:
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import os
import io
import traceback
from datetime import datetime

# --- Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = r"G:\Мой диск\ai\sync.log"


def log(msg, log_file=None):
    """Write a timestamped message to the log file and stdout."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    if log_file:
        try:
            log_file.write(line + "\n")
            log_file.flush()
        except Exception:
            pass


def run_sync():
    """Import and run sync_dialogues and export_brain_state."""
    # Ensure script dir is in path so imports work
    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)

    # Open log file
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    log_file = open(LOG_PATH, "a", encoding="utf-8")

    log("=" * 60, log_file)
    log("DNTS AutoSync — Начало синхронизации", log_file)
    log("=" * 60, log_file)

    # Step 1: Sync dialogues
    log("--- Этап 1: Синхронизация диалогов ---", log_file)
    try:
        import sync_dialogues
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            sync_dialogues.main()
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
            sys.stdout.reconfigure(encoding='utf-8')

        for line in output.strip().split("\n"):
            if line.strip():
                log(f"  {line.strip()}", log_file)
        log("✅ Диалоги синхронизированы", log_file)
    except Exception as e:
        log(f"❌ Ошибка синхронизации диалогов: {e}", log_file)
        log(traceback.format_exc(), log_file)

    # Step 2: Export brain state
    log("--- Этап 2: Экспорт состояния мозга ---", log_file)
    try:
        import export_brain_state
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            export_brain_state.export_brain_state()
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
            sys.stdout.reconfigure(encoding='utf-8')

        for line in output.strip().split("\n"):
            if line.strip():
                log(f"  {line.strip()}", log_file)
        log("✅ Состояние мозга экспортировано", log_file)
    except Exception as e:
        log(f"❌ Ошибка экспорта состояния мозга: {e}", log_file)
        log(traceback.format_exc(), log_file)

    log("DNTS AutoSync — Синхронизация завершена", log_file)
    log("", log_file)

    log_file.close()


if __name__ == "__main__":
    run_sync()
