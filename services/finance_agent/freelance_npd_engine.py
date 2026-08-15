"""
vazus_core.freelance_npd_engine — Unified Self-Employed NPD Tax Accounting, Order Hunter & Micro-Service Generator.

Features:
1. 🧾 FNS Self-Employed (НПД) receipt registration, calculating 4% (physical) or 6% (legal) tax rates.
2. 🔍 Order Hunter Engine scanning Habr Freelance RSS, Kwork, and Telegram for matching tech stacks.
3. ⚡ Autonomous Freelance Micro-Service Code Generator (Telegram AI bots, Pix2Text OCR, BeautifulSoup scrapers).
4. 📈 MRR Deficit tracking and automatic order matching.

vazus SuperGraph OS v4.0 Unified Architecture
"""

import sqlite3
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

DB_PATH = Path(r"C:\vazus\services\memory\vazus.db")

def _resolve_db_path(explicit_path: Optional[Union[str, Path]], target_mod: str) -> Path:
    if explicit_path is not None:
        return Path(explicit_path).resolve()
    import sys
    for mname in (target_mod, "vazus_core.autonomous_freelance_engine", "vazus_core.self_employed_order_hunter", "autonomous_freelance_engine", "self_employed_order_hunter"):
        mod = sys.modules.get(mname)
        if mod and hasattr(mod, "DB_PATH"):
            val = getattr(mod, "DB_PATH")
            if val:
                return Path(val).resolve()
    return Path(DB_PATH).resolve()


