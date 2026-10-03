"""
vazus SuperGraph OS — R5 RTU MIREA Student Portal E2E Test Suite
Covers Features 20-23:
- Feature 20: R5 MIREA Online Schedule API
- Feature 21: R5 MIREA Offline SQLite Cache
- Feature 22: R5 MIREA Keycloak SSO & 2FA
- Feature 23: R5 MIREA Moodle Material Exporter

Tier 1: Feature Coverage (20 tests)
Tier 2: Boundary & Corner Cases (20 tests)
Total: 40 tests.
"""

import sys
import os
import json
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(r"C:\vazus")
sys.path.append(r"C:\vazus\vazus_core")

from vazus_core.mirea_student_manager import (
    MireaStudentManager,
    SessionRequiredError,
    ScheduleFetchError
)
from vazus_core.mirea_exporter import (
    load_env_credentials,
    YandexIMAP2FAReader,
    MoodleSessionManager,
    MireaCourseExporter
)


@pytest.fixture
def tmp_db(tmp_path):
    """Fixture providing an isolated SQLite database path and initializing MIREA schema."""
    db_file = tmp_path / "vazus_test_mirea.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mirea_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT,
        weekday TEXT,
        lesson_time TEXT,
        subject TEXT,
        lesson_type TEXT,
        classroom TEXT,
        teacher TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mirea_milestones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT,
        subject TEXT,
        milestone_name TEXT,
        milestone_type TEXT,
        due_date TEXT,
        status TEXT,
        description TEXT
    )
    """)
    conn.commit()
    conn.close()
    return str(db_file)


@pytest.fixture
def mirea_mgr(tmp_db):
    """Fixture returning MireaStudentManager initialized with isolated tmp_db."""
    mgr = MireaStudentManager(group_name="ИВБО-22-25", db_path=tmp_db)
    return mgr


# ============================================================================
# FEATURE 20: R5 MIREA Online Schedule API (Tier 1 & Tier 2)
# ============================================================================

def test_feature_20_01_fetch_online_schedule_success(mirea_mgr):
    """Tier 1: Verify successful online schedule fetch returns list of lesson dicts."""
    mock_payload = json.dumps({
        "schedule": {
            "Понедельник": [
                {"time": "09:00 - 10:30", "name": "Высшая математика", "type": "Лекция", "room": "А-418", "teacher": "проф. Смирнов А.В."}
            ]
        }
    }).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_payload

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        result = mirea_mgr.fetch_mirea_schedule_online()
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0]["subject"] == "Высшая математика"
        mock_urlopen.assert_called_once()


def test_feature_20_02_fetch_schedule_url_encoding(mirea_mgr):
    """Tier 1: Verify URL formatting and User-Agent headers for group requests."""
    mirea_mgr.group_name = "ИВБО-02-22"
    mock_payload = json.dumps({
        "schedule": {
            "Вторник": [{"time": "10:40 - 12:10", "name": "Физика", "type": "Практика", "room": "Б-101", "teacher": "Петров П.П."}]
        }
    }).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_payload

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        result = mirea_mgr.fetch_mirea_schedule_online()
        assert isinstance(result, list)
        assert result[0]["subject"] == "Физика"
        req_arg = mock_urlopen.call_args[0][0]
        assert "schedule-of.mirea.ru" in req_arg.full_url
        assert req_arg.headers.get("User-agent") == "VazusOS/1.0"


def test_feature_20_03_fetch_schedule_custom_group(tmp_db):
    """Tier 1: Test fetching schedule for custom group initialization."""
    mgr = MireaStudentManager(group_name="БСБО-04-21", db_path=tmp_db)
    mock_payload = json.dumps({
        "schedule": {
            "Среда": [{"time": "12:40", "name": "Информатика", "type": "Лаб", "room": "В-1", "teacher": "Сидоров С.С."}]
        }
    }).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_payload

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = mgr.fetch_mirea_schedule_online()
        assert isinstance(res, list)
        assert res[0]["subject"] == "Информатика"


def test_feature_20_04_schedule_json_schema_validation(mirea_mgr):
    """Tier 1: Validate schedule response schema elements."""
    mock_data = {
        "schedule": {
            "Вторник": [{"time": "10:40", "name": "Физика", "room": "А-101", "type": "Лекция", "teacher": "Иванов И.И."}]
        }
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_data).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = mirea_mgr.fetch_mirea_schedule_online()
        assert isinstance(res, list)
        lesson = res[0]
        assert lesson["weekday"] == "Вторник"
        assert lesson["classroom"] == "А-101"


def test_feature_20_05_fetch_schedule_http_headers(mirea_mgr):
    """Tier 1: Verify HTTP request configuration."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"schedule": {}}'

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        mirea_mgr.fetch_mirea_schedule_online()
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.get_header("User-agent") == "VazusOS/1.0"


