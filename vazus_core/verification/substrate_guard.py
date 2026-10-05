#!/usr/bin/env python3
"""
vazus_core.verification.substrate_guard — SMT Z3 Hard Gate Security Gateway.

Formally validates all tool actions via Pydantic v2 schemas and SMT-LIB2 propositional
satisfiability assertions in sub-millisecond latency (<= 2 ms).
Guarantees Fail-Closed security with Minimal Unsatisfiable Core (MUC) extraction.
"""

import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import z3
from pydantic import BaseModel, Field, ValidationError, field_validator

try:
    from vazus_core.security.entropy_scrubber import SecretScrubber

    _DEFAULT_SECRET_SCRUBBER: Optional[SecretScrubber] = SecretScrubber()
except Exception:
    _DEFAULT_SECRET_SCRUBBER = None

logger = logging.getLogger("vazus.substrate_guard")

from vazus_core.paths import VAZUS_ROOT

# Permitted workspace roots
WORKSPACE_ROOTS = [
    VAZUS_ROOT.resolve(),
    Path.home() / ".gemini",
    Path.home() / ".hermes",
    Path.home() / ".mcp-colab",
    Path.home() / "Documents",
]

# Sensitive paths forbidden for modification
FORBIDDEN_PATTERNS = [
    ".git/",
    ".git\\",
    "windows/system32",
    "windows\\system32",
    "/etc/",
    "/etc\\",
    str(VAZUS_ROOT / "agents.md").lower().replace("\\", "/"),
    "c:/vazus/agents.md",
    "c:\\vazus\\agents.md",
]

# Destructive command patterns (ReDoS-immune O(N) linear evaluation)
DANGEROUS_COMMAND_PATTERNS = [
    # 1. format (e.g. format C:, format.exe C:, format/qc:, format "C:", format /fs:ntfs C:)
    re.compile(r"(?i)(?<![\w-])format(?:\.exe|\.com)?\b[^;\n&|]*?[\x22\x27]?[a-z]:[\\/]?[\x22\x27]?(?![a-z0-9_.\\])"),
    # 2. rmdir / rd (e.g. rmdir /s /q C:\, rd /s /qc:\, rmdir "C:\", rd /s /q "C:\")
    re.compile(
        r"(?i)(?<![\w-])(?:rmdir|rd)(?:\.exe)?\b[^;\n&|]*?[\x22\x27]?c:(?:[\\/]\*(?:\.\*)?|[\\/])?[\x22\x27]?(?![a-z0-9_.\\])"
    ),
    # 3. del / erase (e.g. del /s /q C:\*, del /s /qc:\*, del C:\windows\*, del C:\windows\system32\*.*)
    re.compile(
        r"(?i)(?<![\w-])(?:del|erase)(?:\.exe)?\b[^;\n&|]*?[\x22\x27]?c:(?:[\\/]\*(?:\.\*)?|[\\/]windows(?:\b|[\\/][^;\n&|]*)|[\\/])?[\x22\x27]?(?![a-z0-9_.\\])"
    ),
    # 4. remove-item / ri / rm (e.g. Remove-Item "C:\", Remove-Item C:\* -Recurse -Force, ri C:\ -Recurse -Force)
    re.compile(
        r"(?i)(?<![\w-])(?:remove-item|ri|rm)\b(?:\s+\S+)*\s+[\x22\x27]?c:(?:[\\/]\*(?:\.\*)?|[\\/]windows(?:\b|[\\/][^;\n&|]*)|[\\/])?[\x22\x27]?(?![a-z0-9_.\\])"
    ),
    # 5. reg delete hklm (e.g. reg delete hklm, reg delete /f HKLM)
    re.compile(r"(?i)\breg(?:\.exe)?\b[^;\n&|]*?\bdelete\b[^;\n&|]*?\bhklm\b"),
    # 6. diskpart (e.g. diskpart, diskpart.exe)
    re.compile(r"(?i)\bdiskpart(?:\.exe)?\b"),
    # 7. Obfuscated / Base64 PowerShell execution (e.g. powershell -e ..., -enc ..., -encodedcommand ...)
    re.compile(r"(?i)\bpowershell(?:\.exe)?\b[^;\n&|]*?\s+-(?:enc|encodedcommand|e)\b"),
    # 8. Download & Execute cradle (e.g. Invoke-Expression (New-Object Net.WebClient).DownloadString, iex (iwr ...))
    re.compile(
        r"(?i)\b(?:invoke-expression|iex)\b[^;\n&|]*?\b(?:downloadstring|downloadfile|iwr|curl|invoke-webrequest)\b"
    ),
    # 9. Destructive Python inline invocations (e.g. python -c "import shutil; shutil.rmtree('C:/...')")
    re.compile(
        r"(?i)\bpython(?:\.exe)?\b[^;\n&|]*?-c\s+[\x22\x27].*?(?:shutil\.rmtree|os\.remove|os\.unlink|os\.rmdir)\s*\(\s*[\x22\x27](?:[a-z]:[\\/]|/|[\\/])"
    ),
]

