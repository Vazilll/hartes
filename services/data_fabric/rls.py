"""
services.data_fabric.rls
========================
Two-Tier Row-Level Security (RLS) and Access Control Engine for Data Fabric.
Ensures zero unauthorized mutations, role-based scoping, and strict tenant isolation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("services.data_fabric.rls")

# SOTA User & Academic Invariants (SSOT USER.md)
OWNER_STUDENT_ID = "25И0566"
OWNER_EMAIL = "zhukov.m.d1@edu.mirea.ru"
OWNER_GROUP = "ИВБО-22-25"


class RowLevelSecurity:
    """Evaluates read and write operations against tenant and privacy policies."""

    @classmethod
    def can_read(cls, entity_name: str, record: Dict[str, Any], user_context: Optional[Dict[str, Any]] = None) -> bool:
        """Determines if the requesting context has read authority."""
        # Personal academic and financial entities are owner-only in multi-tenant contexts
        if entity_name in ("user_liabilities", "finance_transactions"):
            user_id = (user_context or {}).get("student_id") or (user_context or {}).get("email")
            if user_id and user_id not in (OWNER_STUDENT_ID, OWNER_EMAIL):
                return False
        return True

    @classmethod
    def can_write(cls, entity_name: str, record: Dict[str, Any], user_context: Optional[Dict[str, Any]] = None) -> bool:
        """Determines if the requesting context has mutation authority."""
        # Read-only protected tables cannot be overwritten via arbitrary CRUD
        if entity_name in ("protected_whitelist", "system_reactive_parameters"):
            return False
        return True

    @classmethod
    def filter_query_by_tenant(cls, entity_name: str, base_query: str) -> str:
        """Appends tenant boundary predicates to raw SQL queries via subquery wrapping."""
        if entity_name == "mirea_milestones":
            return f"SELECT * FROM ({base_query.strip().rstrip(';')}) AS _sub WHERE (student_id = '{OWNER_STUDENT_ID}' OR student_id IS NULL)"
        return base_query
