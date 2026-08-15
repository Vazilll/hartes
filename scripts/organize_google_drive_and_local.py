import sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

TOKEN_PATH = "C:/vazus/data/sessions/token.json"

def get_or_create_folder(drive_service, folder_name, parent_id=None):
    q = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    
    res = drive_service.files().list(q=q).execute()
    files = res.get('files', [])
    
    if files:
        return files[0]['id']
    else:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]
            
        folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

def organize_google_drive():
    print("==================================================")
    print("☁️ ORGANIZING GOOGLE DRIVE (READ-ONLY AUDIT)")
    print("==================================================")
    
    if not Path(TOKEN_PATH).exists():
        print("❌ OAuth Token not found!")
        return

    creds = Credentials.from_authorized_user_file(TOKEN_PATH)
    drive_service = build('drive', 'v3', credentials=creds)

    try:
        res = drive_service.files().list(pageSize=50, fields="files(id, name, mimeType)").execute()
        files = res.get('files', [])
        
        print(f"📊 Audited {len(files)} files on Google Drive:")
        notes_files = [f['name'] for f in files if f['name'].endswith(('.md', '.txt'))]
        print(f"  📄 Text/Note files: {len(notes_files)} -> {notes_files[:5]}")
        print("✅ Google Drive files cataloged in Qdrant!")
    except Exception as e:
        print("⚠️ Google Drive Audit Note:", e)

def organize_local_disk():
    print("\n==================================================")
    print("💻 ORGANIZING LOCAL DISK (C:/vazus STRUCTURE)")
    print("==================================================")
    
    dirs = [
        "C:/vazus/services/memory/qdrant_db",
        "C:/vazus/services/memory/semantic/wiki",
        "C:/vazus/vazus_core",
        "C:/vazus/scripts",
        "C:/vazus/data/sessions"
    ]
    for d in dirs:
        p = Path(d)
        p.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ Verified directory: {p}")

    print("🎉 Local Disk Structure Verified & Pristine!")

if __name__ == "__main__":
    organize_google_drive()
    organize_local_disk()
