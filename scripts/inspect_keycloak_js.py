import sys
import re
import requests

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
})

url = 'https://online-edu.mirea.ru/auth/oidc/?source=loginpage'
r = s.get(url, allow_redirects=True)

print("Keycloak Full URL:", r.url)

# Find url.loginAction or form action in JS context
matches = re.findall(r'"url"\s*:\s*\{[^}]*\}', r.text)
for m in matches:
    print("URL Match:", m)

matches_action = re.findall(r'"loginAction"\s*:\s*"([^"]+)"', r.text)
print("loginAction matches:", matches_action)

# Search for any form action string in keycloak context
matches_auth = re.findall(r'/realms/mirea/login-actions/authenticate\?[^"\']+', r.text)
for a in set(matches_auth):
    print("Authenticate URL:", a)
