"""
vazus_autonomous_harness.memory.preflight_filter — Pre-Flight Retrieval & Executable Negative Constraint Filter.

Milestone 2 (F7):
- Tri-Hybrid Retrieval Engine:
  * FTS5 Lexical BM25 (0.35 weight)
  * 768D Vector Cosine Similarity (0.40 weight)
  * Recurrence & Efficacy Boost (0.25 weight)
- Pre-Execution Hard-Gate Interception:
  * Deterministic static inspection executing in < 5 ms
  * Evaluates REGEX_DENY, AST_PATTERN_DENY, and SMT_PREDICATE_BLOCK
  * Intercepts known dead-ends before compute expenditure
  * Automatically increments intercept_count on active memory records
"""

import ast
import logging
import math
import operator
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from vazus_autonomous_harness.memory.episodic_store import EpisodicMemoryStore
from vazus_autonomous_harness.memory.reflexion_engine import (
    ExecutableNegativeConstraint,
    ReflexionRecord,
)

logger = logging.getLogger("vazus.harness.memory.preflight")


@dataclass
class PreFlightCheckResult:
    """Diagnostic outcome of pre-execution hard-gate inspection."""
    allowed: bool
    violation_message: Optional[str] = None
    violated_rule: Optional[ExecutableNegativeConstraint] = None
    execution_time_ms: float = 0.0

    @property
    def is_blocked(self) -> bool:
        return not self.allowed


class ASTNegativeConstraintVisitor(ast.NodeVisitor):
    """
    High-speed AST visitor inspecting candidate syntax tree against negative rules.
    Detects empty stubs, forbidden imports, forbidden calls, and structural anti-patterns.
    """

    def __init__(self, rules: List[ExecutableNegativeConstraint]):
        self.rules = rules
        self.violated_rule: Optional[ExecutableNegativeConstraint] = None
        self.violation_message: Optional[str] = None

    def check(self, tree: ast.AST) -> Tuple[bool, Optional[ExecutableNegativeConstraint], Optional[str]]:
        self.visit(tree)
        if self.violated_rule:
            return False, self.violated_rule, self.violation_message
        return True, None, None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_function_stubs(node)
        if not self.violated_rule:
            self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_function_stubs(node)
        if not self.violated_rule:
            self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self._check_import_name(alias.name)
            if self.violated_rule:
                return
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        self._check_import_name(mod)
        if self.violated_rule:
            return
        for alias in node.names:
            full_name = f"{mod}.{alias.name}" if mod else alias.name
            self._check_import_name(full_name)
            if self.violated_rule:
                return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        func_name = ""
        full_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            full_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            if isinstance(node.func.value, ast.Name):
                full_name = f"{node.func.value.id}.{node.func.attr}"

        for rule in self.rules:
            if rule.rule_type == "AST_PATTERN_DENY":
                target = rule.pattern.replace("call:", "").replace("Call:", "").rstrip("(").strip().lower()
                if (func_name and func_name.lower() == target) or (full_name and full_name.lower() == target) or (target and target in full_name.lower()):
                    self.violated_rule = rule
                    self.violation_message = f"[PRE-FLIGHT AST VETO] (AST_PATTERN_DENY) Prohibited call to '{full_name or func_name}': {rule.description}"
                    return

        self.generic_visit(node)

    def _check_function_stubs(self, node: Any):
        """Checks for empty stubs: pass, ellipsis, or NotImplementedError."""
        # Skip abstract methods
        is_abstract = any(
            isinstance(d, ast.Name) and d.id in ("abstractmethod", "overload")
            or isinstance(d, ast.Attribute) and d.attr in ("abstractmethod", "overload")
            for d in node.decorator_list
        )
        if is_abstract:
            return

        # Filter out docstrings
        body_stmts = [
            s for s in node.body
            if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))
        ]

        if not body_stmts:
            self._match_stub_rule(node.name, "empty function body")
            return

        if len(body_stmts) == 1:
            s = body_stmts[0]
            if isinstance(s, ast.Pass):
                self._match_stub_rule(node.name, "empty 'pass' stub")
            elif isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and s.value.value is Ellipsis:
                self._match_stub_rule(node.name, "empty '...' ellipsis stub")
            elif isinstance(s, ast.Raise):
                exc = s.exc
                if isinstance(exc, ast.Call) and getattr(exc.func, "id", None) == "NotImplementedError":
                    self._match_stub_rule(node.name, "unimplemented 'NotImplementedError' stub")
                elif isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                    self._match_stub_rule(node.name, "unimplemented 'NotImplementedError' stub")

    def _match_stub_rule(self, func_name: str, reason: str):
        for rule in self.rules:
            if rule.rule_type == "AST_PATTERN_DENY" and ("stub" in rule.pattern.lower() or "pass" in rule.pattern.lower() or "ellipsis" in rule.pattern.lower()):
                self.violated_rule = rule
                self.violation_message = f"[PRE-FLIGHT AST VETO] (AST_PATTERN_DENY) Function '{func_name}' is a {reason}: {rule.description}"
                return

    def _check_import_name(self, name: str):
        for rule in self.rules:
            if rule.rule_type == "IMPORT_BAN":
                target = rule.pattern.replace("import:", "").replace("Import:", "").strip().lower()
                if target in name.lower() or name.lower() in target:
                    self.violated_rule = rule
                    self.violation_message = f"[PRE-FLIGHT IMPORT VETO] (IMPORT_BAN) Prohibited import '{name}': {rule.description}"
                    return
            elif rule.rule_type == "AST_PATTERN_DENY" and ("import" in rule.pattern.lower() or rule.target_scope == "imports"):
                target = rule.pattern.replace("import:", "").replace("Import:", "").strip().lower()
                if target in name.lower():
                    self.violated_rule = rule
                    self.violation_message = f"[PRE-FLIGHT AST VETO] (AST_PATTERN_DENY) Prohibited import '{name}': {rule.description}"
                    return


