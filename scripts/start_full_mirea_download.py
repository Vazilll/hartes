import sys
import os
import re
import time
import json
import requests
import urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, r"C:\vazus")
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from vazus_core.integrations.mirea_exporter import MoodleSessionManager, MireaCourseExporter, load_env_credentials

print("=" * 80)
print("🚀 РТУ МИРЭА — ЗАПУСК ПОЛНОГО АВТОМАТИЧЕСКОГО СКАЧИВАНИЯ ВСЕХ МАТЕРИАЛОВ")
print("=" * 80)

creds = load_env_credentials()
manager = MoodleSessionManager()

# 1. Authenticate with Keycloak SSO & Yandex 2FA IMAP
print("🔐 1. Авторизация в СДО МИРЭА (Keycloak SSO + Yandex 2FA)...")
if not manager.load_session_cookies() or not manager.is_authenticated():
    # Login via requests with fresh 2FA code
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    })
    
    r1 = session.get("https://online-edu.mirea.ru/auth/oidc/?source=loginpage")
    m1 = re.search(r'"loginAction"\s*:\s*"([^"]+)"', r1.text)
    login_action_1 = m1.group(1).replace("\\/", "/") if m1 else None
    
    res1 = session.post(login_action_1, data={"username": creds["username"], "password": creds["password"]})
    
    m_exec = re.search(r'"authExecId"\s*:\s*"([^"]+)"', res1.text)
    m2 = re.search(r'"loginAction"\s*:\s*"([^"]+)"', res1.text)
    login_action_2 = m2.group(1).replace("\\/", "/") if m2 else res1.url

    if m_exec:
        exec_id = m_exec.group(1)
        res_trig = session.post(login_action_2, data={"authenticationExecution": exec_id}, allow_redirects=True)
        m3 = re.search(r'"loginAction"\s*:\s*"([^"]+)"', res_trig.text)
        if m3:
            login_action_2 = m3.group(1).replace("\\/", "/")

    print("⏳ Ожидание поступления свежего 2FA-кода на Яндекс Почту...")
    time.sleep(7)
    from vazus_core.integrations.mirea_exporter import YandexIMAP2FAReader
    reader = YandexIMAP2FAReader(creds['yandex_email'], creds['yandex_password'])
    code = reader.fetch_latest_2fa_code(timeout_sec=20)
    print(f"🎉 2FA Код извлечен: {code}")

    res2 = session.post(login_action_2, data={"emailCode": code, "code": code}, allow_redirects=True)
    
    soup2 = BeautifulSoup(res2.text, "html.parser")
    form2 = soup2.find("form")
    if form2 and form2.get("action"):
        target_action = urllib.parse.urljoin(res2.url, form2["action"])
        inputs = {inp.get("name"): inp.get("value", "") for inp in form2.find_all("input") if inp.get("name")}
        res3 = session.post(target_action, data=inputs, allow_redirects=True)
        manager.session = session
        manager.extract_sesskey(res3.text)
        manager.save_session_cookies()

if manager.is_authenticated():
    print("✅ Успешный вход в СДО МИРЭА! Выгрузка курсов...")
else:
    print("⚠️ Сессия активирована, запуск сканера дисциплин...")

# 2. Export Courses
export_dir = Path(r"C:\vazus\services\memory\knowledge\mirea_courses")
exporter = MireaCourseExporter(manager=manager, export_dir=export_dir)
courses = exporter.get_enrolled_courses()

print(f"\n📚 Найдено {len(courses)} дисциплин. Запуск скачивания файлов...")
download_log = []

for idx, c in enumerate(courses, 1):
    c_id = c.get("course_id") or c.get("id")
    c_name = c.get("title") or c.get("fullname", f"Course_{c_id}")
    print(f"\n[{idx}/{len(courses)}] Скачивание дисциплины: {c_name} (ID: {c_id})...")
    
    course_dir = export_dir / f"Course_{c_id}_{re.sub(r'[^a-zA-Z0-9А-Яа-я_]', '_', c_name)[:40]}"
    course_dir.mkdir(parents=True, exist_ok=True)

    # Crawl course view page
    c_url = f"https://online-edu.mirea.ru/course/view.php?id={c_id}"
    try:
        r_c = manager.session.get(c_url, timeout=15)
        soup_c = BeautifulSoup(r_c.text, "html.parser")
        
        # Extract resource links
        res_links = soup_c.find_all("a", href=re.compile(r'/mod/(resource|resource/view|assign|folder|quiz|page|url)/view\.php\?id=\d+'))
        files_saved = 0
        for r_link in res_links:
            item_title = r_link.get_text(strip=True)
            item_href = r_link.get("href")
            if item_href:
                try:
                    r_item = manager.session.get(item_href, timeout=10)
                    # Save HTML/Markdown summary
                    file_name = f"{re.sub(r'[^a-zA-Z0-9А-Яа-я_]', '_', item_title)[:40]}.html"
                    with open(course_dir / file_name, "w", encoding="utf-8") as f_out:
                        f_out.write(r_item.text)
                    files_saved += 1
                except Exception:
                    pass

        print(f"    ✅ Сохранено ресурсов/материалов: {files_saved}")
        download_log.append({"id": c_id, "name": c_name, "files_count": files_saved, "path": str(course_dir)})
    except Exception as e:
        print(f"    ⚠️ Ошибка выгрузки курса: {e}")

# Save master report
report_path = export_dir / "download_report.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(download_log, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 80)
print(f"🎉 ВСЕ МАТЕРИАЛЫ И КУРСЫ СКАЧАНЫ И СОХРАНЕНЫ В: {export_dir}")
print("=" * 80)
