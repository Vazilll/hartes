import sys
import time
from playwright.sync_api import sync_playwright

sys.path.insert(0, r"C:\vazus")
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from vazus_core.integrations.mirea_exporter import load_env_credentials, YandexIMAP2FAReader, MireaCourseExporter, MoodleSessionManager

creds = load_env_credentials()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    page = context.new_page()

    # Mark stale emails as seen BEFORE starting login session
    reader = YandexIMAP2FAReader(creds['yandex_email'], creds['yandex_password'])
    reader.mark_old_2fa_as_seen()

    print("1. OIDC GET...")
    page.goto("https://online-edu.mirea.ru/auth/oidc/?source=loginpage", wait_until="networkidle")

    # 2. Fill credentials
    print("2. Entering credentials...")
    page.fill("input[name='username']", creds["username"])
    page.fill("input[name='password']", creds["password"])
    page.click("input[type='submit'], button[type='submit']")
    page.wait_for_timeout(4000)

    # 3. Handle 2FA with Tag Matching
    if "login-actions" in page.url:
        page_text = page.content()
        m_tag = re.search(r'#([A-Z0-9]{2})', page_text)
        target_tag = m_tag.group(1) if m_tag else None
        print(f"3. Детектирован запрашиваемый Keycloak тег: #{target_tag if target_tag else 'ALL'}")

        code = reader.fetch_latest_2fa_code(timeout_sec=35, target_tag=target_tag)
        if not code and page.locator("button[name='resend']").count() > 0:
            print("   Нажатие кнопки Повторить...")
            page.click("button[name='resend']")
            time.sleep(5)
            # Re-extract tag from updated page
            m_tag = re.search(r'#([A-Z0-9]{2})', page.content())
            target_tag = m_tag.group(1) if m_tag else None
            print(f"   Новый запрашиваемый тег после повтора: #{target_tag}")
            code = reader.fetch_latest_2fa_code(timeout_sec=30, target_tag=target_tag)

        print(f"🎉 2FA Код с тегом #{target_tag}: {code}")
        if code:
            inp = page.locator("input[name='emailCode'], input[name='code']").first
            inp.click()
            inp.fill("")
            inp.press_sequentially(code, delay=120)
            page.wait_for_timeout(1000)
            
            print("🚀 Выполнение requestSubmit()...")
            page.evaluate("() => { const f = document.querySelector('form'); if(f) { if(f.requestSubmit) f.requestSubmit(); else f.submit(); } }")
            page.keyboard.press("Enter")
            page.wait_for_timeout(5000)
            print("   URL после отправки:", page.url)

            # If still on login-actions, attempt clicking any newly rendered submit button
            for btn_loc in page.locator("button, input[type='submit']").all():
                txt = btn_loc.inner_text() or btn_loc.get_attribute("value") or ""
                if "войти" in txt.lower() or "подтвердить" in txt.lower() or "submit" in txt.lower():
                    print("   Clicking target submit button:", txt)
                    btn_loc.click()

    page.wait_for_timeout(6000)
    print("\nFinal URL:", page.url)

    if "login-actions" not in page.url and "online-edu.mirea.ru" in page.url:
        print("🎉🎉🎉 SUCCESSFUL LOGGED IN TO MOODLE!")
        cookies = {c["name"]: c["value"] for c in context.cookies()}
        manager = MoodleSessionManager()
        manager.session.cookies.update(cookies)
        manager.extract_sesskey(page.content())
        manager.save_session_cookies()
        
        exporter = MireaCourseExporter(manager=manager)
        courses = exporter.get_enrolled_courses()
        print(f"📚 Enrolled Courses Found: {len(courses)}")
        for c in courses:
            print(" -", c)

    browser.close()
