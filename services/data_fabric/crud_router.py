"""
services.data_fabric.crud_router
================================
Auto-CRUD and Academic Data Router for Vazus Data Fabric.
Connects SQLite vazus.db to REST consumers (Academic Dashboard, VAE Preview, fast MCP).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from services.data_fabric.entity_schema import AcademicDebtEntity, ScheduleSlotEntity
from services.data_fabric.rls import RowLevelSecurity

router = APIRouter(prefix="/api", tags=["DataFabric"])
_DEFAULT_DB = Path(__file__).resolve().parents[2] / "services" / "memory" / "vazus.db"
DB_PATH = Path(os.getenv("VAZUS_DB_PATH", str(_DEFAULT_DB)))


def get_db_connection() -> sqlite3.Connection:
    target = Path(os.getenv("VAZUS_DB_PATH", str(DB_PATH)))
    conn = sqlite3.connect(str(target), timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/academic/debts", response_model=List[Dict[str, Any]])
def get_academic_debts():
    """
    Returns all 18 RTU MIREA academic debt milestones dynamically from vazus.db.
    Maps mirea_milestones table to Academic Dashboard schema.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        query = RowLevelSecurity.filter_query_by_tenant(
            "mirea_milestones",
            """
            SELECT m.id, m.student_id, m.subject, m.milestone_name, m.milestone_type, m.status, 
                   m.stage1_deadline, m.due_date, m.description,
                   COALESCE(s.teacher, 'Кафедра КИТПиПИ') as teacher,
                   COALESCE(s.classroom, 'А-10') as room
            FROM mirea_milestones m
            LEFT JOIN mirea_schedule s ON s.subject = m.subject
            GROUP BY m.id
            ORDER BY m.id ASC
            """
        )
        cur.execute(query)
        rows = cur.fetchall()

        debts = []
        for r in rows:
            rec = dict(r)
            if not RowLevelSecurity.can_read("mirea_milestones", rec, {"student_id": rec.get("student_id", "25И0566")}):
                continue
            status = r["status"]
            # Map canonical status to dashboard styling
            m_type = r["milestone_type"] or "Лабораторная"
            due = r["due_date"] or r["stage1_deadline"] or "15.10.2026"
            debts.append({
                "id": r["id"],
                "subject": r["subject"],
                "teacher": r["teacher"] or "Преподаватель кафедры",
                "type": m_type,
                "room": r["room"] or "А-10",
                "next": f"Дедлайн: {due}",
                "status": status,
                "stage1_deadline": r["stage1_deadline"] or "15.10.2026",
            })
        return debts
    finally:
        conn.close()


@router.get("/academic/schedule", response_model=List[Dict[str, Any]])
def get_academic_schedule():
    """
    Returns current timetable slots from vazus.db mirea_schedule table.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, weekday, lesson_time, subject, lesson_type, classroom, teacher
            FROM mirea_schedule
            ORDER BY id ASC
        """)
        rows = cur.fetchall()

        urgent_subjects: set[str] = set()
        try:
            cur.execute(
                "SELECT DISTINCT subject FROM mirea_milestones WHERE status NOT IN ('Сдано', 'CLOSED')"
            )
            urgent_subjects = {str(r[0]) for r in cur.fetchall() if r[0]}
        except sqlite3.Error:
            pass

        slots = []
        for r in rows:
            ltype = str(r["lesson_type"] or "Занятие")
            subj = str(r["subject"] or "")
            is_urgent = (
                any(k in ltype.lower() for k in ("экзамен", "зачет", "зачёт", "дедлайн", "контрольн"))
                or subj in urgent_subjects
            )
            slots.append({
                "id": r["id"],
                "date": r["weekday"],
                "time": r["lesson_time"],
                "subject": subj,
                "teacher": r["teacher"] or "Преподаватель",
                "room": r["classroom"] or "Ауд.",
                "type": ltype,
                "urgent": is_urgent,
            })
        return slots
    finally:
        conn.close()


@router.get("/academic/stats")
def get_academic_stats():
    """Returns summary debt progress metrics directly from vazus.db."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT status, count(*) FROM mirea_milestones GROUP BY status")
        counts = {r[0]: r[1] for r in cur.fetchall()}
        total = sum(counts.values())
        return {
            "total_debts": total,
            "closed": counts.get("Сдано", 0) + counts.get("CLOSED", 0),
            "ready": counts.get("Готово к сдаче", 0) + counts.get("READY", 0),
            "in_progress": counts.get("В процессе", 0) + counts.get("IN_PROGRESS", 0),
            "pending": counts.get("PENDING", 0),
            "deadline": "15.10.2026",
            "group": "ИВБО-22-25",
            "student_id": "25И0566",
        }
    finally:
        conn.close()
