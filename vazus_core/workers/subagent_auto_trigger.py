"""
vazus_core.subagent_auto_trigger — Hermes Multi-Agent Task Intent Evaluator,
Interactive Confirmation Gate, and Background Subagent Dispatcher.

Fulfills Requirement R1 for Vazus OS Milestone M1.
"""

import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from vazus_core.engine.utils import fast_json_dumps
from vazus_core.engine.reasoning_effort_controller import ReasoningEffortController
from vazus_core.engine.subagent_framework import DeclarativeSubagentEngine
from vazus_core.memory.dialogue_persister import SubagentDialoguePersister

logger = logging.getLogger("SubagentAutoTrigger")


def safe_print(text: str = "", end: str = "\n"):
    """Safe print helper for Windows cp1252 / ANSI HUD streams."""
    try:
        sys.stdout.write(text + end)
        sys.stdout.flush()
    except (UnicodeEncodeError, AttributeError) as exc:
        logger.debug("safe_print fallback encoding note: %s", exc)
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_text = text.encode(enc, errors="replace").decode(enc, errors="replace")
        sys.stdout.write(safe_text + end)
        sys.stdout.flush()


@dataclass(init=False)
class IntentEvaluationResult:
    """
    Encapsulates the result of intent evaluation for a user request.
    Supports attribute aliases for seamless compatibility across subsystem APIs.
    """
    user_prompt: str
    complexity_score: float
    requires_subagents: bool
    recommended_subagents: list[str]
    reasoning_summary: str
    estimated_effort: str
    recommended_mode: str
    matched_skills: list[str]
    subtasks: list[dict[str, Any]]
    metadata: dict[str, Any]

    def __init__(
        self,
        user_prompt: str = "",
        complexity_score: float = 0.0,
        *,
        requires_subagents: bool = False,
        recommended_subagents: list[str] | None = None,
        reasoning_summary: str = "",
        estimated_effort: str = "low",
        recommended_mode: str = "single_agent",
        matched_skills: list[str] | None = None,
        subtasks: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs
    ):
        self.user_prompt = user_prompt
        self.complexity_score = complexity_score
        self.requires_subagents = kwargs.get("requires_multi_agent", requires_subagents)
        self.recommended_subagents = kwargs.get("suggested_subagents", recommended_subagents if recommended_subagents is not None else [])
        self.reasoning_summary = kwargs.get("rationale", kwargs.get("reasoning", reasoning_summary))
        self.estimated_effort = kwargs.get("effort_level", estimated_effort)
        self.recommended_mode = recommended_mode
        self.matched_skills = matched_skills if matched_skills is not None else []
        self.subtasks = subtasks if subtasks is not None else []
        self.metadata = metadata if metadata is not None else {}

    @property
    def intent_score(self) -> float:
        return self.complexity_score

    @intent_score.setter
    def intent_score(self, val: float):
        self.complexity_score = val

    @property
    def requires_multi_agent(self) -> bool:
        return self.requires_subagents

    @requires_multi_agent.setter
    def requires_multi_agent(self, val: bool):
        self.requires_subagents = val

    @property
    def suggested_subagents(self) -> list[str]:
        return self.recommended_subagents

    @suggested_subagents.setter
    def suggested_subagents(self, val: list[str]):
        self.recommended_subagents = val

    @property
    def reasoning(self) -> str:
        return self.reasoning_summary

    @reasoning.setter
    def reasoning(self, val: str):
        self.reasoning_summary = val

    @property
    def rationale(self) -> str:
        return self.reasoning_summary

    @rationale.setter
    def rationale(self, val: str):
        self.reasoning_summary = val

    @property
    def effort_level(self) -> str:
        return self.estimated_effort

    @effort_level.setter
    def effort_level(self, val: str):
        self.estimated_effort = val

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_prompt": self.user_prompt,
            "complexity_score": self.complexity_score,
            "intent_score": self.intent_score,
            "requires_subagents": self.requires_subagents,
            "requires_multi_agent": self.requires_multi_agent,
            "recommended_subagents": self.recommended_subagents,
            "suggested_subagents": self.suggested_subagents,
            "reasoning_summary": self.reasoning_summary,
            "reasoning": self.reasoning,
            "estimated_effort": self.estimated_effort,
            "effort_level": self.effort_level,
            "recommended_mode": self.recommended_mode,
            "matched_skills": self.matched_skills,
            "subtasks": self.subtasks,
            "metadata": self.metadata
        }


