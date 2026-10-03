"""
services/academic_verification/safety_guard.py — Strict Read-Only Academic Safety Guardrail.

Enforces a fail-closed, read-only safety invariant preventing unauthorized, accidental,
or adversarial mutations against authoritative university endpoints (online-edu.mirea.ru, lk.mirea.ru).

Key Invariants:
1. Mutating HTTP verbs (POST, PUT, DELETE, PATCH) are blocked by default.
2. Whitelisted Moodle 4 AJAX query methods (e.g. core_course_get_enrolled_courses_by_timeline_classification)
   are permitted for read-only course/catalogue discovery.
3. Dangerous GET URLs that initiate quiz attempts or submit coursework (startattempt.php, attempt.php, action=submit)
   are blocked.
4. Mutation override requires dual confirmation:
   - Explicit flag: allow_mutating_ops=True
   - Environment variable: ALLOW_MUTATING_ACADEMIC_OPS=="1"
"""

from __future__ import annotations

import json
import logging
import os
import posixpath
import re
import urllib.parse
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

import requests

logger = logging.getLogger("academic_verification.safety_guard")


class AcademicSafetyViolationError(PermissionError):
    """
    Raised when an outgoing HTTP operation violates the strict read-only academic invariant.
    Inherits from PermissionError for standard security error handling.
    """
    pass


# Authoritative whitelisted Moodle 4 AJAX read-only query methods
WHITELISTED_AJAX_METHODS: Tuple[str, ...] = (
    "core_course_get_enrolled_courses_by_timeline_classification",
    "core_course_get_courses_by_field",
    "core_enrol_get_users_courses",
    "core_course_get_contents",
    "core_user_get_users_by_field",
)

# Safe read-only HTTP verbs (fail-closed whitelist)
SAFE_HTTP_VERBS: Tuple[str, ...] = (
    "GET",
    "HEAD",
)

# Mutating HTTP verbs
MUTATING_HTTP_VERBS: Tuple[str, ...] = (
    "POST",
    "PUT",
    "DELETE",
    "PATCH",
)

# Dangerous GET URL substrings and query actions that alter academic state or start exams
DANGEROUS_GET_SUBSTRINGS: Tuple[str, ...] = (
    "startattempt.php",
    "attempt.php",
    "action=submit",
    "action=savesubmission",
    "processattempt.php",
    "repository/upload.php",
)