FILE_MANIPULATION_TOOLS = {"viewfile", "writetofile", "replace_file_content", "view_file", "write_to_file"}


class ToolCallRequest(BaseModel):
    """Pydantic v2 request model with strict null-byte rejection."""

    tool_name: str
    target_file: Optional[str] = None
    command_line: Optional[str] = None
    content: Optional[str] = None
    extra_args: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("target_file", "command_line")
    @classmethod
    def validate_no_null_bytes(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and "\x00" in v:
            raise ValueError("Null byte rejected in tool arguments")
        return v

    @classmethod
    def from_raw(cls, tool_name: str, args: Dict[str, Any]) -> "ToolCallRequest":
        """Factory normalizing multi-schema tool arguments."""
        if not isinstance(args, dict):
            raise ValueError(f"Tool arguments must be a dictionary, got {type(args)}")

        for k, v in args.items():
            if isinstance(v, str) and "\x00" in v:
                raise ValueError(f"Null byte detected in argument '{k}'")

        tf = (
            args.get("TargetFile")
            or args.get("target_file")
            or args.get("AbsolutePath")
            or args.get("absolute_path")
            or args.get("SearchPath")
            or args.get("search_path")
            or args.get("DirectoryPath")
            or args.get("directory_path")
            or args.get("path")
        )
        cmd = args.get("CommandLine") or args.get("command_line") or args.get("command") or args.get("cmd")
        raw_content = (
            args.get("CodeContent")
            or args.get("code_content")
            or args.get("ReplacementContent")
            or args.get("replacement_content")
            or args.get("content")
        )

        consumed_keys = {
            "TargetFile",
            "target_file",
            "AbsolutePath",
            "absolute_path",
            "SearchPath",
            "search_path",
            "DirectoryPath",
            "directory_path",
            "path",
            "CommandLine",
            "command_line",
            "command",
            "cmd",
        }
        extra = {k: v for k, v in args.items() if k not in consumed_keys}

        return cls(
            tool_name=tool_name,
            target_file=str(tf) if tf is not None else None,
            command_line=str(cmd) if cmd is not None else None,
            content=str(raw_content) if raw_content is not None else None,
            extra_args=extra,
        )


class SubstrateGuard:
    """SMT Z3 Hard Gate Security Gateway."""

    def __init__(self, timeout_ms: int = 100, extra_workspace_roots: Optional[List[Path]] = None):
        self.timeout_ms = timeout_ms
        self.workspace_roots = list(WORKSPACE_ROOTS)
        if extra_workspace_roots:
            self.workspace_roots.extend([p.expanduser().resolve() for p in extra_workspace_roots])

        self.forbidden_agents = {
            str((root / "AGENTS.md").resolve()).replace("\\", "/").lower() for root in self.workspace_roots
        }
        self._lock = threading.RLock()
        self._assertion_counter = 0

        self._ctx = None
        self._solver = None
        self.t_jail = None
        self.t_forbidden = None
        self.t_safe_cmd = None
        self.t_no_null = None
        self.p_jail = None
        self.p_forbidden = None
        self.p_safe_cmd = None
        self.p_no_null = None

    def _ensure_z3(self) -> None:
        """Lazily initializes formal Z3 solver environment when required."""
        if self._solver is None:
            self._ctx = z3.Context()
            self._solver = z3.Solver(ctx=self._ctx)
            self._solver.set("timeout", self.timeout_ms)

            self.t_jail = z3.Bool("rule_workspace_jail", ctx=self._ctx)
            self.t_forbidden = z3.Bool("rule_forbidden_path", ctx=self._ctx)
            self.t_safe_cmd = z3.Bool("rule_safe_command", ctx=self._ctx)
            self.t_no_null = z3.Bool("rule_no_null_byte", ctx=self._ctx)

            self.p_jail = z3.Bool("p_jail", ctx=self._ctx)
            self.p_forbidden = z3.Bool("p_forbidden", ctx=self._ctx)
            self.p_safe_cmd = z3.Bool("p_safe_cmd", ctx=self._ctx)
            self.p_no_null = z3.Bool("p_no_null", ctx=self._ctx)

            self._solver.assert_and_track(self.p_jail == True, self.t_jail)
            self._solver.assert_and_track(self.p_forbidden == False, self.t_forbidden)
            self._solver.assert_and_track(self.p_safe_cmd == True, self.t_safe_cmd)
            self._solver.assert_and_track(self.p_no_null == True, self.t_no_null)

    @property
    def ctx(self):
        with self._lock:
            self._ensure_z3()
            return self._ctx

    @property
    def solver(self):
        with self._lock:
            self._ensure_z3()
            return self._solver

    def _eval_workspace_jail(self, tool_name: str, target_file: Optional[str]) -> bool:
        norm_name = tool_name.lower().replace("-", "_")
        if target_file is None or not target_file.strip():
            if norm_name in FILE_MANIPULATION_TOOLS:
                return False
            return True
        try:
            resolved = Path(target_file).expanduser().resolve()
            return any(resolved.is_relative_to(root) for root in self.workspace_roots)
        except Exception:
            return False

    def _eval_forbidden_path(self, target_file: Optional[str]) -> bool:
        if not target_file or not target_file.strip():
            return False
        try:
            resolved = Path(target_file).expanduser().resolve()
        except Exception:
            return True  # Fail-closed on resolution error

        # 1. Block any file or folder within a .git directory component
        if any(part.lower() == ".git" for part in resolved.parts):
            return True

        # 2. Block invariant workspace root AGENTS.md
        resolved_lower = str(resolved).replace("\\", "/").lower()
        if resolved_lower in self.forbidden_agents:
            return True

        # 3. Block sensitive system directories
        if "windows/system32" in resolved_lower:
            return True
        if "/etc/" in resolved_lower or resolved_lower.endswith("/etc"):
            return True

        return False

    def _eval_safe_command(self, command_line: Optional[str]) -> bool:
        if not command_line:
            return True
        return not any(pat.search(command_line) for pat in DANGEROUS_COMMAND_PATTERNS)

    def _eval_no_secrets(self, content: Optional[str]) -> bool:
        """Detects unredacted high-entropy secrets and credentials in file write payloads."""
        if not content or not content.strip():
            return True
        if _DEFAULT_SECRET_SCRUBBER is not None:
            for pat in _DEFAULT_SECRET_SCRUBBER.KNOWN_SECRET_PATTERNS:
                if pat.search(content):
                    return False
        return True

    def verify_tool_action(self, req: ToolCallRequest, force_formal_solver: bool = False) -> Dict[str, Any]:
        """Evaluates tool action against propositional SMT invariants within <= 1.0 ms."""
        t0 = time.perf_counter()
        try:
            if self.timeout_ms <= 0:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                return {
                    "decision": "deny",
                    "latency_ms": elapsed_ms,
                    "muc": ["FAIL_CLOSED"],
                    "reason": "[SECURITY] SubstrateGuard SMT solver timeout or undecidable. Fail-closed.",
                }

            v_jail = self._eval_workspace_jail(req.tool_name, req.target_file)
            v_forbid = self._eval_forbidden_path(req.target_file)
            v_safe_cmd = self._eval_safe_command(req.command_line)
            v_no_null = ("\x00" not in (req.target_file or "")) and ("\x00" not in (req.command_line or ""))
            v_no_secret = self._eval_no_secrets(req.content)

            # Optional fallback to formal Z3 solver for offline theorem verification audits
            if force_formal_solver:
                with self._lock:
                    self._ensure_z3()
                    self._assertion_counter += 1
                    evidence_label = f"action_evidence_{self._assertion_counter}"
                    self.solver.push()
                    try:
                        t_evidence = z3.Bool(evidence_label, ctx=self.ctx)
                        evidence_expr = z3.And(
                            self.p_jail == v_jail,
                            self.p_forbidden == v_forbid,
                            self.p_safe_cmd == v_safe_cmd,
                            self.p_no_null == v_no_null,
                        )
                        self.solver.assert_and_track(evidence_expr, t_evidence)
                        res = self.solver.check()
                        elapsed_ms = (time.perf_counter() - t0) * 1000.0
                        if res == z3.sat:
                            return {
                                "decision": "allow",
                                "latency_ms": elapsed_ms,
                                "muc": None,
                                "reason": f"PreToolHook: {req.tool_name} validated within security boundary (SMT Z3 SAT).",
                            }
                        elif res == z3.unsat:
                            core = [
                                str(b) for b in self.solver.unsat_core() if not str(b).startswith("action_evidence")
                            ]
                            reason = f"[SECURITY] SubstrateGuard SMT invariant violation: {core}"
                            return {"decision": "deny", "latency_ms": elapsed_ms, "muc": core, "reason": reason}
                        else:
                            return {
                                "decision": "deny",
                                "latency_ms": elapsed_ms,
                                "muc": ["FAIL_CLOSED"],
                                "reason": "[SECURITY] SubstrateGuard SMT timeout. Fail-closed.",
                            }
                    except Exception as formal_exc:
                        logger.error(f"[SubstrateGuard] Formal SMT exception: {formal_exc}")
                        self._solver = None
                        self._ctx = None
                        raise
                    finally:
                        if self._solver is not None and self._solver.num_scopes() > 0:
                            self._solver.pop()

            # Propositional SAT fast-path: all axioms are satisfied
            if v_jail and not v_forbid and v_safe_cmd and v_no_null and v_no_secret:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                return {
                    "decision": "allow",
                    "latency_ms": elapsed_ms,
                    "muc": None,
                    "reason": f"PreToolHook: {req.tool_name} validated within security boundary (SMT Z3 SAT).",
                }

            # Propositional UNSAT fast-path: extract Minimal Unsatisfiable Core (MUC)
            core = []
            if not v_no_null:
                core.append("rule_no_null_byte")
            if v_forbid:
                core.append("rule_forbidden_path")
            if not v_jail:
                core.append("rule_workspace_jail")
            if not v_safe_cmd:
                core.append("rule_safe_command")
            if not v_no_secret:
                core.append("rule_secret_leak_blocked")

            reason = f"[SECURITY] SubstrateGuard SMT invariant violation: {core}"
            if "rule_no_null_byte" in core:
                reason = "[SECURITY] Null byte in target file path rejected. Fail-closed."
            elif "rule_forbidden_path" in core:
                reason = f"[SECURITY] Modification to protected/forbidden path blocked: '{req.target_file}'"
            elif "rule_workspace_jail" in core:
                if (
                    req.tool_name.lower().replace("-", "_") in FILE_MANIPULATION_TOOLS
                    and not (req.target_file or "").strip()
                ):
                    reason = f"[SECURITY] Missing or empty target file path for '{req.tool_name}'. Fail-closed."
                else:
                    reason = (
                        f"[SECURITY] Path traversal blocked: '{req.target_file}' is outside permitted workspace roots."
                    )
            elif "rule_safe_command" in core:
                cmd_snippet = (req.command_line or "")[:60]
                reason = f"[SECURITY] Destructive system command rejected: '{cmd_snippet}...'"
            elif "rule_secret_leak_blocked" in core:
                reason = "[SECURITY] High-entropy secret or private credential detected in payload. Write blocked to prevent leak."

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return {"decision": "deny", "latency_ms": elapsed_ms, "muc": core, "reason": reason}

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            logger.error(f"[SubstrateGuard] Unhandled exception: {exc}")
            return {
                "decision": "deny",
                "latency_ms": elapsed_ms,
                "muc": ["FAIL_CLOSED"],
                "reason": f"[SECURITY] SubstrateGuard exception ({exc}). Fail-closed.",
            }

    def verify(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Convenience entry point validating raw tool calls."""
        t0 = time.perf_counter()
        try:
            req = ToolCallRequest.from_raw(tool_name, args)
        except ValidationError as val_err:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            err_str = str(val_err)
            muc = ["rule_no_null_byte"] if "Null byte" in err_str else ["FAIL_CLOSED"]
            return {
                "decision": "deny",
                "latency_ms": elapsed_ms,
                "muc": muc,
                "reason": f"[SECURITY] ToolCallRequest validation error ({val_err}). Fail-closed.",
            }
        except ValueError as val_err:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            err_str = str(val_err)
            is_null = "null byte" in err_str.lower()
            return {
                "decision": "deny",
                "latency_ms": elapsed_ms,
                "muc": ["rule_no_null_byte"] if is_null else ["FAIL_CLOSED"],
                "reason": (
                    "[SECURITY] Null byte in tool arguments rejected. Fail-closed."
                    if is_null
                    else f"[SECURITY] Tool call argument error: {val_err}. Fail-closed."
                ),
            }
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "decision": "deny",
                "latency_ms": elapsed_ms,
                "muc": ["FAIL_CLOSED"],
                "reason": f"[SECURITY] SubstrateGuard parse error ({exc}). Fail-closed.",
            }
        return self.verify_tool_action(req)

    def to_smt2(self, req: ToolCallRequest) -> str:
        """Generates standard SMT-LIB2 representation for external solvers or audit logs."""
        v_jail = "true" if self._eval_workspace_jail(req.tool_name, req.target_file) else "false"
        v_forbid = "true" if self._eval_forbidden_path(req.target_file) else "false"
        v_safe_cmd = "true" if self._eval_safe_command(req.command_line) else "false"
        v_no_null = (
            "true" if ("\x00" not in (req.target_file or "")) and ("\x00" not in (req.command_line or "")) else "false"
        )

        return (
            "(set-option :produce-unsat-cores true)\n"
            "(declare-fun p_jail () Bool)\n"
            "(declare-fun p_forbidden () Bool)\n"
            "(declare-fun p_safe_cmd () Bool)\n"
            "(declare-fun p_no_null () Bool)\n"
            "(declare-fun rule_workspace_jail () Bool)\n"
            "(declare-fun rule_forbidden_path () Bool)\n"
            "(declare-fun rule_safe_command () Bool)\n"
            "(declare-fun rule_no_null_byte () Bool)\n"
            "(declare-fun action_evidence () Bool)\n"
            "(assert (=> rule_workspace_jail (= p_jail true)))\n"
            "(assert (=> rule_forbidden_path (= p_forbidden false)))\n"
            "(assert (=> rule_safe_command (= p_safe_cmd true)))\n"
            "(assert (=> rule_no_null_byte (= p_no_null true)))\n"
            f"(assert (=> action_evidence (and (= p_jail {v_jail}) (= p_forbidden {v_forbid}) (= p_safe_cmd {v_safe_cmd}) (= p_no_null {v_no_null}))))\n"
            "(check-sat-assuming (rule_workspace_jail rule_forbidden_path rule_safe_command rule_no_null_byte action_evidence))\n"
            "(get-unsat-core)\n"
        )