def test_feature_20_06_fetch_schedule_network_timeout_fallback(mirea_mgr, tmp_db):
    """Tier 2 Edge: Timeout exception triggers fallback to local cached schedule."""
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM mirea_schedule WHERE group_name='ИВБО-22-25'")
    cur.execute("""
    INSERT INTO mirea_schedule (group_name, weekday, lesson_time, subject, lesson_type, classroom, teacher)
    VALUES ('ИВБО-22-25', 'Среда', '12:40', 'Информатика', 'Лабораторная', 'В-202', 'Иванов И.И.')
    """)
    conn.commit()
    conn.close()

    with patch("urllib.request.urlopen", side_effect=Exception("Network Timeout")):
        res = mirea_mgr.fetch_mirea_schedule_online()
        assert isinstance(res, list)
        assert len(res) == 1
        assert res[0]["subject"] == "Информатика"


def test_feature_20_07_fetch_schedule_http_500_server_error(mirea_mgr, tmp_db):
    """Tier 2 Edge: HTTP 500 server error triggers cache fallback gracefully."""
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM mirea_schedule WHERE group_name='ИВБО-22-25'")
    conn.commit()
    conn.close()

    with patch("urllib.request.urlopen", side_effect=Exception("HTTP Error 500: Internal Server Error")):
        res = mirea_mgr.fetch_mirea_schedule_online()
        assert isinstance(res, list)
        assert res == []


def test_feature_20_08_fetch_schedule_invalid_json(mirea_mgr):
    """Tier 2 Edge: Malformed JSON response triggers cache fallback without crashing."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"<html>502 Bad Gateway</html>"

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = mirea_mgr.fetch_mirea_schedule_online()
        assert isinstance(res, list)


def test_feature_20_09_fetch_schedule_special_characters_group(tmp_db):
    """Tier 2 Edge: Group names with slash or special symbols handle request safely."""
    mgr = MireaStudentManager(group_name="ИВБО-22/25", db_path=tmp_db)
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"schedule": {}}'

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = mgr.fetch_mirea_schedule_online()
        assert isinstance(res, list)


def test_feature_20_10_fetch_schedule_empty_response(mirea_mgr):
    """Tier 2 Edge: Empty HTTP payload is handled properly."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"{}"

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = mirea_mgr.fetch_mirea_schedule_online()
        assert isinstance(res, list)


# ============================================================================
# FEATURE 21: R5 MIREA Offline SQLite Cache (Tier 1 & Tier 2)
# ============================================================================

def test_feature_21_01_init_mirea_db_schema(tmp_db):
    """Tier 1: Verify mirea_schedule table creation and columns."""
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(mirea_schedule)")
    columns = [col[1] for col in cur.fetchall()]
    conn.close()

    expected = ["id", "group_name", "weekday", "lesson_time", "subject", "lesson_type", "classroom", "teacher"]
    for col in expected:
        assert col in columns


def test_feature_21_02_get_cached_schedule_existing_rows(mirea_mgr, tmp_db):
    """Tier 1: Retrieve cached schedule entries from SQLite database."""
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM mirea_schedule WHERE group_name='ИВБО-22-25'")
    cur.execute("""
    INSERT INTO mirea_schedule (group_name, weekday, lesson_time, subject, lesson_type, classroom, teacher)
    VALUES ('ИВБО-22-25', 'Понедельник', '09:00', 'Алгебра', 'Лекция', 'А-1', 'Петров П.П.')
    """)
    conn.commit()
    conn.close()

    cached = mirea_mgr.get_cached_schedule()
    assert len(cached) == 1
    assert cached[0]["weekday"] == 'Понедельник'
    assert cached[0]["lesson_time"] == '09:00'
    assert cached[0]["subject"] == 'Алгебра'
    assert cached[0]["lesson_type"] == 'Лекция'
    assert cached[0]["classroom"] == 'А-1'
    assert cached[0]["teacher"] == 'Петров П.П.'


