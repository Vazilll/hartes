import sys
import os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

sys.stdout.reconfigure(encoding='utf-8')

TOKEN_PATH = r"C:\vazus\token.json"
DB_PATH = r"C:\vazus\memory\vazus.db"

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks"
]

# 1. Write Markdown note to semantic wiki
note_path = r"C:\vazus\services\memory\semantic\wiki\Buy_Supplements_Task.md"
note_content = """# 💊 Закупка БАДов и витаминов (vazus SuperGraph OS)

- [ ] 🛒 Купить БАДы и добавки по активному стеку: Maxler D3+K2, NOW Boron 3mg, Maxler Креатин (500g), Омега-3, Цинк, Селен, Магний, Ашваганда 📅 2026-07-29 11:00
- [ ] 💊 Настроить дозировки: Maxler D3+K2 (4 капс/день), NOW Boron (3 капс/день 9 мг), Креатин (5g/день) 📅 2026-07-29 12:00
"""

with open(note_path, "w", encoding="utf-8") as f:
    f.write(note_content)

print(f"✅ Локальная заметка создана: {note_path}")

# 2. Push to Google Tasks & Google Calendar
if not os.path.exists(TOKEN_PATH):
    print("❌ TOKEN_PATH not found!")
    sys.exit(1)

creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

tasks_pushed = 0
calendar_pushed = 0

# A. Google Tasks
try:
    tasks_service = build("tasks", "v1", credentials=creds)
    tasklists = tasks_service.tasklists().list().execute()
    default_list_id = tasklists.get("items", [{}])[0].get("id", "@default")

    task_body = {
        "title": "💊 Купить БАДы: Maxler D3+K2, NOW Boron 3mg, Maxler Креатин, Омега-3, Цинк, Магний, Ашваганда",
        "notes": "Детальный стек из vazus.db:\n• Maxler D3+K2 (2400 МЕ D3 + 120мкг K2)\n• NOW Boron 3mg (9 мг/день, цикл 2 нед)\n• Maxler Креатин (5г/день)\n• Омега-3, Цинк, Селен, Магний, Ашваганда",
        "due": "2026-07-29T08:00:00.000Z"
    }

    created_task = tasks_service.tasks().insert(tasklist=default_list_id, body=task_body).execute()
    print(f"🎉 [Google Tasks SUCCESS] Задача создана! Link/ID: {created_task.get('id')}")
    tasks_pushed += 1
except Exception as e:
    print(f"⚠️ [Google Tasks Notice]: {e}")

# B. Google Calendar Event
try:
    calendar_service = build("calendar", "v3", credentials=creds)
    
    start_dt = datetime.now() + timedelta(days=1)
    start_dt = start_dt.replace(hour=11, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(hours=1)

    event_body = {
        'summary': '💊 Покупка БАДов (Maxler D3+K2, NOW Boron, Креатин, Омега-3, Цинк, Магний)',
        'location': 'Аптека / Маркетплейс',
        'description': 'Автоматическая задача из vazus SuperGraph OS.\n\nТочный список стека:\n1. Maxler D3+K2 (4 капс/день = 2400 МЕ D3 + 120мкг K2)\n2. NOW Boron 3mg (3 капс = 9 мг/день)\n3. Maxler Креатин (5г/день с водой)\n4. Омега-3, Цинк, Селен, Магний, Ашваганда',
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': 'Europe/Moscow',
        },
        'end': {
            'dateTime': end_dt.isoformat(),
            'timeZone': 'Europe/Moscow',
        },
    }

    created_event = calendar_service.events().insert(calendarId='primary', body=event_body).execute()
    print(f"🎉 [Google Calendar SUCCESS] Событие создано! Link: {created_event.get('htmlLink')}")
    calendar_pushed += 1
except Exception as e:
    print(f"⚠️ [Google Calendar Notice]: {e}")

print("=" * 60)
print(f"РЕЗУЛЬТАТ: Tasks pushed = {tasks_pushed}, Calendar events pushed = {calendar_pushed}")
print("=" * 60)
