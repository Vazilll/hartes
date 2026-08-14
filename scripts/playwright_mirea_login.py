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

def get_2fa_code_by_tag(yandex_email, yandex_pass, target_tag, timeout_sec=130):
    """Polls Yandex Mail for up to 130 seconds (2+ minutes) until the 2FA code with exact #TAG arrives."""
    print(f"📩 [2FA Reader] Запуск 2-минутного ожидания письма с тегом #{target_tag} на {yandex_email}...")
    start_time = time.time()
    
    try:
        mail = imaplib.IMAP4_SSL("imap.yandex.ru", 993)
        mail.login(yandex_email, yandex_pass)
        mail.select("INBOX")
    except Exception as e:
        print(f"❌ [2FA Reader] IMAP Error: {e}")
        return None

    while time.time() - start_time < timeout_sec:
        elapsed = int(time.time() - start_time)
        try:
            status, messages = mail.search(None, '(FROM "sso@mirea.ru")')
            if status == "OK" and messages[0]:
                msg_ids = messages[0].split()
                for msg_id in reversed(msg_ids[-6:]):
                    res, msg_data = mail.fetch(msg_id, "(RFC822)")
                    if res == "OK":
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        subj_raw = msg.get("Subject", "")
                        decoded = decode_header(subj_raw)
                        subject = "".join([str(t[0], t[1] or 'utf-8') if isinstance(t[0], bytes) else t[0] for t in decoded])
                        
                        m = re.search(r'(\d{6})\s*–\s*ваш\s*код\s*#([A-Z0-9]{2})', subject, re.IGNORECASE)
                        if m:
                            code = m.group(1)
                            tag = m.group(2).upper()
                            if tag == target_tag.upper():
                                print(f"🎉🎉🎉 СВЕЖИЙ КОД ПОЛУЧЕН ЗА {elapsed} СЕК! [Тег #{tag}]: {code}")
                                try:
                                    mail.logout()
                                except:
                                    pass
                                return code
        except Exception as err:
            pass
            
        print(f"   ⏳ [2FA Reader] Ожидание доставки письма РТУ МИРЭА ({elapsed}с / {timeout_sec}с)...")
        time.sleep(4)

    try:
        mail.logout()
    except:
        pass
    print("❌ [2FA Reader] Таймаут 2 минуты истек.")
    return None


def run():
    print("=" * 80)
    print("🎓 РТУ МИРЭА — АВТОРИЗАЦИЯ С 2-МИНУТНЫМ ТАЙМЕРОМ ОЖИДАНИЯ 2FA")
    print("=" * 80)

    creds = load_env_credentials()
    username = creds["username"]
    password = creds["password"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        print("1. Переход на online-edu.mirea.ru...")
        page.goto("https://online-edu.mirea.ru/auth/oidc/?source=loginpage", wait_until="networkidle")
        
        print("2. Ввод логина и пароля...")
        page.fill("input[name='username']", username)
        page.fill("input[name='password']", password)
        page.click("input[type='submit'], button[type='submit']")
        page.wait_for_timeout(4000)

        print("   URL после входа:", page.url)

        # 2FA Step
        if "login-actions" in page.url or page.locator("input[name='emailCode'], input[name='code']").count() > 0:
            page_text = page.content()
            m_tag = re.search(r'код\s*\(\s*#([A-Z0-9]{2})\s*\)', page_text, re.IGNORECASE)
            target_tag = m_tag.group(1).upper() if m_tag else None
            print(f"🔐 ДЕТЕКТИРОВАН ТЕГ НА ЭКРАНЕ: #{target_tag}")

            # 2 MINUTE TIMER POLLING
            code = get_2fa_code_by_tag(creds["yandex_email"], creds["yandex_password"], target_tag=target_tag, timeout_sec=130) if target_tag else None

            if code:
                print(f"🔑 Ввод 2FA кода '{code}' для тега #{target_tag}...")
                inp = page.locator("input[name='emailCode'], input[name='code']").first
                inp.focus()
                inp.fill("")
                page.keyboard.type(code, delay=100)
                page.wait_for_timeout(2000)

                btn = page.locator("button[type='submit'], input[type='submit'], button#kc-login").first
                if btn.count() > 0:
                    btn.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(6000)

        # Handle MAX required action if present
        if "required-action" in page.url or "max" in page.url:
            print("🛑 Экран MAX. Нажатие продолжить/пропустить...")
            form = page.locator("form").first
            if form.count() > 0:
                page.evaluate("() => { const f = document.querySelector('form'); if(f) f.submit(); }")
                page.wait_for_timeout(4000)

        print("3. Переход в СДО дашборд https://online-edu.mirea.ru/my/...")
        page.goto("https://online-edu.mirea.ru/my/", wait_until="networkidle")
        print("   Итоговый URL:", page.url)

        if "login/index.php" not in page.url:
            print("🎉🎉🎉 УСПЕШНЫЙ ВХОД В СДО РТУ МИРЭА!")
            cookies = {c["name"]: c["value"] for c in context.cookies()}
            
            manager = MoodleSessionManager()
            manager.session.cookies.update(cookies)
            manager.extract_sesskey(page.content())
            manager.save_session_cookies()
            print("   MoodleSession:", cookies.get("MoodleSession"))

            exporter = MireaCourseExporter(manager=manager)
            courses = exporter.get_enrolled_courses()
            
            print(f"\n📚 ВСЕГО КУРСОВ И ДИСЦИПЛИН НАЙДЕНО: {len(courses)}")
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
            print("❌ Авторизация не завершена.")

        browser.close()

if __name__ == "__main__":
    run()
