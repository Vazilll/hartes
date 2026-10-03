"""
services.academic_verification.auth — Keycloak SSO session and token manager.

Handles authentication with RTU MIREA Keycloak SSO (sso.mirea.ru, client_id=lk-mirea),
persisting and validating session cookies for lk.mirea.ru and online-edu.mirea.ru (Moodle),
extracting login actions, parsing 2FA OTP codes, and enforcing fail-closed security.
"""

from __future__ import annotations

import datetime
import html
import json
import logging
import os
import re
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional, Union

import requests

logger = logging.getLogger("academic_verification.auth")

# Authoritative Keycloak SSO contracts
KEYCLOAK_BASE_URL: str = "https://sso.mirea.ru"
KEYCLOAK_REALM: str = "mirea"
KEYCLOAK_CLIENT_ID: str = "lk-mirea"
KEYCLOAK_SSO_AUTH_URL: str = "https://sso.mirea.ru/realms/mirea/protocol/openid-connect/auth"
KEYCLOAK_SSO_TOKEN_URL: str = "https://sso.mirea.ru/realms/mirea/protocol/openid-connect/token"

# Default session cookie storage paths
DEFAULT_SESSION_FILE: Path = Path(r"C:\vazus\user_mirea_session.json")
ALT_SESSION_FILE: Path = Path(r"C:\vazus\data\sessions\user_mirea_session.json")

ONLINE_EDU_BASE_URL: str = "https://online-edu.mirea.ru"
LK_MIREA_BASE_URL: str = "https://lk.mirea.ru"


class SessionRequiredError(Exception):
    """Raised when an authenticated session is required but missing, expired, or invalid."""
    pass


class AuthenticationRequiredError(SessionRequiredError):
    """Raised when authentication credentials or SSO tokens are missing."""
    pass


