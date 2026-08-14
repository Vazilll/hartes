import sys
import os
import re
import time
import json
import imaplib
import email
from email.header import decode_header
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, r"C:\vazus")
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from vazus_core.integrations.mirea_exporter import load_env_credentials, MoodleSessionManager, MireaCourseExporter

def get_latest_2fa_code(yandex_email, yandex_pass, timeout_sec=45):
    """Polls Yandex Mail for the newest 2FA code from sso@mirea.ru."""
    print(f"📩 [2FA Reader] Сканирование Яндекс Почты ({yandex_email})...")
    start_time = time.time()
    
    try:
        mail = imaplib.IMAP4_SSL("imap.yandex.ru", 993)
        mail.login(yandex_email, yandex_pass)
        mail.select("INBOX")
    except Exception as e:
        print(f"❌ [2FA Reader] Ошибка входа в IMAP: {e}")
        return None

    while time.time() - start_time < timeout_sec:
        try:
            status, messages = mail.search(None, '(FROM "sso@mirea.ru")')
            if status == "OK" and messages[0]:
                msg_ids = messages[0].split()
                # Check the very latest email
                for msg_id in reversed(msg_ids[-3:]):
                    res, msg_data = mail.fetch(msg_id, "(RFC822)")
                    if res == "OK":
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        subj_raw = msg.get("Subject", "")
                        decoded = decode_header(subj_raw)
                        subject = "".join([str(t[0], t[1] or 'utf-8') if isinstance(t[0], bytes) else t[0] for t in decoded])
                        
                        m = re.search(r'(\d{6})', subject)
                        if m:
                            code = m.group(1)
                            print(f"🎉 [2FA Reader] ИЗВЛЕЧЕН 2FA КОД: {code} | (Тема: {subject})")
                            try:
                                mail.logout()
                            except:
                                pass
                            return code
        except Exception as err:
            print(f"⚠️ [2FA Error]: {err}")
        
        print("   ⏳ [2FA Reader] Ожидание доставления письма в папку Входящие...")
        time.sleep(4)

    try:
        mail.logout()
    except:
        pass
    print("❌ [2FA Reader] Таймаут ожидания письма.")
    return None


def run():
    print("=" * 80)
    print("🎓 РТУ МИРЭА — НАДЕЖНЫЙ PLAYWRIGHT АВТОРИЗАТОР С ДОЖИДАНИЕМ 2FA")
    print("=" * 80)

    creds = load_env_credentials()
    username = creds["username"]
    password = creds["password"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        print("1. Переход на страницу авторизации online-edu.mirea.ru...")
        page.goto("https://online-edu.mirea.ru/auth/oidc/?source=loginpage", wait_until="networkidle")
        
        print(f"2. Ввод логина ({username}) и пароля...")
        page.fill("input[name='username']", username)
        page.fill("input[name='password']", password)
        page.click("input[type='submit'], button[type='submit']")
        page.wait_for_timeout(4000)

        print("   Текущий URL после входа:", page.url)

        # Check if 2FA form appeared
        if "login-actions" in page.url or page.locator("input[name='emailCode'], input[name='code']").count() > 0:
            print("🔐 Детектирован ввод 2FA-кода! Запуск ожидания письма в Яндекс Почте...")
            code = get_latest_2fa_code(creds["yandex_email"], creds["yandex_password"], timeout_sec=40)
            
            if code:
                print(f"🔑 Ввод 2FA-кода '{code}'...")
                inp = page.locator("input[name='emailCode'], input[name='code']").first
                inp.focus()
                inp.fill("")
                page.keyboard.type(code, delay=100)
                page.wait_for_timeout(2000)
                
                print("🚀 Отправка 2FA формы...")
                if page.locator("button[type='submit'], input[type='submit']").count() > 0:
                    page.click("button[type='submit'], input[type='submit']")
                else:
                    page.keyboard.press("Enter")
                
                page.wait_for_timeout(6000)

        print("3. Проверка результата и обработка страниц Keycloak...")
        print("   Текущий URL:", page.url)

        # Handle MAX / required actions if any
        if "required-action" in page.url or "max" in page.url:
            print("🛑 Экран регистрации/подтверждения MAX. Пропуск...")
            form = page.locator("form").first
            if form.count() > 0:
                page.evaluate("() => { const f = document.querySelector('form'); if(f) f.submit(); }")
                page.wait_for_timeout(4000)

        # Ensure we navigate directly to Moodle dashboard with active session
        print("4. Переход на главную страницу СДО https://online-edu.mirea.ru/my/...")
        page.goto("https://online-edu.mirea.ru/my/", wait_until="networkidle")
        print("   Итоговый URL в СДО:", page.url)

        if "login/index.php" not in page.url:
            print("🎉🎉🎉 УСПЕШНЫЙ ВХОД В ЛИЧНЫЙ КАБИНЕТ СДО РТУ МИРЭА!")
            cookies = {c["name"]: c["value"] for c in context.cookies()}
            
            manager = MoodleSessionManager()
            manager.session.cookies.update(cookies)
            manager.extract_sesskey(page.content())
            manager.save_session_cookies()
            print("   Извлеченный MoodleSession:", cookies.get("MoodleSession"))

            print("\n5. Сканирование всех зачисленных курсов и дисциплин...")
            exporter = MireaCourseExporter(manager=manager)
            courses = exporter.get_enrolled_courses()
            
            print(f"\n📚 ВСЕГО КУРСОВ НАЙДЕНО: {len(courses)}")
            for idx, c in enumerate(courses, 1):
                title = c.get("fullname") or c.get("title") or c.get("shortname") or "Курс"
                url = c.get("url") or f"https://online-edu.mirea.ru/course/view.php?id={c.get('id')}"
                prog = c.get("progress")
                print(f"   {idx:2d}. {title} | Прогресс: {prog}% | {url}")

            out_path = r"C:\vazus\services\memory\knowledge\mirea_courses\enrolled_catalog.json"
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(courses, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Полный каталог дисциплин сохранен в: {out_path}")
        else:
            print("❌ Авторизация не завершена. Проверьте правильность логина и пароля.")

        browser.close()

if __name__ == "__main__":
    run()
