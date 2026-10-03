"""
moodle_fetch_tests.py — RTU MIREA Semester 1 Test & Quiz Extractor.
Extracts tests, quizzes, and control questions for:
1. Математический анализ (81917)
2. Линейная алгебра и аналитическая геометрия (66804)
3. Математическая логика и теория алгоритмов (86958)
4. Иностранный язык (86146)
"""

import sys
import os
import argparse
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

sys.path.insert(0, r"C:\vazus")
from vazus_core.integrations.mirea_exporter import (
    load_env_credentials,
    MoodleSessionManager,
    MIREA_BASE_URL,
    OIDC_LOGIN_URL
)

SEMESTER_1_COURSES = [
    {"id": 16479, "title": "Математический анализ", "folder": "01_math_analysis"},
    {"id": 16480, "title": "Линейная алгебра и аналитическая геометрия", "folder": "02_linear_algebra"},
    {"id": 16486, "title": "Математическая логика и теория алгоритмов", "folder": "03_math_logic"},
    {"id": 16017, "title": "Иностранный язык", "folder": "04_english_it"},
]

OUTPUT_DIR = Path(r"C:\vazus\knowledge\mirea\tests")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def do_login(mgr: MoodleSessionManager, otp_code: str = None) -> bool:
    if mgr.load_session_cookies() and mgr.is_authenticated():
        print("✅ [Moodle] Уже авторизован по сохраненной сессии!")
        return True

    creds = load_env_credentials()
    username = creds.get("username")
    password = creds.get("password")

    print(f"🔑 [Moodle Auth] Запуск входа для {username}...")
    login_action_url = mgr._acquire_login_action_url()
    if not login_action_url:
        print("❌ Не удалось получить точку входа Keycloak.")
        return False

    res = mgr.session.post(login_action_url, data={"username": username, "password": password}, timeout=20, allow_redirects=True)
    print(f"🌐 [Keycloak POST] Status: {res.status_code}")

    if "email-code-form" in res.text or "email-authenticator" in res.text:
        action_2fa = mgr.extract_login_action_url(res.text, res.url) or res.url
        if not otp_code:
            print("\n" + "=" * 60)
            print("📩 [2FA ТРЕБУЕТСЯ] 6-значный код отправлен на почту zhukov.m.d1@edu.mirea.ru!")
            print("Для завершения входа запустите команду:")
            print(f"python C:\\vazus\\scripts\\moodle_fetch_tests.py --code <ВАШ_КОД>")
            print("=" * 60 + "\n")
            return False

        print(f"🔑 Отправка 2FA-кода: {otp_code} -> {action_2fa[:70]}...")
        payload = {"code": otp_code, "otp": otp_code}
        res2 = mgr.session.post(action_2fa, data=payload, timeout=20, allow_redirects=True)
        print(f"🌐 [Keycloak 2FA POST] Status: {res2.status_code} | URL: {res2.url}")
        mgr.handle_max_registration_bypass(res2.text, res2.url)

    if mgr.is_authenticated():
        print("🎉 [Moodle] Полная авторизация успешна! Сохраняем сессию...")
        mgr.save_session_cookies()
        return True
    else:
        print("❌ [Moodle] Авторизация не удалась. Возможно, неверный код.")
        return False


def fetch_course_tests(mgr: MoodleSessionManager, course: dict):
    cid = course["id"]
    ctitle = course["title"]
    curl = f"{MIREA_BASE_URL}/course/view.php?id={cid}"
    print(f"\n=======================================================")
    print(f"🔍 Сканирование тестов предмета: [{cid}] {ctitle}")
    print(f"URL: {curl}")
    print(f"=======================================================")

    res = mgr.session.get(curl, timeout=15)
    if res.status_code != 200:
        print(f"⚠️ Ошибка запроса курса: HTTP {res.status_code}")
        return

    soup = BeautifulSoup(res.text, "html.parser")
    sections = soup.find_all(["li", "section"], class_=re.compile(r'section|topic')) or [soup]

    test_items = []

    for sec in sections:
        sec_title_el = sec.find(["h3", "h4", "span"], class_=re.compile(r'sectionname|title'))
        sec_title = sec_title_el.get_text(strip=True) if sec_title_el else "Общий раздел"

        for act in sec.find_all(["li", "div"], class_=re.compile(r'activity|modtype')):
            act_name_el = act.find(["span", "a"], class_=re.compile(r'instancename|activityname'))
            act_name = act_name_el.get_text(strip=True) if act_name_el else ""
            link_el = act.find("a", href=True)
            link_url = link_el["href"] if link_el else ""

            is_test = False
            mod_type = "resource"
            if "/mod/quiz/" in link_url:
                is_test = True
                mod_type = "quiz"
            elif any(w in act_name.lower() for w in ["тест", "контрольн", "билет", "экзамен", "опрос", "аттестац"]):
                is_test = True
                mod_type = "assignment/test"

            if is_test:
                print(f"   🎯 [{mod_type.upper()}] {act_name}")
                print(f"      URL: {link_url}")
                test_items.append({
                    "section": sec_title,
                    "name": act_name,
                    "url": link_url,
                    "type": mod_type
                })

    # Save to JSON
    safe_name = course["folder"]
    out_file = OUTPUT_DIR / f"{safe_name}_tests_manifest.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"course": course, "items": test_items}, f, ensure_ascii=False, indent=2)
    print(f"✅ Сохранен манифест тестов: {out_file.name} ({len(test_items)} элементов)")


def main():
    parser = argparse.ArgumentParser(description="Fetch Semester 1 Tests from RTU MIREA Moodle")
    parser.add_argument("--code", type=str, default=None, help="6-digit 2FA code sent to email")
    args = parser.parse_args()

    mgr = MoodleSessionManager()
    success = do_login(mgr, otp_code=args.code)
    if not success:
        print("Завершение. Для получения тестов требуется актуальная сессия.")
        return

    for c in SEMESTER_1_COURSES:
        fetch_course_tests(mgr, c)


if __name__ == "__main__":
    main()
