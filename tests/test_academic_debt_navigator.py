"""
Unit Test Suite for Milestone 7 (F18): Academic Debt Navigator.

Tests:
- AcademicDebtItem dataclass fields and serialization.
- Loading the 18 verified academic debts from vazus.db / STUDY.md / canonical dataset.
- Priority identification for Semester 1 Mathematics (66804, 81917, 86958) and English (86146).
- Cross-referencing real_retake_schedule.xlsx and custom Excel/JSON workbooks.
- Filtering by semester and finding debt by ID.
- Summary statistics and Markdown export.
- NO MOCKS: All tests use genuine objects, SQLite databases, and openpyxl workbooks.
"""

import sqlite3
import tempfile
from pathlib import Path

import openpyxl
import pytest

from vazus_autonomous_harness.academic.debt_navigator import (
    AcademicDebtItem,
    AcademicDebtNavigator,
    PRIORITY_DISCIPLINE_IDS,
    STAGE1_CRITICAL_DEADLINE,
    STUDENT_GROUP,
    STUDENT_ID,
    STUDENT_NAME,
)


def test_academic_debt_item_dataclass():
    item = AcademicDebtItem(
        discipline_id="66804",
        discipline_name="Линейная алгебра и аналитическая геометрия",
        semester=1,
        exam_type="Экзамен",
        deadline=STAGE1_CRITICAL_DEADLINE,
        is_priority=True,
        moodle_course_id=16480,
        status="PENDING",
    )
    assert item.discipline_id == "66804"
    assert item.semester == 1
    assert item.exam_type == "Экзамен"
    assert item.deadline == "2026-10-15"
    assert item.is_priority is True
    assert item.retake_date is None
    assert item.retake_auditorium is None
    assert item.teacher is None

    d = item.to_dict()
    assert d["discipline_id"] == "66804"
    assert d["is_priority"] is True
    assert d["moodle_course_id"] == 16480


def test_navigator_loads_18_debts():
    nav = AcademicDebtNavigator()
    debts = nav.get_all_debts()
    assert len(debts) == 18

    # Student metadata
    assert nav.student_id == STUDENT_ID
    assert nav.group_name == STUDENT_GROUP
    assert nav.student_name == STUDENT_NAME

    # Check all have deadline 2026-10-15
    for d in debts:
        assert d.deadline == STAGE1_CRITICAL_DEADLINE
        assert d.semester in (1, 2)
        assert len(d.discipline_name) > 0


def test_priority_debts_october_15():
    nav = AcademicDebtNavigator()
    priority = nav.get_priority_debts()

    # Exactly 4 priority debts for Semester 1 Math and English
    assert len(priority) == 4

    priority_ids = {d.discipline_id for d in priority}
    assert priority_ids == {"66804", "81917", "86958", "86146"}

    # Verify all priority debts are in Semester 1
    for d in priority:
        assert d.is_priority is True
        assert d.semester == 1
        assert d.deadline == STAGE1_CRITICAL_DEADLINE

    # Verify non-priority debts
    non_priority = [d for d in nav.get_all_debts() if not d.is_priority]
    assert len(non_priority) == 14
    for d in non_priority:
        assert d.is_priority is False


def test_debts_by_semester():
    nav = AcademicDebtNavigator()
    sem1 = nav.get_debts_by_semester(1)
    sem2 = nav.get_debts_by_semester(2)

    assert len(sem1) == 4
    assert len(sem2) == 14
    assert len(sem1) + len(sem2) == 18

    # Sem 1 debts should all be priority
    for d in sem1:
        assert d.is_priority is True

    # Sem 2 debts should all be non-priority
    for d in sem2:
        assert d.is_priority is False


def test_get_debt_by_id():
    nav = AcademicDebtNavigator()

    # Search for Math Logic
    logic = nav.get_debt_by_id("86958")
    assert logic is not None
    assert "логика" in logic.discipline_name.lower()
    assert logic.semester == 1
    assert logic.is_priority is True

    # Search for English (exists in both sem 1 and sem 2)
    eng_sem1 = nav.get_debt_by_id("86146", semester=1)
    assert eng_sem1 is not None
    assert eng_sem1.semester == 1
    assert eng_sem1.is_priority is True

    eng_sem2 = nav.get_debt_by_id("86146", semester=2)
    assert eng_sem2 is not None
    assert eng_sem2.semester == 2
    assert eng_sem2.is_priority is False

    # Non-existent
    assert nav.get_debt_by_id("999999") is None


def test_cross_reference_schedule_real_excel():
    nav = AcademicDebtNavigator()
    real_schedule = Path(r"C:\vazus\hartes\scratch\real_retake_schedule.xlsx")
    if real_schedule.exists():
        debts = nav.cross_reference_schedule(real_schedule)
        assert len(debts) == 18

        # Check that room and teachers are populated
        oop_course = nav.get_debt_by_id("86959")
        assert oop_course is not None
        assert oop_course.retake_auditorium is not None

        eng = nav.get_debt_by_id("86146", semester=1)
        assert eng is not None
        assert eng.retake_auditorium == "И-330"


