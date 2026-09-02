"""
Vazus SuperGraph OS - RTU MIREA Student Schedule & Academic Manager
Fetches schedule, classroom assignments, teacher names, homework, and exam dates for RTU MIREA groups.
Supports online API fetching (with urllib.parse Cyrillic encoding), offline SQLite caching, and academic milestone tracking.
"""

import json
import logging
import os
import sqlite3
import sys
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception as exc:
        logger.debug("Failed stdout reconfigure: %s", exc)

sys.path.append(r"C:\vazus")

DB_PATH = os.getenv("VAZUS_DB_PATH", r"C:\vazus\services\memory\vazus.db")

# Default seed schedule for RTU MIREA group ИКБО-01-23 when offline and cache empty
DEFAULT_SEED_SCHEDULE = [
    ("Понедельник", "09:00 - 10:30", "Высшая математика", "Лекция", "А-418", "проф. Смирнов А.В."),
    ("Понедельник", "10:40 - 12:10", "Программирование на Python", "Практика", "Б-210", "доц. Ковалев Д.М."),
    ("Вторник", "10:40 - 12:10", "Архитектура ЭВМ", "Лекция", "А-302", "проф. Васильев Е.П."),
    ("Вторник", "12:40 - 14:10", "Архитектура ЭВМ", "Лабораторная работа", "В-112", "асс. Николаев С.А."),
    ("Среда", "09:00 - 10:30", "Базы данных", "Лекция", "А-418", "доц. Сидоров П.И."),
    ("Среда", "10:40 - 12:10", "Базы данных", "Лабораторная работа", "Б-105", "доц. Сидоров П.И."),
    ("Четверг", "12:40 - 14:10", "Физика", "Лекция", "А-201", "проф. Морозов И.Г."),
    ("Четверг", "14:20 - 15:50", "Иностранный язык", "Практика", "Г-304", "ст.пр. Федорова Е.А."),
    ("Пятница", "09:00 - 10:30", "Операционные системы", "Лекция", "А-418", "проф. Григорьев В.М."),
    ("Пятница", "10:40 - 12:10", "Операционные системы", "Лабораторная работа", "В-208", "асс. Романов А.С."),
    ("Суббота", "09:00 - 10:30", "Физическая культура", "Практика", "Спорткомплекс", "преп. Захаров О.В.")
]

# Default seed academic milestones for RTU MIREA
DEFAULT_SEED_MILESTONES = [
    ("Программирование на Python", "Защита лабораторной работы №3", "lab_defense", "2026-08-10", "PENDING", "Реализация декораторов и асинхронных генераторов"),
    ("Общий рейтинг МИРЭА", "Промежуточная аттестация №1 (8 неделя)", "attestation", "2026-08-15", "PENDING", "Контрольная точка БРС по всем дисциплинам"),
    ("Базы данных", "Зачёт по Базам данных", "credit", "2026-08-20", "PENDING", "Защита ER-диаграмм и SQL-запросов в SQLite/PostgreSQL"),
    ("Высшая математика", "Экзамен по Высшей математике", "exam", "2026-08-25", "PENDING", "Интегральное исчисление и дифференциальные уравнения"),
    ("Архитектура ЭВМ", "Курсовой проект по Архитектуре ЭВМ", "coursework", "2026-08-28", "PENDING", "Моделирование процессора в Logisim / VHDL")
]


