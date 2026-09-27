"""
vazus_autonomous_harness.academic.debt_navigator — Academic Debt Navigator for RTU MIREA.

Milestone 7 (F18):
- Loads the 18 verified academic debts from vazus.db (mirea_milestones) and STUDY.md
  for student Zhukov M.D. (ИВБО-22-25, 25И0566).
- Cross-references real_retake_schedule.xlsx (retake dates, auditoriums, teachers).
- Flags Semester 1 Mathematics (Linear Algebra 66804, Math Analysis 81917, Math Logic 86958)
  and English (86146) as priority for the critical 2026-10-15 deadline.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("vazus.harness.academic.debt_navigator")

DEFAULT_DB_PATH = Path(r"C:\vazus\services\memory\vazus.db")
DEFAULT_STUDY_MD_PATH = Path(r"C:\vazus\services\memory\STUDY.md")
DEFAULT_SCHEDULE_PATH = Path(r"C:\vazus\hartes\scratch\real_retake_schedule.xlsx")
FALLBACK_SUMMARY_JSON_PATH = Path(r"C:\vazus\hartes\scratch\debt_retake_summary.json")

PRIORITY_DISCIPLINE_IDS = {"66804", "81917", "86958", "86146"}
STAGE1_CRITICAL_DEADLINE = "2026-10-15"

STUDENT_NAME = "Жуков Максим Дмитриевич"
STUDENT_ID = "25И0566"
STUDENT_GROUP = "ИВБО-22-25"
STUDENT_SPECIALTY = "09.03.01"


@dataclass
class AcademicDebtItem:
    discipline_id: str
    discipline_name: str
    semester: int
    exam_type: str  # 'Экзамен', 'Зачет', 'Дифф.зачет', 'Курсовая работа'
    deadline: str  # '2026-10-15'
    retake_date: Optional[str] = None
    retake_auditorium: Optional[str] = None
    teacher: Optional[str] = None
    is_priority: bool = False
    moodle_course_id: Optional[int] = None
    status: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "discipline_id": self.discipline_id,
            "discipline_name": self.discipline_name,
            "semester": self.semester,
            "exam_type": self.exam_type,
            "deadline": self.deadline,
            "retake_date": self.retake_date,
            "retake_auditorium": self.retake_auditorium,
            "teacher": self.teacher,
            "is_priority": self.is_priority,
            "moodle_course_id": self.moodle_course_id,
            "status": self.status,
            "description": self.description,
        }


# Canonical dataset of all 18 debts as recorded in vazus.db and STUDY.md
CANONICAL_18_DEBTS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "discipline_id": "86146",
        "discipline_name": "Иностранный язык",
        "semester": 1,
        "exam_type": "Зачет",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": 16017,
        "status": "PENDING",
        "description": "Готовые топики / перевод | Сдать лексический минимум преподавателю",
        "is_priority": True,
        "default_teacher": "Кафедра иностранных языков",
        "default_auditorium": "И-330",
        "default_dates": "Вт 1 пара (09:00), Чт 6 пара (18:00), Сб 1 пара (09:00)",
    },
    {
        "id": 2,
        "discipline_id": "66804",
        "discipline_name": "Линейная алгебра и аналитическая геометрия",
        "semester": 1,
        "exam_type": "Экзамен",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": 16480,
        "status": "PENDING",
        "description": "Решатель матриц и СЛАУ | Прорешать билеты 1-го семестра",
        "is_priority": True,
        "default_teacher": "Горшунова Т.А., Муханов А.А., Никитина С.В., Берков Н.А.",
        "default_auditorium": "А-405, А-403, А-401, А-9а",
        "default_dates": "Пн 4 пара (А-403), Вт 2-3 пара (А-401/А-405), Ср 4 пара (А-405), Пт 4 пара (А-9а), Сб 3 пара (А-9а)",
    },
    {
        "id": 3,
        "discipline_id": "81917",
        "discipline_name": "Математический анализ",
        "semester": 1,
        "exam_type": "Экзамен",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": 16479,
        "status": "IN_PROGRESS",
        "description": "handwritten_solutions.pdf на диске | Отправить готовые решения на проверку",
        "is_priority": True,
        "default_teacher": "Батиенков Р.В., Доронкина С.В., Николаева С.В., Павлова Т.А.",
        "default_auditorium": "А-182, А-411, А-427, А-9а",
        "default_dates": "Пн 3 пара (А-9а, А-182), Пн 5 пара (А-411), Вт 3 пара (А-427), Ср 3 пара (Батиенков, А-182)",
    },
    {
        "id": 4,
        "discipline_id": "86958",
        "discipline_name": "Математическая логика и теория алгоритмов",
        "semester": 1,
        "exam_type": "Экзамен",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": 16486,
        "status": "PENDING",
        "description": "Z3 / Булевы таблицы истинности | Сдать расчетные задания по исчислению предикатов",
        "is_priority": True,
        "default_teacher": "Волощук С.А., Даева С.Г., Староверов И.Н.",
        "default_auditorium": "Г-414, Г-426",
        "default_dates": "Чт 10:40, 12:40 (Волощук, Г-414); Сб 12:40 (Даева); Вт 14:20 (Староверов, Г-426)",
    },
    {
        "id": 5,
        "discipline_id": "69956",
        "discipline_name": "Русский язык и культура речи",
        "semester": 2,
        "exam_type": "Зачет",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": None,
        "status": "PENDING",
        "description": "Рефераты / тесты | Закрыть онлайн-тест за 1 вечер",
        "is_priority": False,
        "default_teacher": "Кафедра русского языка",
        "default_auditorium": "И-322 / И-341",
        "default_dates": "Пн (нечет) 1 пара, Ср (нечет) 5 пара, Пт (нечет) 4 пара, Сб (чет) 5 пара",
    },
    {
        "id": 6,
        "discipline_id": "86971",
        "discipline_name": "Основы конструирования",
        "semester": 2,
        "exam_type": "Зачет",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": None,
        "status": "PENDING",
        "description": "Чертежи / САПР конспекты | Сдать отчет по практическим работам",
        "is_priority": False,
        "default_teacher": "Преподаватели кафедры ВТ / КИТПиПИ",
        "default_auditorium": "Г-310, Г-327",
        "default_dates": "По расписанию консультаций кафедры ВТ / КИТПиПИ",
    },
    {
        "id": 7,
        "discipline_id": "86959",
        "discipline_name": "Объектно-ориентированное программирование",
        "semester": 2,
        "exam_type": "Курсовая работа",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": None,
        "status": "PENDING",
        "description": "Проект на Python / C++ | Оформить пояснительную записку и код",
        "is_priority": False,
        "default_teacher": "Асадова Ю.С.",
        "default_auditorium": "Г-107",
        "default_dates": "2026-10-06 10:40-12:10 (спецпоток ИВБО-22-25)",
    },
    {
        "id": 8,
        "discipline_id": "86146",
        "discipline_name": "Иностранный язык",
        "semester": 2,
        "exam_type": "Зачет",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": 16017,
        "status": "PENDING",
        "description": "Технический перевод | Сдать терминологический словарь",
        "is_priority": False,
        "default_teacher": "Кафедра иностранных языков",
        "default_auditorium": "И-330",
        "default_dates": "Вт 1 пара (09:00), Чт 6 пара (18:00), Сб 1 пара (09:00)",
    },
    {
        "id": 9,
        "discipline_id": "78208",
        "discipline_name": "Физика",
        "semester": 2,
        "exam_type": "Зачет",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": None,
        "status": "PENDING",
        "description": "Лабораторные отчеты | Защитить лабораторные по механике/оптике",
        "is_priority": False,
        "default_teacher": "Кафедра физики и технической механики",
        "default_auditorium": "В-323",
        "default_dates": "01.10.2026, 13.10.2026 в 16:20 (Консультация 16.09 в 18:00)",
    },
    {
        "id": 10,
        "discipline_id": "6082",
        "discipline_name": "Ознакомительная практика",
        "semester": 2,
        "exam_type": "Дифф.зачет",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": None,
        "status": "PENDING",
        "description": "Шаблон отчета по практике | Подписать дневник и сдать отчет",
        "is_priority": False,
        "default_teacher": "Черняускас В.В.",
        "default_auditorium": "Г-310",
        "default_dates": "Ср: 23.09, 30.09, 07.10, 14.10 в 10:40-12:30",
    },
    {
        "id": 11,
        "discipline_id": "72287",
        "discipline_name": "Физическая культура и спорт",
        "semester": 2,
        "exam_type": "Зачет",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": None,
        "status": "PENDING",
        "description": "Реферат / Нормативы | Сдать реферат по физкультуре",
        "is_priority": False,
        "default_teacher": "Кафедра физического воспитания",
        "default_auditorium": "Спорткомплекс МИРЭА",
        "default_dates": "По графику отработок спорткомплекса",
    },
    {
        "id": 12,
        "discipline_id": "82576",
        "discipline_name": "Основы российской государственности",
        "semester": 2,
        "exam_type": "Зачет",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": None,
        "status": "PENDING",
        "description": "Тесты / Эссе | Закрыть онлайн-курс в СДО",
        "is_priority": False,
        "default_teacher": "Кафедра истории и политологии",
        "default_auditorium": "А-430",
        "default_dates": "Чт: 17.09, 24.09, 01.10, 08.10, 15.10 в 18:00-19:30",
    },
    {
        "id": 13,
        "discipline_id": "66804",
        "discipline_name": "Линейная алгебра и аналитическая геометрия",
        "semester": 2,
        "exam_type": "Экзамен",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": 16480,
        "status": "PENDING",
        "description": "Квадратичные формы / Линейные операторы | Подготовка к экзамену 2-го семестра",
        "is_priority": False,
        "default_teacher": "Горшунова Т.А., Сидоров С.М.",
        "default_auditorium": "А-405, Г-414",
        "default_dates": "Ср 4 пара (Горшунова); 25.09, 29.09, 09.10, 13.10 в 14:20-15:50 (Сидоров, Г-414)",
    },
    {
        "id": 14,
        "discipline_id": "86959",
        "discipline_name": "Объектно-ориентированное программирование",
        "semester": 2,
        "exam_type": "Экзамен",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": None,
        "status": "PENDING",
        "description": "Паттерны / ООП тесты | Сдать теорию ООП и алгоритмы",
        "is_priority": False,
        "default_teacher": "Асадова Ю.С., Быков А.Ю.",
        "default_auditorium": "Г-107, Г-108",
        "default_dates": "06.10.2026 в 10:40-12:10 (Асадова, Г-107); 01.10, 07.10, 15.10 (Быков, Г-108)",
    },
    {
        "id": 15,
        "discipline_id": "81917",
        "discipline_name": "Математический анализ",
        "semester": 2,
        "exam_type": "Экзамен",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": 16479,
        "status": "PENDING",
        "description": "Интегралы / Ряды / ДУ | Пакетная сдача расчетно-графических работ",
        "is_priority": False,
        "default_teacher": "Батиенков Р.В., Доронкина С.В., Козлова О.Ю., Чекалкин Н.С.",
        "default_auditorium": "А-182, А-411, А-405",
        "default_dates": "Ср 3 пара (Батиенков, А-182); Пн 5 пара (Доронкина, А-411); Вт 5 пара (Козлова, А-405); Пт 3 пара (Чекалкин, А-113)",
    },
    {
        "id": 16,
        "discipline_id": "78208",
        "discipline_name": "Физика",
        "semester": 2,
        "exam_type": "Экзамен",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": None,
        "status": "PENDING",
        "description": "Электромагнетизм / Кванты | Билеты и задачи по физике",
        "is_priority": False,
        "default_teacher": "Кафедра физики и технической механики",
        "default_auditorium": "В-323",
        "default_dates": "01.10.2026, 13.10.2026 в 16:20 (ауд. В-323)",
    },
    {
        "id": 17,
        "discipline_id": "82054",
        "discipline_name": "История России",
        "semester": 2,
        "exam_type": "Экзамен",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": None,
        "status": "PENDING",
        "description": "Хронологические таблицы / Тексты | Тестирование и устный ответ",
        "is_priority": False,
        "default_teacher": "Кафедра истории (ИБО)",
        "default_auditorium": "А-430",
        "default_dates": "Чт: 17.09, 24.09, 01.10, 08.10, 15.10 в 18:00-19:30",
    },
    {
        "id": 18,
        "discipline_id": "85415",
        "discipline_name": "Информатика",
        "semester": 2,
        "exam_type": "Экзамен",
        "deadline": STAGE1_CRITICAL_DEADLINE,
        "moodle_course_id": None,
        "status": "PENDING",
        "description": "Python / Архитектура ЭВМ | Зачетные задачи по алгоритмам",
        "is_priority": False,
        "default_teacher": "Петров М.Ю., преп. каф. пром. инф.",
        "default_auditorium": "Г-327 (В-108-1)",
        "default_dates": "30.09.2026 в 12:40-15:50 (В-108-1); 26.09, 03.10, 10.10, 14.10 в 14:20 (Петров, Г-327)",
    },
]


def _normalize_deadline(raw_val: Optional[str]) -> str:
    """Converts DD.MM.YYYY to YYYY-MM-DD or defaults to 2026-10-15."""
    if not raw_val or not raw_val.strip():
        return STAGE1_CRITICAL_DEADLINE
    cleaned = raw_val.strip()
    match = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", cleaned)
    if match:
        day, month, year = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return cleaned


def _normalize_exam_type(raw_type: Optional[str]) -> str:
    """Normalizes milestone type to standard Russian casing."""
    if not raw_type:
        return "Зачет"
    t = raw_type.strip().lower()
    if "дифф" in t:
        return "Дифф.зачет"
    if "курс" in t:
        return "Курсовая работа"
    if "экзамен" in t:
        return "Экзамен"
    if "зачет" in t:
        return "Зачет"
    return raw_type.strip().capitalize()


class AcademicDebtNavigator:
    """
    Navigator for RTU MIREA Academic Debts.
    Maintains the 18 verified debts of student Zhukov M.D., cross-references
    retake schedules, and prioritizes foundational Semester 1 Math and English.
    """

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        study_md_path: Optional[Union[str, Path]] = None,
        schedule_path: Optional[Union[str, Path]] = None,
        student_id: str = STUDENT_ID,
        group_name: str = STUDENT_GROUP,
        student_name: str = STUDENT_NAME,
        student_specialty: str = STUDENT_SPECIALTY,
    ):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.study_md_path = Path(study_md_path) if study_md_path else DEFAULT_STUDY_MD_PATH
        self.schedule_path = Path(schedule_path) if schedule_path else DEFAULT_SCHEDULE_PATH
        self.student_id = student_id
        self.group_name = group_name
        self.student_name = student_name
        self.student_specialty = student_specialty
        self._debts: List[AcademicDebtItem] = []
        self._load_debts()

    def _load_debts(self) -> None:
        """Loads debts using vazus.db, STUDY.md, or canonical fallback."""
        loaded: List[AcademicDebtItem] = []

        # 1. Attempt loading from vazus.db
        if self.db_path.exists():
            try:
                loaded = self._load_from_sqlite(self.db_path)
            except Exception as e:
                logger.warning(f"Failed to load from sqlite db {self.db_path}: {e}")

        # 2. If SQLite was empty or failed, attempt parsing STUDY.md
        if not loaded and self.study_md_path.exists():
            try:
                loaded = self._load_from_study_md(self.study_md_path)
            except Exception as e:
                logger.warning(f"Failed to load from study_md {self.study_md_path}: {e}")

        # 3. Fallback to canonical dataset if neither could supply 18 debts
        if not loaded or len(loaded) < 18:
            logger.info("Using authoritative canonical 18-debt dataset.")
            loaded = self._load_from_canonical()

        self._debts = loaded

    def _load_from_sqlite(self, db_path: Path) -> List[AcademicDebtItem]:
        """Queries mirea_milestones from vazus.db."""
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        query = """
            SELECT id, subject, milestone_name, milestone_type, due_date,
                   stage1_deadline, student_id, external_id, semester,
                   moodle_course_id, status, description
            FROM mirea_milestones
            WHERE student_id = ? OR group_name = ?
            ORDER BY id
        """
        cur.execute(query, (self.student_id, self.group_name))
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return []

        debts: List[AcademicDebtItem] = []
        for r in rows:
            (
                row_id, subject, milestone_name, milestone_type, due_date,
                stage1_deadline, st_id, external_id, semester,
                moodle_course_id, status, description
            ) = r

            ext_id = str(external_id) if external_id is not None else str(row_id)
            sem = int(semester) if semester is not None else 1
            deadline = _normalize_deadline(stage1_deadline or due_date)
            exam_type = _normalize_exam_type(milestone_type)

            # Determine priority: Semester 1 Math & English
            is_priority = (sem == 1) and (
                ext_id in PRIORITY_DISCIPLINE_IDS
                or any(k in subject.lower() for k in ("линейная алгебра", "математический анализ", "математическая логика", "иностранный язык"))
            )

            # Check canonical mapping for default retake info
            def_teacher = None
            def_room = None
            def_dates = None
            if row_id <= len(CANONICAL_18_DEBTS):
                c = CANONICAL_18_DEBTS[row_id - 1]
                def_teacher = c.get("default_teacher")
                def_room = c.get("default_auditorium")
                def_dates = c.get("default_dates")

            debt = AcademicDebtItem(
                discipline_id=ext_id,
                discipline_name=subject,
                semester=sem,
                exam_type=exam_type,
                deadline=deadline,
                retake_date=def_dates,
                retake_auditorium=def_room,
                teacher=def_teacher,
                is_priority=is_priority,
                moodle_course_id=int(moodle_course_id) if moodle_course_id else None,
                status=status,
                description=description,
            )
            debts.append(debt)

        return debts

    def _load_from_study_md(self, study_md_path: Path) -> List[AcademicDebtItem]:
        """Parses the 18 debts table from STUDY.md."""
        content = study_md_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        in_table = False
        parsed_rows = []
        for line in lines:
            line_str = line.strip()
            if line_str.startswith("| № | Дисциплина |"):
                in_table = True
                continue
            if in_table and line_str.startswith("|---"):
                continue
            if in_table and line_str.startswith("|"):
                parts = [p.strip() for p in line_str.split("|")[1:-1]]
                if len(parts) >= 6:
                    parsed_rows.append(parts)
            elif in_table and not line_str.startswith("|"):
                if parsed_rows:
                    break

        if len(parsed_rows) < 18:
            return []

        debts: List[AcademicDebtItem] = []
        for idx, parts in enumerate(parsed_rows, start=1):
            name = parts[1]
            raw_type = parts[2]
            raw_moodle = parts[3]
            raw_deadline = parts[4]
            status = parts[5]
            desc = parts[6] if len(parts) > 6 else ""

            # Extract discipline id if present in type or moodle
            ext_id_match = re.search(r"№\s*(\d+)", raw_type)
            ext_id = ext_id_match.group(1) if ext_id_match else str(idx)

            # Extract semester if present (e.g. "1/3" or "2/2")
            sem_match = re.search(r"\((\d)/", raw_type)
            sem = int(sem_match.group(1)) if sem_match else (1 if idx <= 4 else 2)

            moodle_match = re.search(r"\[?(\d{5})\]?", raw_moodle)
            moodle_id = int(moodle_match.group(1)) if moodle_match else None

            deadline = _normalize_deadline(raw_deadline)
            exam_type = _normalize_exam_type(raw_type)

            is_priority = (sem == 1) and (
                ext_id in PRIORITY_DISCIPLINE_IDS
                or any(k in name.lower() for k in ("линейная алгебра", "математический анализ", "математическая логика", "иностранный язык"))
            )

            c = CANONICAL_18_DEBTS[idx - 1] if idx <= len(CANONICAL_18_DEBTS) else {}

            debt = AcademicDebtItem(
                discipline_id=ext_id,
                discipline_name=name,
                semester=sem,
                exam_type=exam_type,
                deadline=deadline,
                retake_date=c.get("default_dates"),
                retake_auditorium=c.get("default_auditorium"),
                teacher=c.get("default_teacher"),
                is_priority=is_priority,
                moodle_course_id=moodle_id or c.get("moodle_course_id"),
                status=status,
                description=desc or c.get("description"),
            )
            debts.append(debt)

        return debts

    def _load_from_canonical(self) -> List[AcademicDebtItem]:
        """Loads canonical 18 debts."""
        debts: List[AcademicDebtItem] = []
        for c in CANONICAL_18_DEBTS:
            debt = AcademicDebtItem(
                discipline_id=str(c["discipline_id"]),
                discipline_name=c["discipline_name"],
                semester=c["semester"],
                exam_type=c["exam_type"],
                deadline=c["deadline"],
                retake_date=c.get("default_dates"),
                retake_auditorium=c.get("default_auditorium"),
                teacher=c.get("default_teacher"),
                is_priority=c["is_priority"],
                moodle_course_id=c.get("moodle_course_id"),
                status=c.get("status", "PENDING"),
                description=c.get("description"),
            )
            debts.append(debt)
        return debts

    def get_all_debts(self) -> List[AcademicDebtItem]:
        """Returns all 18 verified academic debts."""
        return list(self._debts)

    def get_priority_debts(self) -> List[AcademicDebtItem]:
        """
        Returns the critical priority debts for the October 15, 2026 deadline:
        Semester 1 Mathematics (Linear Algebra, Math Analysis, Math Logic) and English.
        """
        return [d for d in self._debts if d.is_priority]

    def get_debts_by_semester(self, semester: int) -> List[AcademicDebtItem]:
        """Returns debts filtered by semester."""
        return [d for d in self._debts if d.semester == semester]

    def get_debt_by_id(self, discipline_id: str, semester: Optional[int] = None) -> Optional[AcademicDebtItem]:
        """Finds a debt item by discipline_id and optional semester."""
        for d in self._debts:
            if d.discipline_id == str(discipline_id):
                if semester is None or d.semester == semester:
                    return d
        return None

    def cross_reference_schedule(self, schedule_path: Optional[Union[str, Path]] = None) -> List[AcademicDebtItem]:
        """
        Cross-references retake dates, auditoriums, and teachers against institute schedule.
        Supports both real_retake_schedule.xlsx and pre-parsed JSON summaries.
        """
        target_path = Path(schedule_path) if schedule_path else self.schedule_path

        # If schedule_path doesn't exist, check fallback locations
        if not target_path.exists():
            if FALLBACK_SUMMARY_JSON_PATH.exists():
                target_path = FALLBACK_SUMMARY_JSON_PATH
            elif DEFAULT_SCHEDULE_PATH.exists():
                target_path = DEFAULT_SCHEDULE_PATH

        if not target_path.exists():
            logger.warning(f"Retake schedule file not found at {target_path}. Retaining defaults.")
            return list(self._debts)

        suffix = target_path.suffix.lower()
        if suffix == ".json":
            self._cross_reference_json(target_path)
        elif suffix in (".xlsx", ".xlsm"):
            self._cross_reference_excel(target_path)
        else:
            logger.warning(f"Unsupported schedule format: {suffix}. Retaining defaults.")

        return list(self._debts)

    def _cross_reference_json(self, json_path: Path) -> None:
        """Enriches debts from debt_retake_summary.json or parsed_retakes.json."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read json schedule {json_path}: {e}")
            return

        if isinstance(data, dict):
            # Keyed by debt index "1".."18"
            for idx_str, entries in data.items():
                if not idx_str.isdigit():
                    continue
                idx = int(idx_str) - 1
                if 0 <= idx < len(self._debts):
                    debt = self._debts[idx]
                    # Select entry: prefer is_ivbo == True, else first entry
                    ivbo_entries = [e for e in entries if e.get("is_ivbo") or e.get("is_ivbo_22")]
                    chosen = ivbo_entries[0] if ivbo_entries else (entries[0] if entries else None)
                    if chosen:
                        if chosen.get("room"):
                            debt.retake_auditorium = str(chosen["room"]).strip()
                        if chosen.get("teacher"):
                            debt.teacher = str(chosen["teacher"]).strip()
                        dates = chosen.get("dates", "")
                        times = chosen.get("times", "")
                        combined = f"{dates} {times}".strip()
                        if combined:
                            debt.retake_date = combined

    def _cross_reference_excel(self, excel_path: Path) -> None:
        """Parses an Excel workbook directly using openpyxl."""
        try:
            import openpyxl
        except ImportError:
            logger.warning("openpyxl not installed, cannot parse excel directly.")
            return

        try:
            wb = openpyxl.load_workbook(str(excel_path), data_only=True)
        except Exception as e:
            logger.warning(f"Could not open workbook {excel_path}: {e}")
            return

        # Target sheet inspection
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            for row in ws.iter_rows(values_only=True):
                if not row or not any(row):
                    continue
                row_str = " ".join(str(c) for c in row if c is not None).lower()

                # Match each debt against row
                for idx, debt in enumerate(self._debts):
                    dname_lower = debt.discipline_name.lower()
                    # Check matching keywords
                    matches = False
                    if "линейная алгебра" in dname_lower and "линейная алгебра" in row_str:
                        matches = True
                    elif "математический анализ" in dname_lower and "математический анализ" in row_str:
                        matches = True
                    elif "математическая логика" in dname_lower and "математическая логика" in row_str:
                        matches = True
                    elif "иностранный язык" in dname_lower and ("иностранный" in row_str or "английский" in row_str):
                        matches = True
                    elif "объектно-ориентированное" in dname_lower and ("объектно" in row_str or "ооп" in row_str):
                        matches = True
                    elif "ознакомительная практика" in dname_lower and "практик" in row_str:
                        matches = True
                    elif "физика" in dname_lower and "физик" in row_str:
                        matches = True
                    elif "информатика" in dname_lower and "информатик" in row_str:
                        matches = True

                    if matches:
                        # Extract teacher, auditorium, dates from row cells
                        cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                        for cell in cells:
                            if re.search(r"\b[А-Я][а-я]+\s+[А-Я]\.[А-Я]\.", cell):
                                debt.teacher = cell
                            if re.search(r"\b[А-Я]-\d+", cell):
                                debt.retake_auditorium = cell
                            if re.search(r"\d{2}\.\d{2}\.\d{4}", cell):
                                debt.retake_date = cell

    def get_summary(self) -> Dict[str, Any]:
        """Provides a statistical summary of the student's academic standing."""
        all_debts = self.get_all_debts()
        priority_debts = self.get_priority_debts()
        sem1 = self.get_debts_by_semester(1)
        sem2 = self.get_debts_by_semester(2)

        return {
            "student_name": self.student_name,
            "student_id": self.student_id,
            "group": self.group_name,
            "specialty": self.student_specialty,
            "total_debts": len(all_debts),
            "priority_debts_count": len(priority_debts),
            "priority_discipline_ids": [d.discipline_id for d in priority_debts],
            "semester_1_count": len(sem1),
            "semester_2_count": len(sem2),
            "stage1_deadline": STAGE1_CRITICAL_DEADLINE,
        }

    def export_markdown_table(self) -> str:
        """Formats the 18 debts into a clean Markdown table compatible with STUDY.md."""
        lines = [
            f"# Академические задолженности: {self.student_name} ({self.group_name}, {self.student_id})",
            f"**Дедлайн 1-го этапа ликвидации**: {STAGE1_CRITICAL_DEADLINE} | **Всего задолженностей**: {len(self._debts)}",
            "",
            "| № | Дисциплина | Сем | Форма контроля | ID СДО | Дедлайн | Приоритет | Преподаватель | Ауд. | Расписание пересдач |",
            "|---|---|:---:|---|:---:|:---:|:---:|---|:---:|---|",
        ]
        for idx, d in enumerate(self._debts, start=1):
            prio = "🔥 СРОЧНО" if d.is_priority else "Обычный"
            moodle = str(d.moodle_course_id) if d.moodle_course_id else "-"
            teacher = d.teacher or "-"
            room = d.retake_auditorium or "-"
            dates = d.retake_date or "-"
            lines.append(
                f"| {idx} | {d.discipline_name} | {d.semester} | {d.exam_type} | {moodle} | {d.deadline} | {prio} | {teacher} | {room} | {dates} |"
            )
        return "\n".join(lines)
