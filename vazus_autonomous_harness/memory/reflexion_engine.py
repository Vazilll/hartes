"""
vazus_autonomous_harness.memory.reflexion_engine — Continuous Reflexion Generator & Memory Engine.

Milestone 2 (F5):
- Structured error-to-insight generator producing ReflexionRecord with:
  * root_cause: diagnostic explanation of the flaw
  * violated_invariant: formal contract or domain policy broken (including USER.md#L37)
  * negative_rules: executable negative constraint rules (AST, REGEX, SMT)
  * smt_counterexample: exact variable assignment model from Z3
  * fitness_score: historical score or penalty
- Implements ReflexionMemoryStore interface contract from PROJECT.md § M2:
  * record_failure(record: ReflexionRecord) -> None
  * retrieve_similar_dead_ends(task_description: str, limit: int = 5) -> List[ReflexionRecord]
  * check_negative_constraints(candidate_code: str) -> tuple[bool, Optional[str]]
"""

import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("vazus.harness.memory.reflexion")


@dataclass
class ExecutableNegativeConstraint:
    """
    Executable negative constraint rule for pre-flight filtering (F7).
    Rule types: 'AST_PATTERN_DENY', 'REGEX_DENY', 'SMT_PREDICATE_BLOCK'
    """
    rule_id: str
    rule_type: str  # 'AST_PATTERN_DENY', 'REGEX_DENY', 'SMT_PREDICATE_BLOCK'
    pattern: str
    description: str
    target_scope: str = "code"  # 'code', 'function_body', 'imports', 'prompt'
    is_hard_block: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutableNegativeConstraint":
        return cls(
            rule_id=data.get("rule_id", f"neg_{uuid.uuid4().hex[:8]}"),
            rule_type=data.get("rule_type", "REGEX_DENY"),
            pattern=data.get("pattern", ""),
            description=data.get("description", ""),
            target_scope=data.get("target_scope", "code"),
            is_hard_block=data.get("is_hard_block", True),
        )


@dataclass
class ReflexionRecord:
    """
    Structured episodic failure retrospective adhering to PROJECT.md § M2 contract.
    """
    record_id: str
    timestamp: float
    task_id: str
    candidate_summary: str
    root_cause: str
    violated_invariant: str
    negative_rules: List[ExecutableNegativeConstraint]
    smt_counterexample: Optional[Dict[str, Any]] = None
    fitness_score: float = 0.0

    # Extended metadata for SQLite SSOT and Wiki synchronization
    category: str = "general_failure"
    remediation_hint: str = ""
    recurrence_count: int = 1
    intercept_count: int = 0
    resolved: bool = False
    dedup_hash: Optional[str] = None
    wiki_relpath: Optional[str] = None
    embedding: Optional[List[float]] = None

    def __post_init__(self):
        if not self.dedup_hash:
            self.dedup_hash = self.compute_dedup_hash()
        if not self.remediation_hint and self.root_cause:
            self.remediation_hint = f"Fix for: {self.root_cause[:120]}"

    def compute_dedup_hash(self) -> str:
        """Computes deterministic SHA256 deduplication fingerprint."""
        rule_patterns = "-".join(r.pattern.strip() for r in self.negative_rules)
        payload = f"{self.task_id.strip()}|{self.violated_invariant.strip()}|{self.root_cause.strip()}|{rule_patterns}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "candidate_summary": self.candidate_summary,
            "root_cause": self.root_cause,
            "violated_invariant": self.violated_invariant,
            "negative_rules": [r.to_dict() for r in self.negative_rules],
            "smt_counterexample": self.smt_counterexample,
            "fitness_score": self.fitness_score,
            "category": self.category,
            "remediation_hint": self.remediation_hint,
            "recurrence_count": self.recurrence_count,
            "intercept_count": self.intercept_count,
            "resolved": self.resolved,
            "dedup_hash": self.dedup_hash,
            "wiki_relpath": self.wiki_relpath,
            "embedding": self.embedding,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReflexionRecord":
        raw_rules = data.get("negative_rules", [])
        parsed_rules = []
        for r in raw_rules:
            if isinstance(r, ExecutableNegativeConstraint):
                parsed_rules.append(r)
            elif isinstance(r, dict):
                parsed_rules.append(ExecutableNegativeConstraint.from_dict(r))

        return cls(
            record_id=data["record_id"],
            timestamp=float(data.get("timestamp", time.time())),
            task_id=data.get("task_id", "default_task"),
            candidate_summary=data.get("candidate_summary", ""),
            root_cause=data.get("root_cause", ""),
            violated_invariant=data.get("violated_invariant", ""),
            negative_rules=parsed_rules,
            smt_counterexample=data.get("smt_counterexample"),
            fitness_score=float(data.get("fitness_score", 0.0)),
            category=data.get("category", "general_failure"),
            remediation_hint=data.get("remediation_hint", ""),
            recurrence_count=int(data.get("recurrence_count", 1)),
            intercept_count=int(data.get("intercept_count", 0)),
            resolved=bool(data.get("resolved", False)),
            dedup_hash=data.get("dedup_hash"),
            wiki_relpath=data.get("wiki_relpath"),
            embedding=data.get("embedding"),
        )