def test_cross_reference_schedule_custom_excel(tmp_path: Path):
    # Construct a genuine custom .xlsx workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ПМ"

    # Header rows
    ws.append(["Инфо", "Расписание"])
    ws.append(["Дисциплина", "Преподаватель", "Формат", "Аудитория", "Дата", "Время", "Группы"])

    # Row matching Линейная алгебра
    ws.append([
        "Линейная алгебра и аналитическая геометрия (Экзамен)",
        "Иванов И.И.",
        "Очно",
        "А-405",
        "10.10.2026",
        "10:40-12:10",
        "ИВБО-22-25",
    ])
    # Row matching Математическая логика
    ws.append([
        "Математическая логика и теория алгоритмов (Экзамен)",
        "Петров П.П.",
        "Очно",
        "Г-414",
        "15.10.2026",
        "12:40-14:10",
        "ИВБО-22-25",
    ])

    excel_file = tmp_path / "custom_schedule.xlsx"
    wb.save(str(excel_file))

    nav = AcademicDebtNavigator()
    debts = nav.cross_reference_schedule(excel_file)
    assert len(debts) == 18

    # Verify that matching rows updated the items
    linalg = nav.get_debt_by_id("66804", semester=1)
    assert linalg is not None
    assert linalg.retake_auditorium == "А-405"
    assert linalg.teacher == "Иванов И.И."
    assert linalg.retake_date == "10.10.2026"

    logic = nav.get_debt_by_id("86958")
    assert logic is not None
    assert logic.retake_auditorium == "Г-414"
    assert logic.teacher == "Петров П.П."
    assert logic.retake_date == "15.10.2026"


def test_cross_reference_schedule_custom_json(tmp_path: Path):
    import json
    json_data = {
        "1": [
            {
                "debt_num": 1,
                "room": "И-330-CUSTOM",
                "teacher": "Смит Д.",
                "dates": "12.10.2026",
                "times": "09:00",
                "is_ivbo": True,
            }
        ],
        "7": [
            {
                "debt_num": 7,
                "room": "Г-107-SPECIAL",
                "teacher": "Асадова Ю.С.",
                "dates": "06.10.2026",
                "times": "10:40",
                "is_ivbo": True,
            }
        ],
    }
    json_file = tmp_path / "custom_schedule.json"
    json_file.write_text(json.dumps(json_data), encoding="utf-8")

    nav = AcademicDebtNavigator()
    debts = nav.cross_reference_schedule(json_file)

    eng = nav.get_debt_by_id("86146", semester=1)
    assert eng.retake_auditorium == "И-330-CUSTOM"
    assert eng.teacher == "Смит Д."
    assert "12.10.2026" in eng.retake_date

    oop = nav.get_debt_by_id("86959", semester=2)
    assert oop.retake_auditorium == "Г-107-SPECIAL"
    assert oop.teacher == "Асадова Ю.С."


def test_loading_from_custom_sqlite_database(tmp_path: Path):
    db_file = tmp_path / "test_vazus.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE mirea_milestones (
            id INTEGER PRIMARY KEY,
            group_name TEXT,
            subject TEXT,
            milestone_name TEXT,
            milestone_type TEXT,
            due_date TEXT,
            status TEXT,
            description TEXT,
            stage1_deadline TEXT,
            student_id TEXT,
            external_id TEXT,
            semester INTEGER,
            moodle_course_id INTEGER,
            updated_at TEXT
        )
    """)

    # Insert 18 mock-free records with Russian data
    for i in range(1, 19):
        is_sem1 = i <= 4
        cur.execute("""
            INSERT INTO mirea_milestones (
                id, group_name, subject, milestone_name, milestone_type,
                due_date, stage1_deadline, student_id, external_id, semester,
                moodle_course_id, status, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            i,
            STUDENT_GROUP,
            f"Тестовая дисциплина {i}",
            f"Контроль {i}",
            "экзамен" if i % 2 == 0 else "зачет",
            "15.10.2026",
            "15.10.2026",
            STUDENT_ID,
            str(66800 + i),
            1 if is_sem1 else 2,
            16000 + i,
            "PENDING",
            f"Описание долга {i}",
        ))
    conn.commit()
    conn.close()

    nav = AcademicDebtNavigator(db_path=db_file)
    debts = nav.get_all_debts()
    assert len(debts) == 18
    assert debts[0].deadline == "2026-10-15"
    assert debts[0].discipline_id == "66801"
    assert debts[0].exam_type == "Зачет"


def test_get_summary_and_markdown_export():
    nav = AcademicDebtNavigator()
    summary = nav.get_summary()

    assert summary["student_name"] == STUDENT_NAME
    assert summary["student_id"] == STUDENT_ID
    assert summary["group"] == STUDENT_GROUP
    assert summary["total_debts"] == 18
    assert summary["priority_debts_count"] == 4
    assert summary["semester_1_count"] == 4
    assert summary["semester_2_count"] == 14
    assert summary["stage1_deadline"] == "2026-10-15"

    md = nav.export_markdown_table()
    assert "# Академические задолженности" in md
    assert STUDENT_NAME in md
    assert STUDENT_ID in md
    assert "🔥 СРОЧНО" in md
    assert "Линейная алгебра и аналитическая геометрия" in md
    assert "Математический анализ" in md
    assert "Математическая логика" in md
    assert "Иностранный язык" in md