class PreFlightFilter:
    """
    F7 Pre-Flight Retrieval & Executable Negative Constraint Filter Engine.
    Executes sub-5ms static gating and tri-hybrid semantic retrieval.
    """

    def __init__(
        self,
        episodic_store: Optional[EpisodicMemoryStore] = None,
        cached_rules: Optional[List[ExecutableNegativeConstraint]] = None,
    ):
        self.episodic_store = episodic_store or EpisodicMemoryStore()
        self._compiled_regex_cache: Dict[str, re.Pattern] = {}
        self._active_rules: List[ExecutableNegativeConstraint] = []

        if cached_rules is not None:
            self._active_rules = list(cached_rules)
            self._compile_regex_rules()
        else:
            self.reload_rules()

    def reload_rules(self) -> int:
        """Fetches active negative rules from episodic store and pre-compiles regexes."""
        self._active_rules = self.episodic_store.get_active_negative_rules(limit=200)
        self._compile_regex_rules()
        return len(self._active_rules)

    def add_rule(self, rule: ExecutableNegativeConstraint):
        """Adds a single negative rule to in-memory filter."""
        self._active_rules.append(rule)
        if rule.rule_type == "REGEX_DENY":
            try:
                self._compiled_regex_cache[rule.rule_id] = re.compile(rule.pattern, re.IGNORECASE | re.MULTILINE)
            except re.error as e:
                logger.debug("Failed compiling regex pattern '%s': %s", rule.pattern, e)

    def _compile_regex_rules(self):
        """Pre-compiles regex rules for sub-millisecond evaluation."""
        self._compiled_regex_cache.clear()
        for r in self._active_rules:
            if r.rule_type == "REGEX_DENY" and r.pattern:
                try:
                    self._compiled_regex_cache[r.rule_id] = re.compile(r.pattern, re.IGNORECASE | re.MULTILINE)
                except re.error as e:
                    logger.debug("Failed compiling regex for rule %s: %s", r.rule_id, e)

    def check_candidate(
        self,
        candidate_code: str,
        active_rules: Optional[List[ExecutableNegativeConstraint]] = None,
    ) -> PreFlightCheckResult:
        """
        Executes pre-execution hard-gate inspection in < 5 ms.
        Evaluates REGEX_DENY, AST_PATTERN_DENY, and SMT_PREDICATE_BLOCK rules.
        """
        t0 = time.perf_counter()
        rules = active_rules if active_rules is not None else self._active_rules

        # Empty candidate check
        if not candidate_code or not candidate_code.strip():
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return PreFlightCheckResult(
                allowed=True,
                violation_message=None,
                execution_time_ms=elapsed_ms,
            )

        # 1. Fast Pattern & Regex Inspection
        for rule in rules:
            if rule.rule_type == "REGEX_DENY":
                regex = self._compiled_regex_cache.get(rule.rule_id)
                if regex is None:
                    try:
                        regex = re.compile(rule.pattern, re.IGNORECASE | re.MULTILINE)
                        self._compiled_regex_cache[rule.rule_id] = regex
                    except re.error:
                        regex = None

                if regex and regex.search(candidate_code):
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    try:
                        self.episodic_store.increment_intercept_count(rule.rule_id)
                    except Exception as e:
                        logger.debug("Failed incrementing intercept count: %s", e)
                    return PreFlightCheckResult(
                        allowed=False,
                        violation_message=f"[PRE-FLIGHT REGEX VETO] (REGEX_DENY) {rule.description} [pattern: {rule.pattern}]",
                        violated_rule=rule,
                        execution_time_ms=elapsed_ms,
                    )
            elif rule.rule_type == "IMPORT_BAN" and rule.pattern:
                if rule.pattern in candidate_code:
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    try:
                        self.episodic_store.increment_intercept_count(rule.rule_id)
                    except Exception as e:
                        logger.debug("Failed incrementing intercept count: %s", e)
                    return PreFlightCheckResult(
                        allowed=False,
                        violation_message=f"[PRE-FLIGHT IMPORT VETO] (IMPORT_BAN) Prohibited import '{rule.pattern}': {rule.description}",
                        violated_rule=rule,
                        execution_time_ms=elapsed_ms,
                    )
            elif rule.rule_type == "AST_PATTERN_DENY" and rule.pattern:
                pat_clean = rule.pattern.rstrip("(").strip()
                if pat_clean and pat_clean in candidate_code:
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    try:
                        self.episodic_store.increment_intercept_count(rule.rule_id)
                    except Exception as e:
                        logger.debug("Failed incrementing intercept count: %s", e)
                    return PreFlightCheckResult(
                        allowed=False,
                        violation_message=f"[PRE-FLIGHT AST VETO] (AST_PATTERN_DENY) Prohibited AST pattern '{rule.pattern}': {rule.description}",
                        violated_rule=rule,
                        execution_time_ms=elapsed_ms,
                    )

        # 2. AST Pattern Inspection
        try:
            tree = ast.parse(candidate_code)
            ast_rules = [r for r in rules if r.rule_type in ("AST_PATTERN_DENY", "IMPORT_BAN")]
            if ast_rules:
                visitor = ASTNegativeConstraintVisitor(ast_rules)
                ok, violated_rule, msg = visitor.check(tree)
                if not ok and violated_rule:
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    try:
                        self.episodic_store.increment_intercept_count(violated_rule.rule_id)
                    except Exception as e:
                        logger.debug("Failed incrementing intercept count: %s", e)
                    return PreFlightCheckResult(
                        allowed=False,
                        violation_message=msg or f"[PRE-FLIGHT AST VETO] {violated_rule.description}",
                        violated_rule=violated_rule,
                        execution_time_ms=elapsed_ms,
                    )
        except SyntaxError as se:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return PreFlightCheckResult(
                allowed=False,
                violation_message=f"[PRE-FLIGHT SYNTAX VETO] SyntaxError in candidate: {se}",
                execution_time_ms=elapsed_ms,
            )

        # 3. SMT Predicate / Counterexample Block Inspection
        smt_rules = [r for r in rules if r.rule_type == "SMT_PREDICATE_BLOCK"]
        if smt_rules:
            for rule in smt_rules:
                if self._matches_smt_predicate(rule.pattern, candidate_code):
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    try:
                        self.episodic_store.increment_intercept_count(rule.rule_id)
                    except Exception as e:
                        logger.debug("Failed incrementing intercept count: %s", e)
                    return PreFlightCheckResult(
                        allowed=False,
                        violation_message=f"[PRE-FLIGHT SMT VETO] {rule.description}",
                        violated_rule=rule,
                        execution_time_ms=elapsed_ms,
                    )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        return PreFlightCheckResult(
            allowed=True,
            violation_message=None,
            violated_rule=None,
            execution_time_ms=elapsed_ms,
        )

    def _matches_smt_predicate(self, pattern: str, code: str) -> bool:
        """
        Determines whether candidate code instantiates the disproved SMT model.
        Supports condition clauses like 'x == 0 and y == 1' or assignments like 'x = 0'.
        """
        if not pattern or not pattern.strip():
            return False

        clauses = [c.strip() for c in pattern.split("and") if c.strip()]
        matches_all = True

        for clause in clauses:
            # Look for variable and target value
            m = re.match(r"(\w+)\s*(?:==|=)\s*(.+)", clause)
            if m:
                var_name = m.group(1).strip()
                val_target = m.group(2).strip()
                # Check if literal assignment or parameter exists in code
                var_assign_pat = rf"\b{re.escape(var_name)}\s*=\s*{re.escape(val_target)}\b"
                if not re.search(var_assign_pat, code):
                    matches_all = False
                    break
            else:
                if clause not in code:
                    matches_all = False
                    break

        return matches_all

    def check_negative_constraints(self, candidate_code: str) -> Tuple[bool, Optional[str]]:
        """
        Adheres to PROJECT.md § M2 contract:
        returns (is_blocked: bool, violation_message: Optional[str])
        """
        res = self.check_candidate(candidate_code)
        return (not res.allowed, res.violation_message)

    def tri_hybrid_search(
        self,
        query: str,
        limit: int = 5,
        w_vec: float = 0.40,
        w_lex: float = 0.35,
        w_boost: float = 0.25,
    ) -> List[ReflexionRecord]:
        """
        Retrieves top-ranked dead ends using tri-hybrid scoring:
        Score = w_vec * S_vec + w_lex * S_lex + w_boost * S_boost
        """
        scored_records = self.tri_hybrid_search_with_scores(
            query=query,
            limit=limit,
            w_vec=w_vec,
            w_lex=w_lex,
            w_boost=w_boost,
        )
        return [r for r, _ in scored_records]

    def tri_hybrid_search_with_scores(
        self,
        query: str,
        limit: int = 5,
        w_vec: float = 0.40,
        w_lex: float = 0.35,
        w_boost: float = 0.25,
    ) -> List[Tuple[ReflexionRecord, float]]:
        """
        Computes composite tri-hybrid rank scores across SQLite FTS5, vector cosine similarity,
        and recurrence/intercept efficacy boost.
        """
        if not query or not query.strip():
            return []

        # 1. Lexical Retrieval (FTS5 BM25)
        fts_results = self.episodic_store.fts_search(query, limit=limit * 3)
        lexical_scores: Dict[str, float] = {r.record_id: score for r, score in fts_results}
        candidate_records: Dict[str, ReflexionRecord] = {r.record_id: r for r, _ in fts_results}

        # Also load recent records for comprehensive vector evaluation
        recent_records = self.episodic_store.list_records(limit=limit * 4)
        for r in recent_records:
            if r.record_id not in candidate_records:
                candidate_records[r.record_id] = r

        if not candidate_records:
            return []

        # 2. Vector Semantic Similarity
        query_vec = self.episodic_store.compute_embedding(query)
        vector_scores: Dict[str, float] = {}

        for rid, rec in candidate_records.items():
            if rec.embedding:
                rec_vec = rec.embedding
            else:
                rec_vec = self.episodic_store.compute_embedding(f"{rec.root_cause} {rec.violated_invariant} {rec.candidate_summary}")
                rec.embedding = rec_vec

            # Cosine similarity
            sim = self._cosine_similarity(query_vec, rec_vec)
            # Map [-1, 1] to [0, 1]
            vector_scores[rid] = max(0.0, round((sim + 1.0) / 2.0, 4))

        # 3. Composite Ranking with Recurrence & Intercept Boost
        scored_list: List[Tuple[ReflexionRecord, float]] = []

        for rid, rec in candidate_records.items():
            s_lex = lexical_scores.get(rid, 0.0)
            s_vec = vector_scores.get(rid, 0.0)

            # Efficacy & Recurrence Boost
            rec_factor = min(1.0, rec.recurrence_count / 5.0)
            intercept_factor = min(1.0, rec.intercept_count / 10.0)
            s_boost = min(1.0, (rec_factor * 0.6 + intercept_factor * 0.4))

            final_score = round(w_vec * s_vec + w_lex * s_lex + w_boost * s_boost, 4)
            scored_list.append((rec, final_score))

        # Sort descending by composite score
        scored_list.sort(key=lambda x: x[1], reverse=True)
        return scored_list[:limit]

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Computes cosine similarity between two float vectors."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0

        # ⚡ Bolt Optimization: Pure Python Vector Math
        # Replacing zip() loops with math.sumprod and math.hypot(*v)
        # Yields a significant speedup by pushing iteration into C extensions in Python 3.12+
        # Fallback to map(operator.mul) for Python 3.11 and below to support CI checks
        if hasattr(math, "sumprod"):
            dot = math.sumprod(v1, v2)
        else:
            dot = sum(map(operator.mul, v1, v2))

        norm1 = math.hypot(*v1)
        norm2 = math.hypot(*v2)

        if norm1 <= 1e-9 or norm2 <= 1e-9:
            return 0.0

        return max(-1.0, min(1.0, dot / (norm1 * norm2)))


# Alias for compatibility
PreFlightFilterEngine = PreFlightFilter
