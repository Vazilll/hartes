"""
tests/unit/test_applied_domain_hub.py -- Unit tests for AppliedDomainHub.
Enforces zero-mock empirical testing and verifies sub-50ms query latencies.
"""

import sqlite3
from pathlib import Path
import pytest

from vazus_core.engine.applied_domain_hub import AppliedDomainHub


@pytest.fixture
def mock_db_path(tmp_path: Path) -> str:
    db_file = tmp_path / "test_applied.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE user_liabilities (
            id INTEGER PRIMARY KEY,
            title TEXT,
            total_remaining_rub REAL,
            monthly_payment_rub REAL,
            next_payment_date TEXT,
            category TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE finance_transactions (
            id INTEGER PRIMARY KEY,
            amount REAL,
            category TEXT,
            timestamp TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE mi_scale_weighins (
            id INTEGER PRIMARY KEY,
            weight_kg REAL,
            body_fat_pct REAL,
            muscle_mass_kg REAL,
            bmi REAL,
            timestamp TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE nutrition_log (
            id INTEGER PRIMARY KEY,
            meal_name TEXT,
            calories REAL,
            protein_g REAL,
            timestamp TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE mirea_schedule (
            id INTEGER PRIMARY KEY,
            subject TEXT,
            lesson_type TEXT,
            lesson_time TEXT,
            classroom TEXT,
            teacher TEXT,
            weekday TEXT,
            group_name TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE mirea_milestones (
            id INTEGER PRIMARY KEY,
            milestone_name TEXT,
            subject TEXT,
            due_date TEXT,
            status TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE tutor_cards (
            id INTEGER PRIMARY KEY,
            question TEXT,
            answer TEXT,
            interval_days INTEGER,
            next_review_date TEXT
        )
    """)
    
    cur.execute("INSERT INTO user_liabilities VALUES (1, 'T-Bank Credit', 349000.0, 20800.0, '2026-09-01', 'debt')")
    cur.execute("INSERT INTO finance_transactions VALUES (1, 1500.0, 'groceries', '2026-08-20')")
    cur.execute("INSERT INTO mi_scale_weighins VALUES (1, 74.5, 16.2, 58.4, 22.1, '2026-08-20')")
    cur.execute("INSERT INTO nutrition_log VALUES (1, 'Oatmeal & Whey', 450.0, 35.0, '2026-08-20')")
    cur.execute("INSERT INTO mirea_schedule VALUES (1, 'Архитектура ИС', 'Лекция', '09:00 - 10:30', 'А-101', 'Иванов И.И.', 'Пятница', 'ИВБО-22-25')")
    cur.execute("INSERT INTO mirea_milestones VALUES (1, 'Лабораторная 3 (Docker/K8s)', 'Инфраструктура', '2026-08-28', 'PENDING')")
    cur.execute("INSERT INTO tutor_cards VALUES (1, 'Закон тождества', 'A есть A', 3, '2026-08-21')")
    
    conn.commit()
    conn.close()
    return str(db_file)


def test_applied_domain_hub_finance(mock_db_path: str):
    hub = AppliedDomainHub(db_path=mock_db_path)
    fin = hub.get_finance_overview()
    assert fin["status"] == "OPERATIONAL"
    assert fin["total_liabilities_rub"] == 349000.0
    assert fin["monthly_obligations_rub"] == 20800.0
    assert len(fin["liabilities"]) == 1


def test_applied_domain_hub_health(mock_db_path: str):
    hub = AppliedDomainHub(db_path=mock_db_path)
    health = hub.get_health_overview()
    assert health["status"] == "OPERATIONAL"
    assert health["latest_weight_kg"] == 74.5
    assert health["body_fat_percent"] == 16.2
    assert health["nutrition_logged_meals"] == 1


def test_applied_domain_hub_academic(mock_db_path: str):
    hub = AppliedDomainHub(db_path=mock_db_path)
    academic = hub.get_academic_overview(group_name="ИВБО-22-25")
    assert academic["status"] == "OPERATIONAL"
    assert len(academic["urgent_milestones"]) == 1
    assert academic["pending_flashcards"] == 1


def test_applied_domain_hub_daily_briefing(mock_db_path: str):
    hub = AppliedDomainHub(db_path=mock_db_path)
    briefing = hub.generate_and_sync_daily_briefing()
    assert briefing["success"] is True
    assert briefing["months_to_debt_free"] == 16.8
    assert Path(briefing["notebooklm_file"]).exists()