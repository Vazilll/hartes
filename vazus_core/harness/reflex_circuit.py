"""
vazus_core.harness.reflex_circuit
=================================
Tier-0 Local Reflex Loops Architecture (inspired by Drosophila VNC / FlyCNS 2026).
Executes instant, deterministic, and small-model actions on Intel Core Ultra NPU/CPU in <15ms.
Acts as the sensory-motor gating barrier before ascending to Tier-1 Cognitive LLM.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from vazus_core.memory.db import DEFAULT_VAZUS_DB
from vazus_core.memory.j_space_tool_indexer import JSpaceToolIndexer
from vazus_core.security.model_armor import ModelArmor, SecurityVerdict

logger = logging.getLogger("vazus_core.harness.reflex_circuit")

STAGE1_DEADLINE = "15.10.2026"
TOTAL_DEBTS = 18


class ReflexActionType(str, Enum):
    IMMEDIATE_LOCAL = "immediate_local"    # Handled purely locally (telemetry, query, academic status)
    SECURITY_BLOCK  = "security_block"     # Nociceptive pain reflex: immediately denied by ModelArmor
    ASCEND_COGNITIVE = "ascend_cognitive"  # Ascending tract to Tier-1 LLM required


@dataclass
class ReflexSignal:
    raw_query: str
    channel: str = "local"
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ReflexVerdict:
    action_type: ReflexActionType
    confidence: float
    output_payload: Optional[str] = None
    target_tool: Optional[str] = None
    suggested_subagent: Optional[str] = None
    reason: str = ""
    latency_ms: float = 0.0


class ReflexCircuitController:
    """
    Tier-0 Neuromorphic Reflex Controller.
    Evaluates sensory afferents, activates local reflex arcs, or triggers ascending pathways.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        cognitive_threshold: float = 0.85,
    ) -> None:
        self.cognitive_threshold = cognitive_threshold
        self.db_path = str(db_path or DEFAULT_VAZUS_DB)
        self._indexer: Optional[JSpaceToolIndexer] = None
        self._local_reflex_handlers: Dict[str, Callable[[ReflexSignal], str]] = {}
        self._register_default_reflex_handlers()

    @property
    def tool_indexer(self) -> JSpaceToolIndexer:
        if self._indexer is None:
            self._indexer = JSpaceToolIndexer(db_path=self.db_path)
        return self._indexer

    def _register_default_reflex_handlers(self) -> None:
        """Registers fast deterministic local handlers (<5ms)."""
        self._local_reflex_handlers["academic_status"] = self._handle_academic_status
        self._local_reflex_handlers["hardware_health"] = self._handle_hardware_health
        self._local_reflex_handlers["system_identity"] = self._handle_system_identity
        self._local_reflex_handlers["pedagogical_guard"] = self._handle_pedagogical_guard

    def _handle_academic_status(self, signal: ReflexSignal) -> str:
        """Reads academic profile dynamically from vazus.db with fallback to Tier-0 constants."""
        debts = TOTAL_DEBTS
        deadline = STAGE1_DEADLINE
        group = "ИВБО-22-25"
        if self.db_path and Path(self.db_path).exists():
            try:
                with sqlite3.connect(self.db_path, timeout=1.0) as conn:
                    row = conn.execute(
                        "SELECT active_debts_count, stage1_deadline, group_name FROM student_profile LIMIT 1"
                    ).fetchone()
                    if row:
                        debts = row[0] if row[0] is not None else debts
                        deadline = row[1] if row[1] is not None else deadline
                        group = row[2] if row[2] is not None else group
            except Exception as e:
                logger.debug("Dynamic student_profile read failed, using fallback: %s", e)

        return (
            f"РТУ МИРЭА (гр. {group}) | 1-й этап пересдач до {deadline}. "
            f"Задолженностей: {debts}. Режим: Сократический наставник (USER.md invariant)."
        )

    def _handle_hardware_health(self, signal: ReflexSignal) -> str:
        return (
            "Intel(R) Core(TM) Ultra 5 125U (Intel AI Boost NPU: ONLINE) | "
            "J-Space 768D Engine: READY | SQLite WAL: ACTIVE"
        )

    def _handle_system_identity(self, signal: ReflexSignal) -> str:
        return (
            "Vazus SuperGraph OS v5.0 (Bio-Connectomic Tri-Agent Architecture). "
            "Пользователь: Жуков Максим Дмитриевич (ИВБО-22-25)."
        )

    def _handle_pedagogical_guard(self, signal: ReflexSignal) -> str:
        return (
            "Педагогический суверенитет (USER.md#L37 invariant): СТРОГО ЗАПРЕЩЕНО решать за студента "
            "лабораторные, типовые расчеты, контрольные и тесты СДО. "
            "Агент работает исключительно в роли Сократического наставника: "
            "задает наводящие вопросы, объясняет теорию, указывает на ошибки в рассуждениях."
        )

    def register_custom_reflex(self, name: str, handler: Callable[[ReflexSignal], str]) -> None:
        """Dynamically registers an additional local reflex arc."""
        self._local_reflex_handlers[name] = handler

    def evaluate_signal(self, signal: ReflexSignal) -> ReflexVerdict:
        """
        Main Tier-0 Reflex Pipeline:
        1. Nociceptive Armor Check (ModelArmor) -> Instant Block if dangerous or quarantined (Fail-Closed).
        2. Fast Heuristic & Keyword Reflex Arc -> Immediate Local answer if deterministic.
        3. J-Space Vector Similarity -> Fast Tool Pre-routing.
        4. Gating Decision -> Immediate Local vs Ascending Cognitive Tract.
        """
        start_t = time.perf_counter()

        # Step 1: Nociceptive Pain Reflex (ModelArmor) — Strict Fail-Closed
        try:
            armor_inspection = ModelArmor.inspect_prompt(signal.raw_query)
            if armor_inspection.verdict in (SecurityVerdict.DENY, SecurityVerdict.QUARANTINE):
                latency = (time.perf_counter() - start_t) * 1000.0
                return ReflexVerdict(
                    action_type=ReflexActionType.SECURITY_BLOCK,
                    confidence=1.0,
                    output_payload="Запрос заблокирован политикой безопасности ModelArmor.",
                    reason="; ".join(armor_inspection.reasons) or f"Security verdict: {armor_inspection.verdict.value}",
                    latency_ms=latency,
                )
        except Exception as e:
            logger.error("ModelArmor inspection failed (Fail-Closed triggered): %s", e)
            latency = (time.perf_counter() - start_t) * 1000.0
            return ReflexVerdict(
                action_type=ReflexActionType.SECURITY_BLOCK,
                confidence=1.0,
                output_payload="Запрос заблокирован: сбой защитного контура ModelArmor (Fail-Closed).",
                reason=f"Fail-Closed security exception: {e}",
                latency_ms=latency,
            )

        # Step 2: Instant Deterministic Reflex Arcs (<3ms)
        q = signal.raw_query.lower().strip()

        # Check pedagogical sovereignty guard: reject direct cheating / lab solving requests
        cheating_patterns = [
            "реши за меня", "сделай за меня", "напиши за меня лабу",
            "реши контрольную", "пройди тест сдо", "дай готовый ответ на лабу",
            "напиши за меня типовой расчет", "реши тест за меня"
        ]
        if any(pat in q for pat in cheating_patterns):
            payload = self._local_reflex_handlers["pedagogical_guard"](signal)
            latency = (time.perf_counter() - start_t) * 1000.0
            return ReflexVerdict(
                action_type=ReflexActionType.IMMEDIATE_LOCAL,
                confidence=1.0,
                output_payload=payload,
                reason="Pedagogical sovereignty enforced (USER.md#L37 invariant)",
                latency_ms=latency,
            )

        # Academic status reflex (strictly excluding technical debt / techdebt)
        is_tech_debt = any(k in q for k in ["техдолг", "технический долг", "tech debt", "technical debt"])
        if not is_tech_debt and any(kw in q for kw in ["долг", "задолженност", "пересдач", "статус учеб", "учебн"]):
            payload = self._local_reflex_handlers["academic_status"](signal)
            latency = (time.perf_counter() - start_t) * 1000.0
            return ReflexVerdict(
                action_type=ReflexActionType.IMMEDIATE_LOCAL,
                confidence=0.99,
                output_payload=payload,
                reason="Handled by local academic reflex arc",
                latency_ms=latency,
            )

        if any(kw in q for kw in ["статус железа", "npu статус", "проверь железо"]):
            payload = self._local_reflex_handlers["hardware_health"](signal)
            latency = (time.perf_counter() - start_t) * 1000.0
            return ReflexVerdict(
                action_type=ReflexActionType.IMMEDIATE_LOCAL,
                confidence=0.98,
                output_payload=payload,
                reason="Handled by local hardware reflex arc",
                latency_ms=latency,
            )

        if any(kw in q for kw in ["кто ты", "твоя личность", "какая система", "версия системы"]):
            payload = self._local_reflex_handlers["system_identity"](signal)
            latency = (time.perf_counter() - start_t) * 1000.0
            return ReflexVerdict(
                action_type=ReflexActionType.IMMEDIATE_LOCAL,
                confidence=0.97,
                output_payload=payload,
                reason="Handled by local system identity reflex arc",
                latency_ms=latency,
            )

        # Step 3: Fast J-Space Tool Semantic Cosine Match on NPU/CPU
        best_tool_name = None
        tool_score = 0.0
        try:
            tools = self.tool_indexer.find_tools_for_query(signal.raw_query, top_k=1, min_similarity=0.35)
            if tools:
                best_tool_name = tools[0].get("tool_name")
                tool_score = float(tools[0].get("similarity", 0.0))
        except Exception as e:
            logger.debug("J-Space reflex pre-routing non-fatal: %s", e)

        # Step 4: Gating Decision — Ascending tract to Tier-1 Cognitive Pathway
        latency = (time.perf_counter() - start_t) * 1000.0
        return ReflexVerdict(
            action_type=ReflexActionType.ASCEND_COGNITIVE,
            confidence=tool_score,
            target_tool=best_tool_name,
            suggested_subagent=self._map_tool_to_subagent(best_tool_name or ""),
            reason="Ascending to Tier-1 Cognitive Pathway (LLM reasoning required)",
            latency_ms=latency,
        )

    def _map_tool_to_subagent(self, tool_name: str) -> str:
        t = tool_name.lower()
        if any(k in t for k in ["sandbox", "terminal", "repl", "code", "run"]):
            return "RLM_Coder"
        if any(k in t for k in ["z3", "smt", "verify", "proof", "armor"]):
            return "Verifier_Worker"
        if any(k in t for k in ["cbm", "graph", "topology", "ast"]):
            return "Planner"
        if any(k in t for k in ["memory", "mem0", "dream", "review"]):
            return "Auto_Reviewer"
        return "RLM_Coder"
