import sys
from pathlib import Path
sys.path.insert(0, 'C:/vazus')

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

TOKEN_PATH = "C:/vazus/data/sessions/token.json"

def fetch_keep_and_tasks():
    print("==================================================")
    print("📱 SEARCHING GOOGLE KEEP & GOOGLE TASKS FROM PHONE")
    print("==================================================")
    
    if not Path(TOKEN_PATH).exists():
        print("❌ Token file not found!")
        return

    creds = Credentials.from_authorized_user_file(TOKEN_PATH)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            print("✅ Token refreshed successfully!")
        except Exception as e:
            print("⚠️ Token refresh failed:", e)

    # 1. Check Google Tasks (Phone Notes are frequently saved as Tasks)
    try:
        tasks_service = build('tasks', 'v1', credentials=creds)
        tasklists = tasks_service.tasklists().list().execute().get('items', [])
        print(f"\n📋 Google Task Lists Found: {len(tasklists)}")
        
        for tlist in tasklists:
            print(f"\n--- List: {tlist.get('title')} ---")
            tasks = tasks_service.tasks().list(tasklist=tlist['id']).execute().get('items', [])
            for t in tasks[:10]:
                title = t.get('title', 'Untitled')
                notes = t.get('notes', '')
                updated = t.get('updated', '')[:16]
                print(f"  📌 [{updated}] {title}")
                if notes:
                    print(f"     Note: {notes[:150]}...")
    except Exception as e:
        print("⚠️ Google Tasks fetch error:", e)

    # 2. Check Google Drive for Keep backups or text notes created from phone
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        query = "mimeType = 'text/plain' or mimeType = 'text/markdown' or name contains 'Keep' or name contains 'Заметки'"
        res = drive_service.files().list(q=query, pageSize=15, fields="files(id, name, modifiedTime, mimeType)").execute()
        files = res.get('files', [])
        print(f"\n📂 Drive Text Notes / Keep Backups Found: {len(files)}")
        for f in files:
            print(f"  📄 [{f.get('modifiedTime')[:16]}] {f.get('name')} (ID: {f.get('id')})")
    except Exception as e:
        print("⚠️ Google Drive fetch error:", e)

if __name__ == "__main__":
    fetch_keep_and_tasks()
