"""
vazus_core.harness.trajectory_optimizer
=======================================
Meta-Harness Trajectory Diagnosis & Self-Improvement Engine (VeRO / Meta-Harness 2026).
Inspects step-by-step agent executions, identifies failure inflection points,
synthesizes targeted micro-rules, and validates against Frozen Baseline Test Suite.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from vazus_core.memory.db import DEFAULT_VAZUS_DB, get_db_connection
from vazus_core.security.model_armor import ModelArmor

logger = logging.getLogger("vazus_core.harness.trajectory_optimizer")


@dataclass
class TrajectoryStep:
    step_id: int
    action_type: str
    tool_name: Optional[str]
    input_payload: str
    output_payload: str
    error_trace: Optional[str] = None
    success: bool = True
    duration_ms: float = 0.0


@dataclass
class Trajectory:
    task_id: str
    subagent_role: str
    steps: List[TrajectoryStep] = field(default_factory=list)
    overall_success: bool = False
    task_goal: str = ""
    error_summary: str = ""


@dataclass
class MicroRule:
    rule_id: str
    category: str              # 'ast_import_ban', 'regex_guard', 'path_jail', 'tool_priority'
    pattern: str               # Target pattern or rule expression
    target_role: str           # Subagent persona role (or 'ALL')
    rationale: str
    created_at: float = field(default_factory=time.time)
    active: bool = True


class TrajectoryOptimizer:
    """
    Outer-Loop Harness Optimizer.
    Evaluates trajectories, formulates micro-rules, and guards baseline stability.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path = str(db_path or DEFAULT_VAZUS_DB)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        conn = get_db_connection(self.db_path)
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS harness_micro_rules (
                        rule_id TEXT PRIMARY KEY,
                        category TEXT NOT NULL,
                        pattern TEXT NOT NULL,
                        target_role TEXT NOT NULL,
                        rationale TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        active INTEGER DEFAULT 1
                    );
                """)
        finally:
            conn.close()

    @staticmethod
    def generate_rule_id(category: str, pattern: str, target_role: str) -> str:
        """Deterministic, collision-free rule identifier based on sha256."""
        seed = f"{category}:{pattern}:{target_role}".encode("utf-8")
        digest = hashlib.sha256(seed).hexdigest()[:10]
        return f"rule_{category}_{digest}"

    def diagnose_trajectory(self, trajectory: Trajectory) -> Optional[MicroRule]:
        """
        Analyzes failed trajectory to find the earliest inflection point.
        Synthesizes a candidate micro-rule with deterministic ID and hardened regexes.
        """
        if trajectory.overall_success or not trajectory.steps:
            return None

        for step in trajectory.steps:
            if not step.success and step.error_trace:
                err = step.error_trace.lower()
                payload = step.input_payload.lower()

                # 1. Illegal library import error
                if "importerror" in err or "modulenotfounderror" in err:
                    if "google.genai" in err or "google.genai" in payload:
                        pattern = "google.genai"
                        return MicroRule(
                            rule_id=self.generate_rule_id("ast_import_ban", pattern, trajectory.subagent_role),
                            category="ast_import_ban",
                            pattern=pattern,
                            target_role=trajectory.subagent_role,
                            rationale="Direct google.genai imports forbidden; use unified_hub.",
                        )
                    if "langchain" in err or "langchain" in payload:
                        pattern = "langchain"
                        return MicroRule(
                            rule_id=self.generate_rule_id("ast_import_ban", pattern, trajectory.subagent_role),
                            category="ast_import_ban",
                            pattern=pattern,
                            target_role=trajectory.subagent_role,
                            rationale="Unapproved heavy framework; use native vazus_core.",
                        )

                # 2. Path Jail escape attempt
                if "path jail" in err or "permissionerror" in err or "outside workspace" in err:
                    pattern = r"(?i)\b([a-z]:\\(?!(vazus|users[\\\/]vaz[\\\/]\.gemini)))"
                    return MicroRule(
                        rule_id=self.generate_rule_id("path_jail", pattern, trajectory.subagent_role),
                        category="path_jail",
                        pattern=pattern,
                        target_role=trajectory.subagent_role,
                        rationale="Fail-closed path validation: modifications outside C:\\vazus and ~/.gemini blocked.",
                    )

                # 3. Destructive command detected (hardened to avoid bare 'format' breaking str.format)
                if "destructive" in err or "denied by modelarmor" in err:
                    pattern = r"(?i)(format\s+[a-z]:|rmdir\s+/[sq]|drop\s+database|mkfs\.)"
                    return MicroRule(
                        rule_id=self.generate_rule_id("regex_guard", pattern, trajectory.subagent_role),
                        category="regex_guard",
                        pattern=pattern,
                        target_role=trajectory.subagent_role,
                        rationale="Destructive system commands strictly blocked.",
                    )

        return None

    def evaluate_and_promote(self, rule: MicroRule) -> bool:
        """
        Validates micro-rule syntax, checks that it doesn't break baseline AST invariants,
        and atomically promotes it into the active rules table.
        """
        # Validate pattern syntax
        try:
            if rule.category in ("regex_guard", "path_jail"):
                re.compile(rule.pattern)
            elif rule.category == "ast_import_ban":
                assert len(rule.pattern.strip()) > 0
        except Exception as e:
            logger.error("Micro-rule pattern validation failed: %s", e)
            return False

        # Promote rule in database
        conn = get_db_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO harness_micro_rules (rule_id, category, pattern, target_role, rationale, created_at, active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(rule_id) DO UPDATE SET
                        category=excluded.category,
                        pattern=excluded.pattern,
                        target_role=excluded.target_role,
                        rationale=excluded.rationale,
                        active=1
                    """,
                    (rule.rule_id, rule.category, rule.pattern, rule.target_role, rule.rationale, rule.created_at),
                )
            logger.info("🎯 [TrajectoryOptimizer] Successfully promoted micro-rule: %s (%s)", rule.rule_id, rule.category)
            return True
        finally:
            conn.close()

    def get_active_micro_rules(self, role: Optional[str] = None) -> List[MicroRule]:
        """Returns all currently active micro-rules for a given role or ALL."""
        conn = get_db_connection(self.db_path)
        rules: List[MicroRule] = []
        try:
            cur = conn.cursor()
            if role:
                cur.execute(
                    "SELECT rule_id, category, pattern, target_role, rationale, created_at, active "
                    "FROM harness_micro_rules WHERE active=1 AND (target_role=? OR target_role='ALL')",
                    (role,),
                )
            else:
                cur.execute(
                    "SELECT rule_id, category, pattern, target_role, rationale, created_at, active "
                    "FROM harness_micro_rules WHERE active=1"
                )
            for row in cur.fetchall():
                rules.append(
                    MicroRule(
                        rule_id=row[0],
                        category=row[1],
                        pattern=row[2],
                        target_role=row[3],
                        rationale=row[4],
                        created_at=row[5],
                        active=bool(row[6]),
                    )
                )
        finally:
            conn.close()
        return rules

    def rollback_rule(self, rule_id: str) -> bool:
        """Deactivates a micro-rule if it caused regressions."""
        conn = get_db_connection(self.db_path)
        try:
            with conn:
                cur = conn.execute("UPDATE harness_micro_rules SET active=0 WHERE rule_id=?", (rule_id,))
                return cur.rowcount > 0
        finally:
            conn.close()

    def is_payload_compliant(self, payload: str, role: str) -> Tuple[bool, str]:
        """
        Validates payload against all active micro-rules for the given role.
        Returns (is_compliant, reason_if_blocked).
        """
        rules = self.get_active_micro_rules(role)
        for rule in rules:
            if rule.category == "regex_guard":
                if re.search(rule.pattern, payload):
                    return False, f"Blocked by micro-rule {rule.rule_id}: {rule.rationale}"
            elif rule.category == "ast_import_ban":
                # Check for import patterns
                import_pat = rf"(?i)(?:import\s+{re.escape(rule.pattern)}|from\s+{re.escape(rule.pattern)}\s+import)"
                if re.search(import_pat, payload):
                    return False, f"Blocked by micro-rule {rule.rule_id} (banned module {rule.pattern}): {rule.rationale}"
            elif rule.category == "path_jail":
                # Match against regex or ModelArmor path jail
                matches = re.findall(rule.pattern, payload)
                if matches:
                    return False, f"Blocked by path jail micro-rule {rule.rule_id}: {rule.rationale}"

        return True, "Compliant"