class ContinuousReflexionGenerator:
    """
    F5 Continuous Reflexion Generator.
    Analyzes failed candidate code, quality evaluations, SMT disproofs, test errors,
    or academic sovereignty leaks, synthesizing machine-actionable ReflexionRecord instances.
    """

    def generate_record(
        self,
        task_id: str,
        candidate_code: str,
        root_cause: str,
        violated_invariant: str,
        negative_rules: List[ExecutableNegativeConstraint],
        smt_counterexample: Optional[Dict[str, Any]] = None,
        fitness_score: float = 0.0,
        category: str = "general_failure",
        remediation_hint: str = "",
    ) -> ReflexionRecord:
        """Core factory producing structured ReflexionRecord."""
        record_id = f"refl_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        summary = self._summarize_code(candidate_code)

        return ReflexionRecord(
            record_id=record_id,
            timestamp=time.time(),
            task_id=task_id,
            candidate_summary=summary,
            root_cause=root_cause,
            violated_invariant=violated_invariant,
            negative_rules=negative_rules,
            smt_counterexample=smt_counterexample,
            fitness_score=fitness_score,
            category=category,
            remediation_hint=remediation_hint,
        )

    def from_quality_score(
        self,
        task_id: str,
        candidate_code: str,
        score: Any,
        baseline_code: str = "",
        context_prompt: str = "",
    ) -> ReflexionRecord:
        """
        Synthesizes a ReflexionRecord from an M1 QualityScore.
        Extracts counterexamples, sovereignty leaks, AST bloat, and illicit mocks.
        """
        violation_reasons = getattr(score, "violation_reasons", []) or []
        counterexample = getattr(score, "counterexample", None)
        total_score = getattr(score, "total_score", 0.0)

        rules: List[ExecutableNegativeConstraint] = []
        root_causes: List[str] = []
        violated_invariants: List[str] = []
        category = "quality_evaluation_failure"
        remediation_hints: List[str] = []

        # 1. SMT Formal Verification Disproof
        if counterexample or getattr(score, "correctness_smt", 0.0) < 40.0:
            category = "smt_contract_violation"
            cex_str = json.dumps(counterexample) if counterexample else "unknown model"
            root_causes.append(f"Formal SMT contract disproven by Z3 solver. Counterexample model: {cex_str}")
            violated_invariants.append("∀x ∈ Inputs: Contract(Pre(x) → Post(x))")
            remediation_hints.append("Ensure candidate preserves formal invariants across domain edge boundaries.")

            pattern_parts = []
            if counterexample and isinstance(counterexample, dict):
                for var, val in counterexample.items():
                    pattern_parts.append(f"{var} == {val}")
                smt_pat = " and ".join(pattern_parts) if pattern_parts else "smt_counterexample_model"
            else:
                smt_pat = "smt_disproved_model"

            rules.append(
                ExecutableNegativeConstraint(
                    rule_id=f"neg_smt_{uuid.uuid4().hex[:6]}",
                    rule_type="SMT_PREDICATE_BLOCK",
                    pattern=smt_pat,
                    description=f"Prohibit candidate parameter combinations matching SMT counterexample: {cex_str}",
                    target_scope="code",
                )
            )

        # 2. Academic Sovereignty / Socratic Policy (USER.md#L37)
        if getattr(score, "academic_sovereignty", 15.0) < 15.0 or any("sovereignty" in r.lower() or "socratic" in r.lower() or "stub" in r.lower() for r in violation_reasons):
            category = "academic_sovereignty_leak"
            # Check for stubs vs direct solution dumps
            has_stub = any("stub" in r.lower() or "facade" in r.lower() for r in violation_reasons)
            if has_stub:
                root_causes.append("Empty facade / stub implementation detected (USER.md#L33 violation).")
                violated_invariants.append("USER.md#L33: Zero dummy stubs, pass, or ellipsis in concrete code.")
                remediation_hints.append("Implement genuine functional logic instead of empty stubs or NotImplementedError.")
                rules.append(
                    ExecutableNegativeConstraint(
                        rule_id=f"neg_stub_{uuid.uuid4().hex[:6]}",
                        rule_type="AST_PATTERN_DENY",
                        pattern="ast.Pass|ast.Constant(Ellipsis)|NotImplementedError",
                        description="Veto empty stubs, ellipsis placeholders, and unhandled NotImplementedError bodies.",
                        target_scope="function_body",
                    )
                )
            else:
                root_causes.append("Direct academic solution dump detected in academic task (USER.md#L37 violation).")
                violated_invariants.append("USER.md#L37: Student pedagogical sovereignty prohibits solving coursework/tests for user.")
                remediation_hints.append("Reformulate response into Socratic guiding questions and conceptual explanations.")
                rules.append(
                    ExecutableNegativeConstraint(
                        rule_id=f"neg_sov_{uuid.uuid4().hex[:6]}",
                        rule_type="REGEX_DENY",
                        pattern=r"(?i)(?:готовое\s+решение|вот\s+готовый\s+код|спиши\s+это|ответ\s*[:=]\s*[a-d1-4])",
                        description="Block direct academic solution dumps; demand Socratic tutoring.",
                        target_scope="code",
                    )
                )

        # 3. Empirical Test Integrity (Mocks / Assertion failures)
        if getattr(score, "empirical_integrity", 30.0) < 30.0 or any("mock" in r.lower() for r in violation_reasons):
            if any("mock" in r.lower() for r in violation_reasons):
                root_causes.append("Illicit mock detected: mocking core components violates empirical integrity.")
                violated_invariants.append("Empirical integrity requires genuine execution without synthetic mocks.")
                remediation_hints.append("Use genuine production logic; do not substitute mocks.")
                rules.append(
                    ExecutableNegativeConstraint(
                        rule_id=f"neg_mock_{uuid.uuid4().hex[:6]}",
                        rule_type="REGEX_DENY",
                        pattern=r"(?i)\b(?:from\s+unittest\.mock|import\s+mock|unittest\.mock|MagicMock)\b",
                        description="Prohibit synthetic mocks in core components.",
                        target_scope="imports",
                    )
                )
            else:
                root_causes.append("Empirical test failure: candidate failed assertion or test suite execution.")
                violated_invariants.append("Empirical integrity: all unit and property tests must pass.")
                remediation_hints.append("Inspect failed assertion details and resolve boundary test cases.")

        # 4. AST Bloat & Parsimony
        bloat_ratio = getattr(score, "ast_bloat_ratio", 0.0)
        if bloat_ratio > 0.50:
            root_causes.append(f"Excessive AST bloat detected (+{round(bloat_ratio * 100, 1)}% node increase).")
            violated_invariants.append("Parsimony: candidate diffs must remain concise without unnecessary AST expansion.")
            remediation_hints.append("Refactor candidate code into a more parsimonious implementation.")

        # Fallback if no specific rule generated
        if not rules:
            summary_err = "; ".join(violation_reasons) if violation_reasons else "Quality score below admission threshold"
            root_causes.append(summary_err)
            violated_invariants.append("Quality score must be >= 75.0 points with zero hard vetoes.")
            rules.append(
                ExecutableNegativeConstraint(
                    rule_id=f"neg_gen_{uuid.uuid4().hex[:6]}",
                    rule_type="REGEX_DENY",
                    pattern=re.escape(candidate_code.strip()[:60]),
                    description="Veto repetition of exact failing code snippet.",
                    target_scope="code",
                )
            )

        combined_root_cause = " | ".join(root_causes) if root_causes else "Candidate failed quality evaluation."
        combined_invariant = " | ".join(violated_invariants) if violated_invariants else "Quality standard invariant."
        combined_hint = " | ".join(remediation_hints) if remediation_hints else "Review error feedback and remediate."

        return self.generate_record(
            task_id=task_id,
            candidate_code=candidate_code,
            root_cause=combined_root_cause,
            violated_invariant=combined_invariant,
            negative_rules=rules,
            smt_counterexample=counterexample,
            fitness_score=total_score,
            category=category,
            remediation_hint=combined_hint,
        )

    def from_smt_disproof(
        self,
        task_id: str,
        candidate_code: str,
        contract_name: str,
        counterexample: Dict[str, Any],
        details: str = "",
    ) -> ReflexionRecord:
        """Synthesizes a ReflexionRecord directly from an SMT disproof result."""
        cex_str = json.dumps(counterexample)
        root_cause = f"SMT disproof on contract '{contract_name}': {details}. Counterexample model: {cex_str}"
        violated_invariant = f"Formal contract '{contract_name}' postcondition holds ∀ inputs."
        remediation_hint = f"Fix boundary handling for model assignment: {cex_str}"

        rules = [
            ExecutableNegativeConstraint(
                rule_id=f"neg_smt_{uuid.uuid4().hex[:6]}",
                rule_type="SMT_PREDICATE_BLOCK",
                pattern=" and ".join(f"{k} == {v}" for k, v in counterexample.items()),
                description=f"Counterexample block: {cex_str}",
            )
        ]

        return self.generate_record(
            task_id=task_id,
            candidate_code=candidate_code,
            root_cause=root_cause,
            violated_invariant=violated_invariant,
            negative_rules=rules,
            smt_counterexample=counterexample,
            fitness_score=0.0,
            category="smt_contract_violation",
            remediation_hint=remediation_hint,
        )

    def from_test_failure(
        self,
        task_id: str,
        candidate_code: str,
        error_message: str,
        test_name: str = "",
    ) -> ReflexionRecord:
        """Synthesizes a ReflexionRecord from test execution or assertion breakdown."""
        test_lbl = f" in '{test_name}'" if test_name else ""
        root_cause = f"Empirical test failure{test_lbl}: {error_message.strip()[:200]}"
        violated_invariant = "Empirical test assertion integrity: 100% test pass rate required."
        remediation_hint = "Address assertion discrepancies revealed by test run."

        # Extract offending identifiers or patterns
        neg_rule = ExecutableNegativeConstraint(
            rule_id=f"neg_test_{uuid.uuid4().hex[:6]}",
            rule_type="REGEX_DENY",
            pattern=re.escape(error_message.strip()[:40]),
            description=f"Avoid recurring error pattern: {error_message.strip()[:60]}",
        )

        return self.generate_record(
            task_id=task_id,
            candidate_code=candidate_code,
            root_cause=root_cause,
            violated_invariant=violated_invariant,
            negative_rules=[neg_rule],
            fitness_score=0.0,
            category="test_assertion_failure",
            remediation_hint=remediation_hint,
        )

    def from_exception(
        self,
        task_id: str,
        candidate_code: str,
        exc: Exception,
        traceback_str: str = "",
    ) -> ReflexionRecord:
        """Synthesizes a ReflexionRecord from an unhandled exception or syntax error."""
        exc_type = type(exc).__name__
        root_cause = f"Unhandled {exc_type}: {exc}"
        violated_invariant = "Code must be syntactically valid and execute without fatal runtime crashes."
        remediation_hint = f"Fix {exc_type} exception at runtime."

        neg_rule = ExecutableNegativeConstraint(
            rule_id=f"neg_exc_{uuid.uuid4().hex[:6]}",
            rule_type="REGEX_DENY",
            pattern=re.escape(str(exc)[:50]) if str(exc) else exc_type,
            description=f"Prevent recurrence of fatal exception {exc_type}",
        )

        return self.generate_record(
            task_id=task_id,
            candidate_code=candidate_code,
            root_cause=root_cause,
            violated_invariant=violated_invariant,
            negative_rules=[neg_rule],
            fitness_score=0.0,
            category="runtime_exception",
            remediation_hint=remediation_hint,
        )

    def from_titans_surprise(
        self,
        task_id: str,
        surprise_loss: float,
        threshold: float = 25.0,
        context: str = "",
        candidate_code: str = "",
        key_vector: Optional[Any] = None,
        value_vector: Optional[Any] = None,
    ) -> Optional[ReflexionRecord]:
        """
        Titans surprise-gated retrospective generation (arXiv:2501.00663).
        If surprise_loss (||x̂_t - x_t||^2) exceeds the given threshold,
        generates and returns a structured ReflexionRecord capturing the epistemic anomaly.
        If surprise_loss <= threshold, returns None (no retrospective needed).
        """
        if surprise_loss <= threshold:
            return None

        root_cause = (
            f"Epistemic anomaly detected by Titans Neural Memory: "
            f"surprise loss {surprise_loss:.4f} exceeded threshold {threshold:.4f}."
        )
        if context:
            root_cause += f" Context: {context.strip()[:150]}"

        violated_invariant = (
            "Titans Epistemic Continuity Invariant: test-time surprise loss "
            f"L_surprise <= {threshold:.2f}."
        )

        remediation_hint = (
            "Re-calibrate associative memory weights via test-time adaptation "
            "or explore alternative solution paths."
        )

        rules: List[ExecutableNegativeConstraint] = []
        if candidate_code and candidate_code.strip():
            rules.append(
                ExecutableNegativeConstraint(
                    rule_id=f"neg_titans_{uuid.uuid4().hex[:6]}",
                    rule_type="REGEX_DENY",
                    pattern=re.escape(candidate_code.strip()[:50]),
                    description=f"Block high-surprise anomaly pattern (loss={surprise_loss:.2f})",
                    target_scope="code",
                )
            )

        return self.generate_record(
            task_id=task_id,
            candidate_code=candidate_code,
            root_cause=root_cause,
            violated_invariant=violated_invariant,
            negative_rules=rules,
            fitness_score=max(0.0, 100.0 - float(surprise_loss)),
            category="titans_surprise_anomaly",
            remediation_hint=remediation_hint,
        )

    def _summarize_code(self, code: str, max_lines: int = 4) -> str:
        """Extracts brief signature/summary lines from candidate code."""
        if not code or not code.strip():
            return "empty code"
        lines = [line.strip() for line in code.strip().splitlines() if line.strip()]
        return " // ".join(lines[:max_lines])[:200]