@dataclass
class TaskSpec:
    """Specification for a subagent task dispatch request."""
    subagent_name: str = "code_engineer"
    prompt: str = ""
    task_id: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    background: bool = True
    effort: str = "high"
    timeout: int = 300
    log_file: str | None = None
    auto_confirm: bool = False
    dry_run: bool = False
    backend: str = "auto"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubagentDispatchHandle:
    """Handle for tracking and managing a non-blocking background subagent task."""
    task_id: str
    subagent_name: str
    status: str = "DISPATCHED"
    pid: int = 0
    log_path: str = ""
    created_at: float = field(default_factory=time.time)
    result: dict[str, Any] | None = None
    process: subprocess.Popen | None = field(default=None, repr=False)
    backend: str = "subprocess"
    go_client: Any = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def start_time(self) -> float:
        return self.created_at

    @start_time.setter
    def start_time(self, val: float):
        self.created_at = val

    @property
    def log_file(self) -> str:
        return self.log_path

    @log_file.setter
    def log_file(self, val: str):
        self.log_path = val

    @property
    def is_background(self) -> bool:
        return self.process is not None or self.pid > 0 or self.backend == "go_bus"

    def is_alive(self) -> bool:
        """Checks if background subagent process is actively running."""
        if self.go_client is not None and self.backend == "go_bus":
            try:
                st_res = self.go_client.get_status(self.task_id)
                curr_status = st_res.get("status", self.status)
                self.status = curr_status
                return curr_status in ("CREATED", "RUNNING", "PAUSED")
            except Exception:
                return self.status in ("DISPATCHED", "RUNNING")

        if self.process is not None:
            poll_res = self.process.poll()
            if poll_res is None:
                self.status = "RUNNING"
                return True
            self.status = "COMPLETED" if poll_res == 0 else "FAILED"
            return False
        return self.status in ("DISPATCHED", "RUNNING")

    def poll_status(self) -> str:
        """Non-blocking status check."""
        self.is_alive()
        return self.status

    def poll_events(self, since_seq: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        """Polls events emitted by subagent."""
        if self.go_client is not None and self.backend == "go_bus":
            try:
                res = self.go_client.poll_events(self.task_id, since_seq=since_seq, limit=limit)
                return res.get("events", [])
            except Exception as exc:
                logger.debug("Go bus poll_events error: %s", exc)
        return []

    def get_result(self, timeout: float = 0.0) -> dict[str, Any] | None:
        """Non-blocking or bounded result getter."""
        if self.process is not None and timeout > 0:
            self.wait(timeout=timeout)
        return self.result

    def close(self):
        """Closes process stream descriptors and releases OS process handle references."""
        if self.process is not None:
            try:
                if self.process.stdout and not getattr(self.process.stdout, "closed", True):
                    self.process.stdout.close()
                if self.process.stderr and not getattr(self.process.stderr, "closed", True):
                    self.process.stderr.close()
                if self.process.stdin and not getattr(self.process.stdin, "closed", True):
                    self.process.stdin.close()
            except Exception as exc:
                logger.debug("Process stream close note: %s", exc)
            try:
                poll_res = self.process.poll()
                if poll_res is not None and self.process.returncode is None:
                    self.process.returncode = poll_res
            except Exception as exc:
                logger.debug("Process returncode check note: %s", exc)
            if hasattr(self.process, "_handle") and self.process._handle is not None:
                try:
                    if hasattr(self.process._handle, "Close"):
                        self.process._handle.Close()
                    else:
                        import _winapi
                        _winapi.CloseHandle(self.process._handle)
                except Exception as exc:
                    logger.debug("WinAPI CloseHandle note: %s", exc)
                try:
                    if self.process.returncode is None:
                        self.process.returncode = 0
                    self.process._handle = None
                except Exception as exc:
                    logger.debug("Reset process handle note: %s", exc)

    def wait(self, timeout: float | None = None) -> dict[str, Any]:
        """Waits for background subagent process completion and returns status dict."""
        with self._lock:
            if self.result is not None:
                return self.result
            if self.go_client is not None and self.backend == "go_bus":
                t_end = time.time() + (timeout or 300)
                while time.time() < t_end:
                    if not self.is_alive():
                        break
                    time.sleep(0.1)
                self.result = {"task_id": self.task_id, "status": self.status}
                return self.result

            if self.process is not None:
                try:
                    stdout, stderr = self.process.communicate(timeout=timeout)
                    ret_code = self.process.returncode if self.process.returncode is not None else 0
                    self.status = "COMPLETED" if ret_code == 0 else "FAILED"
                    self.result = {
                        "task_id": self.task_id,
                        "returncode": ret_code,
                        "stdout": (stdout or "").decode("utf-8", errors="ignore") if isinstance(stdout, bytes) else (stdout or ""),
                        "stderr": (stderr or "").decode("utf-8", errors="ignore") if isinstance(stderr, bytes) else (stderr or ""),
                        "status": self.status
                    }
                    self.close()
                    return self.result
                except subprocess.TimeoutExpired:
                    logger.warning(f"[DispatchHandle] Task {self.task_id} timed out after {timeout}s. Terminating PID {self.pid}.")
                    self._kill_unlocked()
                    self.result = {
                        "task_id": self.task_id,
                        "returncode": -1,
                        "error": f"Timeout expired ({timeout}s) while waiting for background subagent; process killed.",
                        "status": "KILLED"
                    }
                    return self.result
            return {"task_id": self.task_id, "status": self.status, "result": self.result}

    def cancel(self, reason: str = "") -> bool:
        """Cancels background subagent execution."""
        with self._lock:
            if self.go_client is not None and self.backend == "go_bus":
                try:
                    self.go_client.cancel(self.task_id, reason=reason)
                except Exception as exc:
                    logger.debug("Go bus cancel error: %s", exc)
                self.status = "CANCELLED"
                return True
            return self._kill_unlocked()

    def kill(self) -> bool:
        """Terminates background subagent process or thread task."""
        return self.cancel("process killed")

    def _kill_unlocked(self) -> bool:
        if self.process is not None:
            try:
                self.process.kill()
                try:
                    self.process.wait(timeout=1.0)
                except Exception as exc:
                    logger.debug("Process wait note after kill: %s", exc)
                if self.process.returncode is None:
                    self.process.returncode = -9
                self.status = "KILLED"
                self.close()
                return True
            except Exception as e:
                logger.error(f"Failed to kill process {self.pid}: {e}")
                if self.process and self.process.returncode is None:
                    self.process.returncode = -9
                self.status = "KILLED"
                self.close()
                return False
        self.status = "KILLED"
        return True

    def __del__(self):
        self.close()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "subagent_name": self.subagent_name,
            "status": self.status,
            "pid": self.pid,
            "log_path": self.log_path,
            "log_file": self.log_file,
            "created_at": self.created_at,
            "start_time": self.start_time,
            "result": self.result,
            "backend": self.backend
        }


