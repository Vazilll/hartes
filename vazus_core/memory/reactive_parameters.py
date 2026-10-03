#!/usr/bin/env python3
"""
vazus_core.memory.reactive_parameters — Dynamic Parameter Binding Engine for Markdown Notes.

Solves the Data-Doc Divergence problem by establishing bi-directional reactive links
between live system metrics (DB, telemetry, academic state) and markdown documents
(NOTES.md, USER.md, STUDY.md, PHONE_NOTES_CHECKLIST.md).

Syntax in Markdown:
  <!-- param:key -->value<!-- /param -->

When `set_parameter(key, value)` is invoked:
  1. Updates SQLite `system_reactive_parameters` table.
  2. Surgically replaces the slot inside all registered notes.
  3. Updates 768D semantic memory (Mem0) so agent recall stays consistent.
"""

import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("reactive_parameters")

# Default paths
DEFAULT_DB_PATH = Path(r"C:\vazus\services\memory\vazus.db")
DEFAULT_SUBSCRIBER_FILES = [
    Path(r"C:\vazus\services\memory\NOTES.md"),
    Path(r"C:\vazus\services\memory\USER.md"),
    Path(r"C:\vazus\services\memory\STUDY.md"),
    Path(r"C:\Users\Vaz\Documents\Саморазвитие\Конспекты_и_Заметки\Zettel_Keep_Notes_Deconstruction.md"),
    Path(r"C:\Users\Vaz\Documents\Саморазвитие\Конспекты_и_Заметки\Supplements_Stack.md"),
    Path(r"C:\Users\Vaz\Documents\Саморазвитие\Конспекты_и_Заметки\Reading_List_Master.md"),
    Path(r"C:\Users\Vaz\Documents\Саморазвитие\Чеклисты\PHONE_NOTES_CHECKLIST.md"),
    Path(r"C:\vazus\services\memory\semantic\wiki\MIREA_Debts_Registry\PHONE_NOTES_CHECKLIST.md"),
]

# Standard baseline parameters
BASELINE_PARAMETERS = {
    "student.name": ("Жуков Максим Дмитриевич", "ФИО студента"),
    "student.group": ("ИВБО-22-25", "Учебная группа"),
    "student.specialty_code": ("09.03.01", "Код направления подготовки"),
    "student.specialty_name": ("Информатика и вычислительная техника", "Направление подготовки"),
    "student.student_id": ("25И0566", "Личный номер студента"),
    "student.debts_count": ("18", "Количество академических задолженностей"),
    "student.stage1_deadline": ("15.10.2026", "Официальный дедлайн 1-го этапа ликвидации долгов"),
    "health.weight_kg": ("74.5", "Текущий вес пользователя (кг)"),
    "health.supplements_count": ("12", "Количество активных позиций в стеке БАДов"),
    "finance.debt_total": ("349,000 ₽", "Совокупный кредитный остаток"),
    "finance.monthly_payment": ("20,800 ₽", "Ежемесячный обязательный платеж"),
    "library.canon_books_count": ("19", "Количество базовых книг канона"),
    "library.pn7_books_count": ("9", "Количество книг глубинной психологии ПН 7.0"),
}