# Alias for compatibility
ReflexionGenerator = ContinuousReflexionGenerator


class ReflexionMemoryStore:
    """
    Unified Façade adhering to PROJECT.md § M2 interface contract:
    - record_failure(record: ReflexionRecord) -> None
    - retrieve_similar_dead_ends(task_description: str, limit: int = 5) -> List[ReflexionRecord]
    - check_negative_constraints(candidate_code: str) -> tuple[bool, Optional[str]]
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        wiki_root: Optional[Union[str, Path]] = None,
        wiki_dir: Optional[Union[str, Path]] = None,
    ):
        from vazus_autonomous_harness.memory.episodic_store import EpisodicMemoryStore
        from vazus_autonomous_harness.memory.preflight_filter import PreFlightFilter

        target_wiki = wiki_root if wiki_root is not None else wiki_dir
        self.wiki_root = Path(target_wiki) if target_wiki else None
        self.wiki_dir = self.wiki_root
        self.db_path = db_path
        self.episodic_store = EpisodicMemoryStore(db_path=db_path, wiki_root=self.wiki_root)
        self.preflight_filter = PreFlightFilter(episodic_store=self.episodic_store)

    def close(self) -> None:
        """Closes underlying episodic store."""
        if hasattr(self, "episodic_store"):
            self.episodic_store.close()

    def record_failure(self, record: ReflexionRecord) -> None:
        """
        Records failure episode into SQLite SSOT, syncs to Markdown Wiki,
        and refreshes the pre-flight filter negative constraint cache.
        """
        self.episodic_store.insert_record(record)
        self.preflight_filter.reload_rules()

    def retrieve_similar_dead_ends(self, task_description: str, limit: int = 5) -> List[ReflexionRecord]:
        """
        Retrieves top-ranked historical dead-ends matching task description
        using tri-hybrid ranking (FTS5 BM25 + vector similarity + recurrence boost).
        """
        return self.preflight_filter.tri_hybrid_search(task_description, limit=limit)

    def check_negative_constraints(self, candidate_code: str) -> Tuple[bool, Optional[str]]:
        """
        Pre-execution hard-gate evaluating candidate code in < 5 ms.
        Returns: (is_blocked: bool, violation_message: Optional[str])
        """
        check_res = self.preflight_filter.check_candidate(candidate_code)
        is_blocked = not check_res.allowed
        return (is_blocked, check_res.violation_message)

    def check_and_record_titans_surprise(
        self,
        task_id: str,
        surprise_loss: float,
        threshold: float = 25.0,
        context: str = "",
        candidate_code: str = "",
    ) -> Optional[ReflexionRecord]:
        """
        Surprise-gated episodic recording:
        If surprise_loss > threshold, synthesizes ReflexionRecord, persists to SQLite SSOT & Wiki,
        reloads negative constraint filter, and returns the record.
        Otherwise returns None.
        """
        generator = ContinuousReflexionGenerator()
        record = generator.from_titans_surprise(
            task_id=task_id,
            surprise_loss=surprise_loss,
            threshold=threshold,
            context=context,
            candidate_code=candidate_code,
        )
        if record:
            self.record_failure(record)
        return record
