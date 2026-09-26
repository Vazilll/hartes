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
        return briefing

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
