"""
services/academic_verification/moodle_client.py — Authoritative Moodle LMS Client.

Provides read-only discovery of Moodle courses and quizzes for RTU MIREA students
on online-edu.mirea.ru via Moodle 4 AJAX APIs and semantic course HTML scraping.

Key Features:
- Resolves examination sheet numbers to real Moodle course IDs (e.g. 81917 -> 16479).
- Discovers enrolled courses via `core_course_get_enrolled_courses_by_timeline_classification`.
- Discovers available quizzes via read-only `/mod/quiz/view.php?id=...` extraction.
- Fully protected by `AcademicSafetyGuard` to enforce the fail-closed read-only invariant.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests

from services.academic_verification.safety_guard import AcademicSafetyGuard

logger = logging.getLogger("academic_verification.moodle_client")

# Authoritative examination sheet to Moodle course ID mapping
EXAM_SHEET_TO_MOODLE_MAP: Dict[str, int] = {
    "81917": 16479,  # Математический анализ
    "66804": 16480,  # Линейная алгебра и аналитическая геометрия
    "86958": 16486,  # Математическая логика и теория алгоритмов
    "86146": 16017,  # Иностранный язык
}

DEFAULT_MOODLE_BASE_URL: str = "https://online-edu.mirea.ru"
DEFAULT_SESSION_FILE: Path = Path(r"C:\vazus\user_mirea_session.json")
ALT_SESSION_FILE: Path = Path(r"C:\vazus\data\sessions\user_mirea_session.json")


class MoodleLMSClient:
    """
    Client for RTU MIREA Moodle LMS (online-edu.mirea.ru).
    Operates strictly under AcademicSafetyGuard to prevent accidental test mutation.
    """

    EXAM_SHEET_TO_MOODLE_MAP: Dict[str, int] = EXAM_SHEET_TO_MOODLE_MAP

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        auth_manager: Optional[Any] = None,
        safety_guard: Optional[AcademicSafetyGuard] = None,
        session_path: Optional[Union[str, Path]] = None,
        base_url: str = DEFAULT_MOODLE_BASE_URL,
    ) -> None:
        self.base_url: str = base_url.rstrip("/")
        self.safety_guard: AcademicSafetyGuard = safety_guard if safety_guard is not None else AcademicSafetyGuard()
        self.auth_manager = auth_manager
        self.session_path: Optional[Path] = Path(session_path) if session_path else None
        self._session: requests.Session = session if session is not None else requests.Session()
        
        # Hook safety guard into session requests
        self._session = self.safety_guard.wrap_session(self._session)

        self.exam_sheet_map: Dict[str, int] = dict(EXAM_SHEET_TO_MOODLE_MAP)
        self.sesskey: Optional[str] = None
        self._load_cached_session_if_available()

    def _resolve_session_path(self) -> Optional[Path]:
        """Resolves existing session file path."""
        if self.session_path and self.session_path.exists():
            return self.session_path
        if ALT_SESSION_FILE.exists():
            return ALT_SESSION_FILE
        if DEFAULT_SESSION_FILE.exists():
            return DEFAULT_SESSION_FILE
        return None

    def _load_cached_session_if_available(self) -> None:
        """Loads cookies and sesskey from local session JSON cache or auth manager."""
        if self.auth_manager and hasattr(self.auth_manager, "get_cookies"):
            cookies = self.auth_manager.get_cookies()
            if cookies:
                self._session.cookies.update(cookies)
                self.sesskey = getattr(self.auth_manager, "sesskey", None)
                return

        path = self._resolve_session_path()
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cookies = data.get("cookies", data)
                if isinstance(cookies, dict):
                    self._session.cookies.update(cookies)
                self.sesskey = data.get("sesskey", self._session.cookies.get("sesskey"))
        except Exception as exc:
            logger.debug("Failed loading cached session in MoodleLMSClient: %s", exc)

    def resolve_course_id(self, exam_sheet: Union[str, int]) -> Optional[int]:
        """
        Maps university examination sheet number (e.g. '81917') to real Moodle course ID (16479).
        """
        return self.exam_sheet_map.get(str(exam_sheet).strip())

    def get_enrolled_courses(
        self,
        classification: str = "all",
        sort: str = "fullname",
    ) -> List[Dict[str, Any]]:
        """
        Queries Moodle 4 AJAX API (core_course_get_enrolled_courses_by_timeline_classification)
        to discover all courses in which the student is currently enrolled.
        """
        url = f"{self.base_url}/lib/ajax/service.php"
        payload = [
            {
                "index": 0,
                "methodname": "core_course_get_enrolled_courses_by_timeline_classification",
                "args": {
                    "offset": 0,
                    "limit": 0,
                    "classification": classification,
                    "sort": sort,
                },
            }
        ]

        # Explicitly invoke safety guard check before issuing request
        self.safety_guard.intercept_request("POST", url, kwargs={"json": payload})

        params: Dict[str, str] = {}
        if self.sesskey:
            params["sesskey"] = self.sesskey

        response = self._session.post(url, json=payload, params=params, timeout=15)
        response.raise_for_status()

        raw_json = response.json()
        if isinstance(raw_json, list) and len(raw_json) > 0:
            first_block = raw_json[0]
            if isinstance(first_block, dict):
                if first_block.get("error"):
                    err_msg = first_block.get("exception", {}).get("message", "Moodle AJAX error")
                    logger.warning("Moodle AJAX returned error flag: %s", err_msg)
                data = first_block.get("data", {})
                if isinstance(data, dict) and "courses" in data:
                    return data["courses"]
                if "courses" in first_block:
                    return first_block["courses"]
        elif isinstance(raw_json, dict):
            data = raw_json.get("data", {})
            if isinstance(data, dict) and "courses" in data:
                return data["courses"]
            if "courses" in raw_json:
                return raw_json["courses"]

        return []

    # Alias for API compatibility
    discover_enrolled_courses = get_enrolled_courses

    def get_quizzes_for_course(self, course_id: int) -> List[Dict[str, Any]]:
        """
        Fetches the course overview HTML page and extracts available quiz/test links
        without initiating exam attempts (strictly read-only).
        """
        cid = int(course_id)
        url = f"{self.base_url}/course/view.php?id={cid}"

        # Guard against unauthorized mutation
        self.safety_guard.intercept_request("GET", url, kwargs={})

        response = self._session.get(url, timeout=15)
        response.raise_for_status()
        html_text = response.text

        # Extract quizzes using regex pattern targeting /mod/quiz/view.php?id=...
        # Ignore other modules (resource, forum, assign, etc.)
        quiz_pattern = re.compile(
            r'<a[^>]+href=["\']([^"\']*/mod/quiz/view\.php\?[^"\']*)["\'][^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )

        quizzes: List[Dict[str, Any]] = []
        seen_urls = set()

        for match in quiz_pattern.finditer(html_text):
            raw_href = match.group(1).strip()
            inner_html = match.group(2)

            # Ensure URL is absolute
            if raw_href.startswith("/"):
                full_url = f"{self.base_url}{raw_href}"
            else:
                full_url = raw_href

            # Safety check: ensure never to capture startattempt.php
            if "startattempt.php" in full_url or full_url in seen_urls:
                continue

            seen_urls.add(full_url)

            # Extract quiz cmid parameter
            id_match = re.search(r'[?&]id=(\d+)', full_url)
            quiz_id = int(id_match.group(1)) if id_match else None

            # Clean HTML tags to get human-readable quiz name
            clean_name = re.sub(r'<[^>]+>', '', inner_html).strip()
            clean_name = html.unescape(clean_name)
            if not clean_name and quiz_id:
                clean_name = f"Тест {quiz_id}"

            quizzes.append({
                "id": quiz_id,
                "url": full_url,
                "name": clean_name,
                "course_id": cid,
            })

        return quizzes

    # Alias for API compatibility
    fetch_course_quizzes = get_quizzes_for_course

    def validate_session(self) -> bool:
        """
        Validates whether the current Moodle session is active and authenticated.
        Returns False if redirected to login/index.php.
        """
        url = f"{self.base_url}/my/"
        try:
            self.safety_guard.intercept_request("GET", url, kwargs={})
            resp = self._session.get(url, allow_redirects=False, timeout=10)
            if resp.status_code in (301, 302, 303, 307):
                loc = resp.headers.get("Location", "")
                if "login" in loc:
                    return False
            if "login/index.php" in getattr(resp, "url", ""):
                return False
            if "Please login" in resp.text:
                return False
            return resp.status_code == 200
        except Exception as exc:
            logger.debug("Session validation error in MoodleLMSClient: %s", exc)
            return False


# Aliases for interface compatibility
MoodleTruthClient = MoodleLMSClient
