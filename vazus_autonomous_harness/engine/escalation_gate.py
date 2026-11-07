"""
vazus_autonomous_harness.engine.escalation_gate — Human Escalation Diagnostic Briefing.

Generates executive markdown diagnostic briefings when the Anti-Thrashing Circuit Breaker trips.
Formats:
1. Incident metadata and severity header.
2. Executive summary of task failure and stall reason.
3. Chronology matrix of mutation cycles, AST hashes, scores, and failure reasons.
4. Minimal Unsatisfiable Core (MUC) and SMT counterexample evidence.
5. Push-button actionable human decision forks (Option A: Manual Patch, Option B: Relax Contract, Option C: Abort & Blacklist).
6. Multi-target publication to Google Drive 30TB Vault and local telemetry vaults.
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("vazus.engine.escalation_gate")

DEFAULT_PRIMARY_CLOUD_VAULT = Path(r"G:\My Drive\Tars_30TB_Vault\04_flywheel_runs\escalations")
DEFAULT_LOCAL_VAULT = Path("artifacts/vault/04_flywheel_runs/escalations")
DEFAULT_TELEMETRY_VAULT = Path("artifacts/telemetry/escalations")


@dataclass
class HumanDecisionFork:
    """Actionable human decision path presented in the diagnostic briefing."""
    option_key: str  # "[OPTION A]", "[OPTION B]", "[OPTION C]"
    title: str
    description: str
    action_command: str


@dataclass
class JulesRemediationPayload:
    """Structured machine-readable dispatch payload for Google Jules Cloud VM remediation."""
    task_id: str
    title: str
    target: str = "google_jules"
    url: str = "https://jules.googleapis.com/v1alpha/sessions"
    prompt: str = ""
    remediation_plan: Dict[str, Any] = None
    metadata: Dict[str, Any] = None
    timestamp: float = 0.0

    def __post_init__(self):
        if self.remediation_plan is None:
            self.remediation_plan = {}
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "target": self.target,
            "url": self.url,
            "prompt": self.prompt,
            "remediation_plan": self.remediation_plan,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


def build_jules_remediation_payload(
    task_id: str,
    reason: str,
    attempts: Optional[List[Any]] = None,
    smt_counterexample: Optional[Dict[str, Any]] = None,
    last_error: Optional[str] = None,
) -> JulesRemediationPayload:
    """
    Constructs an automated Google Jules Cloud VM remediation dispatch payload.
    Adheres to ORIGINAL_REQUEST.md § R4 and PROJECT.md § M3 / F21.
    """
    attempts_list = attempts or []
    consecutive_failed_count = sum(
        1 for a in reversed(attempts_list) if getattr(a, "score", 0.0) < 75.0
    )
    if consecutive_failed_count == 0 and attempts_list:
        consecutive_failed_count = len(attempts_list)

    if attempts_list:
        last_attempt = attempts_list[-1]
        last_score = getattr(last_attempt, "score", 0.0)
        last_hash = getattr(last_attempt, "code_hash", "None") or "None"
        err_msg = getattr(last_attempt, "error_message", None) or getattr(last_attempt, "missing_prerequisite", None)
        final_err = last_error or err_msg or "Unknown failure"
        cex = smt_counterexample or getattr(last_attempt, "smt_counterexample", None)
    else:
        last_score = 0.0
        last_hash = "None"
        final_err = last_error or "Unknown failure"
        cex = smt_counterexample

    cex_formatted = (
        json.dumps(cex, indent=2, ensure_ascii=False)
        if cex
        else "None recorded (No SMT SAT model)"
    )

    prompt = (
        f"[AUTONOMOUS REMEDIATION DIRECTIVE - GOOGLE JULES TIER 1]\n"
        f"Incident ID: ESC-{task_id}\n"
        f"Target Task: {task_id}\n"
        f"Anti-Thrashing Trip Reason: {reason}\n"
        f"Consecutive Failed Cycles: {consecutive_failed_count} (Admission score < 75.0)\n"
        f"Last Score: {last_score:.1f} / 100.0\n"
        f"Last Code AST Hash: {last_hash}\n"
        f"Failure Reason: {final_err}\n\n"
        f"Diagnostic Minimal Unsatisfiable Core (SMT Counterexample):\n"
        f"{cex_formatted}\n\n"
        f"Autonomous Remediation Tasks:\n"
        f"1. Analyze failing AST structure and SMT counterexample for task '{task_id}'.\n"
        f"2. Formulate bounded code mutations resolving contract violations while preserving invariants.\n"
        f"3. Run isolated test suite to verify 100% pass rate without mocks.\n"
        f"4. Verify SMT Z3 formal proof satisfiability (UNSAT) before proposing commit.\n"
    )

    title = f"Autonomous Remediation Sprint: {task_id}"
    remediation_plan = {
        "task_id": task_id,
        "objective": f"Remediate stalled task {task_id} following {consecutive_failed_count} failed cycles",
        "consecutive_failures": consecutive_failed_count,
        "admission_threshold": 75.0,
        "last_score": last_score,
        "last_ast_hash": last_hash,
        "required_verifications": [
            "SMT_Z3_FORMAL_PROOF",
            "EMPIRICAL_TEST_PASS_100_PERCENT",
            "PARSIMONY_AST_BLOAT_GATE",
            "SOCRATIC_ACADEMIC_SOVEREIGNTY",
        ],
    }

    metadata = {
        "task_id": task_id,
        "incident_id": f"ESC-{task_id}",
        "subsystem": "AntiThrashingCircuitBreaker",
        "tier": "Tier 1 (Headless Cloud Compute)",
        "endpoint": "https://jules.googleapis.com/v1alpha/sessions",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    return JulesRemediationPayload(
        task_id=task_id,
        title=title,
        target="google_jules",
        url="https://jules.googleapis.com/v1alpha/sessions",
        prompt=prompt,
        remediation_plan=remediation_plan,
        metadata=metadata,
    )


class EscalationBriefingGenerator:
    """
    Genuine Executive Diagnostic Briefing Generator adhering to PROJECT.md § M3 (F9)
    and ORIGINAL_REQUEST.md § R3.
    """

    def __init__(
        self,
        vault_path: Optional[Union[str, Path]] = None,
        local_path: Optional[Union[str, Path]] = None,
        telemetry_path: Optional[Union[str, Path]] = None,
    ):
        if vault_path is not None:
            self.vault_path = Path(vault_path)
        else:
            if DEFAULT_PRIMARY_CLOUD_VAULT.parent.exists():
                self.vault_path = DEFAULT_PRIMARY_CLOUD_VAULT
            else:
                self.vault_path = DEFAULT_LOCAL_VAULT

        self.local_path = Path(local_path) if local_path is not None else DEFAULT_LOCAL_VAULT
        self.telemetry_path = Path(telemetry_path) if telemetry_path is not None else DEFAULT_TELEMETRY_VAULT
        self.last_jules_payload: Optional[JulesRemediationPayload] = None

    def _sanitize_cell(self, text: Optional[str], max_len: int = 240) -> str:
        """Sanitizes text for safe rendering in Markdown tables, avoiding table syntax breakage."""
        if not text:
            return "None"
        # Escape markdown table delimiters with HTML entity and collapse linebreaks
        cleaned = str(text).replace("|", "&#124;").replace("\r", " ").replace("\n", " ").strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if len(cleaned) > max_len:
            return cleaned[:max_len] + "..."
        return cleaned

    def format_chronology_table(self, attempts: List[Any]) -> str:
        """Renders the Markdown churn chronology table from attempts history."""
        headers = [
            "| Cycle | Code Hash | Score | Failure Reason |",
            "|:---:|:---:|:---:|:---|",
        ]
        if not attempts:
            headers.append("| 0 | None | 0.0 | No attempts recorded before halt |")
            return "\n".join(headers)

        rows = []
        for a in attempts:
            cycle = getattr(a, "cycle_number", 0)
            code_hash = getattr(a, "code_hash", "None") or "None"
            score = getattr(a, "score", 0.0)
            err = getattr(a, "error_message", None) or getattr(a, "missing_prerequisite", None) or "None"
            sanitized_err = self._sanitize_cell(err)
            rows.append(f"| {cycle} | {code_hash} | {score:.1f} | {sanitized_err} |")

        return "\n".join(headers + rows)

    def render_briefing(
        self,
        task_id: str,
        reason: str,
        attempts: Optional[List[Any]] = None,
        smt_counterexample: Optional[Dict[str, Any]] = None,
        last_error: Optional[str] = None,
    ) -> str:
        """
        Renders the full executive diagnostic Markdown briefing document.
        """
        attempts_list = attempts or []
        timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Determine last attempt data
        if attempts_list:
            last_attempt = attempts_list[-1]
            last_score = getattr(last_attempt, "score", 0.0)
            last_hash = getattr(last_attempt, "code_hash", "None") or "None"
            err_from_attempt = getattr(last_attempt, "error_message", None) or getattr(last_attempt, "missing_prerequisite", None)
            final_err = last_error or err_from_attempt or "None"
            cex = smt_counterexample or getattr(last_attempt, "smt_counterexample", None)
        else:
            last_score = 0.0
            last_hash = "None"
            final_err = last_error or "None"
            cex = smt_counterexample

        chronology_table = self.format_chronology_table(attempts_list)

        # Counterexample formatting
        if cex:
            try:
                cex_str = json.dumps(cex, indent=2, ensure_ascii=False)
            except Exception:
                cex_str = str(cex)
            counterexample_section = f"```json\n{cex_str}\n```"
        else:
            counterexample_section = "None recorded (Non-SMT failure, prerequisite block, or timeout)"

        # Full rendered briefing
        briefing = f"""# 🚨 EXECUTIVE ESCALATION BRIEFING: AUTONOMOUS FLYWHEEL HALTED
