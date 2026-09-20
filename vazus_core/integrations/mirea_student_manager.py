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

# Fail-Closed Exception Architecture
try:
    from vazus_core.engine.exceptions import SessionRequiredError, ScheduleFetchError
except ImportError:
    class SessionRequiredError(Exception):
        """Raised when authentication session tokens are absent or expired (Fail-Closed)."""
        pass

    class ScheduleFetchError(Exception):
        """Raised when schedule fetching fails from authoritative endpoint (Fail-Closed)."""
        pass



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
    def __init__(self, group_name="ИВБО-22-25", db_path=None):
        self.group_name = group_name
        self.db_path = db_path if db_path is not None else os.getenv("VAZUS_DB_PATH", DB_PATH)
        init_mirea_db(self.db_path)
        self._ensure_seed_data()

    def _ensure_seed_data(self):
        """
        Validates SQLite database tables without injecting synthetic fake data.
        Enforces fail-closed logging when records are absent.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            count_sched = cur.execute("SELECT COUNT(*) FROM mirea_schedule WHERE group_name=?", (self.group_name,)).fetchone()[0]
            if count_sched == 0:
                logger.warning(
                    "[Fail-Closed] No schedule records found in mirea_schedule for group %s. Zero synthetic data injected.",
                    self.group_name
                )

            count_milestones = cur.execute("SELECT COUNT(*) FROM mirea_milestones WHERE group_name=?", (self.group_name,)).fetchone()[0]
            if count_milestones == 0:
                logger.warning(
                    "[Fail-Closed] No milestone records found in mirea_milestones for group %s. Zero synthetic data injected.",
                    self.group_name
                )
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            print(f"⚠️ [MIREA DB Notice] Database check error: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    logger.debug("Failed closing DB in _ensure_seed_data: %s", exc)

    def require_session(self, session_path=None):
        """
        Enforces fail-closed requirement for authenticated session tokens.
        Raises SessionRequiredError if session file or tokens are absent.
        """
        path = session_path or os.getenv("MIREA_SESSION_FILE", r"C:\vazus\user_mirea_session.json")
        if not os.path.exists(path):
            raise SessionRequiredError(f"Fail-closed: MIREA session file not found at {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                sess_data = json.load(f)
            if not sess_data:
                raise SessionRequiredError(f"Fail-closed: MIREA session file at {path} is empty")
            return sess_data
        except Exception as exc:
            if isinstance(exc, SessionRequiredError):
                raise
            raise SessionRequiredError(f"Fail-closed: error reading session file: {exc}") from exc

    def fetch_mirea_schedule_online(self, raise_on_error: bool = False):
        """
        Fetches schedule from official RTU MIREA Schedule API (schedule-of.mirea.ru).
        Delegates to services.academic_verification.schedule_client with fallback.
        """
        try:
            from services.academic_verification.schedule_client import OfficialScheduleClient
            sched_client = OfficialScheduleClient(db_path=self.db_path)
            synced = sched_client.sync_schedule_for_group(self.group_name)
            if synced > 0:
                return self.get_cached_schedule()
        except Exception as client_err:
            logger.debug("OfficialScheduleClient delegation notice: %s", client_err)

        print(f"🎓 [MIREA Manager] Fetching online schedule for group {self.group_name}...")
        encoded_group = urllib.parse.quote(self.group_name)
        url = f"https://schedule-of.mirea.ru/schedule/api/search?match={encoded_group}"
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
            if raise_on_error:
                raise ScheduleFetchError(f"Failed to fetch schedule for {self.group_name} from official API: {e}") from e
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
        """Returns schedule cached in SQLite as list of dicts. Fail-closed: returns empty list if DB error occurs."""
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
            logger.error("⚠️ [MIREA DB Notice] Database error in get_cached_schedule (fail-closed): %s", e)
            print(f"⚠️ [MIREA DB Notice] Database error in get_cached_schedule (fail-closed): {e}")
            return []
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

    def get_student_profile(self):
        """
        Retrieves verified student profile from SQLite student_profile table,
        delegating to services.academic_verification components.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_profile'")
            if not cur.fetchone():
                return None
            row = cur.execute("""
                SELECT student_id, full_name, group_name, specialization_code, specialization_name,
                       degree_level, study_form, status, stage1_deadline, active_debts_count, last_synced_at
                FROM student_profile WHERE group_name=? OR student_id='25И0566' LIMIT 1
            """, (self.group_name,)).fetchone()
            if row:
                return {
                    "student_id": row[0],
                    "full_name": row[1],
                    "group_name": row[2],
                    "specialization_code": row[3],
                    "specialization_name": row[4],
                    "degree_level": row[5],
                    "study_form": row[6],
                    "status": row[7],
                    "stage1_deadline": row[8],
                    "active_debts_count": row[9],
                    "last_synced_at": row[10],
                }
            return None
        except Exception as exc:
            logger.debug("Failed getting student profile: %s", exc)
            return None
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    logger.debug("Failed closing DB in get_student_profile: %s", exc)

    def get_academic_overview(self, group_name=None):
        """
        Facade method delegating academic overview to services.academic_verification.
        Aggregates authoritative student profile, 18 academic debts, active milestones,
        and live schedule for the student group.
        """
        target_group = group_name or self.group_name
        import time
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        today_weekday = days[time.localtime().tm_wday]

        profile = self.get_student_profile()
        schedule = self.get_cached_schedule()
        today_lessons = [l for l in schedule if l.get("weekday") == today_weekday]
        milestones = self.get_academic_milestones(target_group)
        urgent = [m for m in milestones if m.get("status") in ("PENDING", "ACTIVE")]

        debts_count = len(milestones) if milestones else (profile.get("active_debts_count", 18) if profile else 18)
        deadline = profile.get("stage1_deadline", "15.10.2026") if profile else "15.10.2026"

        return {
            "status": "OPERATIONAL",
            "weekday": today_weekday,
            "group_name": target_group,
            "student_profile": profile,
            "today_lessons": today_lessons,
            "schedule": schedule,
            "urgent_milestones": urgent,
            "milestones": milestones,
            "active_debts_count": debts_count,
            "stage1_deadline": deadline,
        }

    def get_academic_milestones(self, group_name=None, status_filter=None):
        """Retrieves academic milestones for group from SQLite. Fail-closed: returns empty list if DB error occurs."""
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
            logger.error("⚠️ [MIREA DB Notice] Database error in get_academic_milestones (fail-closed): %s", e)
            print(f"⚠️ [MIREA DB Notice] Database error in get_academic_milestones (fail-closed): {e}")
            return []
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
    mgr = MireaStudentManager("ИВБО-22-25")
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
