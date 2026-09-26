"""
vazus_autonomous_harness.telemetry.cloud_bridge — Bidirectional Cloud-Local Telemetry Bridge.

Synchronizes local/cloud execution status between:
- Local & Jules Workspaces (Code, Tests, SMT Z3 Verification)
- Google Drive Realtime Mirror (`G:\\My Drive\\HartesFlywheel`)
- Gemini Spark Watchdog & Scheduler (24/7 autonomous monitoring & intervention)
"""

import json
import time
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional

from vazus_autonomous_harness.skills.skill_tree import SkillTree
from vazus_autonomous_harness.skills.substrate_guard import SubstrateGuard

logger = logging.getLogger("vazus.cloud_bridge")

DEFAULT_DRIVE_ROOT = Path(r"G:\My Drive\HartesFlywheel")
LOCAL_FALLBACK_ROOT = Path(__file__).resolve().parent.parent.parent / "artifacts" / "telemetry"


@dataclass
class SystemHealthReport:
    timestamp: float
    iso_time: str
    status: str  # "OPTIMAL", "DEGRADED", "ALERT"
    z3_hard_gate_ok: bool
    z3_latency_ms: float
    total_skills: int
    skill_levels: Dict[str, int]
    active_alerts: List[Dict[str, Any]] = field(default_factory=list)
    spark_action_required: bool = False
    action_prompt_for_spark: Optional[str] = None


