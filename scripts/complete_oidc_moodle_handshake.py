import sys
import os
import re
import time
import requests
import urllib.parse
from bs4 import BeautifulSoup

sys.path.insert(0, r"C:\vazus")
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from vazus_core.integrations.mirea_exporter import load_env_credentials, YandexIMAP2FAReader, MoodleSessionManager

creds = load_env_credentials()
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
})

# 1. Start OIDC Handshake
print("1. Starting OIDC Handshake...")
r1 = session.get("https://online-edu.mirea.ru/auth/oidc/?source=loginpage", allow_redirects=True)
print(f"   Keycloak Auth URL: {r1.url[:80]}...")

m1 = re.search(r'"loginAction"\s*:\s*"([^"]+)"', r1.text)
login_action_1 = m1.group(1).replace("\\/", "/") if m1 else r1.url

# 2. Submit Username & Password
print("2. Submitting Username & Password...")
res1 = session.post(login_action_1, data={"username": creds["username"], "password": creds["password"]}, allow_redirects=True)
print(f"   2FA Page URL: {res1.url[:80]}...")

m2 = re.search(r'"loginAction"\s*:\s*"([^"]+)"', res1.text)
login_action_2 = m2.group(1).replace("\\/", "/") if m2 else res1.url

# 3. Wait for 2FA Email
print("3. Waiting 6 seconds for 2FA email...")
time.sleep(6)
reader = YandexIMAP2FAReader(creds['yandex_email'], creds['yandex_password'])
code = reader.fetch_latest_2fa_code(timeout_sec=20)
print(f"🎉 2FA CODE: {code}")

# 4. POST 2FA Code
print("4. POSTing 2FA Code to Keycloak...")
res2 = session.post(login_action_2, data={"emailCode": code, "code": code}, allow_redirects=True)
print(f"   Keycloak POST 2FA Final URL: {res2.url}")
print(f"   Keycloak Response Title: {BeautifulSoup(res2.text, 'html.parser').title.get_text() if BeautifulSoup(res2.text, 'html.parser').title else 'No Title'}")

# Check if there is an OIDC POST form in res2
soup2 = BeautifulSoup(res2.text, "html.parser")
form2 = soup2.find("form")

if form2 and form2.get("action"):
    target_action = urllib.parse.urljoin(res2.url, form2["action"])
    inputs = {inp.get("name"): inp.get("value", "") for inp in form2.find_all("input") if inp.get("name")}
    print(f"\n5. Executing OIDC POST redirect form -> {target_action}")
    print("   Form Inputs:", inputs)
    res3 = session.post(target_action, data=inputs, allow_redirects=True)
    print(f"   After OIDC POST URL: {res3.url}")

# Verify Moodle Access
print("\n6. Checking Moodle Dashboard (/my/)...")
r_my = session.get("https://online-edu.mirea.ru/my/", allow_redirects=True)
print(f"   /my/ Status: {r_my.status_code} | Final URL: {r_my.url}")

if "login/index.php" not in r_my.url:
    print("\n🎉🎉🎉 SUCCESSFUL MOODLE AUTHENTICATION!")
    manager = MoodleSessionManager()
    manager.session = session
    manager.extract_sesskey(r_my.text)
    manager.save_session_cookies()
else:
    print("\n❌ Redirected to login page. Session not established.")
