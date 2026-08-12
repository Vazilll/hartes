import sys
import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
})

r = s.get('https://online-edu.mirea.ru/login/index.php')
print('URL:', r.url)
print('Status:', r.status_code)

soup = BeautifulSoup(r.text, 'html.parser')

print('\n=== ALL FORMS ON PAGE ===')
for idx, form in enumerate(soup.find_all('form'), 1):
    print(f"\nForm #{idx} -> Action: {form.get('action')} | Method: {form.get('method')}")
    for inp in form.find_all(['input', 'button']):
        print(f"  [{inp.name}] name='{inp.get('name')}' type='{inp.get('type')}' value='{inp.get('value', '')[:30]}'")

print('\n=== LOGIN BUTTONS / OAUTH / LINKS ===')
for a in soup.find_all(['a', 'button']):
    href = a.get('href', '')
    text = a.get_text(strip=True)
    if href or text:
        print(f"[{a.name}] text='{text[:40]}' href='{href}'")