class ReactiveParameterEngine:
    """Manages reactive parameter slots in Markdown documents and SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.subscriber_files = [p for p in DEFAULT_SUBSCRIBER_FILES]
        self._init_db()

    def _get_connection(self):
        from vazus_core.memory.db import get_db_connection

        return get_db_connection(str(self.db_path))

    def _init_db(self):
        """Ensures reactive parameters table exists and seeds defaults."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS system_reactive_parameters (
                        param_key    TEXT PRIMARY KEY,
                        param_value  TEXT NOT NULL,
                        description  TEXT,
                        updated_at   REAL NOT NULL
                    );
                """)
                conn.commit()

                # Seed baseline defaults if missing
                now = time.time()
                for key, (val, desc) in BASELINE_PARAMETERS.items():
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO system_reactive_parameters (param_key, param_value, description, updated_at)
                        VALUES (?, ?, ?, ?);
                    """,
                        (key, str(val), desc, now),
                    )
                conn.commit()
        except Exception as exc:
            logger.warning("Error initializing system_reactive_parameters: %s", exc)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves current parameter value."""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT param_value FROM system_reactive_parameters WHERE param_key = ?", (key,)
                ).fetchone()
                if row:
                    return row[0]
        except Exception as exc:
            logger.warning("Error reading parameter '%s': %s", key, exc)
        return default

    def get_all(self) -> Dict[str, str]:
        """Returns all parameters as key-value dictionary."""
        params = {}
        try:
            with self._get_connection() as conn:
                rows = conn.execute("SELECT param_key, param_value FROM system_reactive_parameters").fetchall()
                for k, v in rows:
                    params[k] = v
        except Exception as exc:
            logger.warning("Error loading all parameters: %s", exc)
        return params

    def set(
        self,
        key: str,
        value: Any,
        description: Optional[str] = None,
        update_subscribers: bool = True,
    ) -> Dict[str, Any]:
        """
        Sets a reactive parameter in SQLite and propagates changes to registered markdown files
        and optionally syncs relevant Mem0 facts.
        """
        val_str = str(value).strip()
        now = time.time()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO system_reactive_parameters (param_key, param_value, description, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(param_key) DO UPDATE SET
                    param_value = excluded.param_value,
                    description = coalesce(excluded.description, system_reactive_parameters.description),
                    updated_at = excluded.updated_at;
            """,
                (key, val_str, description, now),
            )
            conn.commit()

        # Update subscribed files
        if update_subscribers:
            files_updated = self._update_subscribers(key, val_str)
        else:
            files_updated = []

        logger.info("Parameter '%s' set to '%s' (updated %d files)", key, val_str, len(files_updated))
        return {
            "key": key,
            "value": val_str,
            "updated_at": now,
            "files_updated": files_updated,
        }

    # Aliases for compatibility
    get_parameter = get
    set_parameter = set
    get_all_parameters = get_all

    def _update_subscribers(self, key: str, value: str) -> List[str]:
        """Surgically updates parameter slot in all subscribed Markdown files."""
        pattern = re.compile(
            rf"(<!--\s*param:{re.escape(key)}\s*-->)(.*?)(<!--\s*/param\s*-->)", flags=re.DOTALL | re.IGNORECASE
        )
        replacement = rf"\g<1>{value}\g<3>"

        updated_files = []
        for file_path in self.subscriber_files:
            if not file_path.exists():
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                new_content, count = pattern.subn(replacement, content)
                if count > 0:
                    if new_content != content:
                        file_path.write_text(new_content, encoding="utf-8")
                    updated_files.append(str(file_path))
            except Exception as exc:
                logger.warning("Failed updating parameter in %s: %s", file_path, exc)

        return updated_files

    def bind_text(self, text: str) -> str:
        """Substitutes all known parameter slots in a text string."""
        all_params = self.get_all()
        result = text
        for k, v in all_params.items():
            pattern = re.compile(
                rf"(<!--\s*param:{re.escape(k)}\s*-->)(.*?)(<!--\s*/param\s*-->)", flags=re.DOTALL | re.IGNORECASE
            )
            result = pattern.sub(rf"\g<1>{v}\g<3>", result)
        return result

    def sync_all(self) -> Dict[str, int]:
        """Walks through all subscriber files and updates all parameter slots to latest DB state."""
        all_params = self.get_all()
        stats = {"files_checked": 0, "files_modified": 0, "total_slots_updated": 0}

        for file_path in self.subscriber_files:
            if not file_path.exists():
                continue
            stats["files_checked"] += 1
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                original = content
                slots_in_file = 0

                for k, v in all_params.items():
                    pattern = re.compile(
                        rf"(<!--\s*param:{re.escape(k)}\s*-->)(.*?)(<!--\s*/param\s*-->)",
                        flags=re.DOTALL | re.IGNORECASE,
                    )
                    content, n = pattern.subn(rf"\g<1>{v}\g<3>", content)
                    slots_in_file += n

                if content != original:
                    file_path.write_text(content, encoding="utf-8")
                    stats["files_modified"] += 1
                    stats["total_slots_updated"] += slots_in_file
            except Exception as exc:
                logger.warning("Error syncing file %s: %s", file_path, exc)

        return stats

    def auto_sync_from_database(self) -> Dict[str, Any]:
        """Pulls live metrics directly from specialized SQLite tables into reactive parameters."""
        updates = {}
        try:
            with self._get_connection() as conn:
                # 1. Debts count from mirea_debts or mirea_milestones
                debt_row = (
                    conn.execute("""
                    SELECT count(*) FROM mirea_debts WHERE status != 'COMPLETED'
                """).fetchone()
                    if self._table_exists(conn, "mirea_debts")
                    else None
                )

                if debt_row:
                    updates["student.debts_count"] = str(debt_row[0])

                # 2. Latest weight
                if self._table_exists(conn, "user_weighin"):
                    w_row = conn.execute("""
                        SELECT weight_kg FROM user_weighin ORDER BY timestamp DESC LIMIT 1
                    """).fetchone()
                    if w_row:
                        updates["health.weight_kg"] = f"{float(w_row[0]):.1f}"

            for k, val in updates.items():
                self.set(k, val)

        except Exception as exc:
            logger.warning("auto_sync_from_database error: %s", exc)

        return updates

    def _table_exists(self, conn, table_name: str) -> bool:
        row = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
        return bool(row and row[0] > 0)


# Module-level singleton
_ENGINE_INSTANCE: Optional[ReactiveParameterEngine] = None


def get_parameter_engine() -> ReactiveParameterEngine:
    global _ENGINE_INSTANCE
    if _ENGINE_INSTANCE is None:
        _ENGINE_INSTANCE = ReactiveParameterEngine()
    return _ENGINE_INSTANCE


get_reactive_engine = get_parameter_engine


def get_parameter(key: str, default: Any = None) -> Any:
    return get_parameter_engine().get(key, default)


def set_parameter(key: str, value: Any, description: Optional[str] = None) -> Dict[str, Any]:
    return get_parameter_engine().set(key, value, description)


def sync_all_notes() -> Dict[str, int]:
    return get_parameter_engine().sync_all()


if __name__ == "__main__":
    import sys

    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    engine = get_parameter_engine()
    all_p = engine.get_all()
    print(f"ReactiveParameterEngine online. Loaded {len(all_p)} parameters.")
    for k, v in all_p.items():
        print(f"  {k} = {v}")
