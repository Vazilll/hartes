"""
db_backup.py — Automated SQLite backup with rotation and integrity check.

Addresses Critical Blind Spot #2: vazus.db is a single point of failure.
All memory (Mem0, organic_insights, academic debts, transactions) is in one file.

Usage:
    python -m vazus_core.workers.db_backup          # one-shot backup
    python -m vazus_core.workers.db_backup --verify  # backup + PRAGMA integrity_check
"""

import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("db_backup")

VAZUS_ROOT = Path(r"/home/tarhes/Проекты/vazus").resolve()
DB_PATH = VAZUS_ROOT / "services" / "memory" / "vazus.db"
BACKUP_DIR = VAZUS_ROOT / "backups"
GDRIVE_BACKUP_DIR = Path(r"G:\My Drive\ai\backups")
MAX_BACKUPS = 7  # Keep last 7 daily backups


def run_backup(
    db_path: Optional[Path] = None,
    backup_dir: Optional[Path] = None,
    max_backups: int = MAX_BACKUPS,
    verify: bool = True,
    sync_gdrive: bool = True,
) -> Dict[str, Any]:
    """
    Creates a safe SQLite backup using sqlite3.backup() API.

    This uses the online backup API which is safe even if the database
    is being written to concurrently (WAL mode). It does NOT just copy the file.

    Returns:
        Dict with backup_path, size_bytes, integrity_ok, gdrive_synced.
    """
    env_db = os.getenv("VAZUS_DB_PATH")
    if db_path is None:
        db_path = Path(env_db) if env_db else DB_PATH
    backup_dir = backup_dir or BACKUP_DIR

    if not db_path.exists():
        logger.error("Database not found: %s", db_path)
        return {"error": f"Database not found: {db_path}", "success": False}

    # Create backup directory
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamped filename
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d_%H%M%S")
    backup_filename = f"vazus_{timestamp}.db"
    backup_path = backup_dir / backup_filename

    try:
        # Use SQLite online backup API (safe with WAL mode)
        source_conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=10.0)
        dest_conn = sqlite3.connect(str(backup_path))

        source_conn.backup(dest_conn, pages=256, sleep=0.01)

        dest_conn.close()
        source_conn.close()

        backup_size = backup_path.stat().st_size
        logger.info("Backup created: %s (%d bytes)", backup_path, backup_size)

    except Exception as e:
        logger.error("Backup failed: %s", e)
        return {"error": str(e), "success": False}

    # Verify integrity
    integrity_ok = True
    if verify:
        try:
            check_conn = sqlite3.connect(str(backup_path), timeout=5.0)
            result = check_conn.execute("PRAGMA integrity_check").fetchone()
            check_conn.close()
            integrity_ok = result and result[0] == "ok"
            if not integrity_ok:
                logger.warning("Integrity check FAILED for %s: %s", backup_path, result)
            else:
                logger.info("Integrity check PASSED for %s", backup_path)
        except Exception as e:
            logger.warning("Integrity check error: %s", e)
            integrity_ok = False

    # Rotate old backups (keep MAX_BACKUPS most recent)
    rotated = _rotate_backups(backup_dir, max_backups)

    # Backup memory markdown triad (STATE.md, USER.md, STUDY.md)
    _backup_memory_docs(backup_dir, timestamp, sync_gdrive)

    # Sync to Google Drive
    gdrive_synced = False
    if sync_gdrive:
        gdrive_synced = _sync_to_gdrive(backup_path, backup_filename)

    return {
        "success": True,
        "backup_path": str(backup_path),
        "size_bytes": backup_size,
        "integrity_ok": integrity_ok,
        "rotated_count": rotated,
        "gdrive_synced": gdrive_synced,
        "timestamp": now.isoformat(),
    }


def _backup_memory_docs(backup_dir: Path, timestamp: str, sync_gdrive: bool) -> None:
    """Copies STATE.md, USER.md, and STUDY.md to backup_dir and GDrive."""
    memory_dir = VAZUS_ROOT / "services" / "memory"
    docs = ["STATE.md", "USER.md", "STUDY.md"]
    for doc_name in docs:
        src = memory_dir / doc_name
        if not src.exists():
            continue
        try:
            dest = backup_dir / f"{src.stem}_{timestamp}{src.suffix}"
            shutil.copy2(str(src), str(dest))
            # Also keep latest un-timestamped copy
            shutil.copy2(str(src), str(backup_dir / doc_name))
            if sync_gdrive and GDRIVE_BACKUP_DIR.parent.exists():
                GDRIVE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(GDRIVE_BACKUP_DIR / f"{src.stem}_{timestamp}{src.suffix}"))
                shutil.copy2(str(src), str(GDRIVE_BACKUP_DIR / doc_name))
        except Exception as exc:
            logger.debug("Failed backing up memory doc %s: %s", doc_name, exc)


def _rotate_backups(backup_dir: Path, max_backups: int) -> int:
    """Deletes oldest backups, keeping only max_backups most recent."""
    all_backups = sorted(
        [f for f in backup_dir.glob("vazus_*.db") if f.is_file()],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    to_delete = all_backups[max_backups:]
    for old_backup in to_delete:
        try:
            old_backup.unlink()
            logger.info("Rotated old backup: %s", old_backup.name)
        except Exception as e:
            logger.warning("Failed to delete old backup %s: %s", old_backup.name, e)

    return len(to_delete)


def _sync_to_gdrive(backup_path: Path, filename: str) -> bool:
    """Copies backup to Google Drive if mounted."""
    if not GDRIVE_BACKUP_DIR.parent.exists():
        logger.debug("Google Drive not mounted, skipping sync")
        return False

    try:
        GDRIVE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        dest = GDRIVE_BACKUP_DIR / filename
        shutil.copy2(str(backup_path), str(dest))
        logger.info("Synced backup to Google Drive: %s", dest)

        # Also rotate on GDrive
        _rotate_backups(GDRIVE_BACKUP_DIR, MAX_BACKUPS)
        return True
    except Exception as e:
        logger.warning("Google Drive sync failed: %s", e)
        return False


def get_backup_status(backup_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Returns current backup inventory."""
    backup_dir = backup_dir or BACKUP_DIR

    if not backup_dir.exists():
        return {"total_backups": 0, "latest": None, "total_size_mb": 0}

    backups = sorted(
        [f for f in backup_dir.glob("vazus_*.db") if f.is_file()],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    total_size = sum(f.stat().st_size for f in backups)

    return {
        "total_backups": len(backups),
        "latest": str(backups[0]) if backups else None,
        "latest_age_hours": round((datetime.now(timezone.utc).timestamp() - backups[0].stat().st_mtime) / 3600, 1)
        if backups
        else None,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "backup_dir": str(backup_dir),
    }


def main():
    """CLI entry point."""
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    verify = "--verify" in sys.argv
    result = run_backup(verify=verify or True)

    import json

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
