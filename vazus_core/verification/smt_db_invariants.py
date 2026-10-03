"""
vazus_core.verification.smt_db_invariants
=========================================
SMT Z3 Formal Invariant Gate for SQLite vazus.db State Transitions.
Formally verifies safety and domain invariants before database commits:
1. Academic deadline monotonicity: new_deadline >= old_deadline.
2. Non-negative financial liabilities: remaining_debt >= 0.
3. Credit utilization safety: used_credit <= credit_limit.
4. Monotonic academic debt workflow transitions (PENDING -> IN_PROGRESS -> READY -> CLOSED).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import z3

logger = logging.getLogger("vazus_core.verification.smt_db_invariants")

# Legal workflow state ranks
STATUS_ORDER = {
    "PENDING": 0,
    "В процессе": 1,
    "IN_PROGRESS": 1,
    "Готово к сдаче": 2,
    "READY": 2,
    "Сдано": 3,
    "CLOSED": 3,
}


def _to_timestamp(val: Union[int, float, str, datetime]) -> float:
    """Converts diverse date representations to Unix epoch timestamp."""
    if isinstance(val, (int, float)):
        return float(val)
    elif isinstance(val, datetime):
        return val.timestamp()
    elif isinstance(val, str):
        # Try ISO format
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(val.strip(), fmt).timestamp()
            except ValueError:
                continue
    # Default fallback
    return 0.0


def verify_deadline_invariant(
    old_deadline: Union[int, float, str, datetime],
    new_deadline: Union[int, float, str, datetime],
) -> bool:
    """
    Formally verifies via Z3 that the academic deadline does not regress backward.
    Invariant: new_deadline >= old_deadline.
    Returns True if invariant holds (UNSAT on violation attempt).
    """
    old_ts = _to_timestamp(old_deadline)
    new_ts = _to_timestamp(new_deadline)

    x, y = z3.Real("old_deadline"), z3.Real("new_deadline")
    solver = z3.Solver()
    solver.add(x == old_ts)
    solver.add(y == new_ts)
    # Attempt to violate: new deadline is strictly earlier than old deadline
    solver.add(y < x)

    # UNSAT proves violation is impossible -> Invariant holds
    return solver.check() == z3.unsat


def verify_non_negative_balance(
    current_balance: float,
    debit_amount: float,
) -> bool:
    """
    Formally verifies that debiting amount does not produce a negative balance.
    Invariant: current_balance - debit_amount >= 0.
    """
    bal = z3.Real("bal")
    deb = z3.Real("debit")
    solver = z3.Solver()
    solver.add(bal == float(current_balance))
    solver.add(deb == float(debit_amount))
    # Attempt to violate: balance becomes negative
    solver.add((bal - deb) < 0)

    return solver.check() == z3.unsat


def verify_credit_limit_invariant(
    credit_limit: float,
    new_used_credit: float,
) -> bool:
    """
    Formally verifies that new credit utilization does not breach credit limit.
    Invariant: new_used_credit <= credit_limit.
    """
    lim = z3.Real("limit")
    used = z3.Real("used")
    solver = z3.Solver()
    solver.add(lim == float(credit_limit))
    solver.add(used == float(new_used_credit))
    # Attempt to violate: credit utilized exceeds limit
    solver.add(used > lim)

    return solver.check() == z3.unsat


def verify_academic_status_transition(
    old_status: str,
    new_status: str,
    allow_rollback: bool = False,
) -> bool:
    """
    Formally verifies via SMT that academic milestone status transitions forward:
    PENDING (0) -> IN_PROGRESS (1) -> READY (2) -> CLOSED (3).
    Rollbacks require explicit saga permission.
    """
    old_rank = STATUS_ORDER.get(old_status.strip(), 0)
    new_rank = STATUS_ORDER.get(new_status.strip(), 0)

    if allow_rollback:
        return True

    r_old = z3.Int("rank_old")
    r_new = z3.Int("rank_new")
    solver = z3.Solver()
    solver.add(r_old == old_rank)
    solver.add(r_new == new_rank)
    # Attempt to violate: new status rank is strictly lower than old status rank
    solver.add(r_new < r_old)

    return solver.check() == z3.unsat


def verify_db_transition(
    table_name: str,
    old_record: Optional[Dict[str, Any]],
    new_record: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Unified gatekeeper for database mutations in vazus.db.
    Checks all applicable domain invariants for the targeted table.
    """
    violations: List[str] = []

    if table_name == "mirea_milestones" and old_record is not None:
        # Check deadline monotonicity
        old_dl = old_record.get("due_date") or old_record.get("stage1_deadline")
        new_dl = new_record.get("due_date") or new_record.get("stage1_deadline")
        if old_dl and new_dl:
            if not verify_deadline_invariant(old_dl, new_dl):
                violations.append(f"SMT Invariant Violation: milestone deadline moved backward ({old_dl} -> {new_dl})")

        # Check status transition
        old_st = old_record.get("status")
        new_st = new_record.get("status")
        if old_st and new_st:
            if not verify_academic_status_transition(old_st, new_st):
                violations.append(f"SMT Invariant Violation: illegal milestone regression ({old_st} -> {new_st})")

    elif table_name == "user_liabilities" and old_record is not None:
        limit = float(new_record.get("credit_limit_rub") or old_record.get("credit_limit_rub") or 0.0)
        used = float(new_record.get("used_credit_rub") or 0.0)
        if limit > 0:
            if not verify_credit_limit_invariant(limit, used):
                violations.append(f"SMT Invariant Violation: credit used ({used}) exceeds limit ({limit})")

    return (len(violations) == 0, violations)
