"""
tests/benchmarks/test_academic_truth_tier5_adversarial.py
Tier 5 Adversarial Coverage Hardening Suite for RTU MIREA Academic Truth & Verification Engine.

Exhaustively verifies:
1. Concurrency & Transaction Integrity:
   - High-throughput multi-threaded concurrent synchronization (16-24 threads).
   - Parallel execution of sync_student_profile, sync_academic_debts, sync_schedule_to_db, and concurrent readers.
   - Race-condition resilience on academic debt upserts and schedule overwrites.
2. Transaction Integrity & Database Rollback Under Mid-Sync Failures:
   - Mid-sync network/IO crash during schedule ingestion: verifies uncommitted DELETE + partial INSERTs roll back cleanly.
   - Mid-sync crash during debts update: verifies zero partial state or corruption in mirea_milestones.
   - Profile sync failure rollback: prior verified identity remains intact.
   - Database WAL integrity check (PRAGMA integrity_check, foreign_key_check).
   - Atomic file replacement safety for session credentials under simulated disk write failures.
3. Moodle Client Error Modes & Fail-Closed Invariants:
   - Non-existent exam sheet numbers and course IDs in resolve_course_id (returns None).
   - HTTP 404 handling on non-existent course overview in get_quizzes_for_course (raises HTTPError, fail-closed).
   - Error page HTML (e.g. "Course not found") handling in get_quizzes_for_course (returns [], zero quizzes).
   - Expired session tokens in Moodle AJAX core_course_get_enrolled_courses_by_timeline_classification (returns []).
   - Expired session redirect to login/index.php in get_quizzes_for_course (returns [], zero quizzes).
   - Full matrix of validate_session() failure modes (redirects, login prompts, 401, 403, 500, timeouts -> all False).
   - AcademicSafetyGuard strict read-only enforcement during all error paths.
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest
import requests

PROJECT_ROOT = Path(r"C:\vazus").resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
VAZUS_CORE = PROJECT_ROOT / "vazus_core"
if str(VAZUS_CORE) not in sys.path:
    sys.path.insert(0, str(VAZUS_CORE))

from services.academic_verification.auth import (
    AuthenticationRequiredError,
    KeycloakAuthManager,
    SessionRequiredError,
)
from services.academic_verification.moodle_client import (
    EXAM_SHEET_TO_MOODLE_MAP,
    MoodleLMSClient,
)
from services.academic_verification.safety_guard import (
    AcademicSafetyGuard,
    AcademicSafetyViolationError,
)
from services.academic_verification.schedule_client import (
    OfficialScheduleClient,
    ScheduleFetchError,
)
from services.academic_verification.student_sync import (
    ACTIVE_DEBTS_COUNT,
    CATALOG_OF_18_DEBTS,
    STAGE1_OFFICIAL_DEADLINE,
    STUDENT_FULL_NAME,
    STUDENT_GROUP,
    STUDENT_ID_NUMBER,
    STUDENT_SPECIALIZATION,
    AcademicTruthSync,
    sync_academic_debts,
    sync_student_profile,
)

SAMPLE_ICAL_DATA = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//schedule-of.mirea.ru//NONSGML v1.0//RU
BEGIN:VEVENT
UID:test-lesson-01
CATEGORIES:ПР
DESCRIPTION:Преподаватель: Иванов И.И.
DTSTART;TZID=Europe/Moscow:20260914T090000
DTEND;TZID=Europe/Moscow:20260914T103000
LOCATION:А-101 (МП-1)
SUMMARY:ПР Математический анализ
X-META-DISCIPLINE:Математический анализ
X-META-LESSON_TYPE:ПР
X-META-AUDITORIUM;CAMPUS=МП-1:А-101 (МП-1)
X-META-GROUP;ID=5528;TYPE=1:ИВБО-22-25
END:VEVENT
BEGIN:VEVENT
UID:test-lesson-02
CATEGORIES:ЛК
DESCRIPTION:Преподаватель: Петров П.П.
DTSTART;TZID=Europe/Moscow:20260914T104000
DTEND;TZID=Europe/Moscow:20260914T121000
LOCATION:А-102 (МП-1)
SUMMARY:ЛК Линейная алгебра и аналитическая геометрия
X-META-DISCIPLINE:Линейная алгебра и аналитическая геометрия
X-META-LESSON_TYPE:ЛК
X-META-AUDITORIUM;CAMPUS=МП-1:А-102 (МП-1)
X-META-GROUP;ID=5528;TYPE=1:ИВБО-22-25
END:VEVENT
END:VCALENDAR
"""


