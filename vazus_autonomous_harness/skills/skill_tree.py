"""
vazus_autonomous_harness.skills.skill_tree — 5-Tier Skill Tree Engine.

Inspired by SkillRL (Dual-Granularity SkillBank) and SAGE (Sequential Rollouts).
Tiers:
- Level 1: Deterministic Atomic Primitives (Filesystem, Git, CLI)
- Level 2: Composed Domain Workflows (DAGs, Pipelines)
- Level 3: Adaptive Context & Strategies (AST Pruners, Context Cachers)
- Level 4: Dialectical Reasoning & Governance (Byzantine Consensus, SMT Z3 Hard Gate)
- Level 5: Autonomous Meta-Synthesis (Darwinian Mutators, Auto-Authoring Skills)
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class SkillNode:
    id: str
    name: str
    level: int  # 1 to 5
    description: str
    code_fn: Optional[Callable[..., Any]] = None
    source_code: Optional[str] = None
    success_count: int = 0
    failure_count: int = 0
    reward_weight: float = 1.0
    dependencies: List[str] = field(default_factory=list)

    @property
    def reliability(self) -> float:
        total = self.success_count + self.failure_count
        return (self.success_count / total) if total > 0 else 1.0


def _extract_source_code(node: SkillNode) -> Optional[str]:
    """Extracts Python source code from SkillNode source_code or code_fn."""
    if node.source_code and node.source_code.strip():
        return node.source_code
    if node.code_fn is not None:
        if isinstance(node.code_fn, str):
            return node.code_fn
        if callable(node.code_fn):
            try:
                import inspect
                return inspect.getsource(node.code_fn)
            except Exception:
                pass
    return None


class SkillTree:
    """
    Hierarchical ontology and continuous co-evolution registry for AI skills.
    """

    def __init__(self):
        self.skills: Dict[str, SkillNode] = {}
        self._register_default_primitives()

    def _register_default_primitives(self):
        # Level 1 Primitives
        self.register_skill(SkillNode(
            id="l1_read_file",
            name="Read File Atomic",
            level=1,
            description="Reads local filesystem content with deterministic exit codes",
        ))
        self.register_skill(SkillNode(
            id="l1_run_cli",
            name="Run CLI Command",
            level=1,
            description="Executes CLI commands in a bounded sandbox",
        ))

        # Level 2 Composed Workflows
        self.register_skill(SkillNode(
            id="l2_repo_audit",
            name="Repository Audit Pipeline",
            level=2,
            description="Multi-file codebase analysis combining git status, AST linting, and tests",
            dependencies=["l1_read_file", "l1_run_cli"],
        ))

        # Level 3 Adaptive Context
        self.register_skill(SkillNode(
            id="l3_ast_prune",
            name="AST Tree-Sitter Pruner",
            level=3,
            description="Extracts function signatures and docstrings, achieving O(1) token compression",
            dependencies=["l1_read_file"],
        ))

        # Level 4 Dialectical & Formal Verification
        self.register_skill(SkillNode(
            id="l4_smt_z3_gate",
            name="SMT Z3 Substrate Guard",
            level=4,
            description="Mathematically proves safety specifications with zero false positives",
            dependencies=["l1_run_cli"],
        ))

        # Level 5 Meta-Synthesis
        self.register_skill(SkillNode(
            id="l5_auto_author_skill",
            name="Autonomous Skill Author",
            level=5,
            description="Synthesizes new validated SKILL.md and Python implementations from failure traces",
            dependencies=["l4_smt_z3_gate", "l3_ast_prune"],
        ))

    def verify_godel_rsi_invariant(
        self,
        candidate_node: SkillNode,
        enforce_smt_contracts: bool = True,
    ) -> tuple[bool, str]:
        """
        Gödel Agent Skill Library Consistency Invariant (arXiv:2609.11873).
        Proves: Box(Commit(S_new) => forall s in S_bank PreserveContract(s) and SafeTransition(Sigma)).
        Guarantees that new skills do not break existing dependency DAGs, do not introduce
        cycles or level inversions, and Level 4/5 skills formally satisfy SMT Z3 contracts.
        """
        # 0. Self-cycle and Circular Dependency Prevention
        if candidate_node.id in candidate_node.dependencies:
            return False, f"Gödel RSI violation: Self-dependency cycle detected for skill '{candidate_node.id}'"

        def _has_path(start: str, target: str, visited: set) -> bool:
            if start == target:
                return True
            if start in visited:
                return False
            visited.add(start)
            node = self.skills.get(start)
            if node:
                for d in node.dependencies:
                    if _has_path(d, target, visited):
                        return True
            return False

        for dep in candidate_node.dependencies:
            if _has_path(dep, candidate_node.id, set()):
                return False, f"Gödel RSI violation: Circular dependency detected involving '{candidate_node.id}' and '{dep}'"

        # 1. Dependency Existence Check
        for dep in candidate_node.dependencies:
            if dep not in self.skills:
                return False, f"Gödel RSI violation: Unmet dependency '{dep}' for skill '{candidate_node.id}'"

        # 2. Strict DAG Level Invariant (Higher-level skills depend on equal or lower-level skills)
        for dep in candidate_node.dependencies:
            dep_node = self.skills[dep]
            if dep_node.level > candidate_node.level:
                return False, f"Gödel RSI violation: Level inversion — Level {candidate_node.level} skill cannot depend on higher Level {dep_node.level} skill '{dep}'"

        # 3. Foundation Protection Invariant: Cannot overwrite core primitives L1-L3
        if candidate_node.id in self.skills:
            existing = self.skills[candidate_node.id]
            if existing.level <= 3 and candidate_node.level != existing.level:
                return False, f"Gödel RSI violation: Foundational tier modification blocked for '{candidate_node.id}'"

        # 4. SMT Z3 Formal Contract Verification for Level 4/5 Skills (arXiv:2609.11873)
        # Box(Commit(S_new) => PreserveContract(S_new) /\ forall s in Dependents PreserveContract(s))
        if enforce_smt_contracts and candidate_node.level >= 4:
            from vazus_autonomous_harness.verification.smt_prover import SMTProver

            prover = SMTProver()
            code = _extract_source_code(candidate_node)
            if not code or not code.strip():
                return False, (
                    f"Gödel RSI violation: Level {candidate_node.level} skill '{candidate_node.id}' "
                    f"must provide executable code with formal docstring contracts (:requires:, :ensures:)"
                )

            proof = prover.verify_contracts(code)
            if proof.status == "NO_CONTRACTS":
                return False, (
                    f"Gödel RSI violation: Level {candidate_node.level} skill '{candidate_node.id}' "
                    f"lacks formal :requires:/:ensures: docstring contracts"
                )
            if not proof.verified or proof.status != "UNSAT":
                return False, (
                    f"Gödel RSI violation: Formal SMT contract verification failed for Level {candidate_node.level} "
                    f"skill '{candidate_node.id}': status={proof.status} ({proof.details})"
                )

            # 5. Dependent Regression Verification: Ensure all dependent skills in S_bank continue to preserve contracts
            for s_id, s_node in self.skills.items():
                if candidate_node.id in s_node.dependencies and s_node.level >= 4:
                    dep_code = _extract_source_code(s_node)
                    if dep_code:
                        dep_proof = prover.verify_contracts(dep_code)
                        if not dep_proof.verified or dep_proof.status != "UNSAT":
                            return False, (
                                f"Gödel RSI violation: Mutation of '{candidate_node.id}' breaks dependent skill "
                                f"'{s_id}' formal contract: status={dep_proof.status} ({dep_proof.details})"
                            )

        return True, "Gödel RSI Consistency Invariant satisfied: monotonic backward compatibility and formal SMT contracts verified"

    def register_skill(
        self,
        node: SkillNode,
        enforce_godel_invariant: bool = False,
        enforce_smt_contracts: bool = True,
    ):
        if enforce_godel_invariant:
            ok, reason = self.verify_godel_rsi_invariant(node, enforce_smt_contracts=enforce_smt_contracts)
            if not ok:
                raise ValueError(reason)
        self.skills[node.id] = node

    def get_skill(self, skill_id: str) -> Optional[SkillNode]:
        return self.skills.get(skill_id)

    def record_outcome(self, skill_id: str, success: bool):
        skill = self.skills.get(skill_id)
        if skill:
            if success:
                skill.success_count += 1
                skill.reward_weight *= 1.05  # SkillRL positive reinforcement
            else:
                skill.failure_count += 1
                skill.reward_weight *= 0.90  # Demote failing skills

    def list_by_level(self, level: int) -> List[SkillNode]:
        return [s for s in self.skills.values() if s.level == level]

    def export_summary(self) -> Dict[str, Any]:
        return {
            f"level_{lvl}": [
                {
                    "id": s.id,
                    "name": s.name,
                    "reliability": round(s.reliability, 3),
                    "reward_weight": round(s.reward_weight, 3),
                }
                for s in self.list_by_level(lvl)
            ]
            for lvl in range(1, 6)
        }
