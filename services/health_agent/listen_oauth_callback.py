import sys
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from google_auth_oauthlib.flow import InstalledAppFlow

sys.stdout.reconfigure(encoding='utf-8')

CREDENTIALS_FILE = r"C:\vazus\credentials.json"
TOKEN_FILE = r"C:\vazus\token.json"

SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.body.read',
    'https://www.googleapis.com/auth/fitness.heart_rate.read',
    'https://www.googleapis.com/auth/fitness.sleep.read',
    'https://www.googleapis.com/auth/fitness.oxygen_saturation.read',
    'https://www.googleapis.com/auth/fitness.location.read'
]

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES, autogenerate_code_verifier=False)
flow.redirect_uri = 'http://localhost:8090/'

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if 'code' in params:
            code = params['code'][0]
            flow.fetch_token(code=code)
            creds = flow.credentials
            with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
                f.write(creds.to_json())
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write("<h1>✅ Авторизация успешна! Права на SpO2, Пульс и Сон обновлены. Окно можно закрыть.</h1>".encode('utf-8'))
            print("Successfully saved new token.json with SpO2 permissions!")
        else:
            self.send_response(400)
            self.end_headers()

print("Listening for OAuth callback on http://localhost:8090/ ...")
httpd = HTTPServer(('localhost', 8090), OAuthHandler)
httpd.handle_request()