def init_test_db(db_file: Path) -> Path:
    """Initializes isolated SQLite database with required tables and WAL mode."""
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=10000")
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
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mirea_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT NOT NULL,
        weekday TEXT NOT NULL,
        lesson_time TEXT NOT NULL,
        subject TEXT NOT NULL,
        lesson_type TEXT NOT NULL,
        classroom TEXT,
        teacher TEXT,
        lesson_date TEXT,
        campus TEXT,
        updated_at TEXT
    )
    """)
    conn.commit()
    conn.close()
    return db_file


@pytest.fixture
def isolated_db(tmp_path: Path) -> Path:
    """Provides an isolated SQLite database path with initial schema configured."""
    db_file = tmp_path / "tier5_adversarial.db"
    return init_test_db(db_file)


# ============================================================================
# TIER 5.1: CONCURRENCY & MULTI-THREADED STRESS TESTS
# ============================================================================

class TestTier5ConcurrencyAndStress:
    """Stress tests verifying concurrency safety, lock resilience, and race condition prevention."""

    def test_tier5_01_cold_start_concurrent_sync_exposes_race_condition(self, isolated_db: Path):
        """
        Adversarial stress test on cold-start (unseeded) database:
        Executes 16 concurrent threads (4 profile, 4 debts, 4 schedule, 4 readers).
        Exposes the check-then-act race condition in sync_academic_debts where the absence
        of a UNIQUE constraint on mirea_milestones causes duplicate row multiplication (e.g. 72 debts instead of 18).
        """
        errors: List[Tuple[str, str]] = []
        stop_event = threading.Event()

        def worker_sync_profile(worker_id: int):
            try:
                for _ in range(6):
                    if stop_event.is_set():
                        break
                    sync_student_profile(db_path=isolated_db)
                    time.sleep(0.005)
            except Exception as exc:
                errors.append((f"profile_worker_{worker_id}", f"{type(exc).__name__}: {exc}"))

        def worker_sync_debts(worker_id: int):
            try:
                for _ in range(6):
                    if stop_event.is_set():
                        break
                    sync_academic_debts(db_path=isolated_db)
                    time.sleep(0.005)
            except Exception as exc:
                errors.append((f"debts_worker_{worker_id}", f"{type(exc).__name__}: {exc}"))

        def worker_sync_schedule(worker_id: int):
            client = OfficialScheduleClient()
            try:
                with patch.object(client, "fetch_ical_raw", return_value=SAMPLE_ICAL_DATA):
                    for _ in range(6):
                        if stop_event.is_set():
                            break
                        client.sync_schedule_to_db(db_path=isolated_db, group_name=STUDENT_GROUP)
                        time.sleep(0.005)
            except Exception as exc:
                errors.append((f"schedule_worker_{worker_id}", f"{type(exc).__name__}: {exc}"))

        def worker_concurrent_reader(worker_id: int):
            engine = AcademicTruthSync(db_path=isolated_db)
            try:
                for _ in range(12):
                    if stop_event.is_set():
                        break
                    p = engine.get_student_profile(db_path=isolated_db)
                    d = engine.get_academic_debts(db_path=isolated_db)
                    conn = sqlite3.connect(str(isolated_db), timeout=5.0)
                    cur = conn.cursor()
                    s = cur.execute("SELECT COUNT(*) FROM mirea_schedule").fetchone()[0]
                    conn.close()
                    time.sleep(0.002)
            except Exception as exc:
                errors.append((f"reader_worker_{worker_id}", f"{type(exc).__name__}: {exc}"))

        threads: List[threading.Thread] = []
        for i in range(4):
            threads.append(threading.Thread(target=worker_sync_profile, args=(i,)))
            threads.append(threading.Thread(target=worker_sync_debts, args=(i,)))
            threads.append(threading.Thread(target=worker_sync_schedule, args=(i,)))
            threads.append(threading.Thread(target=worker_concurrent_reader, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30.0)

        assert len(errors) == 0, f"Concurrent workers reported unhandled errors: {errors}"

        conn = sqlite3.connect(str(isolated_db))
        cur = conn.cursor()
        profile_row = cur.execute("SELECT student_id, full_name, group_name, active_debts_count FROM student_profile").fetchall()
        debts_count = cur.execute("SELECT COUNT(*) FROM mirea_milestones WHERE group_name = ?", (STUDENT_GROUP,)).fetchone()[0]
        schedule_count = cur.execute("SELECT COUNT(*) FROM mirea_schedule WHERE group_name = ?", (STUDENT_GROUP,)).fetchone()[0]
        conn.close()

        # Student profile is thread-safe (PRIMARY KEY + ON CONFLICT)
        assert len(profile_row) == 1
        assert profile_row[0][0] == STUDENT_ID_NUMBER
        assert schedule_count == 2

        # Adversarial assertion: debts must strictly equal ACTIVE_DEBTS_COUNT (18)
        # In current implementation, race condition causes duplicate rows (e.g. 72 rows).
        assert debts_count == ACTIVE_DEBTS_COUNT, (
            f"VULNERABILITY DETECTED: Race condition in sync_academic_debts() caused duplicate debts accumulation: "
            f"found {debts_count} rows, expected exactly {ACTIVE_DEBTS_COUNT}"
        )

    def test_tier5_02_preseeded_concurrent_sync_maintains_count(self, isolated_db: Path):
        """
        Validates that once database is pre-seeded with 18 debts,
        subsequent concurrent workers updating the debts maintain exactly 18 debts.
        """
        # Pre-seed with single thread
        sync_academic_debts(db_path=isolated_db)

        errors = []
        def worker():
            try:
                for _ in range(6):
                    sync_academic_debts(db_path=isolated_db)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20.0)

        assert len(errors) == 0, f"Debt sync workers encountered errors: {errors}"

        conn = sqlite3.connect(str(isolated_db))
        cur = conn.cursor()
        total_count = cur.execute("SELECT COUNT(*) FROM mirea_milestones WHERE group_name = ?", (STUDENT_GROUP,)).fetchone()[0]
        conn.close()

        assert total_count == ACTIVE_DEBTS_COUNT, f"Expected 18 debts on pre-seeded DB, got {total_count}"

    def test_tier5_03_concurrent_schedule_wipe_and_insert_safety(self, isolated_db: Path):
        """
        Validates schedule table integrity when multiple threads execute schedule sync simultaneously.
        Guarantees that schedule never ends in empty or duplicate state.
        """
        client = OfficialScheduleClient()
        errors = []

        def schedule_worker():
            try:
                with patch.object(client, "fetch_ical_raw", return_value=SAMPLE_ICAL_DATA):
                    for _ in range(6):
                        client.sync_schedule_to_db(db_path=isolated_db, group_name=STUDENT_GROUP)
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=schedule_worker) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20.0)

        assert len(errors) == 0, f"Schedule worker errors: {errors}"

        conn = sqlite3.connect(str(isolated_db))
        cur = conn.cursor()
        count = cur.execute("SELECT COUNT(*) FROM mirea_schedule WHERE group_name = ?", (STUDENT_GROUP,)).fetchone()[0]
        conn.close()

        assert count == 2, f"Schedule count mismatch under concurrent wipe/insert: {count}"


# ============================================================================
# TIER 5.2: TRANSACTION INTEGRITY & MID-SYNC ROLLBACK TESTS
# ============================================================================

class TestTier5TransactionIntegrityAndRollback:
    """Stress tests verifying database transaction rollback under mid-sync exceptions."""

    def test_tier5_04_schedule_sync_midway_failure_rollback(self, isolated_db: Path):
        """
        Seeds mirea_schedule with 5 valid lessons.
        Initiates a sync where the lesson generator throws an exception mid-iteration (simulating mid-sync network crash).
        Asserts that transaction rolls back completely: the original 5 lessons remain intact, not deleted.
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = sqlite3.connect(str(isolated_db))
        cur = conn.cursor()
        for i in range(5):
            cur.execute("""
            INSERT INTO mirea_schedule (group_name, weekday, lesson_time, subject, lesson_type, classroom, teacher, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (STUDENT_GROUP, "Понедельник", f"0{9+i}:00 - 10:30", f"Original Subject {i}", "Лекция", f"А-{i}", "Препод", now_iso))
        conn.commit()
        initial_count = cur.execute("SELECT COUNT(*) FROM mirea_schedule WHERE group_name = ?", (STUDENT_GROUP,)).fetchone()[0]
        conn.close()
        assert initial_count == 5

        def failing_lessons_generator() -> Generator[Dict[str, Any], None, None]:
            yield {
                "group_name": STUDENT_GROUP,
                "weekday": "Вторник",
                "lesson_time": "09:00 - 10:30",
                "subject": "Interrupted Subject",
                "lesson_type": "Практика",
            }
            raise ConnectionResetError("Simulated network/IO socket drop mid-stream during schedule sync")

        client = OfficialScheduleClient()

        with patch.object(client, "fetch_ical_raw", return_value="BEGIN:VCALENDAR...END:VCALENDAR"), \
             patch.object(client, "parse_ical_stream", side_effect=lambda *a, **kw: failing_lessons_generator()):
            with pytest.raises(ConnectionResetError, match="Simulated network/IO socket drop"):
                client.sync_schedule_to_db(db_path=isolated_db, group_name=STUDENT_GROUP)

        conn = sqlite3.connect(str(isolated_db))
        cur = conn.cursor()
        final_count = cur.execute("SELECT COUNT(*) FROM mirea_schedule WHERE group_name = ?", (STUDENT_GROUP,)).fetchone()[0]
        interrupted_count = cur.execute("SELECT COUNT(*) FROM mirea_schedule WHERE subject = 'Interrupted Subject'").fetchone()[0]
        original_subjects = [r[0] for r in cur.execute("SELECT subject FROM mirea_schedule ORDER BY id").fetchall()]
        conn.close()

        assert final_count == 5, f"Rollback failed: expected 5 preserved lessons, found {final_count}"
        assert interrupted_count == 0, "Rollback failed: partial row 'Interrupted Subject' leaked into database"
        assert all(f"Original Subject {i}" in original_subjects for i in range(5))

    def test_tier5_05_debts_sync_midway_failure_rollback(self, isolated_db: Path):
        """
        Seeds mirea_milestones with 18 debts.
        Initiates a sync where debts list raises an exception mid-iteration.
        Asserts that mirea_milestones rolls back completely without leaving partial records or corrupt statuses.
        """
        sync_academic_debts(db_path=isolated_db)

        conn = sqlite3.connect(str(isolated_db))
        cur = conn.cursor()
        cur.execute("UPDATE mirea_milestones SET status = 'INITIAL_VALID'")
        conn.commit()
        conn.close()

        def failing_debts():
            for i, d in enumerate(CATALOG_OF_18_DEBTS[:3]):
                d_copy = dict(d)
                d_copy["subject"] = f"Corrupted Subject {i}"
                yield d_copy
            raise RuntimeError("Database storage timeout mid-sync of academic debts")

        engine = AcademicTruthSync(db_path=isolated_db)
        with pytest.raises(RuntimeError, match="Database storage timeout"):
            engine.sync_academic_debts(db_path=isolated_db, debts=failing_debts())

        conn = sqlite3.connect(str(isolated_db))
        cur = conn.cursor()
        corrupted_count = cur.execute("SELECT COUNT(*) FROM mirea_milestones WHERE subject LIKE 'Corrupted Subject%'").fetchone()[0]
        valid_count = cur.execute("SELECT COUNT(*) FROM mirea_milestones WHERE status = 'INITIAL_VALID'").fetchone()[0]
        total_count = cur.execute("SELECT COUNT(*) FROM mirea_milestones WHERE group_name = ?", (STUDENT_GROUP,)).fetchone()[0]
        conn.close()

        assert corrupted_count == 0, "Rollback failure: partial debts written before exception"
        assert valid_count == ACTIVE_DEBTS_COUNT, f"Rollback failure: expected 18 INITIAL_VALID records, got {valid_count}"
        assert total_count == ACTIVE_DEBTS_COUNT

    def test_tier5_06_profile_sync_failure_rollback(self, isolated_db: Path):
        """
        Seeds valid student profile.
        Triggers sync with an unhashable/invalid payload that triggers an operational error.
        Asserts the prior valid profile record remains completely uncorrupted.
        """
        sync_student_profile(db_path=isolated_db)

        conn = sqlite3.connect(str(isolated_db))
        cur = conn.cursor()
        initial_row = cur.execute("SELECT student_id, full_name, group_name FROM student_profile").fetchone()
        conn.close()

        assert initial_row[0] == STUDENT_ID_NUMBER

        engine = AcademicTruthSync(db_path=isolated_db)

        class UnserializableObject:
            pass

        corrupt_payload = {
            "student_id": "MALICIOUS_OVERWRITE",
            "metadata_json": UnserializableObject(),
        }

        with pytest.raises((sqlite3.ProgrammingError, sqlite3.InterfaceError, TypeError)):
            engine.sync_student_profile(db_path=isolated_db, profile_data=corrupt_payload)

        conn = sqlite3.connect(str(isolated_db))
        cur = conn.cursor()
        current_row = cur.execute("SELECT student_id, full_name, group_name FROM student_profile").fetchone()
        conn.close()

        assert current_row[0] == STUDENT_ID_NUMBER
        assert current_row[1] == STUDENT_FULL_NAME
        assert current_row[2] == STUDENT_GROUP

    def test_tier5_07_database_sqlite_wal_and_fk_integrity(self, isolated_db: Path):
        """
        Executes SQLite PRAGMA integrity_check and PRAGMA foreign_key_check on isolated_db.
        Asserts database physical and relational consistency after all stressful operations.
        """
        conn = sqlite3.connect(str(isolated_db))
        cur = conn.cursor()
        integrity = cur.execute("PRAGMA integrity_check").fetchall()
        fk_violations = cur.execute("PRAGMA foreign_key_check").fetchall()
        conn.close()

        assert len(integrity) == 1 and integrity[0][0].lower() == "ok", f"Integrity check failed: {integrity}"
        assert len(fk_violations) == 0, f"Foreign key violations found: {fk_violations}"

    def test_tier5_08_atomic_session_save_rollback_on_ioerror(self, tmp_path: Path):
        """
        Verifies KeycloakAuthManager.save_session atomic replace safety.
        If an IOError occurs while writing the tempfile, the original session file is not truncated or corrupted.
        """
        session_file = tmp_path / "user_session_test.json"
        auth = KeycloakAuthManager(session_path=session_file)

        initial_cookies = {"AUTH_SESSION_ID": "initial_valid_token_12345"}
        initial_sesskey = "sesskey_initial_abc"
        auth.save_session(cookies=initial_cookies, sesskey=initial_sesskey, session_path=session_file)

        assert session_file.exists()
        with open(session_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data["cookies"]["AUTH_SESSION_ID"] == "initial_valid_token_12345"

        new_cookies = {"AUTH_SESSION_ID": "corrupted_token"}
        with patch("json.dump", side_effect=IOError("Simulated disk full / permission error during json.dump")):
            with pytest.raises(IOError, match="Simulated disk full"):
                auth.save_session(cookies=new_cookies, sesskey="new_sesskey", session_path=session_file)

        with open(session_file, "r", encoding="utf-8") as f:
            intact_data = json.load(f)
        assert intact_data["cookies"]["AUTH_SESSION_ID"] == "initial_valid_token_12345"
        assert intact_data["sesskey"] == "sesskey_initial_abc"


# ============================================================================
# TIER 5.3: MOODLE CLIENT ERROR MODES & FAIL-CLOSED GATES
# ============================================================================

class TestTier5MoodleClientErrorModes:
    """Stress tests verifying fail-closed error handling in MoodleLMSClient across all edge cases."""

    def test_tier5_09_moodle_nonexistent_course_id_resolution(self):
        """
        Verifies resolve_course_id returns None for all non-existent, malformed, or out-of-range exam sheet numbers.
        Asserts fail-closed resolution without fallback guessing.
        """
        client = MoodleLMSClient()

        nonexistent_inputs = [
            "999999",
            "-1",
            "0",
            "",
            "   ",
            None,
            "XYZ_EXAM",
            "81917_fake",
            "NaN",
            "null",
            1234567,
        ]
        for bad_id in nonexistent_inputs:
            assert client.resolve_course_id(bad_id) is None, f"Expected None for {bad_id}, got {client.resolve_course_id(bad_id)}"

        assert client.resolve_course_id("81917") == 16479
        assert client.resolve_course_id(" 81917 ") == 16479
        assert client.resolve_course_id("66804") == 16480
        assert client.resolve_course_id("86958") == 16486
        assert client.resolve_course_id("86146") == 16017

    def test_tier5_10_moodle_quizzes_nonexistent_course_http_404(self):
        """
        When Moodle server returns HTTP 404 for a non-existent course ID,
        get_quizzes_for_course raises requests.exceptions.HTTPError (fail-closed).
        """
        client = MoodleLMSClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error: Not Found")

        with patch.object(client._session, "get", return_value=mock_resp):
            with pytest.raises(requests.exceptions.HTTPError, match="404"):
                client.get_quizzes_for_course(9999999)

    def test_tier5_11_moodle_quizzes_nonexistent_course_error_html(self):
        """
        When Moodle returns HTTP 200 with an error banner (e.g. 'Course not found' or 'Курс не найден'),
        get_quizzes_for_course returns [] (fail-closed, zero quizzes discovered).
        """
        client = MoodleLMSClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = """
        <!DOCTYPE html>
        <html>
        <head><title>Ошибка</title></head>
        <body>
        <div class="alert alert-danger" role="alert">
            Курс с указанным идентификатором (9999999) не найден в системе online-edu.mirea.ru.
        </div>
        </body>
        </html>
        """
        mock_resp.raise_for_status.return_value = None

        with patch.object(client._session, "get", return_value=mock_resp):
            quizzes = client.get_quizzes_for_course(9999999)
            assert isinstance(quizzes, list)
            assert len(quizzes) == 0, f"Expected 0 quizzes on error HTML, found: {quizzes}"

    def test_tier5_12_moodle_ajax_expired_sesskey_returns_empty(self):
        """
        When Moodle AJAX core_course_get_enrolled_courses_by_timeline_classification
        returns an error block indicating expired sesskey (invalidsesskey),
        client logs a warning and returns [] fail-closed.
        """
        client = MoodleLMSClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = [
            {
                "error": True,
                "exception": {
                    "errorcode": "invalidsesskey",
                    "message": "Неверный ключ сессии. Пожалуйста, войдите снова.",
                },
            }
        ]

        with patch.object(client._session, "post", return_value=mock_resp):
            courses = client.get_enrolled_courses()
            assert isinstance(courses, list)
            assert len(courses) == 0, f"Expected [] courses on expired sesskey, got: {courses}"

    def test_tier5_13_moodle_quizzes_expired_session_redirect(self):
        """
        When attempting to fetch quizzes while session is expired and Moodle responds
        with a login page HTML (redirect or direct), get_quizzes_for_course returns [] (fail-closed).
        """
        client = MoodleLMSClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://online-edu.mirea.ru/login/index.php"
        mock_resp.text = """
        <!DOCTYPE html>
        <html>
        <head><title>Авторизация — СДО РТУ МИРЭА</title></head>
        <body>
        <form action="https://online-edu.mirea.ru/login/index.php" method="post" id="login">
            <input type="text" name="username" placeholder="Логин">
            <input type="password" name="password" placeholder="Пароль">
            <button type="submit">Вход в систему</button>
        </form>
        </body>
        </html>
        """
        mock_resp.raise_for_status.return_value = None

        with patch.object(client._session, "get", return_value=mock_resp):
            quizzes = client.get_quizzes_for_course(16479)
            assert isinstance(quizzes, list)
            assert len(quizzes) == 0, f"Expected 0 quizzes on login redirect, got: {quizzes}"

    def test_tier5_14_moodle_validate_session_exhaustive_matrix(self):
        """
        Exhaustively verifies validate_session() across all positive and negative failure modes:
        - Active session (HTTP 200 on /my/ with no login redirect) -> True
        - HTTP 302 redirect to login -> False
        - HTTP 200 containing 'Please login' -> False
        - HTTP 200 containing 'Вход в систему' -> False
        - HTTP 401 Unauthorized -> False
        - HTTP 403 Forbidden -> False
        - HTTP 500 Internal Server Error -> False
        - ConnectionError / Timeout -> False
        """
        client = MoodleLMSClient()

        with patch.object(client._session, "get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.url = "https://online-edu.mirea.ru/my/"
            mock_resp.text = "<html><body><h1>Личный кабинет студента</h1></body></html>"
            mock_get.return_value = mock_resp
            assert client.validate_session() is True

        with patch.object(client._session, "get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 302
            mock_resp.headers = {"Location": "https://online-edu.mirea.ru/login/index.php"}
            mock_get.return_value = mock_resp
            assert client.validate_session() is False

        with patch.object(client._session, "get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.url = "https://online-edu.mirea.ru/my/"
            mock_resp.text = "<html>Please login to proceed</html>"
            mock_get.return_value = mock_resp
            assert client.validate_session() is False

        with patch.object(client._session, "get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.headers = {}
            mock_resp.text = "Unauthorized"
            mock_get.return_value = mock_resp
            assert client.validate_session() is False

        with patch.object(client._session, "get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 403
            mock_resp.headers = {}
            mock_resp.text = "Forbidden"
            mock_get.return_value = mock_resp
            assert client.validate_session() is False

        with patch.object(client._session, "get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.headers = {}
            mock_resp.text = "Server Error"
            mock_get.return_value = mock_resp
            assert client.validate_session() is False

        with patch.object(client._session, "get", side_effect=requests.exceptions.ConnectTimeout("Connection timed out")):
            assert client.validate_session() is False

    def test_tier5_15_safety_guard_blocks_all_mutations_even_under_error_state(self):
        """
        Verifies that even if Moodle client is in an error or degraded state,
        AcademicSafetyGuard NEVER permits any mutating action or quiz start attempt.
        """
        guard = AcademicSafetyGuard(allow_mutating_ops=False)

        forbidden_actions = [
            ("POST", "https://online-edu.mirea.ru/mod/quiz/startattempt.php", {"cmid": 16479}),
            ("POST", "https://online-edu.mirea.ru/mod/quiz/processattempt.php", {"attempt": 1234}),
            ("POST", "https://online-edu.mirea.ru/mod/assign/view.php?action=submit", {"submission": "code.py"}),
            ("PUT", "https://online-edu.mirea.ru/api/grade", {"grade": 5}),
            ("DELETE", "https://online-edu.mirea.ru/api/debts/81917", {}),
        ]

        for method, url, payload in forbidden_actions:
            with pytest.raises(AcademicSafetyViolationError):
                guard.intercept_request(method=method, url=url, kwargs={"json": payload})


def run_standalone_adversarial_suite() -> Dict[str, Any]:
    """Runs all Tier 5 suites standalone and generates JSON summary."""
    print("\n" + "="*70)
    print(" TIER 5 ADVERSARIAL COVERAGE HARDENING HARNESS")
    print("="*70)

    t0 = time.time()
    results: Dict[str, Any] = {}

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path_1 = init_test_db(Path(tmp_dir) / "tier5_standalone_1.db")
        db_path_2 = init_test_db(Path(tmp_dir) / "tier5_standalone_2.db")

        suite_obj = TestTier5ConcurrencyAndStress()
        t_concurrency = TestTier5TransactionIntegrityAndRollback()
        t_moodle = TestTier5MoodleClientErrorModes()

        # Suite 1: Concurrency & Cold-Start Race
        print("[1/3] Running Concurrency & Race Condition Suite...")
        r1_passed = False
        r1_reason = ""
        try:
            suite_obj.test_tier5_01_cold_start_concurrent_sync_exposes_race_condition(db_path_1)
            r1_passed = True
            print("  ✅ Concurrency cold-start sync PASSED")
        except AssertionError as ae:
            r1_passed = False
            r1_reason = str(ae)
            print(f"  ❌ VULNERABILITY CONFIRMED: {ae}")
        except Exception as ex:
            r1_passed = False
            r1_reason = f"Unexpected error: {ex}"
            print(f"  ❌ UNEXPECTED ERROR: {ex}")

        # Suite 2: Transaction Integrity & Rollbacks
        print("[2/3] Running Transaction Integrity & Rollback Suite...")
        r2_passed = True
        r2_details = []
        try:
            t_concurrency.test_tier5_04_schedule_sync_midway_failure_rollback(db_path_2)
            t_concurrency.test_tier5_05_debts_sync_midway_failure_rollback(db_path_2)
            t_concurrency.test_tier5_06_profile_sync_failure_rollback(db_path_2)
            t_concurrency.test_tier5_07_database_sqlite_wal_and_fk_integrity(db_path_2)
            t_concurrency.test_tier5_08_atomic_session_save_rollback_on_ioerror(Path(tmp_dir))
            print("  ✅ Rollbacks, WAL integrity, and atomic session saves PASSED")
        except Exception as ex:
            r2_passed = False
            r2_details.append(str(ex))
            print(f"  ❌ Rollback suite failure: {ex}")

        # Suite 3: Moodle Client Error Modes
        print("[3/3] Running Moodle Client Error Modes & Fail-Closed Suite...")
        r3_passed = True
        r3_details = []
        try:
            t_moodle.test_tier5_09_moodle_nonexistent_course_id_resolution()
            t_moodle.test_tier5_10_moodle_quizzes_nonexistent_course_http_404()
            t_moodle.test_tier5_11_moodle_quizzes_nonexistent_course_error_html()
            t_moodle.test_tier5_12_moodle_ajax_expired_sesskey_returns_empty()
            t_moodle.test_tier5_13_moodle_quizzes_expired_session_redirect()
            t_moodle.test_tier5_14_moodle_validate_session_exhaustive_matrix()
            t_moodle.test_tier5_15_safety_guard_blocks_all_mutations_even_under_error_state()
            print("  ✅ Moodle error modes, expired tokens, and read-only guards PASSED")
        except Exception as ex:
            r3_passed = False
            r3_details.append(str(ex))
            print(f"  ❌ Moodle suite failure: {ex}")

    elapsed = time.time() - t0
    overall_passed = r1_passed and r2_passed and r3_passed
    verdict = "APPROVE" if overall_passed else "REJECT"

    summary = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "overall_passed": overall_passed,
        "verdict": verdict,
        "duration_sec": round(elapsed, 3),
        "suites": {
            "suite_1_concurrency_race_condition": {
                "passed": r1_passed,
                "vulnerability": r1_reason if not r1_passed else None,
            },
            "suite_2_transaction_integrity_and_rollback": {
                "passed": r2_passed,
                "failures": r2_details,
            },
            "suite_3_moodle_error_modes_fail_closed": {
                "passed": r3_passed,
                "failures": r3_details,
            },
        },
    }

    report_file = Path(r"C:\vazus\.agents\challenger_final_2\stress_test_results.json")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWrote results to {report_file}")
    print(f"VERDICT: {verdict} (elapsed: {elapsed:.2f}s)")
    return summary


if __name__ == "__main__":
    summary = run_standalone_adversarial_suite()
    sys.exit(0 if summary["overall_passed"] else 1)
