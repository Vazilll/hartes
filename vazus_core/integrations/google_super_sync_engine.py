#!/usr/bin/env python3
"""
vazus_core/google_super_sync_engine.py — Master Sync Engine for Gmail, Google Sheets, Google Keep, Calendar & Tasks.

Ecosystem: vazus SuperGraph OS v4.0
"""

import os
import sys
import json
import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path("C:/vazus")
DB_PATH = Path("C:/vazus/services/memory/vazus.db")
TOKEN_PATH = Path("C:/vazus/token.json") if Path("C:/vazus/token.json").exists() else Path("C:/vazus/data/sessions/token.json")
CREDENTIALS_PATH = Path("C:/vazus/credentials.json") if Path("C:/vazus/credentials.json").exists() else Path("C:/vazus/data/sessions/credentials.json")
WIKI_DIR = Path("C:/vazus/services/memory/semantic/wiki")

SUPER_SCOPES = [
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/fitness.sleep.read",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly"
]


class GoogleSuperSyncEngine:
    """Master Orchestrator for all Google Cloud Services."""

    def __init__(self, db_path: Path = DB_PATH, vault_dir: Optional[Path] = None, wiki_dir: Optional[Path] = None, *args, **kwargs):
        self.db_path = Path(db_path)
        self.vault_dir = Path(vault_dir) if vault_dir else WIKI_DIR
        self.wiki_dir = Path(wiki_dir) if wiki_dir else self.vault_dir
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.creds = None
        self.services = {}
        self._try_authenticate()

    def _init_db(self):
        """Initializes tables for Gmail, Sheets, Keep and Tasks sync."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            cursor = conn.cursor()
            
            # Gmail table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS google_gmail_messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    sender TEXT,
                    subject TEXT,
                    snippet TEXT,
                    date TEXT,
                    extracted_at TEXT,
                    is_actionable INTEGER DEFAULT 0
                )
            """)

            # Google Sheets tracker table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS google_sheets_sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spreadsheet_id TEXT,
                    sheet_name TEXT,
                    synced_rows_count INTEGER,
                    synced_at TEXT
                )
            """)

            conn.commit()

    def _try_authenticate(self):
        if not TOKEN_PATH.exists():
            return
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            self.creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                    with open(str(TOKEN_PATH), 'w') as f:
                        f.write(self.creds.to_json())
                except Exception as rf_err:
                    sys.stderr.write(f"⚠️ [GoogleSuperSync] Refresh Token Warning: {rf_err}\n")

            if self.creds and self.creds.valid:
                self.services['calendar'] = build('calendar', 'v3', credentials=self.creds)
                self.services['tasks'] = build('tasks', 'v1', credentials=self.creds)
                self.services['gmail'] = build('gmail', 'v1', credentials=self.creds)
                self.services['sheets'] = build('sheets', 'v4', credentials=self.creds)
                self.services['drive'] = build('drive', 'v3', credentials=self.creds)
                print("✅ [GoogleSuperSync] Все сервисы (Gmail, Sheets, Calendar, Tasks, Drive) успешно авторизованы!")
        except Exception as e:
            sys.stderr.write(f"⚠️ [GoogleSuperSync] Auth Warning: {e}\n")

    # -------------------------------------------------------------
    # 1. GMAIL SYNC MODULE
    # -------------------------------------------------------------
    def sync_gmail(self, max_results: int = 15) -> Dict[str, Any]:
        if 'gmail' not in self.services:
            return {"status": "error", "message": "Gmail API service not initialized"}

        try:
            gmail_service = self.services['gmail']
            # Search query for academic, financial or health subjects
            query = "МИРЭА OR долг OR задолженность OR экзамен OR зачет OR счет OR оплата OR БАД OR заказ"
            results = gmail_service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
            messages = results.get('messages', [])

            pushed_count = 0
            extracted_items = []

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for msg in messages:
                    msg_id = msg['id']
                    msg_detail = gmail_service.users().messages().get(userId='me', id=msg_id, format='full').execute()
                    
                    headers = msg_detail.get('payload', {}).get('headers', [])
                    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'Без темы')
                    sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Неизвестно')
                    date_str = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
                    snippet = msg_detail.get('snippet', '')

                    cursor.execute("""
                        INSERT INTO google_gmail_messages (id, thread_id, sender, subject, snippet, date, extracted_at, is_actionable)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                        ON CONFLICT(id) DO UPDATE SET snippet=excluded.snippet, date=excluded.date
                    """, (msg_id, msg.get('threadId'), sender, subject, snippet, date_str, datetime.datetime.now().isoformat()))
                    pushed_count += 1
                    extracted_items.append({"id": msg_id, "subject": subject, "sender": sender, "snippet": snippet})
                conn.commit()

            return {
                "status": "success",
                "messages_scanned": len(messages),
                "saved_to_db": pushed_count,
                "items": extracted_items[:5]
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # -------------------------------------------------------------
    # 2. GOOGLE SHEETS SYNC MODULE
    # -------------------------------------------------------------
    def sync_sheets_tracker(self) -> Dict[str, Any]:
        """Creates or updates the master Google Sheet for Debts & Supplement Stack."""
        if 'sheets' not in self.services or 'drive' not in self.services:
            return {"status": "error", "message": "Sheets API service not initialized"}

        try:
            sheets_service = self.services['sheets']
            drive_service = self.services['drive']

            # Check if Spreadsheet already exists
            q = "name = 'vazus SuperGraph OS — Трекер Долгов и БАДов' and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
            res = drive_service.files().list(q=q).execute()
            files = res.get('files', [])

            spreadsheet_id = None
            if files:
                spreadsheet_id = files[0]['id']
                print(f"📊 [Google Sheets] Найдена существующая таблица ID: {spreadsheet_id}")
            else:
                # Create new Spreadsheet
                spreadsheet_body = {
                    'properties': {'title': 'vazus SuperGraph OS — Трекер Долгов и БАДов'},
                    'sheets': [
                        {'properties': {'title': 'Долги и Учёба (МИРЭА)'}},
                        {'properties': {'title': 'Стек БАДов и Дозировки'}}
                    ]
                }
                sp = sheets_service.spreadsheets().create(body=spreadsheet_body).execute()
                spreadsheet_id = sp.get('spreadsheetId')
                print(f"✨ [Google Sheets] Создана новая таблица ID: {spreadsheet_id}")

            # Populate Tab 1: Debts & Academic Tasks
            debts_data = [
                ["Категория", "Предмет / Задача", "Статус", "Дедлайн", "Детали / Источник"],
                ["Учёба МИРЭА", "Ликвидация академических задолженностей", "В процессе", "2026-08-15", "Загружено через download_mirea_courses.py"],
                ["Финансы", "Закрытие текущих финансовых долгов", "В процессе", "2026-08-01", "Учет в vazus.db"],
                ["Здоровье", "Закупка активного стека БАДов", "Запланировано", "2026-07-29", "Maxler D3+K2, Boron, Креатин, Омега-3, Цинк"]
            ]
            sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id, range="'Долги и Учёба (МИРЭА)'!A1",
                valueInputOption="RAW", body={"values": debts_data}
            ).execute()

            # Populate Tab 2: Supplement Stack
            supplements_data = [
                ["Препарат / БАД", "Дозировка / Схема", "Периодичность", "Цель / Статус"],
                ["Maxler D3+K2", "4 капс/день (2400 МЕ D3 + 120 мкг K2)", "Ежедневно", "Активен"],
                ["NOW Boron 3mg", "3 капс/день (9 мг/день)", "2 нед приём / 1 нед отдых", "Активен"],
                ["Maxler Креатин", "5г/день с водой", "Ежедневно", "Активен"],
                ["Омега-3", "Стандартная дозировка", "Ежедневно", "Активен"],
                ["Цинк + Селен + Магний", "По схеме в конце дня", "Ежедневно перед сном", "Активен"],
                ["Ашваганда", "По схеме", "Курсовой приём", "Активен"]
            ]
            sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id, range="'Стек БАДов и Дозировки'!A1",
                valueInputOption="RAW", body={"values": supplements_data}
            ).execute()

            sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
            return {
                "status": "success",
                "spreadsheet_id": spreadsheet_id,
                "spreadsheet_url": sheet_url
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # -------------------------------------------------------------
    # 3. GOOGLE KEEP / DRIVE NOTES MODULE
    # -------------------------------------------------------------
    def sync_keep_notes(self) -> Dict[str, Any]:
        """Scans Google Drive for text notes / Keep backups and indexes into semantic wiki."""
        if 'drive' not in self.services:
            return {"status": "error", "message": "Drive API service not initialized"}

        try:
            drive_service = self.services['drive']
            # Search for text files / notes
            q = "mimeType = 'text/plain' or mimeType = 'text/markdown' or name contains 'Keep'"
            res = drive_service.files().list(q=q, pageSize=10).execute()
            files = res.get('files', [])

            return {
                "status": "success",
                "drive_notes_found": len(files),
                "notes": synced
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def scan_and_sync(self) -> Dict[str, Any]:
        """Scans vault_dir / wiki_dir markdown files for tasks and syncs them in batch into google_synced_items."""
        import re
        search_dir = getattr(self, "vault_dir", None) or getattr(self, "wiki_dir", None) or WIKI_DIR
        tasks = []
        if search_dir and os.path.exists(search_dir):
            for p in Path(search_dir).rglob("*.md"):
                try:
                    text = p.read_text(encoding="utf-8")
                    found = re.findall(r'- \[(?: |x)\] (.*)', text)
                    for item in found:
                        tasks.append((str(p.name), item.strip()))
                except Exception:
                    pass

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS google_synced_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_file TEXT,
                    task_text TEXT
                )
            """)
            conn.executemany(
                "INSERT INTO google_synced_items (source_file, task_text) VALUES (?, ?)",
                tasks
            )
            conn.commit()

        return {
            "total_tasks_found": len(tasks),
            "synced_to_db": len(tasks)
        }


if __name__ == "__main__":
    engine = GoogleSuperSyncEngine()
    print("=" * 70)
    print("🚀 [vazus SuperGraph Master Sync Engine Running...]")
    print("1. Running Gmail Sync...")
    gm_res = engine.sync_gmail()
    print(f"   Gmail Status: {gm_res.get('status')} | Items: {gm_res.get('saved_to_db', 0)}")
    
    print("2. Running Google Sheets Sync...")
    sh_res = engine.sync_sheets_tracker()
    print(f"   Sheets Status: {sh_res.get('status')} | URL: {sh_res.get('spreadsheet_url')}")

    print("3. Running Google Keep / Drive Notes Sync...")
    kp_res = engine.sync_keep_notes()
    print(f"   Keep/Drive Notes Status: {kp_res.get('status')} | Found: {kp_res.get('drive_notes_found', 0)}")
    print("=" * 70)