def test_feature_21_03_get_cached_schedule_group_isolation(tmp_db):
    """Tier 1: Ensure querying schedule filters strictly by group_name."""
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM mirea_schedule")
    cur.execute("""
    INSERT INTO mirea_schedule (group_name, weekday, lesson_time, subject, lesson_type, classroom, teacher)
    VALUES ('ИВБО-22-25', 'Вторник', '09:00', 'Физика', 'Лекция', 'Б-2', 'Сидоров С.С.'),
           ('ИВБО-02-22', 'Вторник', '10:40', 'Химия', 'Практика', 'В-3', 'Кузнецов К.К.')
    """)
    conn.commit()
    conn.close()

    mgr1 = MireaStudentManager("ИВБО-22-25", db_path=tmp_db)
    mgr2 = MireaStudentManager("ИВБО-02-22", db_path=tmp_db)

    assert len(mgr1.get_cached_schedule()) == 1
    assert mgr1.get_cached_schedule()[0]["subject"] == "Физика"
    assert len(mgr2.get_cached_schedule()) == 1
    assert mgr2.get_cached_schedule()[0]["subject"] == "Химия"


def test_feature_21_04_cached_schedule_ordering_and_fields(mirea_mgr, tmp_db):
    """Tier 1: Verify dictionary keys match expected schema fields."""
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM mirea_schedule WHERE group_name='ИВБО-22-25'")
    cur.execute("""
    INSERT INTO mirea_schedule (group_name, weekday, lesson_time, subject, lesson_type, classroom, teacher)
    VALUES ('ИВБО-22-25', 'Четверг', '14:20', 'Базы данных', 'Лабораторная', 'А-405', 'Васильев В.В.')
    """)
    conn.commit()
    conn.close()

    item = mirea_mgr.get_cached_schedule()[0]
    assert item["weekday"] == 'Четверг'
    assert item["lesson_time"] == '14:20'
    assert item["subject"] == 'Базы данных'
    assert item["lesson_type"] == 'Лабораторная'
    assert item["classroom"] == 'А-405'
    assert item["teacher"] == 'Васильев В.В.'


def test_feature_21_05_cached_schedule_multiple_lessons_same_day(mirea_mgr, tmp_db):
    """Tier 1: Retrieve multiple lessons scheduled on the same weekday."""
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM mirea_schedule WHERE group_name='ИВБО-22-25'")
    for t in ['09:00', '10:40', '12:40']:
        cur.execute("""
        INSERT INTO mirea_schedule (group_name, weekday, lesson_time, subject, lesson_type, classroom, teacher)
        VALUES ('ИВБО-22-25', 'Пятница', ?, 'Предмет', 'Пара', 'Кабинет', 'Преподаватель')
        """, (t,))
    conn.commit()
    conn.close()

    res = mirea_mgr.get_cached_schedule()
    assert len(res) == 3


def test_feature_21_06_get_cached_schedule_empty_db(tmp_db):
    """Tier 2 Edge: Query empty database schedule table."""
    mgr = MireaStudentManager("ПУСТАЯ-ГРУППА", db_path=tmp_db)
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM mirea_schedule")
    conn.commit()
    conn.close()

    res = mgr.get_cached_schedule()
    assert isinstance(res, list)
    assert res == []


def test_feature_21_07_cached_schedule_nonexistent_group(mirea_mgr, tmp_db):
    """Tier 2 Edge: Querying for non-existent group returns empty list."""
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM mirea_schedule WHERE group_name='НЕCУЩЕСТВУЮЩАЯ-ГРУППА'")
    conn.commit()
    conn.close()

    mirea_mgr.group_name = "НЕCУЩЕСТВУЮЩАЯ-ГРУППА"
    assert mirea_mgr.get_cached_schedule() == []


