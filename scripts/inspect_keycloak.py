import sys
import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
})

url = 'https://online-edu.mirea.ru/auth/oidc/?source=loginpage'
r = s.get(url, allow_redirects=True)

soup = BeautifulSoup(r.text, 'html.parser')
print("Keycloak Form URL:", r.url)

print("\n--- KEYCLOAK LOGIN FORM ---")
for idx, form in enumerate(soup.find_all('form'), 1):
    print(f"Form #{idx} -> Action: {form.get('action')} | Method: {form.get('method')}")
    for inp in form.find_all(['input', 'button']):
        print(f"  [{inp.name}] name='{inp.get('name')}' type='{inp.get('type')}' value='{inp.get('value', '')[:30]}'")

print("\n--- OTHER LINKS ON KEYCLOAK PAGE ---")
for a in soup.find_all(['a', 'button']):
    print(f"[{a.name}] text='{a.get_text(strip=True)[:40]}' href='{a.get('href', '')}'")
