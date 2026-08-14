import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from google_auth_oauthlib.flow import InstalledAppFlow
import subprocess

sys.stdout.reconfigure(encoding='utf-8')
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

CREDENTIALS_FILE = r"C:\vazus\credentials.json"
TOKEN_FILE = r"C:\vazus\token.json"

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

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SUPER_SCOPES, autogenerate_code_verifier=False)
flow.redirect_uri = 'http://localhost:8090/'

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query_components = parse_qs(urlparse(self.path).query)
        if "code" in query_components:
            code = query_components["code"][0]
            flow.fetch_token(code=code)
            creds = flow.credentials
            with open(TOKEN_FILE, 'w', encoding='utf-8') as token_out:
                token_out.write(creds.to_json())
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write("<h1>🚀 Полная интеграция Gmail, Google Sheets, Keep, Calendar & Tasks успешна!</h1><p>Вы можете закрыть эту страницу.</p>".encode('utf-8'))
            
            # Auto-run google_super_sync_engine.py
            subprocess.Popen([r"C:\vazus\.venv\Scripts\python.exe", r"C:\vazus\vazus_core\google_super_sync_engine.py"])
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        return

def main():
    server_address = ('', 8090)
    httpd = HTTPServer(server_address, OAuthHandler)
    print("⏳ Ожидание клика по ссылке авторизации (Gmail + Sheets + Keep + Calendar + Tasks)...")
    httpd.handle_request()

if __name__ == "__main__":
    main()