class GoSubagentBusClient:
    """
    Client adapter communicating with the Go Subagent Actor Bus (subagent_bus.exe)
    over JSON-RPC 2.0 Stdio or SSE transport.
    """
    def __init__(
        self,
        binary_path: str = r"C:\vazus\services\subagent_bus\subagent_bus.exe",
        sse_url: Optional[str] = None,
        timeout: float = 10.0
    ):
        if not os.path.exists(binary_path) and os.path.exists(r"C:\vazus\tools\bin\subagent_bus.exe"):
            binary_path = r"C:\vazus\tools\bin\subagent_bus.exe"
        self.binary_path = os.path.normpath(binary_path)
        self.sse_url = sse_url
        self.timeout = timeout
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._req_id = 0

    def is_available(self) -> bool:
        """Checks if the subagent_bus.exe binary exists or SSE URL is configured."""
        if self.sse_url:
            return True
        return os.path.isfile(self.binary_path)

    def _ensure_proc(self):
        """Ensures that the Go subagent bus background process is running."""
        if self._proc is None or self._proc.poll() is not None:
            self._proc = subprocess.Popen(
                [self.binary_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )

    def close(self):
        """Terminates persistent Go subagent bus session."""
        with self._lock:
            if self._proc is not None:
                try:
                    if self._proc.stdin:
                        self._proc.stdin.close()
                    self._proc.terminate()
                    self._proc.wait(timeout=2.0)
                except Exception:
                    pass
                self._proc = None

    def __del__(self):
        self.close()

    def call_tool(self, tool_name: str, arguments: dict[str, Any], timeout: Optional[float] = None) -> dict[str, Any]:
        """Calls an MCP tool on the Go bus over persistent Stdio JSON-RPC 2.0 session."""
        if not self.is_available():
            raise RuntimeError(f"Go subagent bus binary not available at {self.binary_path}")

        with self._lock:
            self._ensure_proc()
            self._req_id += 1
            req_id = self._req_id

            req = json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                }
            }) + "\n"

            try:
                assert self._proc is not None and self._proc.stdin is not None
                self._proc.stdin.write(req)
                self._proc.stdin.flush()
                assert self._proc.stdout is not None
                line = self._proc.stdout.readline()
            except Exception as e:
                self.close()
                raise RuntimeError(f"Communication error with Go subagent bus: {e}")

            if not line:
                stderr = self._proc.stderr.read() if self._proc and self._proc.stderr else ""
                self.close()
                raise RuntimeError(f"Empty response from Go subagent bus: stderr={stderr}")

            resp = json.loads(line)
            if "error" in resp:
                raise RuntimeError(f"MCP tool error ({resp['error'].get('code')}): {resp['error'].get('message')}")

            result = resp.get("result", {})
            if result.get("isError"):
                err_msg = ""
                for c in result.get("content", []):
                    if c.get("type") == "text":
                        err_msg += c.get("text", "")
                raise RuntimeError(f"MCP tool returned error: {err_msg}")

            # Extract text content and parse if JSON
            content_items = result.get("content", [])
            for c in content_items:
                if c.get("type") == "text":
                    text = c.get("text", "")
                    try:
                        return json.loads(text)
                    except Exception:
                        return {"text": text}

            return result

    def spawn_actor(
        self,
        task_id: str,
        subagent_name: str,
        prompt: str,
        role: str = "worker",
        params: Optional[dict[str, Any]] = None,
        timeout_sec: int = 300,
        mailbox_cap: int = 256,
        auto_start: bool = True
    ) -> dict[str, Any]:
        """Spawns an actor goroutine via subagent_spawn."""
        args = {
            "id": task_id,
            "name": subagent_name,
            "role": role,
            "prompt": prompt,
            "params": params or {},
            "timeout_sec": timeout_sec,
            "mailbox_cap": mailbox_cap,
            "auto_start": auto_start,
        }
        return self.call_tool("subagent_spawn", args)

    def send_message(
        self,
        subagent_id: str,
        content: str,
        message_type: str = "instruction",
        sender: str = "orchestrator",
        payload: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Delivers a message to the target actor's mailbox."""
        args = {
            "subagent_id": subagent_id,
            "type": message_type,
            "sender": sender,
            "content": content,
            "payload": payload or {},
        }
        return self.call_tool("subagent_send_message", args)

    def broadcast(
        self,
        content: str,
        message_type: str = "instruction",
        sender: str = "orchestrator",
        role_filter: str = "",
        payload: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Broadcasts a message across subagents with optional role filter."""
        args = {
            "content": content,
            "type": message_type,
            "sender": sender,
            "role_filter": role_filter,
            "payload": payload or {},
        }
        return self.call_tool("subagent_broadcast", args)

    def poll_events(
        self,
        subagent_id: str,
        since_seq: int = 0,
        limit: int = 50
    ) -> dict[str, Any]:
        """Polls events from actor ring buffer."""
        args = {
            "subagent_id": subagent_id,
            "since_seq": since_seq,
            "limit": limit,
        }
        return self.call_tool("subagent_poll_events", args)

    def cancel(self, subagent_id: str, reason: str = "") -> dict[str, Any]:
        """Cancels an actor."""
        args = {
            "subagent_id": subagent_id,
            "reason": reason or "cancelled by client",
        }
        return self.call_tool("subagent_cancel", args)

    def get_status(self, subagent_id: str) -> dict[str, Any]:
        """Queries status and telemetry for an actor."""
        return self.call_tool("subagent_get_status", {"subagent_id": subagent_id})

    def list_subagents(self, status: str = "all", role: str = "") -> dict[str, Any]:
        """Lists subagents registered in bus."""
        return self.call_tool("subagent_list", {"status": status, "role": role})

    def reap(self, max_age_sec: int = 3600) -> dict[str, Any]:
        """Reaps terminated subagents."""
        return self.call_tool("subagent_reap", {"max_age_sec": max_age_sec})


class HermesTaskIntentEvaluator:
    """
    Evaluates user prompts to determine task complexity, multi-step requirements,
    and recommended subagent delegation.
    """

    def __init__(self, threshold: float = 0.6, keyword_weights: dict[str, float] | None = None):
        self.threshold = threshold
        self.keyword_weights = keyword_weights if keyword_weights is not None else {
            "deep research": 0.4,
            "smt z3": 0.4,
            "e2e test": 0.35,
            "concordia": 0.35,
            "refactor": 0.3,
            "benchmark": 0.3,
            "multi-agent": 0.4,
            "darwinian": 0.3,
            "reflexion": 0.3,
            "create app": 0.35,
            "full stack": 0.35,
            "optimize": 0.25,
            "verify": 0.25,
            "investigate": 0.3,
            "research": 0.3,
            "build": 0.25,
            "implement": 0.25,
            "codebase": 0.25
        }
        self.skill_parser = None
        try:
            from vazus_core.engine.dynamic_skill_dispatcher import SkillIntentParser
            self.skill_parser = SkillIntentParser(auto_index=True)
        except Exception as e:
            logger.debug(f"[HermesTaskIntentEvaluator] SkillIntentParser initialization skipped: {e}")

    def _compute_structural_complexity(self, prompt_clean: str) -> float:
        struct_score = 0.2
        length = len(prompt_clean)
        lines = [l for l in prompt_clean.splitlines() if l.strip()]

        if length > 50:
            struct_score += 0.15
        if length > 200:
            struct_score += 0.15
        if len(lines) > 3:
            struct_score += 0.15
        if "```" in prompt_clean:
            struct_score += 0.25

        return min(1.0, struct_score)

    def _compute_keyword_complexity(self, prompt_lower: str) -> Tuple[float, List[str]]:
        sorted_kws = sorted(self.keyword_weights.items(), key=lambda x: len(x[0]), reverse=True)
        matched_keywords = []
        keyword_score = 0.0

        prompt_work = re.sub(r'[\-_]', ' ', prompt_lower)
        for kw, weight in sorted_kws:
            kw_normalized = re.sub(r'[\-_]', ' ', kw)
            pattern = r'\b' + re.escape(kw_normalized) + r'\b'
            if re.search(pattern, prompt_work):
                keyword_score += weight
                matched_keywords.append(kw)
                prompt_work = re.sub(pattern, ' ', prompt_work)

        return min(1.0, keyword_score), matched_keywords

    def _compute_skill_score(self, prompt_clean: str) -> Tuple[float, List[str]]:
        if self.skill_parser is None:
            return 0.0, []
        try:
            matched_meta = self.skill_parser.match_skills(prompt_clean, top_k=3)
            matched_ids = [s.skill_id for s in matched_meta]
            skill_score = max([s.score for s in matched_meta], default=0.0) if matched_meta else 0.0
            return skill_score, matched_ids
        except Exception as e:
            logger.debug(f"[HermesTaskIntentEvaluator] Skill matching error: {e}")
            return 0.0, []

    def _map_suggested_subagents(self, prompt_lower: str, requires_subagents: bool) -> List[str]:
        suggested = []
        if any(k in prompt_lower for k in ["research", "deep research", "search", "investigate", "paper", "explore"]):
            suggested.append("open_deep_researcher")
        if any(k in prompt_lower for k in ["code", "refactor", "build", "create app", "implement", "repl", "full stack", "algorithm"]):
            suggested.append("rlm_code_engineer")
        if any(k in prompt_lower for k in ["verify", "smt z3", "test", "concordia", "check", "audit", "provenance"]):
            suggested.append("verifier_worker")

        if requires_subagents and not suggested:
            suggested = ["rlm_code_engineer", "open_deep_researcher", "verifier_worker"]
        return suggested

    def evaluate(self, user_prompt: str) -> IntentEvaluationResult:
        """Evaluates task complexity and identifies subagent requirements."""
        if not user_prompt or not user_prompt.strip():
            return IntentEvaluationResult(
                user_prompt=user_prompt or "",
                complexity_score=0.0,
                requires_subagents=False,
                recommended_subagents=[],
                reasoning_summary="Empty prompt",
                estimated_effort="low",
                recommended_mode="single_agent",
                matched_skills=[],
                subtasks=[],
                metadata={"matched_keywords": [], "prompt_length": 0}
            )

        prompt_clean = user_prompt.strip()
        prompt_lower = prompt_clean.lower()

        struct_score = self._compute_structural_complexity(prompt_clean)
        keyword_score, matched_keywords = self._compute_keyword_complexity(prompt_lower)
        skill_score, matched_skills_ids = self._compute_skill_score(prompt_clean)

        composite_score = round(0.20 * struct_score + 0.60 * keyword_score + 0.20 * skill_score, 3)
        if keyword_score >= 0.7:
            composite_score = max(composite_score, 0.65)
        elif keyword_score >= 0.5:
            composite_score = max(composite_score, 0.55)

        composite_score = min(1.0, max(0.0, composite_score))
        requires_subagents = (composite_score >= self.threshold) or (len(matched_keywords) >= 2)
        suggested = self._map_suggested_subagents(prompt_lower, requires_subagents)

        effort_cfg = ReasoningEffortController.get_config(composite_score)
        estimated_effort = effort_cfg["level"]

        mode = "multi_agent_interactive" if requires_subagents else "single_agent"
        reasoning = f"Matched keywords: {matched_keywords}; Score: {composite_score} (threshold: {self.threshold})"
        subtasks = [{"subagent": name, "action": f"Execute subtask via {name}", "effort": estimated_effort} for name in suggested]

        return IntentEvaluationResult(
            user_prompt=prompt_clean,
            complexity_score=composite_score,
            requires_subagents=requires_subagents,
            recommended_subagents=suggested,
            reasoning_summary=reasoning,
            estimated_effort=estimated_effort,
            recommended_mode=mode,
            matched_skills=matched_skills_ids,
            subtasks=subtasks,
            metadata={"matched_keywords": matched_keywords, "prompt_length": len(prompt_clean)}
        )

    def evaluate_intent(self, user_prompt: str) -> IntentEvaluationResult:
        """Alias for evaluate method."""
        return self.evaluate(user_prompt)


class InteractiveConfirmationGate:
    """
    Handles confirmation gate logic prior to invoking heavy background subagents.
    Provides TTY non-interactive bypass and interactive CLI ANSI HUD rendering.
    """

    def __init__(
        self,
        auto_approve: bool = False,
        interactive_fn: Callable[[str], bool] | None = None,
        input_func: Callable[[str], bool] | None = None,
        **kwargs
    ):
        self.auto_approve = auto_approve
        self.interactive_fn = interactive_fn or input_func or kwargs.get("input_fn")

    @staticmethod
    def is_interactive() -> bool:
        """Determines whether current execution environment is interactive."""
        if os.environ.get("AUTO_CONFIRM", "").strip().lower() in ("1", "true", "yes"):
            return False
        if os.environ.get("NON_INTERACTIVE", "").strip().lower() in ("1", "true", "yes"):
            return False
        if os.environ.get("CI", "").strip().lower() in ("1", "true", "yes"):
            return False
        if "PYTEST_CURRENT_TEST" in os.environ:
            return False
        return sys.stdin.isatty()

    def _handle_custom_interactive(self, prompt_msg: str) -> bool:
        try:
            res = self.interactive_fn(prompt_msg)
            if hasattr(res, "__await__") or hasattr(res, "send"):
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import nest_asyncio
                        nest_asyncio.apply()
                        res = loop.run_until_complete(res)
                    else:
                        res = loop.run_until_complete(res)
                except Exception as exc:
                    logger.debug("Async loop runner note: %s", exc)
                    res = asyncio.run(res)
            if isinstance(res, bool):
                return res
            if isinstance(res, str):
                return res.strip().lower() in ("y", "yes", "true", "1", "")
            if isinstance(res, (int, float)):
                return res != 0
            return bool(res)
        except Exception as e:
            logger.error(f"[ConfirmationGate] Custom interactive_fn callback error: {e}")
            return not self.is_interactive()

    def _render_hud_and_prompt(self, evaluation: IntentEvaluationResult, prompt_msg: str) -> bool:
        prompt_preview = evaluation.user_prompt[:60] + ("..." if len(evaluation.user_prompt) > 60 else "")
        subagent_str = ", ".join(evaluation.recommended_subagents) or "rlm_code_engineer"

        safe_print("\n" + "=" * 72)
        safe_print("         HERMES MULTI-AGENT SUBAGENT AUTO-TRIGGER CONFIRMATION GATE")
        safe_print("=" * 72)
        safe_print(f" Prompt Preview   : \"{prompt_preview}\"")
        safe_print(f" Complexity Score : {evaluation.complexity_score:.2f} / 1.00  [{evaluation.estimated_effort.upper()}]")
        safe_print(" Requires Subagents: YES")
        safe_print(f" Target Subagents : {subagent_str}")
        safe_print(f" Rationale        : {evaluation.reasoning_summary}")
        safe_print("-" * 72)
        try:
            safe_print(prompt_msg, end="")
            choice = input("").strip().lower()
            if choice in ("", "y", "yes"):
                return True
            safe_print("[ConfirmationGate] Execution cancelled by user.")
            return False
        except (KeyboardInterrupt, EOFError) as exc:
            logger.debug("Interactive prompt cancelled: %s", exc)
            safe_print("\n[ConfirmationGate] Execution cancelled.")
            return False

    def request_confirmation(self, evaluation: IntentEvaluationResult) -> bool:
        """Requests user confirmation for executing subagent tasks."""
        if not evaluation.requires_subagents:
            return True

        if self.auto_approve:
            logger.info("[ConfirmationGate] Auto-approving multi-agent execution.")
            return True

        prompt_msg = (
            f"[CONFIRMATION GATE] Deep analysis required (Score: {evaluation.intent_score:.2f}).\n"
            f"Reason: {evaluation.reasoning}\n"
            f"Suggested Subagents: {', '.join(evaluation.suggested_subagents)}\n"
            f"Proceed with multi-agent background breakdown? [Y/n]: "
        )

        if self.interactive_fn is not None:
            return self._handle_custom_interactive(prompt_msg)

        if not self.is_interactive():
            logger.info("[ConfirmationGate] Non-interactive environment detected. Auto-approving task.")
            return True

        return self._render_hud_and_prompt(evaluation, prompt_msg)


class SubagentBackgroundDispatcher:
    """
    Dispatches non-blocking background subagents via process isolation (subprocess.Popen)
    or internal DeclarativeSubagentEngine threads.
    """

    def __init__(self, log_dir: str | None = None):
        self.log_dir = Path(log_dir or os.path.join(WORKSPACE_ROOT, "data", "logs", "subagents"))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.engine = DeclarativeSubagentEngine()
        self.go_client = GoSubagentBusClient()
        self._active_handles: dict[str, SubagentDispatchHandle] = {}

    def _normalize_task_spec(self, task_spec: dict[str, Any] | TaskSpec) -> TaskSpec:
        """Normalizes dict or TaskSpec object into standardized TaskSpec."""
        if isinstance(task_spec, dict):
            spec = TaskSpec(
                subagent_name=task_spec.get("subagent_name", task_spec.get("subagent", "code_engineer")),
                prompt=task_spec.get("prompt", ""),
                task_id=task_spec.get("task_id", ""),
                params=task_spec.get("params", {}),
                background=task_spec.get("background", True),
                effort=task_spec.get("effort", "high"),
                timeout=task_spec.get("timeout", 300),
                log_file=task_spec.get("log_file", None),
                auto_confirm=task_spec.get("auto_confirm", False),
                dry_run=task_spec.get("dry_run", False),
                backend=task_spec.get("backend", "auto")
            )
        else:
            spec = task_spec
        if not spec.task_id:
            spec.task_id = f"task_{int(time.time()*1000)}_{uuid.uuid4().hex[:4]}"
        return spec

    def _spawn_bridge_process(
        self, spec: TaskSpec, log_file_path: Path, bridge_path: str
    ) -> tuple[Optional[subprocess.Popen], int, str]:
        """Spawns dedicated bridge process for the target subagent."""
        cmd = [sys.executable, bridge_path]
        if spec.subagent_name == "open_deep_researcher":
            cmd.extend(["--query", spec.prompt])
        elif spec.subagent_name in ("rlm_code_engineer", "code_engineer"):
            cmd.extend(["--prompt", spec.prompt])
        elif spec.subagent_name == "verifier_worker":
            cmd.extend(["--verify-smt"])

        if spec.dry_run or spec.params.get("dry_run", False):
            cmd.append("--dry-run")

        try:
            with open(log_file_path, "a", encoding="utf-8") as log_fp:
                proc = subprocess.Popen(
                    cmd,
                    stdout=log_fp,
                    stderr=subprocess.STDOUT,
                    cwd=WORKSPACE_ROOT,
                    env=os.environ.copy(),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                )
            return proc, proc.pid, "RUNNING"
        except Exception as e:
            logger.error("[Dispatcher] Subprocess Popen failed: %s", e)
            return None, os.getpid(), "FAILED"

    def _spawn_generic_process(
        self, spec: TaskSpec, log_file_path: Path
    ) -> tuple[Optional[subprocess.Popen], int, str]:
        """Spawns generic python subagent worker process."""
        payload_json = fast_json_dumps({
            "subagent_name": spec.subagent_name,
            "prompt": spec.prompt,
            "task_id": spec.task_id,
            "params": spec.params
        })
        cmd = [
            sys.executable, "-c",
            "import sys, json; "
            "from vazus_core.engine.subagent_framework import DeclarativeSubagentEngine; "
            "data = json.loads(sys.argv[1]); "
            "DeclarativeSubagentEngine().run_subagent_sync(data['subagent_name'], data['prompt'], task_id=data['task_id'], params=data.get('params', {}))",
            payload_json
        ]
        try:
            with open(log_file_path, "a", encoding="utf-8") as log_fp:
                proc = subprocess.Popen(
                    cmd,
                    stdout=log_fp,
                    stderr=subprocess.STDOUT,
                    cwd=WORKSPACE_ROOT,
                    env=os.environ.copy(),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                )
            return proc, proc.pid, "RUNNING"
        except Exception as e:
            logger.error("[Dispatcher] Generic subprocess Popen failed: %s", e)
            return None, os.getpid(), "FAILED"

    def _create_and_register_handle(
        self,
        spec: TaskSpec,
        status: str,
        pid: int,
        log_file_path: Path,
        *,
        proc: Optional[subprocess.Popen] = None,
        result: Optional[dict] = None,
        backend: str = "subprocess",
        go_client: Optional[Any] = None
    ) -> SubagentDispatchHandle:
        """Constructs and registers dispatch handle in active handle registry and DB."""
        handle = SubagentDispatchHandle(
            task_id=spec.task_id,
            subagent_name=spec.subagent_name,
            status=status,
            pid=pid,
            log_path=str(log_file_path),
            created_at=time.time(),
            process=proc,
            result=result,
            backend=backend,
            go_client=go_client
        )
        self._active_handles[spec.task_id] = handle
        try:
            self._log_dispatch_to_db(handle, spec.prompt)
        except Exception as e:
            logger.error("[Dispatcher] DB trace logging failed for task %s, terminating PID %d: %s", spec.task_id, pid, e)
            handle.kill()
            self._active_handles.pop(spec.task_id, None)
            raise
        return handle

    def dispatch(self, task_spec: dict[str, Any] | TaskSpec) -> SubagentDispatchHandle:
        """Dispatches a subagent task in the background or in-process."""
        spec = self._normalize_task_spec(task_spec)
        log_file_path = Path(spec.log_file) if spec.log_file else self.log_dir / f"{spec.task_id}.log"
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        use_go = (
            getattr(spec, "backend", "auto") == "go_bus"
            or (os.environ.get("USE_GO_SUBAGENT_BUS", "0") == "1" and getattr(spec, "backend", "auto") != "subprocess")
        )
        if use_go and self.go_client.is_available() and spec.background and not spec.dry_run:
            try:
                res = self.go_client.spawn_actor(
                    task_id=spec.task_id,
                    subagent_name=spec.subagent_name,
                    prompt=spec.prompt,
                    role=spec.subagent_name,
                    params=spec.params,
                    timeout_sec=spec.timeout,
                )
                logger.info("[Dispatcher] Spawned actor in Go Subagent Bus: %s", res)
                return self._create_and_register_handle(
                    spec,
                    "RUNNING",
                    os.getpid(),
                    log_file_path,
                    backend="go_bus",
                    go_client=self.go_client
                )
            except Exception as e:
                logger.warning("[Dispatcher] Go Bus spawn failed, falling back to subprocess: %s", e)

        bridge_map = {
            "open_deep_researcher": "scripts/subagent_research_bridge.py",
            "rlm_code_engineer": "scripts/subagent_rlm_bridge.py",
            "code_engineer": "scripts/subagent_rlm_bridge.py",
            "verifier_worker": "scripts/subagent_verifier_bridge.py"
        }
        rel_bridge = bridge_map.get(spec.subagent_name)
        bridge_path = os.path.join(WORKSPACE_ROOT, rel_bridge) if rel_bridge else None

        if bridge_path and os.path.exists(bridge_path) and spec.background:
            proc, pid, status = self._spawn_bridge_process(spec, log_file_path, bridge_path)
            logger.info("[Dispatcher] Spawned background process PID=%d for task %s", pid, spec.task_id)
            return self._create_and_register_handle(spec, status, pid, log_file_path, proc=proc)

        if spec.background:
            proc, pid, status = self._spawn_generic_process(spec, log_file_path)
            return self._create_and_register_handle(spec, status, pid, log_file_path, proc=proc)

        ctx = self.engine.run_subagent_sync(
            subagent_name=spec.subagent_name,
            prompt=spec.prompt,
            task_id=spec.task_id,
            params=spec.params
        )
        status = "COMPLETED" if ctx.success else "FAILED"
        return self._create_and_register_handle(spec, status, os.getpid(), log_file_path, result=ctx.results)

    def dispatch_background_subagent(self, task_spec: dict[str, Any] | TaskSpec) -> SubagentDispatchHandle:
        """Alias method for dispatch."""
        return self.dispatch(task_spec)

    def generate_antigravity_invoke_manifest(self, task_spec: dict[str, Any] | TaskSpec) -> dict[str, Any]:
        """
        Generates canonical payload for Antigravity native `invoke_subagent` tool.
        Enforces execution inside active Antigravity session using internal model quota.
        """
        spec = self._normalize_task_spec(task_spec)
        try:
            from vazus_core.roles.system_personas import get_native_invoke_spec
            subagent_entry = get_native_invoke_spec(
                role_name=spec.subagent_name,
                task_prompt=spec.prompt,
                model="inherit",
                workspace="inherit",
            )
        except Exception:
            subagent_entry = {
                "TypeName": f"vazus-{spec.subagent_name}",
                "Role": spec.subagent_name,
                "Prompt": spec.prompt,
                "Model": "inherit",
                "Workspace": "inherit",
            }
        return {
            "tool": "invoke_subagent",
            "args": {
                "Subagents": [subagent_entry]
            }
        }

    def get_handle(self, task_id: str) -> SubagentDispatchHandle | None:
        """Retrieves active handle by task ID."""
        return self._active_handles.get(task_id)

    def list_active(self) -> list[SubagentDispatchHandle]:
        """Lists all active or tracked subagent handles."""
        return list(self._active_handles.values())

    def reap_completed(self) -> list[SubagentDispatchHandle]:
        """Checks status of all active handles and returns completed ones."""
        completed = []
        for task_id, handle in list(self._active_handles.items()):
            if not handle.is_alive():
                handle.close()
                completed.append(handle)
        return completed

    def _log_dispatch_to_db(self, handle: SubagentDispatchHandle, prompt: str):
        """Logs task dispatch event into vazus.db subagent_memory_traces table using canonical schema."""
        try:
            target_db = os.getenv("VAZUS_DB_PATH", "C:/vazus/services/memory/vazus.db")
            persister = SubagentDialoguePersister(db_path=target_db)
            content_json = fast_json_dumps({
                "task_id": handle.task_id,
                "prompt": prompt,
                "status": handle.status,
                "pid": handle.pid,
                "log_path": handle.log_path,
                "result": handle.result
            })
            persister.record_memory_trace(
                agent_name=handle.subagent_name,
                trace_kind="SUBAGENT_DISPATCH",
                summary=f"Dispatched task {handle.task_id} with status {handle.status}",
                content=content_json,
                dialogue_id=handle.task_id,
                export_obsidian=False
            )
        except Exception as e:
            logger.error(f"[Dispatcher DB Error] Critical failure writing trace: {e}")
            raise


# Default global instances for top-level helper APIs
_default_evaluator = HermesTaskIntentEvaluator()
_default_gate = InteractiveConfirmationGate()
_default_dispatcher = SubagentBackgroundDispatcher()


def evaluate_task_intent(user_prompt: str, threshold: float = 0.6) -> IntentEvaluationResult:
    """Top-level helper function to evaluate task intent and complexity."""
    evaluator = HermesTaskIntentEvaluator(threshold=threshold) if threshold != 0.6 else _default_evaluator
    return evaluator.evaluate(user_prompt)


def request_user_confirmation(
    intent: IntentEvaluationResult,
    auto_approve: bool = False,
    interactive_fn: Callable[[str], bool] | None = None,
    input_func: Callable[[str], bool] | None = None,
    **kwargs
) -> bool:
    """Top-level helper function to request user confirmation."""
    fn = interactive_fn or input_func or kwargs.get("input_fn")
    gate = InteractiveConfirmationGate(auto_approve=auto_approve, interactive_fn=fn, **kwargs)
    return gate.request_confirmation(intent)


def dispatch_background_subagent(task_spec: dict[str, Any] | TaskSpec) -> SubagentDispatchHandle:
    """Top-level helper function to dispatch background subagent execution."""
    return _default_dispatcher.dispatch(task_spec)
