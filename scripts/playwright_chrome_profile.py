import sys
import os
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, r"C:\vazus")
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from vazus_core.integrations.mirea_exporter import MoodleSessionManager, MireaCourseExporter

def run():
    print("=" * 80)
    print("🎭 РТУ МИРЭА — ПОДКЛЮЧЕНИЕ К ПРОФИЛЮ БРАУЗЕРА CHROME")
    print("=" * 80)

    user_data_dir = r"C:\Users\Vaz\AppData\Local\Google\Chrome\User Data"
    
    with sync_playwright() as p:
        try:
            browser_context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                channel="chrome",
                args=["--remote-debugging-port=9222"]
            )
        except Exception as e:
            print(f"⚠️ Ошибка открытия профиля Chrome (возможно, закрыть процессы Chrome): {e}")
            # Fallback to standard launch
            browser = p.chromium.launch(headless=True)
            browser_context = browser.new_context()

        page = browser_context.new_page()

        print("1. Переход на https://online-edu.mirea.ru/my/...")
        page.goto("https://online-edu.mirea.ru/my/", wait_until="networkidle")
        print("   Текущий URL:", page.url)

        if "login/index.php" not in page.url and "sso.mirea.ru" not in page.url:
            print("🎉🎉🎉 УСПЕШНЫЙ ВХОД ЧЕРЕЗ АКТИВНЫЙ ПРОФИЛЬ CHROME!")
            cookies = {c["name"]: c["value"] for c in browser_context.cookies()}
            
            manager = MoodleSessionManager()
            manager.session.cookies.update(cookies)
            manager.extract_sesskey(page.content())
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
            print(f"\n💾 Полный каталог сохранен в: {out_path}")
        else:
            print("❌ Профиль Chrome не авторизован на online-edu.mirea.ru. Перенаправлено на:", page.url)

        browser_context.close()

if __name__ == "__main__":
    run()