def init_mirea_db(db_path=None):
    """Initializes mirea_schedule and mirea_milestones tables in vazus.db."""
    target_db = db_path if db_path is not None else os.getenv("VAZUS_DB_PATH", DB_PATH)
    conn = None
    try:
        conn = sqlite3.connect(target_db)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS mirea_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT,
            weekday TEXT,
            lesson_time TEXT,
            subject TEXT,
            lesson_type TEXT,
            classroom TEXT,
            teacher TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS mirea_milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT,
            subject TEXT,
            milestone_name TEXT,
            milestone_type TEXT,
            due_date TEXT,
            status TEXT,
            description TEXT
        )
        """)
        conn.commit()
    except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
        print(f"⚠️ [MIREA DB Notice] Database init error: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception as exc:
                logger.debug("Failed closing DB in init_mirea_db: %s", exc)


class MireaStudentManager:
    def __init__(self, group_name="ИКБО-01-23", db_path=None):
        self.group_name = group_name
        self.db_path = db_path if db_path is not None else os.getenv("VAZUS_DB_PATH", DB_PATH)
        init_mirea_db(self.db_path)
        self._ensure_seed_data()

    def _ensure_seed_data(self):
        """Seeds default schedule and academic milestones into SQLite if empty."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            
            # Check schedule
            count_sched = cur.execute("SELECT COUNT(*) FROM mirea_schedule WHERE group_name=?", (self.group_name,)).fetchone()[0]
            if count_sched == 0:
                for item in DEFAULT_SEED_SCHEDULE:
                    cur.execute("""
                    INSERT INTO mirea_schedule (group_name, weekday, lesson_time, subject, lesson_type, classroom, teacher)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (self.group_name, item[0], item[1], item[2], item[3], item[4], item[5]))

            # Check milestones
            count_milestones = cur.execute("SELECT COUNT(*) FROM mirea_milestones WHERE group_name=?", (self.group_name,)).fetchone()[0]
            if count_milestones == 0:
                for m in DEFAULT_SEED_MILESTONES:
                    cur.execute("""
                    INSERT INTO mirea_milestones (group_name, subject, milestone_name, milestone_type, due_date, status, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (self.group_name, m[0], m[1], m[2], m[3], m[4], m[5]))

            conn.commit()
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            print(f"⚠️ [MIREA DB Notice] Database seed error: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    logger.debug("Failed closing DB in _ensure_seed_data: %s", exc)

    def fetch_mirea_schedule_online(self):
        """
        Fetches schedule from RTU MIREA Schedule API (api.mirea.ninja / LKS).
        Encodes Cyrillic group name via urllib.parse.quote to avoid UnicodeEncodeError.
        """
        print(f"🎓 [MIREA Manager] Fetching online schedule for group {self.group_name}...")
        encoded_group = urllib.parse.quote(self.group_name)
        url = f"https://api.mirea.ninja/v1/schedule/{encoded_group}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'VazusOS/1.0'})
            res = urllib.request.urlopen(req, timeout=5)
            data = json.loads(res.read().decode('utf-8'))
            print("✅ MIREA API Schedule successfully fetched!")
            parsed_schedule = self._parse_api_response(data)
            if parsed_schedule:
                self.save_schedule_to_cache(self.group_name, parsed_schedule)
                return self.get_cached_schedule()
            return self.get_cached_schedule()
        except Exception as e:
            print(f"MIREA API notice (using local cache): {e}")
            return self.get_cached_schedule()

    def _parse_api_response(self, raw_data):
        """Parses API response dictionary into standardized lesson tuples."""
        lessons = []
        if isinstance(raw_data, dict) and "schedule" in raw_data:
            sched_dict = raw_data.get("schedule", {})
            for day, day_lessons in sched_dict.items():
                if isinstance(day_lessons, list):
                    for item in day_lessons:
                        lessons.append((
                            day,
                            item.get("time", "09:00 - 10:30"),
                            item.get("name", item.get("subject", "Неизвестный предмет")),
                            item.get("type", "Практика"),
                            item.get("room", item.get("classroom", "Онлайн")),
                            item.get("teacher", "Преподаватель кафедра")
                        ))
        return lessons

    def save_schedule_to_cache(self, group_name, schedule_items):
        """Saves schedule items to SQLite mirea_schedule table."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("DELETE FROM mirea_schedule WHERE group_name=?", (group_name,))
            for item in schedule_items:
                cur.execute("""
                INSERT INTO mirea_schedule (group_name, weekday, lesson_time, subject, lesson_type, classroom, teacher)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (group_name, item[0], item[1], item[2], item[3], item[4], item[5]))
            conn.commit()
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            print(f"⚠️ [MIREA DB Notice] Failed to save schedule to cache: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    logger.debug("Failed closing DB in save_schedule_to_cache: %s", exc)

    def get_cached_schedule(self):
        """Returns schedule cached in SQLite as list of dicts. Falls back to memory seed schedule if DB error occurs."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            rows = cur.execute(
                "SELECT weekday, lesson_time, subject, lesson_type, classroom, teacher FROM mirea_schedule WHERE group_name=?",
                (self.group_name,)
            ).fetchall()

            result = []
            for r in rows:
                result.append({
                    "weekday": r[0],
                    "lesson_time": r[1],
                    "subject": r[2],
                    "lesson_type": r[3],
                    "classroom": r[4],
                    "teacher": r[5]
                })
            return result
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            print(f"⚠️ [MIREA DB Notice] Database error in get_cached_schedule, falling back to memory seed schedule: {e}")
            return [
                {
                    "weekday": item[0],
                    "lesson_time": item[1],
                    "subject": item[2],
                    "lesson_type": item[3],
                    "classroom": item[4],
                    "teacher": item[5]
                }
                for item in DEFAULT_SEED_SCHEDULE
            ]
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    logger.debug("Failed closing DB in get_cached_schedule: %s", exc)

    def get_schedule(self, group_name=None):
        """
        Unified interface method specified in PROJECT.md.
        Returns complete schedule dict for group.
        """
        if group_name:
            self.group_name = group_name

        raw_sched = self.fetch_mirea_schedule_online()
        if isinstance(raw_sched, list):
            schedule_list = raw_sched
        else:
            schedule_list = self.get_cached_schedule()

        return {
            "group_name": self.group_name,
            "status": "SUCCESS",
            "count": len(schedule_list),
            "schedule": schedule_list,
            "milestones": self.get_academic_milestones()
        }

    def get_academic_milestones(self, group_name=None, status_filter=None):
        """Retrieves academic milestones for group from SQLite. Falls back to memory seed milestones if DB error occurs."""
        target_group = group_name or self.group_name
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            if status_filter:
                rows = cur.execute(
                    "SELECT id, subject, milestone_name, milestone_type, due_date, status, description FROM mirea_milestones WHERE group_name=? AND status=? ORDER BY due_date ASC",
                    (target_group, status_filter)
                ).fetchall()
            else:
                rows = cur.execute(
                    "SELECT id, subject, milestone_name, milestone_type, due_date, status, description FROM mirea_milestones WHERE group_name=? ORDER BY due_date ASC",
                    (target_group,)
                ).fetchall()

            milestones = []
            for r in rows:
                milestones.append({
                    "id": r[0],
                    "subject": r[1],
                    "milestone_name": r[2],
                    "milestone_type": r[3],
                    "due_date": r[4],
                    "status": r[5],
                    "description": r[6]
                })
            return milestones
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            print(f"⚠️ [MIREA DB Notice] Database error in get_academic_milestones, falling back to memory seed milestones: {e}")
            fallback = []
            for idx, m in enumerate(DEFAULT_SEED_MILESTONES, 1):
                if status_filter and m[4] != status_filter:
                    continue
                fallback.append({
                    "id": idx,
                    "subject": m[0],
                    "milestone_name": m[1],
                    "milestone_type": m[2],
                    "due_date": m[3],
                    "status": m[4],
                    "description": m[5]
                })
            return fallback
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    logger.debug("Failed closing DB in get_academic_milestones: %s", exc)

    def add_academic_milestone(self, subject, milestone_name, milestone_type, due_date, *, group_name=None, status="PENDING", description=""):
        """Adds a new academic milestone."""
        target_group = group_name or self.group_name
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO mirea_milestones (group_name, subject, milestone_name, milestone_type, due_date, status, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (target_group, subject, milestone_name, milestone_type, due_date, status, description))
            conn.commit()
            return cur.lastrowid
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            print(f"⚠️ [MIREA DB Notice] Database error in add_academic_milestone: {e}")
            return -1
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    logger.debug("Failed closing DB in add_academic_milestone: %s", exc)

    def update_milestone_status(self, milestone_id, status):
        """Updates milestone status ('PENDING', 'COMPLETED', 'OVERDUE')."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("UPDATE mirea_milestones SET status=? WHERE id=?", (status, milestone_id))
            conn.commit()
            return True
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            print(f"⚠️ [MIREA DB Notice] Database error in update_milestone_status: {e}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    logger.debug("Failed closing DB in update_milestone_status: %s", exc)

    def generate_study_recommendation(self, readiness_score=75.0):
        """
        Integrates R1 Biometric Readiness Score into R5 RTU MIREA Academic Study Recommendation.
        - High readiness (>= 75): High-intensity exam/lab prep for urgent milestones.
        - Moderate readiness (50-74): Standard practice and lecture review.
        - Low readiness (< 50): Light revision with mandatory rest/recovery windows.
        """
        score = float(readiness_score) if readiness_score is not None else 75.0
        milestones = self.get_academic_milestones(status_filter="PENDING")
        schedule = self.get_cached_schedule()

        if score >= 75.0:
            intensity = "HIGH"
            recommendation = (
                f"High Readiness Score ({score:.1f}/100). "
                f"Optimal physiological capacity for intensive exam prep and lab defenses ({len(milestones)} pending milestones)."
            )
            suggested_duration_hours = 4.0
        elif score >= 50.0:
            intensity = "MODERATE"
            recommendation = (
                f"Moderate Readiness Score ({score:.1f}/100). "
                f"Balanced study mode for standard lecture review and practice assignments."
            )
            suggested_duration_hours = 2.5
        else:
            intensity = "LOW"
            recommendation = (
                f"Low Readiness Score ({score:.1f}/100). "
                f"Reduced cognitive load recommended. Focus on light review and prioritize sleep recovery."
            )
            suggested_duration_hours = 1.0

        return {
            "group_name": self.group_name,
            "readiness_score": score,
            "study_intensity": intensity,
            "suggested_duration_hours": suggested_duration_hours,
            "pending_milestones_count": len(milestones),
            "recommendation": recommendation,
            "schedule_summary": {
                "total_classes": len(schedule),
                "upcoming_milestones": milestones[:3]
            }
        }



if __name__ == '__main__':
    mgr = MireaStudentManager("ИКБО-01-23")
    sched = mgr.get_schedule()
    print("=" * 60)
    print(f"🎓 RTU MIREA Schedule Report for Group: {sched['group_name']}")
    print(f"Status: {sched['status']} | Lessons Count: {sched['count']}")
    print("=" * 60)
    for idx, item in enumerate(sched['schedule'], 1):
        print(f"{idx:2d}. [{item['weekday']}] {item['lesson_time']} | {item['subject']} ({item['lesson_type']}) - {item['classroom']} ({item['teacher']})")
    
    print("\n" + "=" * 60)
    print("📌 Academic Milestones:")
    print("=" * 60)
    for m in sched['milestones']:
        print(f"  • [{m['due_date']}] {m['subject']}: {m['milestone_name']} [{m['status']}] - {m['description']}")
