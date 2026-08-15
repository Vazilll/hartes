import sys
import re
import time
import json
import requests
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, r"C:\vazus")
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from vazus_core.integrations.mirea_exporter import load_env_credentials, YandexIMAP2FAReader, MoodleSessionManager, MireaCourseExporter

print("=" * 80)
print("🚀 РТУ МИРЭА — ПОЛНЫЙ СКАНИРОВАТЕЛЬ И ВЫГРУЗЧИК КУРСОВ (MoodleSession Active)")
print("=" * 80)

creds = load_env_credentials()
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
})

# 1. GET OIDC Entry
r1 = session.get("https://online-edu.mirea.ru/auth/oidc/?source=loginpage")
m1 = re.search(r'"loginAction"\s*:\s*"([^"]+)"', r1.text)
login_action_1 = m1.group(1).replace("\\/", "/") if m1 else None

# 2. POST Username & Password
res1 = session.post(login_action_1, data={"username": creds["username"], "password": creds["password"]})
m2 = re.search(r'"loginAction"\s*:\s*"([^"]+)"', res1.text)
login_action_2 = m2.group(1).replace("\\/", "/") if m2 else res1.url

# 3. Wait for 2FA email
time.sleep(6)
reader = YandexIMAP2FAReader(creds['yandex_email'], creds['yandex_password'])
code = reader.fetch_latest_2fa_code(timeout_sec=20)
print(f"🎉 FRESH 2FA CODE: {code}")

# 4. POST 2FA code to Keycloak (issues MoodleSession cookie!)
res2 = session.post(login_action_2, data={"emailCode": code, "code": code}, allow_redirects=True)
print("Cookiejar keys:", session.cookies.get_dict().keys())

manager = MoodleSessionManager()
manager.session = session
manager.extract_sesskey(res2.text)

# Verify /my/ access
r_my = session.get("https://online-edu.mirea.ru/my/", allow_redirects=True)
manager.extract_sesskey(r_my.text)
manager.save_session_cookies()
print(f"Moodle /my/ Status: {r_my.status_code} | sesskey: {manager.sesskey}")

export_dir = Path(r"C:\vazus\services\memory\knowledge\mirea_courses")
export_dir.mkdir(parents=True, exist_ok=True)

exporter = MireaCourseExporter(manager=manager, export_dir=export_dir)
courses = exporter.get_enrolled_courses()

print(f"\n📚 ВСЕГО НАЙДЕНО КУРСОВ И ДИСЦИПЛИН В СДО МИРЭА: {len(courses)}")
print("=" * 80)

summary = []
for idx, c in enumerate(courses, 1):
    c_id = c.get("course_id") or c.get("id")
    c_title = c.get("title") or c.get("fullname", f"Course_{c_id}")
    print(f"\n[{idx}/{len(courses)}] 📖 Скачивание материалов курса: {c_title} (ID: {c_id})")
    
    course_folder = export_dir / f"Course_{c_id}_{re.sub(r'[^a-zA-Z0-9А-Яа-я_]', '_', c_title)[:40]}"
    course_folder.mkdir(parents=True, exist_ok=True)

    c_url = f"https://online-edu.mirea.ru/course/view.php?id={c_id}"
    try:
        r_c = session.get(c_url, timeout=12)
        soup_c = BeautifulSoup(r_c.text, "html.parser")
        
        # Find all resources / activities
        mod_links = soup_c.find_all("a", href=re.compile(r'/mod/(resource|resource/view|assign|folder|quiz|page|url)/view\.php\?id=\d+'))
        saved_files = []
        
        for link in mod_links:
            title = link.get_text(strip=True)
            href = link.get("href")
            if href and title:
                try:
                    r_mod = session.get(href, timeout=10)
                    file_name = f"{re.sub(r'[^a-zA-Z0-9А-Яа-я_]', '_', title)[:40]}.html"
                    out_file = course_folder / file_name
                    with open(out_file, "w", encoding="utf-8") as f_out:
                        f_out.write(r_mod.text)
                    saved_files.append(title)
                except Exception:
                    pass

        print(f"    ✅ Скачано модулей/файлов: {len(saved_files)}")
        summary.append({"id": c_id, "title": c_title, "files": len(saved_files), "path": str(course_folder)})
    except Exception as e:
        print(f"    ⚠️ Ошибка выгрузки: {e}")

# Save JSON Report
with open(export_dir / "download_summary.json", "w", encoding="utf-8") as f_sum:
    json.dump(summary, f_sum, ensure_ascii=False, indent=2)

print("\n" + "=" * 80)
print(f"🎉 ВСЕ ДИСЦИПЛИНЫ И ФАЙЛЫ МИРЭА СОХРАНЕНЫ В: {export_dir}")
print("=" * 80)
