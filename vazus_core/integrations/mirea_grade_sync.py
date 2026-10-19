"""
mirea_grade_sync.py — Automated Academic Grade & Milestone Synchronizer
Connects vazus.db (mirea_milestones, user_liabilities) with STUDY.md and Moodle.
Enables automated grade updates, milestone completion tracking, and markdown recompilation.
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

DB_PATH = "/home/tarhes/Проекты/vazus/services/memory/vazus.db"
STUDY_MD_PATH = "/home/tarhes/Проекты/vazus/services/memory/STUDY.md"


class MireaGradeSync:
    """
    Synchronizes academic performance, milestones, and grades across
    vazus.db and STUDY.md without manual data desynchronization.
    """

    def __init__(self, db_path: str = DB_PATH, study_md_path: str = STUDY_MD_PATH) -> None:
        self.db_path = db_path
        self.study_md_path = study_md_path

    def get_active_milestones(self) -> List[Dict[str, Any]]:
        """Retrieves all academic milestones currently recorded in vazus.db."""
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, subject, milestone_name, milestone_type, due_date, status, description, stage1_deadline, moodle_course_id
            FROM mirea_milestones
            ORDER BY id ASC
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        return rows

    def update_grade(
        self,
        subject: str,
        milestone_name: Optional[str] = None,
        new_status: str = "Сдано",
        grade_note: Optional[str] = None,
        moodle_course_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Updates milestone status/grade in vazus.db and recompiles STUDY.md.
        """
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()

        # Find matching milestone
        query = "SELECT id, subject, milestone_name, status FROM mirea_milestones WHERE subject LIKE ?"
        params: List[Any] = [f"%{subject}%"]

        if milestone_name:
            query += " AND milestone_name LIKE ?"
            params.append(f"%{milestone_name}%")
        if moodle_course_id:
            query += " AND moodle_course_id = ?"
            params.append(str(moodle_course_id))

        cur.execute(query, params)
        matches = cur.fetchall()

        if not matches:
            con.close()
            return {"success": False, "error": f"No milestone found matching subject '{subject}'"}

        updated_ids = []
        now_iso = datetime.now().isoformat()

        for mid, subj, mname, old_status in matches:
            desc_update = f" (Оценка/статус: {grade_note})" if grade_note else ""
            cur.execute(
                """
                UPDATE mirea_milestones
                SET status = ?, description = description || ?, updated_at = ?
                WHERE id = ?
                """,
                (new_status, desc_update, now_iso, mid),
            )
            updated_ids.append(mid)

        con.commit()
        con.close()

        # Recompile STUDY.md to maintain SSOT
        recompile_ok = self.recompile_study_md()

        return {
            "success": True,
            "updated_count": len(updated_ids),
            "updated_ids": updated_ids,
            "new_status": new_status,
            "study_md_recompiled": recompile_ok,
        }

    def recompile_study_md(self) -> bool:
        """
        Recompiles the milestone markdown table in STUDY.md directly from vazus.db.
        Ensures 100% synchronization between database truth and markdown wiki.
        """
        if not os.path.exists(self.study_md_path):
            return False

        try:
            milestones = self.get_active_milestones()
            active_count = sum(1 for m in milestones if m["status"] not in ("Сдано", "Зачтено", "Готово к сдаче"))

            # Build markdown table rows
            table_lines = [
                "| № | Дисциплина | Тип | Moodle Course ID | Дедлайн | Статус | Описание |",
                "|---|---|---|---|---|---|---|",
            ]

            for i, m in enumerate(milestones, 1):
                status_icon = "✅" if m["status"] in ("Сдано", "Зачтено", "Готово к сдаче") else "⏳"
                moodle_link = f"[{m['moodle_course_id']}](https://online-edu.mirea.ru/course/view.php?id={m['moodle_course_id']})" if m["moodle_course_id"] else "-"
                row = f"| {i} | {m['subject']} | {m['milestone_type'] or '-'} | {moodle_link} | {m['due_date'] or '15.10.2026'} | {status_icon} {m['status']} | {m['description'] or '-'} |"
                table_lines.append(row)

            new_table_str = "\n".join(table_lines)

            with open(self.study_md_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Replace table between section marker and schedule
            pattern = re.compile(
                r"(## 📌.*?Академических задолженностей к закрытию\n\n)(.*?)(?=\n---\n\n## 📅|\Z)",
                re.DOTALL,
            )

            if pattern.search(content):
                updated_content = pattern.sub(rf"\1{new_table_str}\n", content)
                with open(self.study_md_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)
                return True

            return False
        except Exception:
            return False
