import sys
import requests

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
})

url = 'https://online-edu.mirea.ru/auth/oidc/?source=loginpage'
r = s.get(url, allow_redirects=True)

print("Page HTML Length:", len(r.text))
print("Page HTML Snippet:\n", r.text[:2000])
