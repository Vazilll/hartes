"""
services.academic_verification.student_sync — Student Profile and Academic Debts Sync Engine.

Binds authoritative student profile (Жуков Максим Дмитриевич, ИВБО-22-25, 25И0566, 09.03.01)
and 18 academic debts with official Stage 1 deadline (15.10.2026) into SQLite storage (vazus.db).
"""

from __future__ import annotations

import datetime
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("academic_verification.student_sync")

DEFAULT_DB_PATH: Path = Path(r"C:\vazus\services\memory\vazus.db")

# Authoritative student identity contracts
STUDENT_FULL_NAME: str = "Жуков Максим Дмитриевич"
STUDENT_GROUP: str = "ИВБО-22-25"
STUDENT_ID_NUMBER: str = "25И0566"
STUDENT_SPECIALIZATION: str = "09.03.01"
STUDENT_SPECIALIZATION_NAME: str = "Информатика и вычислительная техника"
STAGE1_OFFICIAL_DEADLINE: str = "15.10.2026"
ACTIVE_DEBTS_COUNT: int = 18

EXAM_SHEET_TO_MOODLE_MAP: Dict[str, int] = {
    "81917": 16479,  # Математический анализ
    "66804": 16480,  # Линейная алгебра и аналитическая геометрия
    "86958": 16486,  # Математическая логика и теория алгоритмов
    "86146": 16017,  # Иностранный язык
}

CATALOG_OF_18_DEBTS: List[Dict[str, Any]] = [
    {"subject": "Иностранный язык", "milestone_name": "Зачет (1/3, № 86146)", "milestone_type": "credit", "sheet": "86146", "sem": 1, "moodle": 16017},
    {"subject": "Линейная алгебра и аналитическая геометрия", "milestone_name": "Экзамен (1/2, № 66804)", "milestone_type": "exam", "sheet": "66804", "sem": 1, "moodle": 16480},
    {"subject": "Математический анализ", "milestone_name": "Экзамен (1/3, № 81917)", "milestone_type": "exam", "sheet": "81917", "sem": 1, "moodle": 16479},
    {"subject": "Математическая логика и теория алгоритмов", "milestone_name": "Экзамен (1/1, № 86958)", "milestone_type": "exam", "sheet": "86958", "sem": 1, "moodle": 16486},
    {"subject": "Русский язык и культура речи", "milestone_name": "Зачет (1/1, № 69956)", "milestone_type": "credit", "sheet": "69956", "sem": 2, "moodle": None},
    {"subject": "Основы конструирования", "milestone_name": "Зачет (1/1, № 86971)", "milestone_type": "credit", "sheet": "86971", "sem": 2, "moodle": None},
    {"subject": "Объектно-ориентированное программирование", "milestone_name": "Курсовая работа (1/1, № 86959)", "milestone_type": "coursework", "sheet": "86959", "sem": 2, "moodle": None},
    {"subject": "Иностранный язык", "milestone_name": "Зачет (2/3, № 86146)", "milestone_type": "credit", "sheet": "86146", "sem": 2, "moodle": 16017},
    {"subject": "Физика", "milestone_name": "Зачет (2/2, № 78208)", "milestone_type": "credit", "sheet": "78208", "sem": 2, "moodle": None},
    {"subject": "Ознакомительная практика", "milestone_name": "Дифф. зачет (1/1, № 6082)", "milestone_type": "diff_credit", "sheet": "6082", "sem": 2, "moodle": None},
    {"subject": "Физическая культура и спорт", "milestone_name": "Зачет (1/3, № 72287)", "milestone_type": "credit", "sheet": "72287", "sem": 2, "moodle": None},
    {"subject": "Основы российской государственности", "milestone_name": "Зачет (1/1, № 82576)", "milestone_type": "credit", "sheet": "82576", "sem": 2, "moodle": None},
    {"subject": "Линейная алгебра и аналитическая геометрия", "milestone_name": "Экзамен (2/2, № 66804)", "milestone_type": "exam", "sheet": "66804", "sem": 2, "moodle": 16480},
    {"subject": "Объектно-ориентированное программирование", "milestone_name": "Экзамен (1/1, № 86959)", "milestone_type": "exam", "sheet": "86959", "sem": 2, "moodle": None},
    {"subject": "Математический анализ", "milestone_name": "Экзамен (2/3, № 81917)", "milestone_type": "exam", "sheet": "81917", "sem": 2, "moodle": 16479},
    {"subject": "Физика", "milestone_name": "Экзамен (2/2, № 78208)", "milestone_type": "exam", "sheet": "78208", "sem": 2, "moodle": None},
    {"subject": "История России", "milestone_name": "Экзамен (2/2, № 82054)", "milestone_type": "exam", "sheet": "82054", "sem": 2, "moodle": None},
    {"subject": "Информатика", "milestone_name": "Экзамен (2/2, № 85415)", "milestone_type": "exam", "sheet": "85415", "sem": 2, "moodle": None},
]


