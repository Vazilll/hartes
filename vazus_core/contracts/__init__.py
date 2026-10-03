"""
vazus_core.contracts — Core Interfaces and Protocols for Vazus SuperGraph OS v4.0.
===================================================================================

Defines abstract structural protocols (PEP 544) to enforce the Dependency Inversion
Principle (DIP) across core domains:
- Engine / Orchestration
- Verification & Formal Proofs
- Memory & Storage Gateway
- External Integrations & Services
- Sandboxes & Execution Runtimes
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Union, runtime_checkable
from pathlib import Path


@runtime_checkable
class LifecycleComponent(Protocol):
    """Component with explicit lifecycle start and stop semantics."""

    def start(self) -> bool:
        ...

    def stop(self) -> None:
        ...


@runtime_checkable
class DiagnosticCapable(Protocol):
    """Component capable of reporting self-health and internal diagnostic status."""

    def get_status(self) -> Dict[str, Any]:
        ...


@runtime_checkable
class HealthTelemetryProtocol(Protocol):
    """Protocol for health tracking and weight telemetry ingest engines."""

    db_path: Union[str, Path]

    def record_weight(
        self,
        weight_kg: float,
        impedance_ohm: Optional[float] = None,
        source: str = "manual",
    ) -> Dict[str, Any]:
        ...

    def run_multi_agent_evaluation(self, user_query: str) -> Dict[str, Any]:
        ...


@runtime_checkable
class FinanceManagerProtocol(Protocol):
    """Protocol for banking, cash flow, and tax accounting engines."""

    db_path: Union[str, Path]

    def get_financial_summary(self) -> Dict[str, Any]:
        ...


@runtime_checkable
class StudentManagerProtocol(Protocol):
    """Protocol for academic debt tracking, schedules, and MIREA student state."""

    db_path: Union[str, Path]

    def get_academic_debt_summary(self) -> Dict[str, Any]:
        ...


@runtime_checkable
class OrderHunterProtocol(Protocol):
    """Protocol for freelance, self-employed order matching and bidding engines."""

    db_path: Union[str, Path]

    def match_orders_for_target_revenue(self, target_revenue_rub: float) -> List[Dict[str, Any]]:
        ...


@runtime_checkable
class SMTVerifierProtocol(Protocol):
    """Protocol for SMT Z3 formal verification engines."""

    def verify_code_contracts(self, code_str: str, depth: int = 1) -> Any:
        ...

    def verify_functional_equivalence(
        self, orig_code: str, opt_code: str, func_name: Optional[str] = None
    ) -> Any:
        ...


@runtime_checkable
class ExecutionSandboxProtocol(Protocol):
    """Protocol for isolated execution environments (Win32 Job, WSB, Container)."""

    def execute(self, code: str, timeout_sec: int = 30) -> Dict[str, Any]:
        ...


@runtime_checkable
class MemoryGatewayProtocol(Protocol):
    """Protocol for unified memory read/write gateways."""

    def store_fact(
        self,
        fact_text: str,
        category: str = "general",
        entity: str = "user",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        ...

    def recall(
        self,
        query: str,
        top_k: int = 5,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ...
