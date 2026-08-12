import sys
import re
import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from vazus_core.mirea_exporter import load_env_credentials

creds = load_env_credentials()
username = creds["username"]
password = creds["password"]

print(f"Testing SSO Login for: {username}")

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
})

# Step 1: OIDC Redirect
oidc_url = 'https://online-edu.mirea.ru/auth/oidc/?source=loginpage'
r1 = s.get(oidc_url, allow_redirects=True)
print("SSO Redirect URL:", r1.url)

# Step 2: Extract loginAction
m = re.search(r'"loginAction"\s*:\s*"([^"]+)"', r1.text)
if not m:
    print("❌ loginAction not found in Keycloak HTML")
    sys.exit(1)

login_action_url = m.group(1).replace("\\/", "/")
print("Keycloak Action URL:", login_action_url)

# Step 3: Post credentials to Keycloak
payload = {
    "username": username,
    "password": password
}

r2 = s.post(login_action_url, data=payload, allow_redirects=True)
print(f"Post Result URL: {r2.url} | Status: {r2.status_code}")

soup2 = BeautifulSoup(r2.text, 'html.parser')
page_title = soup2.find('title').get_text(strip=True) if soup2.find('title') else 'No Title'
print(f"Post Result Page Title: '{page_title}'")

# Check HTML content
if "mycourses" in r2.text or "sesskey" in r2.text or "logout.php" in r2.text:
    print("🎉 SUCCESSFUL LOGIN TO MOODLE VIA SSO KEYCLOAK!")
else:
    print("Next step HTML snippet:\n", r2.text[:1500])
