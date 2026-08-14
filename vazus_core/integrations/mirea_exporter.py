"""
vazus_core/mirea_exporter.py — RTU MIREA Moodle LMS Exporter (Keycloak SSO + 2FA Yandex IMAP + MAX Bypass + Moodle 4 AJAX API).

Architecture & Authentication Flow:
1. 🎓 OIDC SSO Entry: Hits https://online-edu.mirea.ru/auth/oidc/?source=loginpage.
2. 🔑 Keycloak SSO Extraction: Follows redirect to https://sso.mirea.ru and extracts dynamic `loginAction` URL from kcContext / form.
3. 🔐 Credential Auth & Error Inspection: Posts username & password, decodes Keycloakify errors.
4. 📩 2FA Yandex IMAP Interceptor: If 2FA OTP is required, automatically scans Yandex Mail for 6-digit code.
5. 🛑 MAX Registration Bypass: Auto-declines MAX prompts if displayed.
6. 💾 Session Cookie Persistence: Saves MoodleSession to C:/vazus/user_mirea_session.json for instant auto-login.
7. 📚 Course Discovery: Uses Moodle 4.x AJAX Service API (`core_course_get_enrolled_courses_by_timeline_classification`) + HTML crawlers.
8. 📂 Content Exporter: Exports lectures, PDFs, slides, and Markdown files to C:/vazus/knowledge/mirea_courses.

vazus SuperGraph OS Ecosystem
"""

import os
import sys
import re
import json
import time
import urllib.parse
import imaplib
import email
from email.header import decode_header
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup

# Global paths & defaults
MIREA_BASE_URL = "https://online-edu.mirea.ru"
OIDC_LOGIN_URL = f"{MIREA_BASE_URL}/auth/oidc/?source=loginpage"
MY_URL = f"{MIREA_BASE_URL}/my/"
DEFAULT_EXPORT_DIR = Path("C:/vazus/services/memory/knowledge/mirea_courses")
SESSION_FILE_PATH = Path("C:/vazus/user_mirea_session.json")
ENV_FILE_PATH = Path("C:/vazus/.env")