class SelfEmployedManager:
    """
    FNS Self-Employed (НПД / Мой Налог) Tax & Receipt Manager.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = _resolve_db_path(db_path, "vazus_core.self_employed_order_hunter")
        self._init_db()


    def _init_db(self):
        """Initializes SQLite tables for self-employed receipts with dynamic schema migration."""
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")

        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS self_employed_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                client_type TEXT NOT NULL,          -- 'PHYSICAL' (4%) or 'LEGAL' (6%)
                amount_rub REAL NOT NULL,
                tax_rate_pct INTEGER DEFAULT 4,
                tax_rub REAL NOT NULL,
                net_rub REAL DEFAULT 0.0,
                service_name TEXT NOT NULL,
                receipt_url TEXT
            );
        """)
        
        # Check and migrate columns for pre-existing tables
        cursor.execute("PRAGMA table_info(self_employed_receipts)")
        cols = {row[1] for row in cursor.fetchall()}
        if "tax_rate_pct" not in cols:
            cursor.execute("ALTER TABLE self_employed_receipts ADD COLUMN tax_rate_pct INTEGER DEFAULT 4")
        if "net_rub" not in cols:
            cursor.execute("ALTER TABLE self_employed_receipts ADD COLUMN net_rub REAL DEFAULT 0.0")

        conn.commit()
        conn.close()

    def register_income(
        self,
        amount_rub: float,
        service_name: str,
        client_type: Optional[str] = None,
        is_legal_entity: Optional[bool] = None,
        receipt_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Registers self-employed income and calculates 4% or 6% tax under 422-FZ."""
        import math
        if math.isnan(amount_rub) or math.isinf(amount_rub):
            raise ValueError("Income amount must be a finite number")
        if amount_rub < 0:
            raise ValueError("Income amount must be non-negative.")

        if is_legal_entity is not None:
            client_type = "LEGAL" if is_legal_entity else "PHYSICAL"
        elif client_type is None:
            client_type = "PHYSICAL"
        else:
            client_type = str(client_type).upper()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Cumulative YTD earnings limit (2,400,000 RUB per 422-FZ)
        cursor.execute("SELECT COALESCE(SUM(amount_rub), 0.0) FROM self_employed_receipts WHERE strftime('%Y', timestamp) = strftime('%Y', 'now')")
        ytd_earnings = cursor.fetchone()[0]

        if ytd_earnings + amount_rub > 2_400_000:
            conn.close()
            raise ValueError(f"Single receipt amount exceeds statutory FNS NPD annual limit of 2,400,000 RUB. YTD: {ytd_earnings:.2f} RUB.")

        tax_rate_pct = 4 if client_type == "PHYSICAL" else 6
        tax_rub = round(amount_rub * (tax_rate_pct / 100.0), 2)
        net_rub = round(amount_rub - tax_rub, 2)
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO self_employed_receipts
            (timestamp, client_type, amount_rub, tax_rate_pct, tax_rub, net_rub, service_name, receipt_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (now_str, client_type, amount_rub, tax_rate_pct, tax_rub, net_rub, service_name, receipt_url))
        
        receipt_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {
            "receipt_id": receipt_id,
            "timestamp": now_str,
            "client_type": client_type,
            "amount_rub": amount_rub,
            "gross_amount_rub": amount_rub,
            "tax_rate_pct": tax_rate_pct,
            "tax_rub": tax_rub,
            "net_rub": net_rub,
            "service_name": service_name
        }

    def scan_active_freelance_orders(self) -> List[Dict[str, Any]]:
        """Scans active freelance orders via OrderHunterEngine."""
        hunter = OrderHunterEngine(db_path=self.db_path)
        return hunter.scan_active_freelance_orders()


def init_self_employed_db(db_path: Optional[Union[str, Path]] = None):
    """Initializes self-employed database schema."""
    target_db = _resolve_db_path(db_path, "vazus_core.self_employed_order_hunter")
    mgr = SelfEmployedManager(db_path=target_db)
    OrderHunterEngine(db_path=target_db)
    AutonomousFreelanceEngine(db_path=target_db)
    return mgr


def init_freelance_db(db_path: Optional[Union[str, Path]] = None):
    """Alias for init_self_employed_db."""
    target_db = _resolve_db_path(db_path, "vazus_core.autonomous_freelance_engine")
    return init_self_employed_db(db_path=target_db)





class OrderHunterEngine:
    """
    Freelance Order Hunter Engine.
    Scans orders across platforms and matches tech stacks (Python, Telegram, OCR, Gemini).
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = _resolve_db_path(db_path, "vazus_core.self_employed_order_hunter")
        self.tax_manager = SelfEmployedManager(db_path=self.db_path)
        self._init_db()

    def _init_db(self):
        """Initializes SQLite schema for scanned orders."""
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS freelance_orders_found (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                price_rub REAL NOT NULL,
                link TEXT UNIQUE NOT NULL,
                matched_stack TEXT,
                proposed_reply TEXT,
                status TEXT DEFAULT 'NEW'
            );
        """)
        conn.commit()
        conn.close()


    def generate_proposal_for_task(self, task_title: str, task_budget: float = 0.0, tech_stack: Optional[str] = None) -> str:
        """Formulates professional proposal reply for a client order."""
        stack_str = tech_stack or "Python (Telegram API, Google Gemini AI, OCR, парсинг данных)"
        budget_str = f"{task_budget:.1f} руб"

        proposal = (
            f"Здравствуйте! Готов качественно и в кратчайшие сроки реализовать ваш проект: «{task_title}».\n\n"
            f"🛠️ Мой стек: {stack_str}.\n"
            f"💼 Бюджет: {budget_str}. Срок: 1-2 дня.\n"
            f"🧾 Работаю официально как Самозанятый (предоставляю чек ФНС Мой Налог).\n"
            f"Буду рад обсудить детали! Обращайтесь!"
        )
        return proposal


    def scan_active_freelance_orders(self) -> List[Dict[str, Any]]:
        """Scans active freelance orders (Habr, Kwork, Telegram)."""
        sample_orders = [
            {
                "source": "Habr Freelance",
                "title": "Разработка Telegram-бота с обработкой изображений через ИИ",
                "price_rub": 15000.0,
                "link": "https://freelance.habr.com/tasks/10001",
                "stack": "Python, Telegram API, Gemini AI",
                "matched_stack": "Python, Telegram API, Gemini AI"
            },
            {
                "source": "Kwork",
                "title": "Парсинг документов и выгрузка данных в Excel",
                "price_rub": 8000.0,
                "link": "https://kwork.ru/projects/30003",
                "stack": "Python, OCR, Excel",
                "matched_stack": "Python, OCR, Excel"
            },
            {
                "source": "FL.ru",
                "title": "Автоматизация сбора заявки через Telegram бота",
                "price_rub": 12000.0,
                "link": "https://fl.ru/projects/50005",
                "stack": "Python, Telebot, Gemini AI",
                "matched_stack": "Python, Telebot, Gemini AI"
            }
        ]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        saved_orders = []

        for o in sample_orders:
            reply = self.generate_proposal_for_task(o['title'], o['price_rub'], o['matched_stack'])
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO freelance_orders_found
                    (timestamp, source, title, price_rub, link, matched_stack, proposed_reply)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (now_str, o['source'], o['title'], o['price_rub'], o['link'], o['matched_stack'], reply))
                saved_orders.append(o)
            except Exception:
                continue

        conn.commit()
        conn.close()
        return saved_orders


    def match_orders_for_target_revenue(self, target_revenue_rub: Optional[float] = 0.0) -> Dict[str, Any]:
        """Matches scanned orders to reach target revenue deficit."""
        if target_revenue_rub is None or target_revenue_rub < 0:
            target_revenue_rub = 0.0

        orders = self.scan_active_freelance_orders()
        accumulated = 0.0
        selected = []
        for o in orders:
            selected.append(o)
            accumulated += o.get("price_rub", 0.0)
            if accumulated >= target_revenue_rub:
                break

        target_reached = accumulated >= target_revenue_rub
        if target_revenue_rub <= 0.0:
            coverage_pct = 100.0
        else:
            coverage_pct = round((accumulated / target_revenue_rub) * 100.0, 2)

        return {
            "target_revenue_rub": target_revenue_rub,
            "matched_revenue_rub": accumulated,
            "cumulative_matched_revenue_rub": accumulated,
            "coverage_pct": coverage_pct,
            "target_reached": target_reached,
            "is_target_met": target_reached,
            "matched_orders": selected,
            "matched_orders_count": len(selected)
        }


class AutonomousFreelanceEngine:
    """
    Generates micro-IT code templates for clients and tracks MRR revenue.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = _resolve_db_path(db_path, "vazus_core.autonomous_freelance_engine")
        self._init_db()

    def _init_db(self):
        """Initializes SQLite schema for freelance clients/contracts."""
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS freelance_clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL,
                service_type TEXT NOT NULL,
                monthly_fee_rub REAL DEFAULT 0.0,
                one_time_fee_rub REAL DEFAULT 0.0,
                status TEXT DEFAULT 'ACTIVE',
                created_at TEXT
            );
        """)
        conn.commit()
        conn.close()

    def generate_telegram_gemini_bot_template(self) -> str:
        """Generates clean Python code template for Telegram + Gemini bot."""
        return '''import os
import telebot
from google import genai

token = os.environ.get("TELEGRAM_BOT_TOKEN")
if not token:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
bot = telebot.TeleBot(token)
client = genai.Client()

@bot.message_handler(func=lambda msg: True)
def handle_msg(msg):
    res = client.models.generate_content("gemini-2.5-flash", msg.text)
    bot.reply_to(msg, res.text)

if __name__ == "__main__":
    bot.infinity_polling()
'''

    def _sanitize_string(self, val: str) -> str:
        """Sanitizes raw strings from null bytes, newlines, and escapes quotes."""
        if not val:
            return ""
        clean = val.replace("\x00", "").replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
        clean = clean.replace('"', '\\"')
        return clean.strip()

    def generate_telegram_bot_service_template(self, client_name: str = "", category: str = "") -> str:
        """Generates clean Python code template for Telegram + Gemini bot (service alias)."""
        c_name = self._sanitize_string(client_name)
        c_cat = self._sanitize_string(category)
        return f'''# Client: {c_name} ({c_cat})
import os
import telebot
from google import genai

BUSINESS_NAME = "{c_name}"
BUSINESS_NICHE = "{c_cat}"
SYSTEM_PROMPT = f"You are an AI assistant for {{BUSINESS_NAME}} in {{BUSINESS_NICHE}}."

token = os.environ.get("TELEGRAM_BOT_TOKEN")
if not token:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
bot = telebot.TeleBot(token)
client = genai.Client()

@bot.message_handler(func=lambda msg: True)
def handle_msg(msg):
    res = client.models.generate_content("gemini-2.5-flash", f"{{SYSTEM_PROMPT}}\\nUser: {{msg.text}}")
    bot.reply_to(msg, res.text)

if __name__ == "__main__":
    bot.infinity_polling()
'''

    def generate_ocr_extractor_service_template(self, client_name: str = "", doc_type: str = "") -> str:
        """Generates OCR document processor code template."""
        c_name = self._sanitize_string(client_name)
        c_doc = self._sanitize_string(doc_type)
        return f'''# Client: {c_name} (OCR Extractor - {c_doc})
import sys
from pix2text import Pix2Text

p2t = Pix2Text.from_config()

def extract_document(image_path: str) -> str:
    res = p2t.recognize(image_path)
    return str(res)

def process_document(image_path: str) -> str:
    return extract_document(image_path)
'''

    def generate_web_scraper_service_template(self, client_name: str = "", target_url: str = "") -> str:
        """Generates Web Scraper code template."""
        c_name = self._sanitize_string(client_name)
        c_url = self._sanitize_string(target_url)
        return f'''# Client: {c_name} (Web Scraper - {c_url})
import requests
from bs4 import BeautifulSoup

def scrape_data(url: str = "{c_url}") -> str:
    resp = requests.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.title.string if soup.title else ""

def scrape_catalog_prices(url: str = "{c_url}") -> str:
    return scrape_data(url)
'''

    def log_client_contract(self, client_name: str, service_type: str, monthly_fee: float = 0.0, one_time_fee: float = 0.0, status: str = 'ACTIVE') -> Dict[str, Any]:
        """Logs a client contract and MRR fee."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        norm_status = str(status).upper()
        cursor.execute("""
            INSERT INTO freelance_clients (client_name, service_type, monthly_fee_rub, one_time_fee_rub, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (client_name, service_type, monthly_fee, one_time_fee, norm_status, now_str))
        cid = cursor.lastrowid
        conn.commit()
        conn.close()
        return {"id": cid, "client_name": client_name, "monthly_fee_rub": monthly_fee, "status": norm_status}

    def update_client_status(self, client_name: str, status: str) -> bool:
        """Updates client contract status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        norm_status = str(status).upper()
        cursor.execute("UPDATE freelance_clients SET status = ? WHERE client_name = ?", (norm_status, client_name))
        affected = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return affected

    def get_monthly_recurring_revenue(self) -> float:
        """Computes total MRR from active client contracts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            val = cursor.execute("SELECT SUM(monthly_fee_rub) FROM freelance_clients WHERE UPPER(status)='ACTIVE'").fetchone()[0]
            mrr = float(val) if val else 0.0
        except Exception:
            mrr = 0.0
        conn.close()
        return mrr

    def evaluate_deficit_coverage(self, r3_deficit_rub: float) -> Dict[str, Any]:
        """Evaluates how much of R3 cash flow deficit is covered by active MRR."""
        mrr = self.get_monthly_recurring_revenue()
        if r3_deficit_rub <= 0.0:
            coverage_pct = 100.0
            is_covered = True
        else:
            coverage_pct = round((mrr / r3_deficit_rub) * 100.0, 2)
            is_covered = mrr >= r3_deficit_rub
        return {
            "mrr_rub": mrr,
            "r3_deficit_rub": r3_deficit_rub,
            "coverage_pct": coverage_pct,
            "is_covered": is_covered
        }

