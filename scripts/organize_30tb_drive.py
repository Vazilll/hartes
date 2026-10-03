"""
C:\vazus\scripts\organize_30tb_drive.py — Safe, Non-Destructive 30 TB Google Drive Organizer.

Designed for Vazus OS / TARS MegaLab.
1. Quarantines loose root clutter into structured _ARCHIVE_2026/ folders.
2. Initializes high-throughput Tars_30TB_Vault/ directories for model checkpoints,
   sparse distributed memory (SDM), datasets, and flywheels.
3. Preserves all cloud links and IDs (zero data loss, zero destructive deletion).
4. Generates an undo-ready audit log.
"""

import os
import sys
import shutil
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("drive_organizer")

DRIVE_ROOT = Path("G:/My Drive")
VAULT_ROOT = DRIVE_ROOT / "Tars_30TB_Vault"
ARCHIVE_ROOT = DRIVE_ROOT / "_ARCHIVE_2026"

IGNORE_FILES = {"desktop.ini", "thumbs.db", ".ds_store"}

CATEGORIES = {
    "Colab_Notebooks": [".ipynb"],
    "Media_Unsorted": [".mov", ".mp4", ".avi", ".mkv", ".pptx", ".gslides"],
    "MIREA_Study_Docs": [
        "мирэа", "практика", "бланк", "тетрадь", "peresdach", "философия",
        "debts", "ит-инфраструктура", "вариант", "tina", "трекер", "долгов"
    ],
    "Reports_Briefings": [
        "hartes", "сводка", "briefing", "flywheel", "supergraph"
    ],
    "Misc_Loose_Docs": [
        "решение кейса", "новый документ", "новая таблица", "сканирование",
        "проект без названия", "структура отчета"
    ]
}

VAULT_DIRS = [
    "01_model_checkpoints",
    "02_sdm_sparse_memory",
    "03_datasets_cache",
    "04_flywheel_runs",
    "05_notebooklm_sources",
]


def classify_file(filename: str) -> Optional[str]:
    lower_name = filename.lower()
    if lower_name in IGNORE_FILES or lower_name.startswith("~"):
        return None

    ext = os.path.splitext(lower_name)[1]

    if ext == ".ipynb":
        return "Colab_Notebooks"
    if ext in [".mov", ".mp4", ".avi", ".mkv", ".pptx", ".gslides"]:
        return "Media_Unsorted"
    for kw in CATEGORIES["MIREA_Study_Docs"]:
        if kw in lower_name:
            return "MIREA_Study_Docs"
    for kw in CATEGORIES["Reports_Briefings"]:
        if kw in lower_name:
            return "Reports_Briefings"
    for kw in CATEGORIES["Misc_Loose_Docs"]:
        if kw in lower_name:
            return "Misc_Loose_Docs"
    return "Misc_Loose_Docs"


def run_organization(execute: bool = False):
    if not DRIVE_ROOT.exists():
        logger.error(f"Google Drive root not found at {DRIVE_ROOT}. Is Google Drive Desktop running?")
        sys.exit(1)

    logger.info(f"Target Google Drive root: {DRIVE_ROOT}")
    logger.info(f"Mode: {'EXECUTE (Live Migration)' if execute else 'DRY RUN (Preview Only)'}")

    # Step 1: Ensure Tars_30TB_Vault structure
    logger.info("--- Initializing Tars_30TB_Vault ---")
    for vdir in VAULT_DIRS:
        target_dir = VAULT_ROOT / vdir
        if execute:
            target_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Verified Vault directory: {target_dir}")
        else:
            logger.info(f"[Dry Run] Would create Vault dir: {target_dir}")

    # Step 2: Ensure Archive directories
    logger.info("--- Initializing _ARCHIVE_2026 ---")
    archive_subdirs = [
        "Colab_Notebooks",
        "Media_Unsorted",
        "MIREA_Study_Docs",
        "Reports_Briefings",
        "Misc_Loose_Docs"
    ]
    for adir in archive_subdirs:
        target_dir = ARCHIVE_ROOT / adir
        if execute:
            target_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Verified Archive directory: {target_dir}")
        else:
            logger.info(f"[Dry Run] Would create Archive dir: {target_dir}")

    # Step 3: Scan loose files in Drive root
    logger.info("--- Scanning Loose Files in Root ---")
    root_items = list(DRIVE_ROOT.iterdir())
    loose_files = [f for f in root_items if f.is_file()]

    planned_moves = []
    for f in loose_files:
        cat = classify_file(f.name)
        if not cat:
            continue
        dest_dir = ARCHIVE_ROOT / cat
        dest_path = dest_dir / f.name
        planned_moves.append({
            "source": str(f),
            "dest": str(dest_path),
            "category": cat,
            "size_bytes": f.stat().st_size if f.exists() else 0
        })

    logger.info(f"Found {len(planned_moves)} loose root files to organize.")

    for m in planned_moves:
        cat = m["category"]
        src_name = Path(m["source"]).name
        size_mb = m["size_bytes"] / (1024 * 1024)
        if execute:
            logger.info(f"Moving: {src_name} ({size_mb:.2f} MB) -> {cat}/")
            shutil.move(m["source"], m["dest"])
        else:
            logger.info(f"[Dry Run] Would move: {src_name} ({size_mb:.2f} MB) -> {cat}/")

    # Step 4: Audit log recording
    if execute:
        audit_file = ARCHIVE_ROOT / f"audit_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(audit_file, "w", encoding="utf-8") as out:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_moved": len(planned_moves),
                "moves": planned_moves
            }, out, indent=2, ensure_ascii=False)
        logger.info(f"Audit log successfully written to: {audit_file}")
    else:
        logger.info("[Dry Run Complete] Run with --execute to perform safe organization.")


if __name__ == "__main__":
    is_execute = "--execute" in sys.argv
    run_organization(execute=is_execute)