def load_env_credentials() -> Dict[str, Optional[str]]:
    """Loads MIREA and Yandex credentials from environment or C:/vazus/.env."""
    creds = {
        "username": None,
        "password": None,
        "yandex_email": None,
        "yandex_password": None
    }
    target_env = getattr(sys.modules[__name__], "ENV_FILE_PATH", ENV_FILE_PATH)
    if Path(target_env).exists():
        try:
            with open(target_env, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("MIREA_USERNAME="):
                        creds["username"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("MIREA_PASSWORD="):
                        creds["password"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("YANDEX_EMAIL="):
                        creds["yandex_email"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("YANDEX_APP_PASSWORD="):
                        creds["yandex_password"] = line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass

    if not creds["username"]:
        creds["username"] = os.getenv("MIREA_USERNAME")
    if not creds["password"]:
        creds["password"] = os.getenv("MIREA_PASSWORD")
    if not creds["yandex_email"]:
        creds["yandex_email"] = os.getenv("YANDEX_EMAIL")
    if not creds["yandex_password"]:
        creds["yandex_password"] = os.getenv("YANDEX_APP_PASSWORD")

    return creds


class YandexIMAP2FAReader:
    """Connects to Yandex Mail via IMAP to automatically retrieve 2FA OTP codes from RTU MIREA."""

    def __init__(self, email_address: str, app_password: str, imap_server: str = "imap.yandex.ru"):
        self.email_address = email_address
        self.app_password = app_password
        self.imap_server = imap_server

    def _decode_mime_words(self, mime_str: str) -> str:
        if not mime_str:
            return ""
        try:
            decoded = decode_header(mime_str)
            parts = []
            for sub_decoded, encoding in decoded:
                if isinstance(sub_decoded, bytes):
                    parts.append(sub_decoded.decode(encoding or "utf-8", errors="ignore"))
                else:
                    parts.append(str(sub_decoded))
            return "".join(parts)
        except Exception:
            return mime_str

    def fetch_latest_2fa_code(self, timeout_sec: int = 30, _target_tag: Optional[str] = None) -> Optional[str]:
        """Polls Yandex Mail IMAP with transparent progress logging."""
        print(f"📩 [2FA IMAP Reader] Подключение к Yandex IMAP ({self.email_address})...")
        start_time = time.time()

        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, 993)
            mail.login(self.email_address, self.app_password)
            mail.select("INBOX")
            print("   ✅ [2FA IMAP Reader] Успешный вход в почтовый ящик imap.yandex.ru!")
        except Exception as err:
            print(f"   ❌ [2FA IMAP Reader] Ошибка входа в Яндекс Почту: {err}")
            return None

        while time.time() - start_time < timeout_sec:
            try:
                status, messages = mail.search(None, '(UNSEEN)')
                if status == "OK" and messages[0]:
                    msg_ids = messages[0].split()
                    print(f"   📫 Найдено новых писем: {len(msg_ids)}")
                    for msg_id in reversed(msg_ids[-5:]):
                        res, msg_data = mail.fetch(msg_id, "(RFC822)")
                        if res != "OK":
                            continue

                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        subject = ""
                        if msg["Subject"]:
                            sub_decoded, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(sub_decoded, bytes):
                                subject = sub_decoded.decode(encoding or "utf-8", errors="ignore")
                            else:
                                subject = str(sub_decoded)

                        sender = msg.get("From", "")
                        print(f"      -> Письмо от: '{sender}' | Тема: '{subject}'")

                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode(errors="ignore")
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode(errors="ignore")

                        m_code = (
                            re.search(r'\b(\d{6})\b', body)
                            or re.search(r'\b(\d{6})\b', subject)
                            or re.search(r'код[:\s]+(\d{4,8})', body, re.IGNORECASE)
                            or re.search(r'пароль[:\s]+(\d{4,8})', body, re.IGNORECASE)
                        )
                        if m_code:
                            code = m_code.group(1)
                            print(f"   🎉 [2FA IMAP Reader] Успешно извлечен 2FA-код: {code}")
                            mail.logout()
                            return code
                else:
                    print(f"   ⏳ [2FA IMAP Reader] Сканирование новых писем... ({time.time() - start_time:.0f}s)")

            except Exception as e:
                sys.stderr.write(f"[2FA IMAP Warning]: {e}\n")

            time.sleep(4)

        try:
            mail.logout()
        except Exception:
            pass

        print(f"⚠️ [2FA IMAP Reader] Новых писем с 2FA-кодом не поступило за {timeout_sec} сек.")
        return None


class MoodleSessionManager:
    """Manages Keycloak SSO authentication, 2FA code entry, MAX bypass, and session persistence."""

    def __init__(self, session_file: Path = SESSION_FILE_PATH):
        self.session_file = Path(session_file)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        self.sesskey: Optional[str] = None

    def save_session_cookies(self):
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        cookie_dict = requests.utils.dict_from_cookiejar(self.session.cookies)
        data = {
            "cookies": cookie_dict,
            "sesskey": self.sesskey
        }
        with open(self.session_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_session_cookies(self) -> bool:
        if not self.session_file.exists():
            return False
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "cookies" in data:
                cookie_dict = data["cookies"]
                self.sesskey = data.get("sesskey")
            else:
                cookie_dict = data
            self.session.cookies = requests.utils.cookiejar_from_dict(cookie_dict)
            return True
        except Exception:
            return False

    def extract_sesskey(self, html_text: str) -> Optional[str]:
        m = re.search(r'"sesskey"\s*:\s*"([^"]+)"', html_text) or re.search(r'sesskey=([a-zA-Z0-9]+)', html_text)
        if m:
            self.sesskey = m.group(1)
        return self.sesskey

    def is_authenticated(self) -> bool:
        try:
            r = self.session.get(MY_URL, timeout=10, allow_redirects=True)
            self.extract_sesskey(r.text)
            if r.status_code == 200 and ("login/index.php" not in r.url) and ("sesskey" in r.text or "mycourses" in r.text or "logout.php" in r.text):
                return True
        except Exception as e:
            sys.stderr.write(f"[MIREA Exporter] Auth check warning: {e}\n")
        return False

    def handle_max_registration_bypass(self, response_text: str, current_url: str) -> bool:
        has_max_indicator = (
            "max_registration" in current_url or
            "max.ru" in response_text.lower() or
            "зарегистрироваться через макс" in response_text.lower() or
            "мессенджер max" in response_text.lower() or
            "мессенджер макс" in response_text.lower() or
            bool(re.search(r'\b(max_login|max_auth|max_bypass|no_max|decline_max)\b', response_text, re.I)) or
            bool(re.search(r'\bвойти через max\b', response_text, re.I))
        )
        if has_max_indicator:
            print("🛑 [MIREA Auth] Обнаружен баннер/форма регистрации через MAX — автоматический отказ (Bypass)...")
            soup = BeautifulSoup(response_text, "html.parser")

            skip_link = soup.find("a", href=re.compile(r'skip|cancel|decline|no_max', re.IGNORECASE))
            if skip_link and skip_link.get("href"):
                skip_url = urllib.parse.urljoin(current_url, skip_link["href"])
                self.session.get(skip_url, timeout=10)
                print("   ✅ Предложение MAX пропущено по ссылке.")
                return True

            skip_form = soup.find("form")
            if skip_form:
                action = skip_form.get("action", current_url)
                form_url = urllib.parse.urljoin(current_url, action)
                inputs = skip_form.find_all("input")
                form_data = {}
                for inp in inputs:
                    name = inp.get("name")
                    val = inp.get("value", "")
                    if name:
                        form_data[name] = val
                form_data["skip"] = "1"
                form_data["cancel"] = "Отмена"
                self.session.post(form_url, data=form_data, timeout=10)
                print("   ✅ Форма MAX отклонена.")
                return True
        return False

    def extract_login_action_url(self, html_text: str, current_url: str) -> Optional[str]:
        """Extracts Keycloak SSO loginAction URL with multi-layer fallback strategy."""
        # Layer 1: JSON regex search for loginAction string inside kcContext or HTML
        m_action = re.search(r'"loginAction"\s*:\s*"([^"]+)"', html_text)
        if m_action:
            return m_action.group(1).replace("\\/", "/")

        # Layer 2: Extract kcContext block and parse as JSON or regex search
        m_kc = re.search(r'const kcContext = (\{.*?\});\n', html_text, re.DOTALL)
        if m_kc:
            kc_str = m_kc.group(1)
            m_inner = re.search(r'"loginAction"\s*:\s*"([^"]+)"', kc_str)
            if m_inner:
                return m_inner.group(1).replace("\\/", "/")

        # Layer 3: BeautifulSoup search for static forms or kc-form-login
        soup = BeautifulSoup(html_text, "html.parser")
        form_kc = soup.find("form", id="kc-form-login") or soup.find("form")
        if form_kc and form_kc.get("action"):
            return urllib.parse.urljoin(current_url, form_kc["action"])

        return None

    def extract_keycloak_error(self, html_text: str) -> Optional[str]:
        """Extracts readable error summary if Keycloak auth fails."""
        m_msg = re.search(r'"message"\s*:\s*\{\s*"type"\s*:\s*"error"[^}]*"summary"\s*:\s*"([^"]+)"', html_text)
        if m_msg:
            return m_msg.group(1)

        soup = BeautifulSoup(html_text, "html.parser")
        err_div = soup.find(class_=re.compile(r'kc-feedback-text|alert-error|error-message|alert-danger', re.IGNORECASE))
        if err_div:
            return err_div.get_text(strip=True)

        if "Неверное имя пользователя или пароль" in html_text:
            return "Неверное имя пользователя или пароль."

        return None

    def login(self, username: Optional[str] = None, password: Optional[str] = None,
              yandex_email: Optional[str] = None, yandex_password: Optional[str] = None) -> bool:
        """Authenticates on RTU MIREA via Keycloak SSO with transparent diagnostics."""
        if self.load_session_cookies() and self.is_authenticated():
            print("✅ [MIREA Exporter] Успешный вход по сохраненным куки сессии!")
            return True

        creds = load_env_credentials()
        username = username or creds["username"]
        password = password or creds["password"]
        yandex_email = yandex_email or creds["yandex_email"]
        yandex_password = yandex_password or creds["yandex_password"]

        if not username or not password:
            print("⚠️ [MIREA Exporter] Учетные данные РТУ МИРЭА не заданы в C:\\vazus\\.env.")
            return False

        print("\n" + "=" * 70)
        print(f"🔑 [MIREA SSO Auth] Старт входа через Единую Систему Аутентификации РТУ МИРЭА (Keycloak SSO)")
        print(f"   Логин: {username}")
        print("=" * 70)

        # Step 1: Open OIDC SSO Login Entry Point
        try:
            print(f"🌐 [HTTP GET] OIDC SSO -> {OIDC_LOGIN_URL}")
            r_oidc = self.session.get(OIDC_LOGIN_URL, allow_redirects=True, timeout=15)
            print(f"   Итоговый URL Keycloak: {r_oidc.url}")

            # Step 2: Extract dynamic Keycloak loginAction URL
            login_action_url = self.extract_login_action_url(r_oidc.text, r_oidc.url)

            if not login_action_url:
                print("❌ [MIREA Auth] Не удалось извлечь точку входа Keycloak loginAction.")
                return False

            print(f"🔑 Точка отправки формы Keycloak SSO: {login_action_url[:90]}...")

        except Exception as e:
            print(f"❌ [MIREA Auth] Ошибка подключения к OIDC SSO: {e}")
            return False

        # Step 3: POST Credentials to Keycloak SSO Action URL
        payload = {
            "username": username,
            "password": password
        }

        try:
            res = self.session.post(login_action_url, data=payload, timeout=20, allow_redirects=True)
            print(f"🌐 [HTTP POST Keycloak] Status {res.status_code} | URL: {res.url}")

            soup_res = BeautifulSoup(res.text, "html.parser")
            page_title = soup_res.find("title").get_text(strip=True) if soup_res.find("title") else "Без заголовка"
            print(f"📄 Заголовок ответа сервера: '{page_title}'")

            # Check for Keycloak Authentication Errors
            kc_error = self.extract_keycloak_error(res.text)
            if kc_error:
                print(f"❌ [MIREA Auth] Ошибка аутентификации Keycloak: '{kc_error}'")
                return False

            # Check if 2FA is required by Keycloak / Moodle
            otp_input = soup_res.find("input", {"name": re.compile(r'^(twofactor|authcode|otpcode|token|verification_code|totp)$', re.IGNORECASE)})
            is_2fa_page = bool("twofactor" in res.url or "двухфакторн" in res.text.lower() or "код подтверждения" in res.text.lower() or otp_input)

            if is_2fa_page:
                print("\n🔐 [2FA Детектор] Зафиксирован реальный запрос 2FA-кода подтверждения!")
                code = None

                if yandex_email and yandex_password:
                    reader = YandexIMAP2FAReader(yandex_email, yandex_password)
                    code = reader.fetch_latest_2fa_code(timeout_sec=25)

                if not code:
                    if sys.stdin.isatty():
                        print("⚠️ Автоматический перехват 2FA не дал результата. Введите код вручную:")
                        try:
                            code = input("🔑 2FA-код: ").strip()
                        except (KeyboardInterrupt, EOFError):
                            code = ""
                    else:
                        print("⚠️ Автоматический перехват 2FA не дал результата, терминал неинтерактивен.")

                if code:
                    form_2fa = soup_res.find("form")
                    target_url = urllib.parse.urljoin(res.url, form_2fa.get("action", res.url)) if form_2fa else res.url
                    inputs = form_2fa.find_all("input") if form_2fa else []
                    payload_2fa = {}
                    for inp in inputs:
                        name = inp.get("name")
                        val = inp.get("value", "")
                        if name:
                            payload_2fa[name] = val
                    payload_2fa["code"] = code
                    payload_2fa["otp"] = code

                    res = self.session.post(target_url, data=payload_2fa, timeout=15, allow_redirects=True)
                    print(f"🌐 [HTTP POST 2FA] Status {res.status_code} | URL: {res.url}")

            # Step 4: Bypass MAX registration modal if shown
            self.handle_max_registration_bypass(res.text, res.url)

            # Step 5: Verify final authentication in Moodle
            if self.is_authenticated():
                print("\n🎉 [MIREA Auth] ПОЛНАЯ АВТОРИЗАЦИЯ УСПЕШНА! Сессия сохранена в user_mirea_session.json.")
                self.save_session_cookies()
                return True
            else:
                print("\n❌ [MIREA Auth] Вход не завершен. Проверьте правильность пароля в C:\\vazus\\.env.")
                return False

        except Exception as err:
            print(f"❌ [MIREA Auth] Ошибка сети при аутентификации Keycloak: {err}")
            return False


class MireaCourseExporter:
    """Scrapes enrolled subjects, lectures, PDF slides, and media from online-edu.mirea.ru."""

    def __init__(self, manager: MoodleSessionManager, export_dir: Path = DEFAULT_EXPORT_DIR):
        self.manager = manager
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def get_enrolled_courses(self) -> List[Dict[str, Any]]:
        """Discovers enrolled courses via Moodle 4.x AJAX Service API + HTML Crawling Fallbacks."""
        if not self.manager.is_authenticated():
            print("⚠️ [MIREA Exporter] Требуется авторизация для сканирования предметов.")
            return []

        print("🔍 [MIREA Exporter] Сканирование ваших дисциплин и курсов РТУ МИРЭА...")
        courses = []
        seen_ids = set()

        # Method 1: Moodle 4.x AJAX Service API Call (core_course_get_enrolled_courses_by_timeline_classification)
        if self.manager.sesskey:
            try:
                ajax_url = f"{MIREA_BASE_URL}/lib/ajax/service.php?sesskey={self.manager.sesskey}&info=core_course_get_enrolled_courses_by_timeline_classification"
                payload = [{
                    "index": 0,
                    "methodname": "core_course_get_enrolled_courses_by_timeline_classification",
                    "args": {
                        "offset": 0,
                        "limit": 0,
                        "classification": "all",
                        "sort": "fullname"
                    }
                }]
                r_ajax = self.manager.session.post(ajax_url, json=payload, timeout=12)
                if r_ajax.status_code == 200:
                    resp_json = r_ajax.json()
                    if isinstance(resp_json, list) and len(resp_json) > 0 and not resp_json[0].get("error"):
                        c_list = resp_json[0].get("data", {}).get("courses", [])
                        for item in c_list:
                            cid = item.get("id")
                            fullname = item.get("fullname") or item.get("shortname")
                            if cid and fullname and cid not in seen_ids:
                                seen_ids.add(cid)
                                courses.append({
                                    "course_id": cid,
                                    "title": fullname.strip(),
                                    "url": f"{MIREA_BASE_URL}/course/view.php?id={cid}"
                                })
                        if courses:
                            print(f"   ⚡ [Moodle AJAX API] Успешно извлечено {len(courses)} дисциплин через Moodle 4 WS Service API!")
            except Exception as ajax_err:
                sys.stderr.write(f"[MIREA Exporter] Moodle AJAX API warning: {ajax_err}\n")

        # Method 2: HTML Page Crawling (/my/, /my/courses.php, /user/profile.php)
        crawl_urls = [MY_URL, f"{MIREA_BASE_URL}/my/courses.php", f"{MIREA_BASE_URL}/user/profile.php"]
        for target_url in crawl_urls:
            try:
                r = self.manager.session.get(target_url, timeout=12)
                self.manager.extract_sesskey(r.text)
                soup = BeautifulSoup(r.text, "html.parser")

                course_links = soup.find_all("a", href=re.compile(r'/course/view\.php\?id=\d+'))
                for link in course_links:
                    href = link.get("href", "")
                    m = re.search(r'id=(\d+)', href)
                    if not m:
                        continue
                    cid = int(m.group(1))
                    if cid in seen_ids:
                        continue

                    title = link.get_text(strip=True)
                    if not title or len(title) < 3 or title.lower() in ("перейти к курсу", "подробнее", "открыть"):
                        parent = link.find_parent(["div", "li", "td"])
                        if parent:
                            h_elem = parent.find(["h3", "h4", "h5", "span"])
                            if h_elem:
                                title = h_elem.get_text(strip=True)

                    if title and len(title) >= 3 and title.lower() not in ("my", "dashboard", "личный кабинет", "главная"):
                        seen_ids.add(cid)
                        courses.append({
                            "course_id": cid,
                            "title": title,
                            "url": f"{MIREA_BASE_URL}/course/view.php?id={cid}"
                        })
            except Exception as crawl_err:
                sys.stderr.write(f"[MIREA Exporter] Crawl warning for {target_url}: {crawl_err}\n")

        print(f"📋 [MIREA Exporter] Найдено дисциплин и курсов РТУ МИРЭА: {len(courses)}")
        for idx, c in enumerate(courses, 1):
            print(f"   [{idx}] ID {c['course_id']}: {c['title']}")

        return courses

    def export_course(self, course_id: int, course_title: str) -> Dict[str, Any]:
        """Scrapes and downloads all materials, files, and lectures for a course."""
        safe_title = "".join([char if char.isalnum() or char in (" ", "_", "-") else "_" for char in course_title]).strip()
        course_dir = self.export_dir / safe_title
        course_dir.mkdir(parents=True, exist_ok=True)

        course_url = f"{MIREA_BASE_URL}/course/view.php?id={course_id}"
        print(f"\n📥 [MIREA Exporter] Выгрузка материалов предмета '{course_title}' (ID: {course_id})...")

        downloaded_files = 0
        md_lines = [
            f"# Учебные материалы дисциплины РТУ МИРЭА: {course_title}\n",
            f"**Курс ID**: #{course_id}\n",
            f"**URL**: {course_url}\n",
            f"**Дата экспорта**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
            "---\n\n"
        ]

        try:
            r = self.manager.session.get(course_url, timeout=15)
            self.manager.extract_sesskey(r.text)
            soup = BeautifulSoup(r.text, "html.parser")

            sections = soup.find_all(["li", "section"], class_=re.compile(r'section|topic'))
            if not sections:
                sections = [soup]

            for sec in sections:
                sec_title_elem = sec.find(["h3", "h4", "span"], class_=re.compile(r'sectionname|title'))
                sec_title = sec_title_elem.get_text(strip=True) if sec_title_elem else "Общие материалы"
                md_lines.append(f"## 📚 {sec_title}\n\n")

                activities = sec.find_all(["li", "div"], class_=re.compile(r'activity|modtype'))
                for act in activities:
                    act_name_elem = act.find(["span", "a"], class_=re.compile(r'instancename|activityname'))
                    act_name = act_name_elem.get_text(strip=True) if act_name_elem else "Ресурс"

                    link_elem = act.find("a", href=True)
                    resource_url = link_elem["href"] if link_elem else ""

                    md_lines.append(f"### 📄 {act_name}\n")
                    if resource_url:
                        md_lines.append(f"- **Ссылка**: [{resource_url}]({resource_url})\n")

                    if resource_url and ("/mod/resource/view.php" in resource_url or "/pluginfile.php/" in resource_url or "/mod/url/view.php" in resource_url or "/mod/folder/view.php" in resource_url):
                        try:
                            r_res = self.manager.session.get(resource_url, timeout=12, stream=True)
                            content_disp = r_res.headers.get("Content-Disposition", "")
                            content_type = r_res.headers.get("Content-Type", "")

                            filename = None
                            if "filename=" in content_disp:
                                m_fn = re.search(r'filename\*?=["\']?(?:UTF-8\'\')?([^"\';]+)["\']?', content_disp, re.IGNORECASE)
                                if m_fn:
                                    filename = urllib.parse.unquote(m_fn.group(1))

                            if not filename:
                                ext = ".pdf" if "pdf" in content_type else (".docx" if "word" in content_type else (".pptx" if "presentation" in content_type else ""))
                                filename = f"{act_name[:40]}{ext if ext else '.bin'}"

                            filename = "".join([c if c.isalnum() or c in (" ", "_", ".", "-") else "_" for c in filename]).strip()
                            save_path = course_dir / filename

                            if not save_path.exists() or save_path.stat().st_size == 0:
                                with open(save_path, "wb") as f_out:
                                    for chunk in r_res.iter_content(chunk_size=64*1024):
                                        if chunk:
                                            f_out.write(chunk)
                                downloaded_files += 1
                                print(f"   -> 🚀 Скачан файл: {filename}")
                                md_lines.append(f"- **Локальный файл**: `{filename}`\n")
                        except Exception as file_err:
                            sys.stderr.write(f"   -> ⚠️ Ошибка загрузки ресурса {act_name}: {file_err}\n")

                    md_lines.append("\n")
                md_lines.append("---\n\n")

            md_file = course_dir / f"{safe_title}_конспект.md"
            md_file.write_text("".join(md_lines), encoding="utf-8")
            print(f"   ✅ Сохранен главный конспект предмета: {md_file.name}")

        except Exception as e:
            sys.stderr.write(f"[MIREA Exporter] Error exporting course {course_title}: {e}\n")

        return {
            "course_id": course_id,
            "title": course_title,
            "downloaded_files": downloaded_files,
            "export_dir": str(course_dir).replace("\\", "/")
        }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("Testing Keycloak SSO RTU MIREA Moodle Exporter...")
    mgr = MoodleSessionManager()
    mgr.login()