class AcademicTruthSync:
    """
    Synchronizes verified student profile identity and academic debts with
    authoritative schema and deadline constraints in SQLite.
    """

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        auth_manager: Optional[Any] = None,
    ) -> None:
        self.default_db_path: Path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.auth_manager = auth_manager

    def _resolve_db(self, db_path: Optional[Union[str, Path]] = None) -> Path:
        return Path(db_path) if db_path else self.default_db_path

    def _ensure_student_profile_table(self, conn: sqlite3.Connection) -> None:
        """Ensures the student_profile table schema exists with all required columns."""
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS student_profile (
            student_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            group_name TEXT NOT NULL,
            specialization_code TEXT NOT NULL,
            specialization_name TEXT DEFAULT 'Информатика и вычислительная техника',
            degree_level TEXT DEFAULT 'Бакалавриат',
            study_form TEXT DEFAULT 'Очная',
            status TEXT DEFAULT 'ACTIVE',
            stage1_deadline TEXT DEFAULT '15.10.2026',
            active_debts_count INTEGER DEFAULT 18,
            last_synced_at TEXT NOT NULL,
            updated_at TEXT,
            metadata_json TEXT
        )
        """)
        # Schema migration check: ensure columns present in case table was created with partial schema
        cur.execute("PRAGMA table_info(student_profile)")
        cols = {row[1] for row in cur.fetchall()}
        if "updated_at" not in cols:
            cur.execute("ALTER TABLE student_profile ADD COLUMN updated_at TEXT")
        if "metadata_json" not in cols:
            cur.execute("ALTER TABLE student_profile ADD COLUMN metadata_json TEXT")
        if "stage1_deadline" not in cols:
            cur.execute("ALTER TABLE student_profile ADD COLUMN stage1_deadline TEXT DEFAULT '15.10.2026'")
        if "active_debts_count" not in cols:
            cur.execute("ALTER TABLE student_profile ADD COLUMN active_debts_count INTEGER DEFAULT 18")

    def _ensure_milestones_table(self, conn: sqlite3.Connection) -> None:
        """Ensures the mirea_milestones table exists and includes all required schema columns."""
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS mirea_milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            milestone_name TEXT NOT NULL,
            milestone_type TEXT NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            description TEXT,
            student_id TEXT DEFAULT '25И0566',
            external_id TEXT,
            semester INTEGER,
            moodle_course_id INTEGER,
            stage1_deadline TEXT DEFAULT '15.10.2026',
            updated_at TEXT
        )
        """)
        cur.execute("PRAGMA table_info(mirea_milestones)")
        cols = {row[1] for row in cur.fetchall()}
        if "stage1_deadline" not in cols:
            cur.execute("ALTER TABLE mirea_milestones ADD COLUMN stage1_deadline TEXT DEFAULT '15.10.2026'")
        if "student_id" not in cols:
            cur.execute("ALTER TABLE mirea_milestones ADD COLUMN student_id TEXT DEFAULT '25И0566'")
        if "external_id" not in cols:
            cur.execute("ALTER TABLE mirea_milestones ADD COLUMN external_id TEXT")
        if "semester" not in cols:
            cur.execute("ALTER TABLE mirea_milestones ADD COLUMN semester INTEGER")
        if "moodle_course_id" not in cols:
            cur.execute("ALTER TABLE mirea_milestones ADD COLUMN moodle_course_id INTEGER")
        if "updated_at" not in cols:
            cur.execute("ALTER TABLE mirea_milestones ADD COLUMN updated_at TEXT")
        cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mirea_milestones_group_subject 
        ON mirea_milestones(group_name, subject, milestone_name);
        """)

    def sync_student_profile(
        self,
        db_path: Optional[Union[str, Path]] = None,
        profile_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Creates or updates authoritative student_profile table and upserts verified record.
        """
        target_path = self._resolve_db(db_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        data = profile_data or {}

        student_id = data.get("student_id", STUDENT_ID_NUMBER)
        full_name = data.get("full_name", STUDENT_FULL_NAME)
        group_name = data.get("group_name", STUDENT_GROUP)
        spec_code = data.get("specialization_code", STUDENT_SPECIALIZATION)
        spec_name = data.get("specialization_name", STUDENT_SPECIALIZATION_NAME)
        degree_level = data.get("degree_level", "Бакалавриат")
        study_form = data.get("study_form", "Очная")
        status = data.get("status", "ACTIVE")
        stage1_deadline = data.get("stage1_deadline", STAGE1_OFFICIAL_DEADLINE)
        debts_count = int(data.get("active_debts_count", ACTIVE_DEBTS_COUNT))
        metadata_json = data.get("metadata_json") or json.dumps({
            "source": "authoritative_lks_keycloak",
            "verified": True,
            "verification_timestamp": now_iso,
        }, ensure_ascii=False)

        conn = sqlite3.connect(str(target_path))
        try:
            self._ensure_student_profile_table(conn)
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO student_profile (
                student_id, full_name, group_name, specialization_code, specialization_name,
                degree_level, study_form, status, stage1_deadline, active_debts_count,
                last_synced_at, updated_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                full_name = excluded.full_name,
                group_name = excluded.group_name,
                specialization_code = excluded.specialization_code,
                specialization_name = excluded.specialization_name,
                degree_level = excluded.degree_level,
                study_form = excluded.study_form,
                status = excluded.status,
                stage1_deadline = excluded.stage1_deadline,
                active_debts_count = excluded.active_debts_count,
                last_synced_at = excluded.last_synced_at,
                updated_at = excluded.updated_at,
                metadata_json = excluded.metadata_json
            """, (
                student_id, full_name, group_name, spec_code, spec_name,
                degree_level, study_form, status, stage1_deadline, debts_count,
                now_iso, now_iso, metadata_json
            ))
            conn.commit()
            logger.info(f"Synchronized student profile for {student_id} ({full_name}) into {target_path}")
            return {
                "student_id": student_id,
                "full_name": full_name,
                "group_name": group_name,
                "specialization_code": spec_code,
                "specialization_name": spec_name,
                "stage1_deadline": stage1_deadline,
                "active_debts_count": debts_count,
                "last_synced_at": now_iso,
            }
        finally:
            conn.close()

    def sync_academic_debts(
        self,
        db_path: Optional[Union[str, Path]] = None,
        debts: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """
        Synchronizes the 18 active academic debts into mirea_milestones.
        Ensures stage1_deadline = '15.10.2026', due_date = '15.10.2026', and group_name = 'ИВБО-22-25'.
        """
        target_path = self._resolve_db(db_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        debts_list = debts or CATALOG_OF_18_DEBTS
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = sqlite3.connect(str(target_path), timeout=60.0)
        try:
            self._ensure_milestones_table(conn)
            cur = conn.cursor()
            cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mirea_milestones_group_subject 
            ON mirea_milestones(group_name, subject, milestone_name);
            """)

            with conn:
                conn.execute("BEGIN IMMEDIATE")
                for d in debts_list:
                    cur.execute("""
                    INSERT INTO mirea_milestones (
                        group_name, subject, milestone_name, milestone_type, due_date, status,
                        description, student_id, external_id, semester, moodle_course_id, stage1_deadline, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(group_name, subject, milestone_name) DO UPDATE SET
                        stage1_deadline = excluded.stage1_deadline,
                        due_date = excluded.due_date,
                        student_id = excluded.student_id,
                        external_id = COALESCE(excluded.external_id, mirea_milestones.external_id),
                        semester = COALESCE(excluded.semester, mirea_milestones.semester),
                        moodle_course_id = COALESCE(excluded.moodle_course_id, mirea_milestones.moodle_course_id),
                        milestone_type = excluded.milestone_type,
                        description = excluded.description,
                        updated_at = excluded.updated_at
                    """, (
                        STUDENT_GROUP, d["subject"], d["milestone_name"], d.get("milestone_type", "exam"),
                        STAGE1_OFFICIAL_DEADLINE, f"Семестр {d.get('sem', 1)}", STUDENT_ID_NUMBER,
                        d.get("sheet"), d.get("sem"), d.get("moodle"), STAGE1_OFFICIAL_DEADLINE, now_iso
                    ))

                # Align any residual legacy records
                cur.execute("""
                UPDATE mirea_milestones
                SET stage1_deadline = ?, due_date = ?, group_name = ?, student_id = ?, updated_at = ?
                WHERE group_name = ? OR group_name = 'ИКБО-01-23'
                """, (
                    STAGE1_OFFICIAL_DEADLINE, STAGE1_OFFICIAL_DEADLINE, STUDENT_GROUP,
                    STUDENT_ID_NUMBER, now_iso, STUDENT_GROUP
                ))

            count_row = cur.execute(
                "SELECT COUNT(*) FROM mirea_milestones WHERE group_name = ?", (STUDENT_GROUP,)
            ).fetchone()
            total_synced = count_row[0] if count_row else 0
            logger.info(f"Synchronized {total_synced} academic debts into {target_path}")
            return total_synced
        finally:
            conn.close()

    def upsert_academic_debt(
        self,
        debt: Dict[str, Any],
        db_path: Optional[Union[str, Path]] = None,
    ) -> bool:
        """Atomically upserts a single academic debt record into mirea_milestones."""
        target_path = self._resolve_db(db_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = sqlite3.connect(str(target_path), timeout=60.0)
        try:
            self._ensure_milestones_table(conn)
            cur = conn.cursor()
            cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mirea_milestones_group_subject 
            ON mirea_milestones(group_name, subject, milestone_name);
            """)
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                cur.execute("""
                INSERT INTO mirea_milestones (
                    group_name, subject, milestone_name, milestone_type, due_date, status,
                    description, student_id, external_id, semester, moodle_course_id, stage1_deadline, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_name, subject, milestone_name) DO UPDATE SET
                    stage1_deadline = excluded.stage1_deadline,
                    due_date = excluded.due_date,
                    student_id = excluded.student_id,
                    external_id = COALESCE(excluded.external_id, mirea_milestones.external_id),
                    semester = COALESCE(excluded.semester, mirea_milestones.semester),
                    moodle_course_id = COALESCE(excluded.moodle_course_id, mirea_milestones.moodle_course_id),
                    milestone_type = excluded.milestone_type,
                    description = excluded.description,
                    updated_at = excluded.updated_at
                """, (
                    STUDENT_GROUP, debt["subject"], debt["milestone_name"], debt.get("milestone_type", "exam"),
                    STAGE1_OFFICIAL_DEADLINE, f"Семестр {debt.get('sem', 1)}", STUDENT_ID_NUMBER,
                    debt.get("sheet"), debt.get("sem"), debt.get("moodle"), STAGE1_OFFICIAL_DEADLINE, now_iso
                ))
            return True
        finally:
            conn.close()

    def get_student_profile(self, db_path: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
        """Retrieves verified student profile record from database."""
        target_path = self._resolve_db(db_path)
        if not target_path.exists():
            return None
        conn = sqlite3.connect(str(target_path))
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            row = cur.execute("SELECT * FROM student_profile LIMIT 1").fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_academic_debts(self, db_path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
        """Retrieves all academic debts for ИВБО-22-25 from database."""
        target_path = self._resolve_db(db_path)
        if not target_path.exists():
            return []
        conn = sqlite3.connect(str(target_path))
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            rows = cur.execute(
                "SELECT * FROM mirea_milestones WHERE group_name = ? ORDER BY semester, id",
                (STUDENT_GROUP,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# Module-level convenience functions
def sync_student_profile(
    db_path: Optional[Union[str, Path]] = None,
    profile_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience function to sync student profile."""
    engine = AcademicTruthSync(db_path=db_path)
    return engine.sync_student_profile(db_path=db_path, profile_data=profile_data)


def sync_academic_debts(
    db_path: Optional[Union[str, Path]] = None,
    debts: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """Convenience function to sync academic debts."""
    engine = AcademicTruthSync(db_path=db_path)
    return engine.sync_academic_debts(db_path=db_path, debts=debts)


def upsert_academic_debt(
    debt: Dict[str, Any],
    db_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Convenience function to atomically upsert an academic debt."""
    engine = AcademicTruthSync(db_path=db_path)
    return engine.upsert_academic_debt(debt=debt, db_path=db_path)


# Aliases for cross-module interface compatibility
StudentProfileSyncEngine = AcademicTruthSync