**Incident ID**: ESC-{task_id}
**Timestamp**: {timestamp_iso}
**Subsystem**: Anti-Thrashing Circuit Breaker (R3)
**Severity**: CRITICAL -- AUTONOMOUS EXECUTION FROZEN
**Trip Reason**: {reason}

---

## 1. Executive Summary
The autonomous flywheel execution for task `{task_id}` has been halted to prevent runaway token expenditure, compute depletion, and infinite retry churn.
The anti-thrashing circuit breaker tripped due to: {reason}.

---

## 2. Metric Progression & Churn Chronology
{chronology_table}

---

## 3. Minimal Unsatisfiable Core & Counterexample Evidence
- Task Target: `{task_id}`
- Last Score: {last_score:.1f}
- Last Code Hash: `{last_hash}`
- Last Error: {final_err}
- Counterexample / SMT SAT witness:
{counterexample_section}

---

## 4. Human Decision Gate (Push-Button Actionable Forks)
The human supervisor must choose one of the following resolution pathways:

- **[OPTION A] Manual Patch & Resume**:
  Apply the corrected implementation manually in code and execute unfreeze:
  `python -m vazus_autonomous_harness.engine.anti_thrashing --unfreeze --task-id {task_id}`

- **[OPTION B] Relax Contract Invariant**:
  Permit relaxed postcondition threshold or contract bounds:
  `python -m vazus_autonomous_harness.engine.anti_thrashing --relax-contract --task-id {task_id}`

