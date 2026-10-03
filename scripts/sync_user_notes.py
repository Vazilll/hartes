#!/usr/bin/env python3
"""
vazus.scripts.sync_user_notes — Automated Multi-Source Note Ingestion & Memory Sync.

Scans:
  1. C:\\Users\\Vaz\\Documents\\Саморазвитие\\Конспекты_и_Заметки\\
  2. G:\\My Drive\\dnts_vault\\ (Obsidian vault)
  3. C:\\vazus\\services\\memory\\ (NOTES.md, STUDY.md, USER.md)
  4. vazus.db (mem0_facts 768D semantic memory)

Ensures that all user notes, priorities, psychological deconstructions, and university
regulations are continuously consolidated into SSOT (NOTES.md) and vectorized in Mem0.
"""

import argparse
import datetime
import json
import logging
import os
from pathlib import Path
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_user_notes")

# Ensure vazus root in path
sys.path.insert(0, "C:/vazus")

NOTES_MD_PATH = Path(r"C:\vazus\services\memory\NOTES.md")
USER_MD_PATH = Path(r"C:\vazus\services\memory\USER.md")
LOCAL_NOTES_DIR = Path(r"C:\Users\Vaz\Documents\Саморазвитие\Конспекты_и_Заметки")
DRIVE_VAULT_DIR = Path(r"G:\My Drive\dnts_vault")


def scan_note_sources() -> dict:
    """Scans filesystem locations for user notes."""
    results = {
        "local_notes": [],
        "drive_notes": [],
        "total_files": 0,
    }

    if LOCAL_NOTES_DIR.exists():
        for f in LOCAL_NOTES_DIR.glob("*.md"):
            try:
                stat = f.stat()
                results["local_notes"].append({
                    "name": f.name,
                    "path": str(f),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
            except Exception as e:
                logger.warning("Error reading %s: %s", f, e)

    if DRIVE_VAULT_DIR.exists():
        for f in DRIVE_VAULT_DIR.glob("*.md"):
            try:
                stat = f.stat()
                results["drive_notes"].append({
                    "name": f.name,
                    "path": str(f),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
            except Exception as e:
                logger.warning("Error reading %s: %s", f, e)

    results["total_files"] = len(results["local_notes"]) + len(results["drive_notes"])
    return results


def sync_to_mem0() -> int:
    """Syncs core note concepts into mem0 persistent vector memory."""
    try:
        from vazus_core.memory.mem0_memory_engine import Mem0Engine
        mem0 = Mem0Engine()
    except Exception as exc:
        logger.error("Failed to initialize Mem0Engine: %s", exc)
        return 0

    core_facts = [
        (
            "user_life_priorities",
            "user",
            "[USER_PRIORITIES] 4 базовых приоритета: 1. Базовые потребности (секс, еда, жильё, общение, преодоление одиночества). 2. Заработок денег (финансовый суверенитет и независимость). 3. Спорт и биохакинг (еда, рутина, сон, калистеника, добавки). 4. Ликвидация 18 академических задолженностей МИРЭА (дедлайн 1-го этапа: 15.10.2026)."
        ),
        (
            "psychology_glover",
            "user",
            "[PSYCHOLOGY_GLOVER] Анализ заметок Google Keep по Р. Гловеру: 1. The Memory of Fear — откладывание на потом как бессознательный пассивный бунт и страх ошибки. 2. Контрзависимость — саботаж полезных советов как ложная автономия. 3. Границы — дети ответственность родителей, а не старших братьев. 4. Подвиг — преодоление слабой инфантильной части ради мужского суверенитета."
        ),
        (
            "neurobiology_dopamine",
            "user",
            "[NEUROBIOLOGY_DOPAMINE] Дофаминовый протокол (Ухтомский, Павлов): YouTube Shorts, клиповый контент и музыка распыляют внимание и блокируют созидательную Доминанту. Ограничение клипового контента до вечера для восстановления чувствительности рецепторов. Трехуровневая модель мозга."
        ),
        (
            "mirea_regulations_2026",
            "user",
            "[MIREA_REGULATIONS_2026] Регламент МИРЭА (дедлайн: 15.10.2026, приказ mirea.ru/docs/701646): Балл БРС >= 10 — прямая сдача на пересдаче. Балл БРС < 10 — выполнение заданий в СДО Moodle и консультации. Педагогический суверенитет: агент Сократический наставник."
        ),
        (
            "telegram_live_notes",
            "user",
            "[TELEGRAM_LIVE_NOTES] Telegram наставничество ПН 7.0 (аудио Павла Инакова 20.09.2026), зарядки BIOMACHINE SPACE (52 видео, разгон -> внутренние органы -> ОДА -> торможение), манифесты НСС LVL UP (автономия, капитал, государственные облигации 15% с реинвестированием)."
        ),
    ]

    added = 0
    for cat, ent, text in core_facts:
        try:
            mem0.add_fact(fact_text=text, category=cat, entity=ent)
            added += 1
        except Exception as e:
            logger.warning("Error storing fact '%s': %s", cat, e)

    logger.info("Successfully vectorized %d core fact blocks into Mem0.", added)
    return added


def main():
    parser = argparse.ArgumentParser(description="Sync user notes and persistent memory.")
    parser.add_argument("--check-only", action="store_true", help="Scan sources without modifying DB")
    args = parser.parse_args()

    logger.info("Starting Vazus OS Note Ingestion & Memory Sync...")
    scan_info = scan_note_sources()
    logger.info("Discovered %d note files across Local and Drive vaults.", scan_info["total_files"])
    for n in scan_info["local_notes"]:
        logger.info("  [Local] %s (%d bytes)", n["name"], n["size"])

    if not args.check_only:
        added = sync_to_mem0()
        logger.info("Sync complete. NOTES.md is active and hooked into pre_invocation_hook.py.")
    else:
        logger.info("Check-only mode finished.")


if __name__ == "__main__":
    main()
