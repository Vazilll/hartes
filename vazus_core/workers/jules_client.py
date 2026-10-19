"""
vazus_core/jules_client.py -- Google Jules REST API Async Client.

Provides async client bindings for Google Jules Cloud VM pre-commit analysis
and verification API (https://jules.googleapis.com/v1alpha/).
Includes dataclasses for API payloads and graceful fallback signals when
JULES_API_KEY is missing, rate-limited (HTTP 429), or unavailable.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

DEFAULT_JULES_BASE_URL = "https://jules.googleapis.com/v1alpha"


@dataclass
class JulesSource:
    id: str
    name: str = ""
    repository_url: str = ""
    default_branch: str = "main"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JulesSource":
        name = data.get("name", "")
        src_id = data.get("id") or (name.split("/")[-1] if "/" in name else name) or "unknown_source"
        return cls(
            id=src_id,
            name=name or f"sources/{src_id}",
            repository_url=data.get("repositoryUrl", data.get("repository_url", "")),
            default_branch=data.get("defaultBranch", data.get("default_branch", "main")),
            metadata=data.get("metadata", {})
        )


@dataclass
class JulesSessionRequest:
    source_id: str
    prompt: str
    title: str = ""
    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "prompt": self.prompt,
            "title": self.title or f"Session for {self.source_id}",
        }
        if self.options:
            payload["options"] = self.options
        return payload


@dataclass
class JulesSession:
    id: str
    state: str = "STATE_UNSPECIFIED"
    source_id: str = ""
    title: str = ""
    prompt: str = ""
    create_time: str = ""
    update_time: str = ""
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JulesSession":
        name = data.get("name", "")
        session_id = data.get("id") or (name.split("/")[-1] if "/" in name else name) or "unknown_session"
        source = data.get("source", "")
        source_id = source.split("/")[-1] if "/" in source else source
        return cls(
            id=session_id,
            state=data.get("state", "STATE_UNSPECIFIED"),
            source_id=source_id,
            title=data.get("title", ""),
            prompt=data.get("prompt", ""),
            create_time=data.get("createTime", data.get("create_time", "")),
            update_time=data.get("updateTime", data.get("update_time", "")),
            error_message=data.get("errorMessage", data.get("error_message")),
            metadata=data.get("metadata", {})
        )


@dataclass
class JulesActivity:
    id: str
    session_id: str = ""
    activity_type: str = ""
    status: str = ""
    message: str = ""
    timestamp: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], session_id: str = "") -> "JulesActivity":
        name = data.get("name", "")
        act_id = data.get("id") or (name.split("/")[-1] if "/" in name else name) or "unknown_activity"
        return cls(
            id=act_id,
            session_id=session_id or data.get("sessionId", data.get("session_id", "")),
            activity_type=data.get("activityType", data.get("activity_type", data.get("type", "UNKNOWN"))),
            status=data.get("status", "SUCCESS"),
            message=data.get("message", data.get("description", "")),
            timestamp=data.get("timestamp", data.get("createTime", "")),
            details=data.get("details", {})
        )


class JulesClient:
    """
    Async REST API Client for Google Jules Cloud VM Pre-Commit Verification.
    Authenticates via X-Goog-Api-Key header (sourced from JULES_API_KEY env var).
    Provides structured methods and automatic fallback result signals.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = DEFAULT_JULES_BASE_URL, timeout: float = 30.0):
        self.api_key = api_key or os.getenv("JULES_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.fallback_active: bool = False
        self.last_error: Optional[str] = None

    @property
    def headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Goog-Api-Key"] = self.api_key
        return headers

    def is_live_enabled(self) -> bool:
        """Returns True ONLY if explicit opt-in VAZUS_JULES_LIVE=1 or VAZUS_JULES_ALLOW_CLOUD=1 is set (or during pytest mocks)."""
        if os.getenv("VAZUS_JULES_OFFLINE") == "1":
            return False
        if "PYTEST_CURRENT_TEST" in os.environ:
            return True
        return os.getenv("VAZUS_JULES_LIVE") == "1" or os.getenv("VAZUS_JULES_ALLOW_CLOUD") == "1"

    def is_fallback_required(self) -> bool:
        """Returns True if JULES_API_KEY is missing, cloud live is not enabled, or if previous API calls flagged fallback."""
        return self.fallback_active or not bool(self.api_key) or not self.is_live_enabled()

    async def list_sources_async(self) -> Dict[str, Any]:
        """
        List remote repositories / sources from Google Jules API.
        Returns dict: {"fallback": bool, "reason": Optional[str], "sources": List[JulesSource]}.
        """
        if not self.api_key:
            self.fallback_active = True
            self.last_error = "JULES_API_KEY is not set"
            return {"fallback": True, "reason": self.last_error, "sources": []}

        if not self.is_live_enabled():
            self.fallback_active = True
            self.last_error = "Cloud Jules VM disabled (requires explicit VAZUS_JULES_LIVE=1): defaulting to local verification"
            return {"fallback": True, "reason": self.last_error, "sources": []}

        url = f"{self.base_url}/sources"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_sources = data.get("sources", [])
                    sources = [JulesSource.from_dict(s) for s in raw_sources]
                    return {"fallback": False, "reason": None, "sources": sources}
                elif resp.status_code == 429:
                    self.fallback_active = True
                    self.last_error = "HTTP 429 Rate Limit Exceeded"
                    logger.warning(f"[JulesClient] {self.last_error}")
                    return {"fallback": True, "reason": self.last_error, "sources": []}
                else:
                    self.fallback_active = True
                    self.last_error = f"HTTP {resp.status_code}: {resp.text}"
                    logger.error(f"[JulesClient] {self.last_error}")
                    return {"fallback": True, "reason": self.last_error, "sources": []}
        except Exception as e:
            self.fallback_active = True
            self.last_error = f"Network error: {str(e)}"
            logger.error(f"[JulesClient] {self.last_error}")
            return {"fallback": True, "reason": self.last_error, "sources": []}

    async def create_session_async(
        self,
        source_id: str,
        prompt: str,
        title: str = "",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create cloud VM analysis session in Google Jules API.
        Returns dict: {"fallback": bool, "reason": Optional[str], "session": Optional[JulesSession]}.
        """
        if not self.api_key:
            self.fallback_active = True
            self.last_error = "JULES_API_KEY is not set"
            return {"fallback": True, "reason": self.last_error, "session": None}

        if not self.is_live_enabled():
            self.fallback_active = True
            self.last_error = "Cloud Jules VM disabled (requires explicit VAZUS_JULES_LIVE=1): defaulting to local verification"
            return {"fallback": True, "reason": self.last_error, "session": None}

        req = JulesSessionRequest(
            source_id=source_id,
            prompt=prompt,
            title=title,
            options=options or {}
        )
        url = f"{self.base_url}/sessions"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=req.to_dict(), headers=self.headers)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    session = JulesSession.from_dict(data)
                    return {"fallback": False, "reason": None, "session": session}
                elif resp.status_code == 429:
                    self.fallback_active = True
                    self.last_error = "HTTP 429 Rate Limit Exceeded"
                    logger.warning(f"[JulesClient] {self.last_error}")
                    return {"fallback": True, "reason": self.last_error, "session": None}
                else:
                    self.fallback_active = True
                    self.last_error = f"HTTP {resp.status_code}: {resp.text}"
                    logger.error(f"[JulesClient] {self.last_error}")
                    return {"fallback": True, "reason": self.last_error, "session": None}
        except Exception as e:
            self.fallback_active = True
            self.last_error = f"Network error: {str(e)}"
            logger.error(f"[JulesClient] {self.last_error}")
            return {"fallback": True, "reason": self.last_error, "session": None}

    async def get_session_async(self, session_id: str) -> Dict[str, Any]:
        """
        Poll session state from Google Jules API.
        Returns dict: {"fallback": bool, "reason": Optional[str], "session": Optional[JulesSession]}.
        """
        if not self.is_live_enabled():
            self.fallback_active = True
            self.last_error = "Cloud Jules VM disabled (requires explicit VAZUS_JULES_LIVE=1): defaulting to local verification"
            return {"fallback": True, "reason": self.last_error, "session": None}

        if not self.api_key:
            self.fallback_active = True
            self.last_error = "JULES_API_KEY is not set"
            return {"fallback": True, "reason": self.last_error, "session": None}

        session_path = session_id if session_id.startswith("sessions/") else f"sessions/{session_id}"
        url = f"{self.base_url}/{session_path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    session = JulesSession.from_dict(data)
                    return {"fallback": False, "reason": None, "session": session}
                elif resp.status_code == 429:
                    self.fallback_active = True
                    self.last_error = "HTTP 429 Rate Limit Exceeded"
                    logger.warning(f"[JulesClient] {self.last_error}")
                    return {"fallback": True, "reason": self.last_error, "session": None}
                else:
                    self.fallback_active = True
                    self.last_error = f"HTTP {resp.status_code}: {resp.text}"
                    logger.error(f"[JulesClient] {self.last_error}")
                    return {"fallback": True, "reason": self.last_error, "session": None}
        except Exception as e:
            self.fallback_active = True
            self.last_error = f"Network error: {str(e)}"
            logger.error(f"[JulesClient] {self.last_error}")
            return {"fallback": True, "reason": self.last_error, "session": None}

    async def list_sessions_async(self, page_size: int = 10) -> Dict[str, Any]:
        """
        Lists recent sessions from Google Jules API.
        Returns:
            {"fallback": False, "reason": None, "sessions": List[JulesSession]} on success.
            {"fallback": True, "reason": str, "sessions": []} on fallback.
        """
        if self.is_fallback_required():
            return {"fallback": True, "reason": "Jules offline or credentials missing", "sessions": []}

        url = f"{self.base_url}/sessions"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=self.headers, params={"pageSize": page_size})
                if resp.status_code == 200:
                    data = resp.json()
                    sessions = [JulesSession.from_dict(s) for s in data.get("sessions", [])]
                    return {"fallback": False, "reason": None, "sessions": sessions}
                else:
                    return {"fallback": True, "reason": f"HTTP {resp.status_code}", "sessions": []}
        except Exception as e:
            return {"fallback": True, "reason": str(e), "sessions": []}

    async def list_activities_async(self, session_id: str) -> Dict[str, Any]:
        """
        List activity logs for a session from Google Jules API.
        Returns dict: {"fallback": bool, "reason": Optional[str], "activities": List[JulesActivity]}.
        """
        if not self.is_live_enabled():
            self.fallback_active = True
            self.last_error = "Cloud Jules VM disabled (requires explicit VAZUS_JULES_LIVE=1): defaulting to local verification"
            return {"fallback": True, "reason": self.last_error, "activities": []}

        if not self.api_key:
            self.fallback_active = True
            self.last_error = "JULES_API_KEY is not set"
            return {"fallback": True, "reason": self.last_error, "activities": []}

        session_path = session_id if session_id.startswith("sessions/") else f"sessions/{session_id}"
        url = f"{self.base_url}/{session_path}/activities"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_activities = data.get("activities", [])
                    activities = [JulesActivity.from_dict(a, session_id=session_id) for a in raw_activities]
                    return {"fallback": False, "reason": None, "activities": activities}
                elif resp.status_code == 429:
                    self.fallback_active = True
                    self.last_error = "HTTP 429 Rate Limit Exceeded"
                    logger.warning(f"[JulesClient] {self.last_error}")
                    return {"fallback": True, "reason": self.last_error, "activities": []}
                else:
                    self.fallback_active = True
                    self.last_error = f"HTTP {resp.status_code}: {resp.text}"
                    logger.error(f"[JulesClient] {self.last_error}")
                    return {"fallback": True, "reason": self.last_error, "activities": []}
        except Exception as e:
            self.fallback_active = True
            self.last_error = f"Network error: {str(e)}"
            logger.error(f"[JulesClient] {self.last_error}")
            return {"fallback": True, "reason": self.last_error, "activities": []}

    async def verify_precommit_cloud_async(
        self,
        code_proposal: str,
        task_prompt: str,
        source_id: str = "vazus-main"
    ) -> Dict[str, Any]:
        """
        Attempts end-to-end cloud VM pre-commit verification.
        Returns result with fallback signal if API key is missing or HTTP/network error occurs.
        """
        if not self.api_key:
            return {
                "fallback": True,
                "reason": "JULES_API_KEY env var not configured",
                "verified": False
            }

        create_res = await self.create_session_async(
            source_id=source_id,
            prompt=f"Pre-commit analysis for task: {task_prompt}\nProposal:\n{code_proposal}",
            title="Cloud VM Pre-Commit Verification"
        )
        if create_res.get("fallback"):
            return create_res

        session = create_res.get("session")
        if not session:
            return {"fallback": True, "reason": "Failed to initialize cloud VM session", "verified": False}

        poll_res = await self.get_session_async(session.id)
        if poll_res.get("fallback"):
            return poll_res

        polled_session = poll_res.get("session")
        state = polled_session.state if polled_session else "UNKNOWN"
        return {
            "fallback": False,
            "session_id": session.id,
            "state": state,
            "verified": state in ("SUCCEEDED", "COMPLETED", "APPROVED")
        }
