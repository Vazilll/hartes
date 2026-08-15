import sys
import os
import json
import sqlite3
import shutil

sys.path.insert(0, r"C:\vazus")
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from vazus_core.integrations.mirea_exporter import MoodleSessionManager, MireaCourseExporter

def get_chrome_cookie(domain_substr="mirea.ru"):
    """Reads MoodleSession cookie directly from Chrome / Yandex Browser SQLite database via DPAPI."""
    try:
        import win32crypt
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "pywin32", "--quiet"], check=False)
        import win32crypt

    appdata = os.getenv("LOCALAPPDATA")
    paths = [
        os.path.join(appdata, r"Google\Chrome\User Data\Default\Network\Cookies"),
        os.path.join(appdata, r"Yandex\YandexBrowser\User Data\Default\Network\Cookies"),
    ]

    for path in paths:
        if not os.path.exists(path):
            continue

        print(f"🔍 Поиск куки в: {path}")
        tmp_db = path + ".tmp"
        try:
            shutil.copy2(path, tmp_db)
            conn = sqlite3.connect(tmp_db)
            cursor = conn.cursor()
            
            cursor.execute("SELECT host_key, name, encrypted_value, value FROM cookies WHERE host_key LIKE ?", (f"%{domain_substr}%",))
            rows = cursor.fetchall()
            
            cookies_found = {}
            for host, name, enc_val, val in rows:
                dec_val = val
                if not dec_val and enc_val:
                    try:
                        # Chromium v80+ DPAPI decryption
                        dec_val = win32crypt.CryptUnprotectData(enc_val[3:], None, None, None, 0)[1].decode('utf-8')
                    except Exception:
                        dec_val = ""
                
                if name and dec_val:
                    cookies_found[name] = dec_val
                    print(f"   -> Найдена кука: {name} = {dec_val[:15]}...")

            conn.close()
            if os.path.exists(tmp_db):
                os.remove(tmp_db)

            if "MoodleSession" in cookies_found:
                return cookies_found

        except Exception as e:
            print(f"   ⚠️ Ошибка чтения {path}: {e}")
            if os.path.exists(tmp_db):
                os.remove(tmp_db)

    return None

def run():
    print("=" * 80)
    print("🎓 РТУ МИРЭА — ИЗВЛЕЧЕНИЕ АКТИВНОЙ СЕССИИ ИЗ БРАУЗЕРА (Chrome/Yandex)")
    print("=" * 80)

    cookies = get_chrome_cookie()
    
    if not cookies or "MoodleSession" not in cookies:
        print("❌ Не удалось извлечь куку MoodleSession из вашего браузера.")
        print("💡 Пожалуйста, убедитесь, что вы зашли на online-edu.mirea.ru в Chrome или Yandex Браузере!")
        return

    print(f"\n🎉 Найдена активная кука MoodleSession: {cookies['MoodleSession']}")

    manager = MoodleSessionManager()
    manager.session.cookies.update(cookies)
    
    # Verify session
    if manager.is_authenticated():
        print("✅ АВТОРИЗАЦИЯ ПОДТВЕРЖДЕНА! Сессия активна в СДО РТУ МИРЭА!")
        manager.save_session_cookies()

        exporter = MireaCourseExporter(manager=manager)
        courses = exporter.get_enrolled_courses()

        print(f"\n📚 ВСЕГО НАЙДЕНО КУРСОВ И ДИСЦИПЛИН В СДО МИРЭА: {len(courses)}")
        for idx, c in enumerate(courses, 1):
            title = c.get("fullname") or c.get("title") or c.get("shortname") or "Курс"
            url = c.get("url") or f"https://online-edu.mirea.ru/course/view.php?id={c.get('id')}"
            prog = c.get("progress")
            print(f"   {idx:2d}. {title} | Прогресс: {prog}% | {url}")

        out_path = r"C:\vazus\services\memory\knowledge\mirea_courses\enrolled_catalog.json"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(courses, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Сохранен каталог зачисленных дисциплин: {out_path}")
    else:
        print("❌ Кука MoodleSession из браузера оказалась неактивна.")

if __name__ == "__main__":
    run()