def test_feature_21_08_cached_schedule_null_and_empty_fields(mirea_mgr, tmp_db):
    """Tier 2 Edge: SQLite rows containing NULL or empty strings process safely."""
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM mirea_schedule WHERE group_name='ИВБО-22-25'")
    cur.execute("""
    INSERT INTO mirea_schedule (group_name, weekday, lesson_time, subject, lesson_type, classroom, teacher)
    VALUES ('ИВБО-22-25', 'Понедельник', '09:00', 'Самостоятельная работа', NULL, '', NULL)
    """)
    conn.commit()
    conn.close()

    res = mirea_mgr.get_cached_schedule()
    assert len(res) == 1
    assert res[0]["lesson_type"] is None
    assert res[0]["classroom"] == ''
    assert res[0]["teacher"] is None


def test_feature_21_09_cached_schedule_unicode_cyrillic_teachers(mirea_mgr, tmp_db):
    """Tier 2 Edge: UTF-8 / Cyrillic characters with titles and accents work correctly."""
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM mirea_schedule WHERE group_name='ИВБО-22-25'")
    cur.execute("""
    INSERT INTO mirea_schedule (group_name, weekday, lesson_time, subject, lesson_type, classroom, teacher)
    VALUES ('ИВБО-22-25', 'Среда', '10:40', 'Нейронные сети (AI/ML)', 'Семинар', 'МП-1 (А-405)', 'д.т.н., проф. Смиртюков В.А.')
    """)
    conn.commit()
    conn.close()

    res = mirea_mgr.get_cached_schedule()
    assert "AI/ML" in res[0]["subject"]
    assert "д.т.н., проф." in res[0]["teacher"]


def test_feature_21_10_cached_schedule_concurrent_read_write(tmp_db):
    """Tier 2 Edge: Multiple connections reading/writing cached schedule concurrently."""
    conn1 = sqlite3.connect(tmp_db)
    conn2 = sqlite3.connect(tmp_db)

    cur1 = conn1.cursor()
    cur1.execute("""
    INSERT INTO mirea_schedule (group_name, weekday, lesson_time, subject, lesson_type, classroom, teacher)
    VALUES ('ИВБО-22-25', 'Пятница', '12:40', 'Экономика', 'Лекция', 'Б-10', 'Егоров Е.Е.')
    """)
    conn1.commit()

    cur2 = conn2.cursor()
    rows = cur2.execute("SELECT COUNT(*) FROM mirea_schedule").fetchone()[0]

    conn1.close()
    conn2.close()
    assert rows >= 1


# ============================================================================
# FEATURE 22: R5 MIREA Keycloak SSO & 2FA (Tier 1 & Tier 2)
# ============================================================================

def test_feature_22_01_load_env_credentials_from_file(tmp_path):
    """Tier 1: Parse MIREA & Yandex credentials from local .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("""
