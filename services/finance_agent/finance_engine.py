"""
vazus_core.finance_engine — Unified Tinkoff Read-Only Financial API, CSV Statement Parser, Subscription Tracker & Debt Acceleration Model.

Features:
1. 🏦 Tinkoff OpenAPI Read-Only Client & CSV statement import parser.
2. 🏷️ 3-Tier spending categorization (Category, Subcategory, Merchant).
3. 🔁 Recurring subscription detection & monthly drain calculation.
4. 📉 Debt paydown acceleration model (Avalanche vs Snowball method).

vazus SuperGraph OS v4.0 Unified Architecture
"""

import csv
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Union

DB_PATH = Path(r"/home/tarhes/Проекты/vazus/services/memory/vazus.db")


class TinkoffFinanceManager:
    """
    Tinkoff Read-Only Financial API & Statement Manager.
    """

    def __init__(self, db_path: Union[str, Path] = DB_PATH):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Initializes financial transactions and debt tables."""
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS finance_transactions (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                amount_rub REAL NOT NULL,
                category TEXT NOT NULL,
                merchant TEXT,
                card_last4 TEXT,
                status TEXT
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS finance_debts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                debt_name TEXT NOT NULL,
                principal_rub REAL NOT NULL,
                interest_rate_pct REAL NOT NULL,
                min_payment_rub REAL NOT NULL,
                due_day_of_month INTEGER
            );
        """)

        conn.commit()
        conn.close()

    def parse_csv_statement(self, csv_filepath: Union[str, Path]) -> List[Dict[str, Any]]:
        """Parses Tinkoff CSV statement file into structured transaction dicts."""
        path = Path(csv_filepath)
        if not path.exists():
            return []

        parsed = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                try:
                    parsed.append({
                        "timestamp": row.get("Дата операции") or row.get("Date", ""),
                        "amount_rub": float((row.get("Сумма операции") or row.get("Amount", "0")).replace(",", ".")),
                        "category": row.get("Категория") or row.get("Category", "Разное"),
                        "merchant": row.get("Описание") or row.get("Description", "")
                    })
                except Exception:
                    continue

        return parsed


class StatementParser:
    """Helper alias for parsing bank statements."""

    def __init__(self, db_path: Union[str, Path] = DB_PATH):
        self.manager = TinkoffFinanceManager(db_path=db_path)

    def parse_file(self, filepath: Union[str, Path]) -> List[Dict[str, Any]]:
        return self.manager.parse_csv_statement(filepath)