class AcademicSafetyGuard:
    """
    Interception guardrail for outgoing HTTP requests against university endpoints.
    Enforces fail-closed read-only safety policy.
    """

    WHITELISTED_AJAX_METHODS: Tuple[str, ...] = WHITELISTED_AJAX_METHODS
    SAFE_HTTP_VERBS: Tuple[str, ...] = SAFE_HTTP_VERBS
    MUTATING_HTTP_VERBS: Tuple[str, ...] = MUTATING_HTTP_VERBS
    DANGEROUS_GET_SUBSTRINGS: Tuple[str, ...] = DANGEROUS_GET_SUBSTRINGS

    def __init__(
        self,
        allow_mutating_ops: bool = False,
        whitelisted_methods: Optional[Iterable[str]] = None,
        dangerous_substrings: Optional[Iterable[str]] = None,
        safe_http_verbs: Optional[Iterable[str]] = None,
    ) -> None:
        self.allow_mutating_ops: bool = bool(allow_mutating_ops)
        self.whitelisted_methods: Set[str] = set(whitelisted_methods or WHITELISTED_AJAX_METHODS)
        self.dangerous_substrings: Tuple[str, ...] = tuple(dangerous_substrings or DANGEROUS_GET_SUBSTRINGS)
        self.safe_http_verbs: Set[str] = set(safe_http_verbs or SAFE_HTTP_VERBS)
        self.mutating_verbs: Set[str] = set(MUTATING_HTTP_VERBS)

    def is_dual_override_active(self, explicit_flag: Optional[bool] = None) -> bool:
        """
        Validates whether dual override is fully satisfied.
        Requires BOTH:
        1. explicit_flag == True (or instance allow_mutating_ops == True)
        2. os.environ["ALLOW_MUTATING_ACADEMIC_OPS"] == "1"
        """
        flag_candidate = explicit_flag if explicit_flag is not None else self.allow_mutating_ops
        if not bool(flag_candidate):
            return False

        env_val = os.environ.get("ALLOW_MUTATING_ACADEMIC_OPS", "").strip()
        return env_val == "1"

    def is_whitelisted_ajax_request(
        self,
        method: str,
        url: str,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Determines whether a POST request is an approved read-only Moodle 4 AJAX query.
        Validates URL endpoint (strict /lib/ajax/service.php) and checks that every requested method
        belongs to the approved whitelisted methods set.
        """
        if method.upper() != "POST":
            return False

        # Must target Moodle AJAX service endpoint strictly (/lib/ajax/service.php)
        unquoted_url = urllib.parse.unquote(url)
        parsed_url = urllib.parse.urlparse(unquoted_url)
        path = posixpath.normpath(parsed_url.path.lower())
        if path != "/lib/ajax/service.php":
            return False

        if not kwargs:
            return False

        extracted_methods: List[str] = []

        # 1. Inspect json payload
        json_data = kwargs.get("json")
        if json_data is not None:
            if isinstance(json_data, list):
                for item in json_data:
                    if isinstance(item, dict) and "methodname" in item:
                        extracted_methods.append(str(item["methodname"]).strip())
            elif isinstance(json_data, dict) and "methodname" in json_data:
                extracted_methods.append(str(json_data["methodname"]).strip())

        # 2. Inspect data payload if json was not provided
        data_payload = kwargs.get("data")
        if data_payload is not None and not extracted_methods:
            if isinstance(data_payload, str):
                try:
                    parsed_body = json.loads(data_payload)
                    if isinstance(parsed_body, list):
                        for item in parsed_body:
                            if isinstance(item, dict) and "methodname" in item:
                                extracted_methods.append(str(item["methodname"]).strip())
                    elif isinstance(parsed_body, dict) and "methodname" in parsed_body:
                        extracted_methods.append(str(parsed_body["methodname"]).strip())
                except Exception:
                    pass

        # 3. Inspect query params
        params_payload = kwargs.get("params")
        if params_payload is not None and not extracted_methods:
            if isinstance(params_payload, dict):
                for k, v in params_payload.items():
                    k_str = str(k).strip().lower()
                    if k_str == "methodname":
                        extracted_methods.append(str(v).strip())
                    elif k_str == "info":
                        extracted_methods.append(str(v).strip())

        # If no methods could be extracted, cannot whitelist
        if not extracted_methods:
            return False

        # All extracted methods must be in the whitelist
        return all(m in self.whitelisted_methods for m in extracted_methods)

    def is_dangerous_get_request(
        self,
        method: str,
        url: str,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Determines whether a GET request attempts to start a quiz attempt or submit coursework.
        Canonicalizes URL via unquote and inspects both path and query parameters case-insensitively.
        """
        if method.upper() not in ("GET", "HEAD"):
            return False

        unquoted_url = urllib.parse.unquote(url)
        url_lower = url.lower()
        unquoted_lower = unquoted_url.lower()

        # 1. Check raw and percent-decoded URLs against dangerous substrings
        for pattern in self.dangerous_substrings:
            pat_lower = pattern.lower()
            if pat_lower in url_lower or pat_lower in unquoted_lower:
                return True

        # 2. Check query string in URL itself (case-insensitive)
        try:
            parsed_url = urllib.parse.urlparse(unquoted_url)
            parsed_qs = urllib.parse.parse_qs(parsed_url.query)
            for k, vals in parsed_qs.items():
                if str(k).strip().lower() == "action":
                    for v in vals:
                        if str(v).strip().lower() in ("submit", "savesubmission", "attempt"):
                            return True
        except Exception:
            pass

        # 3. Inspect kwargs params dict with case-insensitive key and value matching
        if kwargs and "params" in kwargs:
            params = kwargs["params"]
            if isinstance(params, dict):
                for k, v in params.items():
                    if str(k).strip().lower() == "action" and str(v).strip().lower() in (
                        "submit",
                        "savesubmission",
                        "attempt",
                    ):
                        return True

        return False

    def intercept_request(
        self,
        method: str,
        url: str,
        kwargs: Optional[Dict[str, Any]] = None,
        allow_mutating_ops: Optional[bool] = None,
    ) -> bool:
        """
        Inspects an outgoing HTTP request before execution.
        Raises AcademicSafetyViolationError if the request violates read-only invariants.
        Returns True if the request is permitted.
        """
        normalized_method = (method or "GET").upper().strip()
        normalized_url = str(url or "").strip()
        kw = dict(kwargs) if kwargs else {}

        # Resolve explicit override flag
        explicit_flag = allow_mutating_ops
        if explicit_flag is None:
            explicit_flag = kw.get("allow_mutating_ops")

        dual_override = self.is_dual_override_active(explicit_flag)

        # Invariant 1: Dangerous GET/HEAD detection
        if self.is_dangerous_get_request(normalized_method, normalized_url, kw):
            if not dual_override:
                err_msg = (
                    f"AcademicSafetyViolationError: Dangerous test initiation/submission GET request "
                    f"blocked for URL: {normalized_url}. Under no circumstances may automated agents "
                    f"start attempts or submit university coursework without explicit dual confirmation."
                )
                logger.error(err_msg)
                raise AcademicSafetyViolationError(err_msg)
            logger.warning(
                "AcademicSafetyGuard: Dual override permitted dangerous GET request to %s",
                normalized_url
            )
            return True

        # Invariant 2: Permitted whitelisted Moodle 4 AJAX query (only for POST to /lib/ajax/service.php)
        if normalized_method == "POST" and self.is_whitelisted_ajax_request(normalized_method, normalized_url, kw):
            logger.debug(
                "AcademicSafetyGuard: Permitted whitelisted Moodle AJAX query to %s",
                normalized_url
            )
            return True

        # Invariant 3: Safe read-only HTTP verbs (GET, HEAD)
        if normalized_method in self.safe_http_verbs:
            return True

        # Invariant 4: Fail-closed for all other verbs (POST, PUT, DELETE, PATCH, CONNECT, TRACE, etc.)
        if not dual_override:
            err_msg = (
                f"AcademicSafetyViolationError: Mutating or unwhitelisted HTTP {normalized_method} blocked for "
                f"URL: {normalized_url}. Operations outside SAFE_HTTP_VERBS {self.safe_http_verbs} are prohibited "
                f"under fail-closed academic safety policy without explicit dual confirmation."
            )
            logger.error(err_msg)
            raise AcademicSafetyViolationError(err_msg)

        logger.warning(
            "AcademicSafetyGuard: Dual override permitted mutating %s request to %s",
            normalized_method,
            normalized_url
        )
        return True

    def guard_request(self, method: str, url: str, *args: Any, **kwargs: Any) -> None:
        """Convenience method calling intercept_request with arbitrary args."""
        self.intercept_request(method=method, url=url, kwargs=kwargs)

    def wrap_session(self, session: requests.Session) -> requests.Session:
        """
        Hooks into requests.Session to intercept and guard all outgoing requests.
        Wraps session.request so any call to session.get, session.post, etc.
        is intercepted by intercept_request.
        """
        original_request = session.request

        def guarded_request(method: str, url: str, *args: Any, **kwargs: Any):
            self.intercept_request(method=method, url=url, kwargs=kwargs)
            return original_request(method, url, *args, **kwargs)

        session.request = guarded_request
        return session
