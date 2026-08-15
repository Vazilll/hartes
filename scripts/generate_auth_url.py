from google_auth_oauthlib.flow import InstalledAppFlow

CREDENTIALS_FILE = r"C:\vazus\credentials.json"

UNIFIED_SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.body.read',
    'https://www.googleapis.com/auth/fitness.heart_rate.read',
    'https://www.googleapis.com/auth/fitness.sleep.read',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks'
]

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, UNIFIED_SCOPES, autogenerate_code_verifier=False)
flow.redirect_uri = 'http://localhost:8090/'
auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')

with open(r"C:\vazus\auth_url.txt", "w", encoding="utf-8") as f:
    f.write(auth_url)

print("AUTH_URL_GENERATED:")
print(auth_url)