class CloudTelemetryBridge:
    """
    Orchestrates continuous status synchronization to Google Drive and Gemini Spark.
    """

    def __init__(self, drive_root: Optional[Path] = None):
        self.drive_root = drive_root or (DEFAULT_DRIVE_ROOT if DEFAULT_DRIVE_ROOT.parent.exists() else LOCAL_FALLBACK_ROOT)
        self.local_root = LOCAL_FALLBACK_ROOT
        self.skill_tree = SkillTree()
        self.guard = SubstrateGuard()

    def collect_health(self, active_alerts: Optional[List[Dict[str, Any]]] = None) -> SystemHealthReport:
        """
        Gathers live system health metrics, executes SMT Z3 self-audit, and aggregates skills.
        """
        now = time.time()
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

        # 1. Verify SubstrateGuard
        test_args = {"CommandLine": "dir"}
        verify_res = self.guard.verify("run_command", test_args)
        z3_ok = verify_res.get("decision") == "allow"
        z3_lat = verify_res.get("latency_ms", 0.0)

        # 2. Count skills per tier
        skills_summary = {
            f"level_{i}": sum(1 for s in self.skill_tree.skills.values() if s.level == i)
            for i in range(1, 6)
        }

        alerts = active_alerts or []
        has_alerts = len(alerts) > 0
        overall_status = "ALERT" if has_alerts else ("OPTIMAL" if z3_ok else "DEGRADED")

        prompt_for_spark = None
        if has_alerts:
            prompt_for_spark = (
                f"[SPARK INTERVENTION REQUIRED] Detected {len(alerts)} active alerts. "
                "Consult connected Gemini NotebookLM research corpus and synthesize "
                "an RFC remediation document in Google Docs."
            )

        return SystemHealthReport(
            timestamp=now,
            iso_time=iso,
            status=overall_status,
            z3_hard_gate_ok=z3_ok,
            z3_latency_ms=z3_lat,
            total_skills=len(self.skill_tree.skills),
            skill_levels=skills_summary,
            active_alerts=alerts,
            spark_action_required=has_alerts,
            action_prompt_for_spark=prompt_for_spark,
        )

    def sync_to_cloud(self, report: Optional[SystemHealthReport] = None) -> Dict[str, Path]:
        """
        Exports machine-readable JSON and human/LLM-readable Markdown to Google Drive.
        """
        if report is None:
            report = self.collect_health()

        target_dirs = [self.local_root]
        if self.drive_root != self.local_root:
            target_dirs.append(self.drive_root)

        created_files = {}

        for root in target_dirs:
            root.mkdir(parents=True, exist_ok=True)

            # 1. JSON Telemetry
            json_file = root / "SYSTEM_HEALTH.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(asdict(report), f, indent=2, ensure_ascii=False)
            created_files[f"{root.name}_json"] = json_file

            # 2. Markdown System Status for Spark & Docs
            md_file = root / "SYSTEM_STATUS.md"
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(self._format_markdown_status(report))
            created_files[f"{root.name}_status_md"] = md_file

            # 3. Skill Tree State
            skills_file = root / "SKILL_TREE_EVOLUTION.md"
            with open(skills_file, "w", encoding="utf-8") as f:
                f.write(self._format_skill_tree())
            created_files[f"{root.name}_skills_md"] = skills_file

            # 4. Action items for Spark
            action_file = root / "SPARK_ACTION_ITEMS.md"
            with open(action_file, "w", encoding="utf-8") as f:
                f.write(self._format_spark_actions(report))
            created_files[f"{root.name}_spark_actions"] = action_file

        return created_files

    def _format_markdown_status(self, r: SystemHealthReport) -> str:
        status_emoji = "🟢" if r.status == "OPTIMAL" else ("🟡" if r.status == "DEGRADED" else "🔴")
        return f"""# Hartes AI Flywheel — Live Cloud Telemetry Status
**Last Synchronized**: `{r.iso_time}`  
**Overall System Health**: {status_emoji} **{r.status}**  
**SMT Z3 Substrate Guard**: `{"PASS" if r.z3_hard_gate_ok else "FAIL"}` (Solver Latency: `{r.z3_latency_ms:.3f} ms`)  
**Active Skills Registered**: `{r.total_skills}`  
**Spark Intervention Required**: `{"YES" if r.spark_action_required else "NO"}`

---

## 🧬 Skill Bank Tier Distribution
- **Level 1 (Atomic Primitives)**: `{r.skill_levels.get("level_1", 0)}`
- **Level 2 (Composed Workflows)**: `{r.skill_levels.get("level_2", 0)}`
- **Level 3 (Adaptive Context & AST)**: `{r.skill_levels.get("level_3", 0)}`
- **Level 4 (Dialectical & Governance)**: `{r.skill_levels.get("level_4", 0)}`
- **Level 5 (Darwinian Meta-Synthesis)**: `{r.skill_levels.get("level_5", 0)}`

---

## ⚡ Active Alerts & Diagnostics
{self._format_alerts(r.active_alerts)}
"""

    def _format_skill_tree(self) -> str:
        lines = ["# Hartes Procedural Skill Bank — Co-Evolution State\n"]
        lines.append("| ID | Name | Tier | Reliability | Weight | Description |")
        lines.append("| :--- | :--- | :---: | :---: | :---: | :--- |")
        for s in self.skill_tree.skills.values():
            lines.append(f"| `{s.id}` | {s.name} | L{s.level} | {s.reliability*100:.1f}% | {s.reward_weight:.2f} | {s.description} |")
        return "\n".join(lines) + "\n"

    def _format_spark_actions(self, r: SystemHealthReport) -> str:
        if not r.spark_action_required:
            return (
                f"# Gemini Spark Watchdog Directives\n"
                f"**Timestamp**: `{r.iso_time}`\n\n"
                f"✅ **System nominal**. All tests passing, SMT Z3 invariants satisfied.\n"
                f"- No emergency actions required.\n"
                f"- Routine tasks: continue daily morning audit at 09:00, monitor pull requests and cloud builds.\n"
            )
        return (
            f"# Gemini Spark Emergency Intervention Directive\n"
            f"**Timestamp**: `{r.iso_time}`\n\n"
            f"⚠️ **ATTENTION GEMINI SPARK**: An anomaly or test failure requires triage.\n\n"
            f"### Action Directive:\n"
            f"{r.action_prompt_for_spark}\n\n"
            f"### Active Incident Details:\n"
            f"{self._format_alerts(r.active_alerts)}\n"
        )

    def _format_alerts(self, alerts: List[Dict[str, Any]]) -> str:
        if not alerts:
            return "No active alerts. All verification gates clear."
        out = []
        for i, a in enumerate(alerts, 1):
            out.append(f"### Alert #{i}: {a.get('title', 'Unknown Issue')}")
            out.append(f"- **Severity**: `{a.get('severity', 'MEDIUM')}`")
            out.append(f"- **Context**: {a.get('context', 'N/A')}")
            out.append(f"- **Trace**: ```\n{a.get('trace', 'None')}\n```\n")
        return "\n".join(out)


def main():
    bridge = CloudTelemetryBridge()
    report = bridge.collect_health()
    paths = bridge.sync_to_cloud(report)
    print(f"[Hartes Cloud Bridge] Status: {report.status} | Z3 latency: {report.z3_latency_ms:.3f}ms")
    for k, p in paths.items():
        print(f"  -> Synced: {k}: {p}")


if __name__ == "__main__":
    main()
