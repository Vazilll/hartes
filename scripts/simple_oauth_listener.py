import sys
import json
import urllib.parse
import http.server
import requests

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

CREDENTIALS_PATH = "C:/vazus/data/sessions/credentials.json"
TOKEN_PATH = "C:/vazus/data/sessions/token.json"

auth_code = None

class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if 'code' in params:
            auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write("<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>".encode('utf-8'))
            self.wfile.write("<h1>🎉 Успешно! Доступ Google получен!</h1>".encode('utf-8'))
            self.wfile.write("<p>Можете закрыть эту вкладку и вернуться в чат.</p></body></html>".encode('utf-8'))
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        return # Silence standard HTTP logs

def run_simple_listener():
    print("🚀 Listening for OAuth callback on http://localhost:8080/ ...")
    server = http.server.HTTPServer(('127.0.0.1', 8080), OAuthCallbackHandler)
    server.handle_request() # Block until 1 authorization request is received
    
    if auth_code:
        print("✅ Auth code received! Exchanging code for Google OAuth Token...")
        with open(CREDENTIALS_PATH, 'r', encoding='utf-8') as f:
            creds_data = json.load(f)['installed']
            
        token_resp = requests.post('https://oauth2.googleapis.com/token', data={
            'code': auth_code,
            'client_id': creds_data['client_id'],
            'client_secret': creds_data['client_secret'],
            'redirect_uri': 'http://localhost:8080/',
            'grant_type': 'authorization_code'
        })
        
        token_json = token_resp.json()
        if 'access_token' in token_json:
            with open(TOKEN_PATH, 'w', encoding='utf-8') as tf:
                json.dump(token_json, tf, indent=2)
            print("🎉 SUCCESS! Saved token to:", TOKEN_PATH)
        else:
            print("❌ Token Exchange Error:", token_json)

if __name__ == "__main__":
    run_simple_listener()
