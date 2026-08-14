import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from google_auth_oauthlib.flow import InstalledAppFlow

sys.stdout.reconfigure(encoding='utf-8')
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

CREDENTIALS_FILE = r"C:\vazus\credentials.json"
TOKEN_FILE = r"C:\vazus\token.json"

UNIFIED_SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.body.read',
    'https://www.googleapis.com/auth/fitness.heart_rate.read',
    'https://www.googleapis.com/auth/fitness.sleep.read',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks'
]

def main():
    print("🔑 [vazus OAuth] Запуск авторизации единого доступа Google (Fitness + Calendar + Tasks)...")
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, UNIFIED_SCOPES, autogenerate_code_verifier=False)
    flow.redirect_uri = 'http://localhost:8090/'
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    
    print(f"\n🌐 Открываем браузер для подтверждения доступа:\n{auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception as e:
        print(f"Не удалось открыть браузер автоматически: {e}")

    class OAuthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            query_components = parse_qs(urlparse(self.path).query)
            if "code" in query_components:
                code = query_components["code"][0]
                flow.fetch_token(code=code)
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write("<h1>✅ Авторизация vazus SuperGraph OS успешно завершена!</h1><p>Вы можете закрыть эту вкладку.</p>".encode('utf-8'))
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, format, *args):
            return

    server_address = ('', 8090)
    httpd = HTTPServer(server_address, OAuthHandler)
    print("⏳ Ожидание подтверждения авторизации в браузере...")
    httpd.handle_request()
    
    creds = flow.credentials
    with open(TOKEN_FILE, 'w', encoding='utf-8') as token_out:
        token_out.write(creds.to_json())

    print("🎉 [vazus OAuth] Успех! Единый токен сохранено в token.json.")

if __name__ == "__main__":
    main()
