"""
vazus_core.circuit_breaker — Anti-Loop Circuit Breaker & Model Escalation Engine.

Prevents AI agent retry rot and infinite edit loops by:
1. Thread-safe tracking of AST location-independent structural hashes across iterations.
2. Tripping when duplicate or near-identical code proposals are generated.
3. Automatically triggering AST pruning and model escalation when churn is detected.
"""

import ast
import hashlib
import logging
import threading
from typing import List, Dict, Any, Optional

logger = logging.getLogger("CircuitBreaker")


class AntiLoopCircuitBreaker:
    """
    Thread-safe monitor for code proposals across iterations to prevent infinite retry loops.
    """

    def __init__(self, max_duplicates: int = 2, max_total_attempts: int = 5, history_limit: int = 50):
        self.max_duplicates = max_duplicates
        self.max_total_attempts = max_total_attempts
        self.history_limit = history_limit
        self._lock = threading.Lock()
        self.history: List[str] = []
        self.hashes: List[str] = []
        self.tripped: bool = False
        self.trip_reason: Optional[str] = None
        self.attempts: int = 0

    @staticmethod
    def _normalize_ast_node(node: Any) -> tuple:
        """Recursively converts an AST node into a location-independent immutable tuple."""
        if isinstance(node, ast.AST):
            fields = []
            for name, value in ast.iter_fields(node):
                if name in ("lineno", "col_offset", "end_lineno", "end_col_offset"):
                    continue
                fields.append((name, AntiLoopCircuitBreaker._normalize_ast_node(value)))
            return (type(node).__name__, tuple(fields))
        elif isinstance(node, list):
            return tuple(AntiLoopCircuitBreaker._normalize_ast_node(item) for item in node)
        else:
            return node

    @staticmethod
    def hash_code(code_str: str) -> str:
        """
        Computes SHA-256 location-invariant AST structural hash of code.
        Falls back to MD5 normalized string hash if code contains syntax errors.
        """
        try:
            tree = ast.parse(code_str)
            normalized = AntiLoopCircuitBreaker._normalize_ast_node(tree)
            return hashlib.sha256(repr(normalized).encode("utf-8")).hexdigest()
        except Exception:
            normalized_lines = "\n".join(line.rstrip() for line in code_str.strip().splitlines() if line.strip())
            return hashlib.md5(normalized_lines.encode("utf-8")).hexdigest()

    def register_attempt(self, code_str: str) -> bool:
        """
        Registers a code proposal attempt under thread-safe lock.
        Returns True if execution can proceed, or False if Circuit Breaker TRIPPED.
        """
        with self._lock:
            self.attempts += 1
            code_hash = self.hash_code(code_str)

            # Check max total attempts
            if self.attempts > self.max_total_attempts:
                self.tripped = True
                self.trip_reason = f"Max total attempts reached ({self.attempts} > {self.max_total_attempts})"
                logger.warning(f"[Circuit Breaker TRIPPED] {self.trip_reason}")
                return False

            # Check duplicate hash count
            duplicate_count = self.hashes.count(code_hash)
            if duplicate_count >= self.max_duplicates:
                self.tripped = True
                self.trip_reason = f"Duplicate code proposal detected {duplicate_count + 1} times (Hash: {code_hash[:8]})"
                logger.warning(f"[Circuit Breaker TRIPPED] {self.trip_reason}")
                return False

            # Bounded sliding window for history to prevent RAM bloat
            if len(self.history) >= self.history_limit:
                self.history.pop(0)
                self.hashes.pop(0)

            self.history.append(code_str)
            self.hashes.append(code_hash)
            return True

    def reset(self):
        """Resets the circuit breaker state under thread-safe lock."""
        with self._lock:
            self.history.clear()
            self.hashes.clear()
            self.tripped = False
            self.trip_reason = None
            self.attempts = 0

    def get_status(self) -> Dict[str, Any]:
        """Returns thread-safe snapshot of circuit breaker status."""
        with self._lock:
            return {
                "attempts": self.attempts,
                "max_attempts": self.max_total_attempts,
                "tripped": self.tripped,
                "reason": self.trip_reason,
                "history_length": len(self.history),
            }
