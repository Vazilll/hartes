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
import time


@dataclass
class SkillNode:
    id: str
    name: str
    level: int  # 1 to 5
    description: str
    code_fn: Optional[Callable[..., Any]] = None
    success_count: int = 0
    failure_count: int = 0
    reward_weight: float = 1.0
    dependencies: List[str] = field(default_factory=list)

    @property
    def reliability(self) -> float:
        total = self.success_count + self.failure_count
        return (self.success_count / total) if total > 0 else 1.0


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

    def register_skill(self, node: SkillNode):
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