MIREA_USERNAME="student_123"
MIREA_PASSWORD="secret_password"
YANDEX_EMAIL="student@yandex.ru"
YANDEX_APP_PASSWORD="app_pass_123"
    """, encoding="utf-8")

    with patch("vazus_core.mirea_exporter.ENV_FILE_PATH", env_file):
        creds = load_env_credentials()
        assert creds["username"] == "student_123"
        assert creds["password"] == "secret_password"
        assert creds["yandex_email"] == "student@yandex.ru"
        assert creds["yandex_password"] == "app_pass_123"


def test_feature_22_02_extract_login_action_url_json_layer(tmp_path):
    """Tier 1: Extract Keycloak loginAction URL from JSON kcContext pattern."""
    manager = MoodleSessionManager(session_file=tmp_path / "session.json")
    html = '''<script>const kcContext = {"loginAction":"https:\\/\\/sso.mirea.ru\\/auth\\/realms\\/mirea\\/login-actions\\/authenticate?execution=123"};</script>'''
    action_url = manager.extract_login_action_url(html, "https://sso.mirea.ru")
    assert action_url == "https://sso.mirea.ru/auth/realms/mirea/login-actions/authenticate?execution=123"


def test_feature_22_03_extract_login_action_url_soup_fallback(tmp_path):
    """Tier 1: Fallback extraction of form action via BeautifulSoup."""
    manager = MoodleSessionManager(session_file=tmp_path / "session.json")
    html = '''<html><body><form id="kc-form-login" action="/auth/realms/mirea/login-actions/auth"></form></body></html>'''
    action_url = manager.extract_login_action_url(html, "https://sso.mirea.ru/login")
    assert action_url == "https://sso.mirea.ru/auth/realms/mirea/login-actions/auth"


def test_feature_22_04_handle_max_registration_bypass_link(tmp_path):
    """Tier 1: Auto-decline MAX registration prompt by following skip link."""
    manager = MoodleSessionManager(session_file=tmp_path / "session.json")
    html = '''<html><body><div>Зарегистрироваться через макс</div><a href="/cancel_max">Пропустить</a></body></html>'''

    with patch.object(manager.session, "get") as mock_get:
        handled = manager.handle_max_registration_bypass(html, "https://online-edu.mirea.ru/my/")
        assert handled is True
        mock_get.assert_called_once_with("https://online-edu.mirea.ru/cancel_max", timeout=10)


def test_feature_22_05_yandex_imap_decode_mime_words():
    """Tier 1: Test MIME header decoding utility in IMAP reader."""
    reader = YandexIMAP2FAReader("test@yandex.ru", "pass")
    decoded = reader._decode_mime_words("=?UTF-8?B?0JrQvtC0INC/0L7QtNGC0LLQtdGA0LbQtNC10L3QuNGP?=")
    assert "Код подтверждения" in decoded


def test_feature_22_06_extract_keycloak_error_parsing(tmp_path):
    """Tier 2 Edge: Extract keycloak error summary from HTML/JSON error structures."""
    manager = MoodleSessionManager(session_file=tmp_path / "session.json")
    html_json = '{"message":{"type":"error","summary":"Неверное имя пользователя или пароль."}}'
    assert manager.extract_keycloak_error(html_json) == "Неверное имя пользователя или пароль."

    html_div = '<html><body><div class="kc-feedback-text">Учетная запись заблокирована</div></body></html>'
    assert manager.extract_keycloak_error(html_div) == "Учетная запись заблокирована"


def test_feature_22_07_session_cookies_save_and_load_roundtrip(tmp_path):
    """Tier 2 Edge: Save and load MoodleSession cookies and sesskey to disk."""
    sess_file = tmp_path / "user_session.json"
    manager = MoodleSessionManager(session_file=sess_file)
    manager.session.cookies.set("MoodleSession", "test_cookie_value_12345", domain="online-edu.mirea.ru", path="/")
    manager.sesskey = "xyz987654"

    manager.save_session_cookies()
    assert sess_file.exists()

    new_manager = MoodleSessionManager(session_file=sess_file)
    loaded = new_manager.load_session_cookies()
    assert loaded is True
    assert new_manager.sesskey == "xyz987654"
    assert new_manager.session.cookies.get("MoodleSession") == "test_cookie_value_12345"


def test_feature_22_08_session_is_authenticated_false(tmp_path):
    """Tier 2 Edge: is_authenticated returns False when redirected to login page."""
    manager = MoodleSessionManager(session_file=tmp_path / "session.json")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://online-edu.mirea.ru/login/index.php"
    mock_resp.text = "Please login"

    with patch.object(manager.session, "get", return_value=mock_resp):
        assert manager.is_authenticated() is False


def test_feature_22_09_yandex_imap_fetch_code_timeout():
    """Tier 2 Edge: IMAP 2FA reader returns None gracefully on timeout when no emails match."""
    reader = YandexIMAP2FAReader("test@yandex.ru", "pass")
    mock_imap = MagicMock()
    mock_imap.login.return_value = "OK"
    mock_imap.select.return_value = ("OK", [b"1"])
    mock_imap.search.return_value = ("OK", [b""])

    with patch("imaplib.IMAP4_SSL", return_value=mock_imap):
        code = reader.fetch_latest_2fa_code(timeout_sec=1)
        assert code is None


def test_feature_22_10_login_missing_credentials_failure(tmp_path):
    """Tier 2 Edge: login returns False when credentials are missing."""
    manager = MoodleSessionManager(session_file=tmp_path / "session.json")
    mock_creds = {
        "username": None,
        "password": None,
        "yandex_email": None,
        "yandex_password": None
    }
    with patch("vazus_core.mirea_exporter.load_env_credentials", return_value=mock_creds):
        res = manager.login(username=None, password=None)
        assert res is False


# ============================================================================
# FEATURE 23: R5 MIREA Moodle Material Exporter (Tier 1 & Tier 2)
# ============================================================================

def test_feature_23_01_exporter_init_directory(tmp_path):
    """Tier 1: MireaCourseExporter creates target export directory."""
    mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    export_dir = tmp_path / "courses"
    exporter = MireaCourseExporter(mgr, export_dir=export_dir)
    assert export_dir.exists()


def test_feature_23_02_get_enrolled_courses_ajax_api(tmp_path):
    """Tier 1: Discover courses via Moodle 4.x AJAX Service API."""
    mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    mgr.sesskey = "valid_sesskey"
    exporter = MireaCourseExporter(mgr, export_dir=tmp_path / "courses")

    ajax_resp = [{
        "data": {
            "courses": [
                {"id": 101, "fullname": "Архитектура ЭВМ"},
                {"id": 102, "fullname": "Операционные системы"}
            ]
        }
    }]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = ajax_resp

    with patch.object(mgr, "is_authenticated", return_value=True), \
         patch.object(mgr.session, "post", return_value=mock_resp):
        courses = exporter.get_enrolled_courses()
        assert len(courses) == 2
        assert courses[0]["course_id"] == 101
        assert courses[0]["title"] == "Архитектура ЭВМ"


def test_feature_23_03_get_enrolled_courses_html_crawling_fallback(tmp_path):
    """Tier 1: Discover courses via HTML page crawling fallback."""
    mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    mgr.sesskey = None
    exporter = MireaCourseExporter(mgr, export_dir=tmp_path / "courses")

    html = '''
    <html><body>
      <a href="https://online-edu.mirea.ru/course/view.php?id=205">Математический анализ</a>
    </body></html>
    '''
    mock_resp = MagicMock()
    mock_resp.text = html

    with patch.object(mgr, "is_authenticated", return_value=True), \
         patch.object(mgr.session, "get", return_value=mock_resp):
        courses = exporter.get_enrolled_courses()
        assert len(courses) >= 1
        assert courses[0]["course_id"] == 205
        assert courses[0]["title"] == "Математический анализ"


def test_feature_23_04_export_course_creates_markdown_summary(tmp_path):
    """Tier 1: export_course generates markdown conspect file."""
    mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    export_dir = tmp_path / "courses"
    exporter = MireaCourseExporter(mgr, export_dir=export_dir)

    html = '''
    <html><body>
      <li class="section">
        <h3 class="sectionname">Тема 1. Введение</h3>
        <div class="activity">
          <span class="instancename">Лекция 1</span>
          <a href="https://online-edu.mirea.ru/mod/resource/view.php?id=99">Ссылка</a>
        </div>
      </li>
    </body></html>
    '''
    mock_resp = MagicMock()
    mock_resp.text = html

    with patch.object(mgr.session, "get", return_value=mock_resp):
        result = exporter.export_course(course_id=301, course_title="Философия")
        assert result["course_id"] == 301

        expected_md = export_dir / "Философия" / "Философия_конспект.md"
        assert expected_md.exists()
        content = expected_md.read_text(encoding="utf-8")
        assert "Тема 1. Введение" in content
        assert "Лекция 1" in content


def test_feature_23_05_export_course_downloads_resource_files(tmp_path):
    """Tier 1: Download PDF file resources during course export."""
    mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    export_dir = tmp_path / "courses"
    exporter = MireaCourseExporter(mgr, export_dir=export_dir)

    course_html = '''
    <html><body>
      <li class="section">
        <div class="activity">
          <span class="instancename">Презентация PDF</span>
          <a href="https://online-edu.mirea.ru/mod/resource/view.php?id=88">Презентация</a>
        </div>
      </li>
    </body></html>
    '''
    page_resp = MagicMock()
    page_resp.text = course_html

    file_resp = MagicMock()
    file_resp.headers = {
        "Content-Disposition": 'attachment; filename="lecture1.pdf"',
        "Content-Type": "application/pdf"
    }
    file_resp.iter_content.return_value = [b"PDF_DUMMY_HEADER_BYTES"]

    def session_get_router(url, **kwargs):
        if "view.php?id=302" in url:
            return page_resp
        return file_resp

    with patch.object(mgr.session, "get", side_effect=session_get_router):
        res = exporter.export_course(course_id=302, course_title="Компьютерные сети")
        assert res["downloaded_files"] == 1
        downloaded = export_dir / "Компьютерные сети" / "lecture1.pdf"
        assert downloaded.exists()
        assert downloaded.read_bytes() == b"PDF_DUMMY_HEADER_BYTES"


def test_feature_23_06_get_enrolled_courses_unauthenticated(tmp_path):
    """Tier 2 Edge: Unauthenticated session returns empty course list."""
    mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    exporter = MireaCourseExporter(mgr, export_dir=tmp_path / "courses")

    with patch.object(mgr, "is_authenticated", return_value=False):
        assert exporter.get_enrolled_courses() == []


def test_feature_23_07_export_course_filename_sanitization(tmp_path):
    """Tier 2 Edge: Course titles with special OS characters are sanitized."""
    mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    export_dir = tmp_path / "courses"
    exporter = MireaCourseExporter(mgr, export_dir=export_dir)

    mock_resp = MagicMock()
    mock_resp.text = "<html><body></body></html>"

    with patch.object(mgr.session, "get", return_value=mock_resp):
        res = exporter.export_course(course_id=400, course_title="C++: Объектно-Ориентированное Программирование / OOP?")
        assert res["course_id"] == 400
        course_folder = Path(res["export_dir"])
        assert course_folder.exists()
        assert ":" not in course_folder.name
        assert "?" not in course_folder.name


def test_feature_23_08_export_course_ajax_api_error_recovery(tmp_path):
    """Tier 2 Edge: Handle AJAX error response and proceed to crawling."""
    mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    mgr.sesskey = "test_key"
    exporter = MireaCourseExporter(mgr, export_dir=tmp_path / "courses")

    ajax_err_resp = MagicMock()
    ajax_err_resp.status_code = 200
    ajax_err_resp.json.return_value = [{"error": True, "exception": "moodle_exception"}]

    crawl_resp = MagicMock()
    crawl_resp.text = '<html><body><a href="/course/view.php?id=999">Физическая культура</a></body></html>'

    def post_router(*args, **kwargs):
        return ajax_err_resp

    def get_router(*args, **kwargs):
        return crawl_resp

    with patch.object(mgr, "is_authenticated", return_value=True), \
         patch.object(mgr.session, "post", side_effect=post_router), \
         patch.object(mgr.session, "get", side_effect=get_router):
        courses = exporter.get_enrolled_courses()
        assert len(courses) == 1
        assert courses[0]["course_id"] == 999


def test_feature_23_09_export_course_duplicate_course_deduplication(tmp_path):
    """Tier 2 Edge: Deduplicate course links appearing multiple times on page."""
    mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    exporter = MireaCourseExporter(mgr, export_dir=tmp_path / "courses")

    html = '''
    <html><body>
      <a href="/course/view.php?id=500">Базы данных</a>
      <a href="/course/view.php?id=500">Перейти к курсу</a>
      <a href="/course/view.php?id=500">Базы данных</a>
    </body></html>
    '''
    mock_resp = MagicMock()
    mock_resp.text = html

    with patch.object(mgr, "is_authenticated", return_value=True), \
         patch.object(mgr.session, "get", return_value=mock_resp):
        courses = exporter.get_enrolled_courses()
        assert len(courses) == 1
        assert courses[0]["course_id"] == 500


def test_feature_23_10_export_course_http_download_exception_resilience(tmp_path):
    """Tier 2 Edge: File download exception does not crash course exporter."""
    mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    export_dir = tmp_path / "courses"
    exporter = MireaCourseExporter(mgr, export_dir=export_dir)

    course_html = '''
    <html><body>
      <li class="section">
        <div class="activity">
          <span class="instancename">Битый файл</span>
          <a href="https://online-edu.mirea.ru/mod/resource/view.php?id=77">Скачать</a>
        </div>
      </li>
    </body></html>
    '''
    course_resp = MagicMock()
    course_resp.text = course_html

    def session_get_router(url, **kwargs):
        if "view.php?id=600" in url:
            return course_resp
        raise Exception("Connection Reset By Peer")

    with patch.object(mgr.session, "get", side_effect=session_get_router):
        res = exporter.export_course(course_id=600, course_title="Сетевые протоколы")
        assert res["downloaded_files"] == 0
        md_file = export_dir / "Сетевые протоколы" / "Сетевые протоколы_конспект.md"
        assert md_file.exists()


def test_feature_21_11_db_corruption_fallback(tmp_path):
    """Tier 2 Remediation: Verify fail-closed empty return on SQLite error with zero fake seed data."""
    corrupt_db = str(tmp_path / "corrupt.db")
    mgr = MireaStudentManager(group_name="ИВБО-22-25", db_path=corrupt_db)

    with patch("sqlite3.connect", side_effect=sqlite3.DatabaseError("Database disk image is malformed")):
        sched = mgr.get_cached_schedule()
        assert isinstance(sched, list)
        assert len(sched) == 0

        milestones = mgr.get_academic_milestones()
        assert isinstance(milestones, list)
        assert len(milestones) == 0


def test_feature_20_11_schedule_fetch_error_fail_closed(tmp_db):
    """Tier 2 Edge: Official API failure with raise_on_error raises ScheduleFetchError."""
    mgr = MireaStudentManager(group_name="ИВБО-22-25", db_path=tmp_db)
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        with pytest.raises(ScheduleFetchError) as exc_info:
            mgr.fetch_mirea_schedule_online(raise_on_error=True)
        assert "Failed to fetch schedule for ИВБО-22-25" in str(exc_info.value)


def test_feature_22_13_session_required_error_fail_closed(tmp_path):
    """Tier 2 Edge: Missing or invalid session tokens raise SessionRequiredError."""
    mgr = MireaStudentManager(group_name="ИВБО-22-25")
    missing_session = tmp_path / "non_existent_session.json"
    with pytest.raises(SessionRequiredError):
        mgr.require_session(str(missing_session))

    empty_session = tmp_path / "empty_session.json"
    empty_session.write_text("{}", encoding="utf-8")
    with pytest.raises(SessionRequiredError):
        mgr.require_session(str(empty_session))



def test_feature_22_11_max_bypass_regex_no_false_positives(tmp_path):
    """Tier 2 Remediation: Verify MAX bypass regex prevents false positives on CSS/HTML max-width."""
    mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    css_html = '<html><head><style>.box { max-width: 100%; }</style></head><body><input maxlength="50"></body></html>'

    # Normal HTML with CSS max-width must NOT trigger bypass
    assert mgr.handle_max_registration_bypass(css_html, "https://online-edu.mirea.ru/my/") is False

    # Actual MAX registration page MUST trigger bypass
    max_html = '<html><body><div>Зарегистрироваться через МАКС</div><a href="/skip_max">Skip</a></body></html>'
    with patch.object(mgr.session, "get"):
        assert mgr.handle_max_registration_bypass(max_html, "https://online-edu.mirea.ru/my/") is True


def test_feature_22_12_imap_2fa_tag_matching_and_dashes():
    """Tier 2 Remediation: Verify IMAP 2FA regex supports hyphens, en-dashes, em-dashes and tags."""
    reader = YandexIMAP2FAReader("test@yandex.ru", "pass")
    mock_imap = MagicMock()
    mock_imap.login.return_value = "OK"
    mock_imap.select.return_value = ("OK", [b"1"])
    mock_imap.search.return_value = ("OK", [b"1"])

    # Subject with hyphen - MIME encoded
    msg_bytes = b"Subject: =?UTF-8?B?NjU0MzIxIC0g0LLQsNGIINC60L7QtCAjQUI=?=\r\n\r\nCode"
    mock_imap.fetch.return_value = ("OK", [(b"1 (RFC822)", msg_bytes)])

    with patch("imaplib.IMAP4_SSL", return_value=mock_imap):
        code = reader.fetch_latest_2fa_code(timeout_sec=5, target_tag="AB")
        assert code == "654321"