- **[OPTION C] Abort & Blacklist Mutation Path**:
  Add mutation fingerprint `{last_hash}` to R2 Reflexion Memory negative constraints and abort task:
  `python -m vazus_autonomous_harness.engine.anti_thrashing --abort --task-id {task_id} --record-reflexion`
"""
        # Section 5: Automated Cloud Remediation Dispatch (Google Jules Tier 1)
        # Triggered upon anti-thrashing circuit breaker trip (3 consecutive cycles)
        is_three_cycles = (
            (attempts_list and len(attempts_list) >= 3 and all(getattr(a, "score", 0.0) < 75.0 for a in attempts_list[-3:]))
            or "consecutive" in reason.lower()
            or "thrashing" in reason.lower()
        )
        if is_three_cycles:
            self.last_jules_payload = self.build_jules_payload(
                task_id=task_id,
                reason=reason,
                attempts=attempts_list,
                smt_counterexample=cex,
                last_error=final_err,
            )
            jules_json = json.dumps(self.last_jules_payload.to_dict(), indent=2, ensure_ascii=False)
            briefing += f"""
---

## 5. Automated Cloud Remediation Dispatch (Google Jules Tier 1)
- **Remediation Target**: Google Jules Cloud VM (`https://jules.googleapis.com/v1alpha/sessions`)
- **Remediation Status**: AUTOMATED REMEDIATION PAYLOAD STAGED (3 consecutive failed cycles detected)
- **Session Title**: `{self.last_jules_payload.title}`
- **Remediation Directives**:
```json
{jules_json}
```
"""
        else:
            self.last_jules_payload = None

        return briefing

    def build_jules_payload(
        self,
        task_id: str,
        reason: str,
        attempts: Optional[List[Any]] = None,
        smt_counterexample: Optional[Dict[str, Any]] = None,
        last_error: Optional[str] = None,
    ) -> JulesRemediationPayload:
        """Constructs an automated Google Jules Cloud VM remediation dispatch payload."""
        return build_jules_remediation_payload(
            task_id=task_id,
            reason=reason,
            attempts=attempts,
            smt_counterexample=smt_counterexample,
            last_error=last_error,
        )

    def dispatch_jules_remediation(
        self,
        payload: Union[JulesRemediationPayload, Dict[str, Any]],
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Dispatches or stages automated remediation session to Google Jules Cloud VM.
        """
        import os
        p_dict = payload.to_dict() if isinstance(payload, JulesRemediationPayload) else payload
        task_id = p_dict.get("task_id", "unknown")
        jules_key = api_key or os.getenv("JULES_API_KEY", "")

        if jules_key:
            import urllib.request
            url = p_dict.get("url", "https://jules.googleapis.com/v1alpha/sessions")
            req_data = json.dumps({
                "prompt": p_dict.get("prompt", ""),
                "title": p_dict.get("title", f"Remediation: {task_id}"),
            }).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={
                    "Authorization": f"Bearer {jules_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    sess_id = resp_data.get("name") or resp_data.get("id") or f"sess_{task_id}"
                    logger.info(f"[JulesDispatch] Successfully dispatched session {sess_id}")
                    return {
                        "status": "DISPATCHED",
                        "session_id": sess_id,
                        "task_id": task_id,
                        "dispatched": True,
                        "response": resp_data,
                    }
            except Exception as e:
                logger.warning(f"[JulesDispatch] Live HTTP dispatch failed ({e}), staging payload.")

        # Staging fallback queue
        stage_dir = self.local_path / "jules_dispatch"
        stage_dir.mkdir(parents=True, exist_ok=True)
        staged_file = stage_dir / f"JULES_PAYLOAD_{task_id}.json"
        staged_file.write_text(json.dumps(p_dict, indent=2, ensure_ascii=False), encoding="utf-8")

        return {
            "status": "STAGED",
            "session_id": f"staged_jules_{task_id}",
            "task_id": task_id,
            "dispatched": False,
            "staged": True,
            "staged_path": str(staged_file),
            "payload": p_dict,
        }

    def publish_briefing(
        self,
        task_id: str,
        content: str,
        target_vault: Optional[Union[str, Path]] = None,
    ) -> List[Path]:
        """
        Publishes the rendered briefing to the specified vault path and local fallback mirrors.
        Returns the list of paths successfully written.
        """
        written_paths: List[Path] = []
        filename = f"ESCALATION_{task_id}.md"

        # 1. Target vault write (if explicitly requested or configured)
        primary_dir = Path(target_vault) if target_vault is not None else self.vault_path
        try:
            primary_dir.mkdir(parents=True, exist_ok=True)
            primary_file = primary_dir / filename
            primary_file.write_text(content, encoding="utf-8")
            written_paths.append(primary_file)
            logger.info(f"Published escalation briefing to primary target: {primary_file}")
        except Exception as e:
            logger.warning(f"Failed to write escalation briefing to primary vault {primary_dir}: {e}")

        # 2. Local fallback sync if primary is a cloud vault or different from local path
        if target_vault is None or Path(target_vault) != self.local_path:
            try:
                self.local_path.mkdir(parents=True, exist_ok=True)
                local_file = self.local_path / filename
                local_file.write_text(content, encoding="utf-8")
                if local_file not in written_paths:
                    written_paths.append(local_file)
            except Exception as e:
                logger.warning(f"Failed to write escalation briefing to local fallback {self.local_path}: {e}")

        # 3. Telemetry vault mirror
        if target_vault is None or Path(target_vault) != self.telemetry_path:
            try:
                self.telemetry_path.mkdir(parents=True, exist_ok=True)
                telem_file = self.telemetry_path / filename
                telem_file.write_text(content, encoding="utf-8")
                if telem_file not in written_paths:
                    written_paths.append(telem_file)
            except Exception:
                pass

        # 4. Also persist Jules remediation payload if generated
        if self.last_jules_payload is not None:
            jules_filename = f"JULES_PAYLOAD_{task_id}.json"
            jules_str = json.dumps(self.last_jules_payload.to_dict(), indent=2, ensure_ascii=False)
            try:
                primary_jules = primary_dir / jules_filename
                primary_jules.write_text(jules_str, encoding="utf-8")
                if primary_jules not in written_paths:
                    written_paths.append(primary_jules)
            except Exception as e:
                logger.warning(f"Failed to write Jules payload to primary vault: {e}")

            try:
                local_jules = self.local_path / jules_filename
                local_jules.write_text(jules_str, encoding="utf-8")
                if local_jules not in written_paths:
                    written_paths.append(local_jules)
            except Exception as e:
                logger.warning(f"Failed to write Jules payload to local fallback: {e}")

        return written_paths

    def generate_and_publish(
        self,
        task_id: str,
        reason: str,
        attempts: Optional[List[Any]] = None,
        target_vault: Optional[Union[str, Path]] = None,
        smt_counterexample: Optional[Dict[str, Any]] = None,
        last_error: Optional[str] = None,
    ) -> Tuple[str, List[Path]]:
        """Generates briefing content and publishes to target vault and local mirrors."""
        content = self.render_briefing(
            task_id=task_id,
            reason=reason,
            attempts=attempts,
            smt_counterexample=smt_counterexample,
            last_error=last_error,
        )
        written = self.publish_briefing(task_id=task_id, content=content, target_vault=target_vault)
        return content, written


# Backward compatibility alias
HumanEscalationGate = EscalationBriefingGenerator
