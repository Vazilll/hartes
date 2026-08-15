import sys
from google_auth_oauthlib.flow import InstalledAppFlow

sys.stdout.reconfigure(encoding='utf-8')
CREDENTIALS_FILE = r"C:\vazus\credentials.json"

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
auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')

print("SUPER_AUTH_URL:")
print(auth_url)