class KeycloakAuthManager:
    """
    Manages SSO authentication lifecycle, session persistence, OTP extraction,
    and fail-closed session validation for RTU MIREA services.
    """

    KEYCLOAK_BASE_URL: str = KEYCLOAK_BASE_URL
    KEYCLOAK_REALM: str = KEYCLOAK_REALM
    KEYCLOAK_CLIENT_ID: str = KEYCLOAK_CLIENT_ID
    KEYCLOAK_SSO_AUTH_URL: str = KEYCLOAK_SSO_AUTH_URL
    KEYCLOAK_SSO_TOKEN_URL: str = KEYCLOAK_SSO_TOKEN_URL
    DEFAULT_SESSION_FILE: Path = DEFAULT_SESSION_FILE
    ALT_SESSION_FILE: Path = ALT_SESSION_FILE

    def __init__(
        self,
        session_path: Optional[Union[str, Path]] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self.session_path: Optional[Path] = Path(session_path) if session_path else None
        self.username: Optional[str] = username or os.environ.get("MIREA_USERNAME")
        self.password: Optional[str] = password or os.environ.get("MIREA_PASSWORD")
        self._session: Optional[requests.Session] = None
        self._cookies: Dict[str, str] = {}
        self._sesskey: Optional[str] = None

    def resolve_session_path(self, explicit_path: Optional[Union[str, Path]] = None) -> Path:
        """Resolves target session file path prioritizing explicit argument, instance path, or defaults."""
        if explicit_path:
            return Path(explicit_path)
        if self.session_path:
            return self.session_path
        if ALT_SESSION_FILE.exists():
            return ALT_SESSION_FILE
        return DEFAULT_SESSION_FILE

    @classmethod
    def extract_login_action_url(cls, html_content: str, base_url: str = KEYCLOAK_BASE_URL) -> Optional[str]:
        """
        Extracts dynamic loginAction URL from Keycloak HTML page / kcContext JavaScript object.
        """
        if not html_content:
            return None

        # 1. Search in kcContext JavaScript object: "loginAction": "https://..."
        kc_match = re.search(r'["\']loginAction["\']\s*:\s*["\']([^"\']+)["\']', html_content)
        if kc_match:
            raw_url = kc_match.group(1).replace(r"\/", "/")
            raw_url = html.unescape(raw_url)
            return urllib.parse.urljoin(base_url, raw_url)

        # 2. Search in HTML login form action: <form id="kc-form-login" action="...">
        form_match = re.search(
            r'<form[^>]+id=["\']kc-form-login["\'][^>]+action=["\']([^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if not form_match:
            form_match = re.search(
                r'<form[^>]+action=["\']([^"\']+)["\'][^>]+id=["\']kc-form-login["\']',
                html_content,
                re.IGNORECASE,
            )
        if not form_match:
            # Fallback to any login-actions/authenticate action
            form_match = re.search(
                r'action=["\']([^"\']*login-actions/authenticate[^"\']*)["\']',
                html_content,
                re.IGNORECASE,
            )

        if form_match:
            raw_url = html.unescape(form_match.group(1))
            return urllib.parse.urljoin(base_url, raw_url)

        return None

    def _extract_login_action(self, html_content: str, base_url: str = KEYCLOAK_BASE_URL) -> Optional[str]:
        """Instance alias for extract_login_action_url."""
        return self.extract_login_action_url(html_content, base_url)

    @classmethod
    def parse_2fa_otp(cls, email_body: str) -> Optional[str]:
        """
        Parses 6-digit one-time password (OTP) from notification email body.
        Standard pattern: 6 consecutive digits bounded by word boundaries.
        """
        if not email_body:
            return None
        match = re.search(r"\b(\d{6})\b", email_body)
        return match.group(1) if match else None

    @classmethod
    def detect_max_registration_prompt(cls, html_content: str) -> bool:
        """
        Detects if Keycloak redirected to MAX messenger registration interstitial.
        Guards against false positives on CSS rules like 'max-width'.
        """
        if not html_content:
            return False
        content_lower = html_content.lower()
        has_max_keyword = (
            "max.ru" in content_lower
            or "мессенджер max" in content_lower
            or "мессенджере max" in content_lower
            or "мессенджер" in content_lower
            or "зарегистрироваться через макс" in content_lower
        )
        is_just_css = "max-width" in content_lower and "мессенджер" not in content_lower and "max.ru" not in content_lower
        return has_max_keyword and not is_just_css

    @classmethod
    def extract_max_skip_url(cls, html_content: str, base_url: str = KEYCLOAK_BASE_URL) -> Optional[str]:
        """Extracts skip URL for MAX messenger registration prompt."""
        if not html_content:
            return None
        match = re.search(r'href=["\']([^"\']*skip[^"\']*)["\']', html_content, re.IGNORECASE)
        if match:
            raw_url = html.unescape(match.group(1))
            return urllib.parse.urljoin(base_url, raw_url)
        return None

    def load_session(self, session_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Loads and parses persisted session file.
        Fails closed with SessionRequiredError if absent, empty, or corrupted.
        """
        target_path = self.resolve_session_path(session_path)
        if not target_path.exists():
            raise SessionRequiredError(f"Session file not found: {target_path}")

        if target_path.stat().st_size == 0:
            raise SessionRequiredError(f"Session file is empty (0 bytes): {target_path}")

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise SessionRequiredError(f"Corrupted or invalid JSON session file {target_path}: {e}") from e

        if not isinstance(data, dict) or "cookies" not in data:
            raise SessionRequiredError(f"Session file missing 'cookies' mapping: {target_path}")

        cookies = data.get("cookies", {})
        if not isinstance(cookies, dict) or not cookies:
            raise SessionRequiredError(f"Session cookies dictionary is empty in {target_path}")

        self._cookies = cookies
        self._sesskey = data.get("sesskey")
        return data

    def save_session(
        self,
        cookies: Dict[str, str],
        sesskey: Optional[str] = None,
        session_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """
        Atomically saves session cookies and Moodle sesskey to disk.
        """
        target_path = self.resolve_session_path(session_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "cookies": cookies,
            "sesskey": sesskey or cookies.get("sesskey", self._sesskey or ""),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        # Atomic write via temporary file
        temp_dir = target_path.parent
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            json.dump(payload, tf, ensure_ascii=False, indent=2)
            temp_name = tf.name

        os.replace(temp_name, target_path)
        self._cookies = cookies
        self._sesskey = payload["sesskey"]
        return target_path

    def validate_session(self, session: Optional[requests.Session] = None) -> bool:
        """
        Validates if current session cookies are authenticated and unexpired.
        Fails closed (returns False) on login redirect, expired cookies, or connection errors.
        """
        s = session or self._session
        if s is None:
            s = requests.Session()
            if self._cookies:
                s.cookies.update(self._cookies)
            else:
                try:
                    data = self.load_session()
                    s.cookies.update(data.get("cookies", {}))
                except SessionRequiredError:
                    return False

        try:
            # Query authenticated endpoint to verify active session
            resp = s.get(f"{ONLINE_EDU_BASE_URL}/login/index.php", allow_redirects=True, timeout=10)
            if resp.status_code != 200:
                return False

            url_lower = str(resp.url).lower()
            text_lower = resp.text.lower()

            # If redirected to login page or page prompts for login, session is expired
            if "login/index.php" in url_lower:
                return False
            if "please login" in text_lower or "вход в систему" in text_lower or "введите логин" in text_lower:
                return False

            return True
        except Exception as e:
            logger.warning(f"Session validation probe failed: {e}")
            return False

    def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        session_path: Optional[Union[str, Path]] = None,
    ) -> requests.Session:
        """
        Authenticates against Keycloak SSO and returns an active requests.Session.
        Fails closed with AuthenticationRequiredError if credentials and session file are missing.
        """
        # 1. Attempt cached session restoration if available
        try:
            target_file = self.resolve_session_path(session_path)
            if target_file.exists():
                self.load_session(target_file)
                session = requests.Session()
                session.cookies.update(self._cookies)
                if self.validate_session(session):
                    self._session = session
                    return session
        except SessionRequiredError:
            pass

        # 2. Check credentials; fail closed if absent
        user = username or self.username
        pwd = password or self.password

        if not user or not pwd:
            target_file = self.resolve_session_path(session_path)
            raise AuthenticationRequiredError(
                f"Fail-closed: No active session found at {target_file} and credentials "
                "(MIREA_USERNAME / MIREA_PASSWORD) are absent."
            )

        # 3. Perform Keycloak SSO authentication flow
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        try:
            # Step A: Request initial SSO auth page
            auth_params = {
                "client_id": self.KEYCLOAK_CLIENT_ID,
                "response_type": "code",
                "scope": "openid",
                "redirect_uri": f"{LK_MIREA_BASE_URL}/auth/callback",
            }
            init_resp = session.get(self.KEYCLOAK_SSO_AUTH_URL, params=auth_params, timeout=15)
            init_resp.raise_for_status()

            login_action_url = self.extract_login_action_url(init_resp.text, base_url=self.KEYCLOAK_BASE_URL)
            if not login_action_url:
                raise AuthenticationRequiredError("Unable to locate loginAction in Keycloak HTML response.")

            # Step B: POST user credentials
            login_data = {"username": user, "password": pwd}
            login_resp = session.post(login_action_url, data=login_data, allow_redirects=True, timeout=15)
            login_resp.raise_for_status()

            # Step C: Detect and bypass MAX prompt if present
            if self.detect_max_registration_prompt(login_resp.text):
                skip_url = self.extract_max_skip_url(login_resp.text, base_url=self.KEYCLOAK_BASE_URL)
                if skip_url:
                    skip_resp = session.get(skip_url, allow_redirects=True, timeout=15)
                    skip_resp.raise_for_status()

            # Save session cookies
            cookie_dict = session.cookies.get_dict()
            if cookie_dict:
                self.save_session(cookie_dict, session_path=session_path)

            self._session = session
            return session
        except Exception as e:
            if isinstance(e, AuthenticationRequiredError):
                raise
            raise AuthenticationRequiredError(f"Keycloak SSO authentication failed: {e}") from e


# Aliases for interface compatibility across test suites
KeycloakSSOClient = KeycloakAuthManager
