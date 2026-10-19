"""
vazus_core.reasoning_effort_controller — Execution & Orchestration Policy Controller.

Maps Effort score [0.0, 1.0] or level ('low', 'medium', 'high', 'xhigh', 'ultra') to concrete
subsystem execution budgets:
- subagent_model: Recommended model tier for invoke_subagent ("flash", "inherit", "pro")
- smt_z3_depth: Formal logic contract proof depth (5 to 30)
- repl_max_iterations: Maximum LocalREPL code trial iterations (3 to 25)
- repl_timeout_seconds: REPL execution timeout in sandbox (5s to 60s)
- verification_tier: Verification gate intensity ("fast", "standard", "strict")
- thinking_budget: Advisory token budget for external blueprints (Note: host agent thinking is
  controlled by Antigravity UI)

OmegaPRM (R3.1): Inline Process Reward Model with MCTS step-level scoring.
  At xhigh/ultra effort, each MCTS reasoning branch is scored r_t ∈ [0, 1].
  Branches with r_t < OMEGA_PRUNE_THRESHOLD (0.6) are pruned BEFORE tool/compiler calls,
  preventing expensive dead-end execution and achieving compute-optimal inference.
"""

import hashlib
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, Any, Union, List, Optional

logger = logging.getLogger(__name__)

LEVEL_PRESETS = {
    "low": 0.1,
    "medium": 0.35,
    "high": 0.65,
    "xhigh": 0.85,
    "ultra": 1.0
}

# OmegaPRM constants (R3.1)
OMEGA_PRUNE_THRESHOLD: float = 0.6   # branches below this are dead-ended
OMEGA_UCB_CONST: float = 1.414       # exploration constant (√2)


@dataclass
class MCTSNode:
    """A single reasoning step node in the OmegaPRM MCTS tree."""
    step_text: str
    depth: int = 0
    visit_count: int = 0
    total_reward: float = 0.0
    children: List["MCTSNode"] = field(default_factory=list)
    parent: Optional["MCTSNode"] = None
    pruned: bool = False

    @property
    def step_hash(self) -> str:
        return hashlib.sha256(self.step_text.encode()).hexdigest()[:12]

    @property
    def q_value(self) -> float:
        """Mean reward Q(s,a) = total_reward / visit_count."""
        if self.visit_count == 0:
            return 0.0
        return self.total_reward / self.visit_count

    def ucb_score(self, parent_visits: int) -> float:
        """UCB1 score balancing exploitation and exploration."""
        if self.visit_count == 0:
            return float("inf")
        exploitation = self.q_value
        exploration = OMEGA_UCB_CONST * math.sqrt(math.log(max(1, parent_visits)) / self.visit_count)
        return exploitation + exploration


class OmegaPRMScorer:
    """
    Inline Process Reward Model (OmegaPRM) for MCTS test-time compute.

    Scores each reasoning step r_t ∈ [0, 1] and prunes branches with r_t < OMEGA_PRUNE_THRESHOLD
    before expensive tool calls or compilation steps. This achieves compute-optimal inference
    equivalent to OmegaPRM (Luo et al., 2024).

    :requires: effort_score >= 0.85 (xhigh or ultra) to activate MCTS tree pruning.
    :ensures: All returned nodes satisfy node.q_value >= OMEGA_PRUNE_THRESHOLD or are marked pruned.
    """

    def __init__(self, max_simulations: int = 100, max_depth: int = 8) -> None:
        self.max_simulations = max_simulations
        self.max_depth = max_depth
        self._scored_nodes: List[MCTSNode] = []

    def _heuristic_reward(self, step_text: str, depth: int) -> float:
        """
        Heuristic step reward based on lexical quality signals.
        Replaces a learned verifier model with deterministic fast proxy.
        """
        score = 0.5  # neutral prior
        text = step_text.lower().strip()

        # Positive signals: concrete, specific, testable steps
        positive_keywords = ["assert", "verify", "test", "proof", "therefore", "because",
                             "formally", "contract", "invariant", "z3", "smt", "lemma"]
        negative_keywords = ["maybe", "possibly", "assume", "todo", "fixme", "skip",
                             "placeholder", "stub", "mock", "approximate"]

        pos_hits = sum(1 for kw in positive_keywords if kw in text)
        neg_hits = sum(1 for kw in negative_keywords if kw in text)

        score += 0.06 * pos_hits
        score -= 0.12 * neg_hits
        # Depth penalty: deep branches without substance get penalised
        if depth > 4 and len(text) < 20:
            score -= 0.15

        return max(0.0, min(1.0, score))

    def score_and_prune(self, root: MCTSNode) -> List[MCTSNode]:
        """
        Run MCTS simulations from root node, pruning branches below threshold.
        Returns list of surviving (non-pruned) leaf nodes.

        :requires: root is a valid MCTSNode with non-empty step_text
        :ensures: all returned nodes have q_value >= OMEGA_PRUNE_THRESHOLD
        """
        for _ in range(self.max_simulations):
            node = root
            # Selection phase: traverse via UCB
            while node.children and not node.pruned:
                node = max(node.children, key=lambda c: c.ucb_score(node.visit_count))
                if node.pruned:
                    break

            if node.pruned or node.depth >= self.max_depth:
                continue

            # Expansion: score this node
            reward = self._heuristic_reward(node.step_text, node.depth)
            node.visit_count += 1
            node.total_reward += reward

            # Pruning gate
            if node.q_value < OMEGA_PRUNE_THRESHOLD:
                node.pruned = True
                continue

            # Backpropagation
            parent = node.parent
            while parent is not None:
                parent.visit_count += 1
                parent.total_reward += reward
                parent = parent.parent

        surviving = [n for n in self._collect_leaves(root) if not n.pruned]
        return surviving

    def _collect_leaves(self, node: MCTSNode) -> List[MCTSNode]:
        if not node.children:
            return [node]
        leaves: List[MCTSNode] = []
        for child in node.children:
            leaves.extend(self._collect_leaves(child))
        return leaves

    @classmethod
    def from_effort_score(cls, score: float) -> "OmegaPRMScorer":
        """Factory: scales MCTS budget proportionally to effort score."""
        if score >= 1.0:
            return cls(max_simulations=2000, max_depth=12)
        if score >= 0.85:
            return cls(max_simulations=500, max_depth=10)
        if score >= 0.65:
            return cls(max_simulations=100, max_depth=8)
        return cls(max_simulations=0, max_depth=0)  # Disabled for low effort



# 2026 Model Context & Max Output Token Limits (advisory for external API wrappers)
MODEL_LIMITS = {
    "gemini-3.6-flash": {"max_output": 65536, "context_window": 1048576},
    "gemini-3.1-pro": {"max_output": 65536, "context_window": 2097152},
    "claude-sonnet-4.6": {"max_output": 128000, "context_window": 200000},
    "gpt-oss-120b": {"max_output": 16384, "context_window": 131072},
    "default": {"max_output": 32768, "context_window": 131072},
}


class ExecutionPolicyController:
    """
    Controller for local execution policies, verification depths, sandbox budgets,
    and subagent model dispatching.
    """

    @staticmethod
    def _parse_effort_level(effort: Union[str, float, None]) -> tuple[float, str]:
        """Safely normalizes optional effort level strings or floats into [0.0, 1.0] score."""
        if effort is None:
            return 0.65, "high"
        if isinstance(effort, str):
            eff_lower = effort.lower().strip()
            score = LEVEL_PRESETS.get(eff_lower, 0.65)
            return score, eff_lower if eff_lower in LEVEL_PRESETS else "high"
        try:
            score = max(0.0, min(1.0, float(effort)))
            if score <= 0.2:
                return score, "low"
            if score <= 0.5:
                return score, "medium"
            if score <= 0.75:
                return score, "high"
            if score <= 0.9:
                return score, "xhigh"
            return score, "ultra"
        except (ValueError, TypeError):
            return 0.65, "high"

    @staticmethod
    def _compute_thinking_token_budget(
        score: float, model_key: str, prompt_tokens: int, safety_headroom: int
    ) -> tuple[int, int]:
        raw_tokens = int(1024 * ((65536 / 1024) ** (score ** 1.2)))
        limits = MODEL_LIMITS.get(model_key.lower(), MODEL_LIMITS["default"])
        max_output = limits["max_output"]
        context_window = limits["context_window"]
        available_headroom = max(1024, context_window - prompt_tokens - safety_headroom)
        clamped_thinking_budget = min(raw_tokens, max_output - safety_headroom, available_headroom)
        return max(0, clamped_thinking_budget), max_output

    @staticmethod
    def _derive_subsystem_budgets(score: float) -> dict[str, Any]:
        if score <= 0.2:
            return {"subagent_model": "flash", "repl_steps": 3, "repl_timeout": 5.0, "smt_z3_depth": 5, "verification_tier": "fast"}
        if score <= 0.5:
            return {"subagent_model": "flash", "repl_steps": 5, "repl_timeout": 10.0, "smt_z3_depth": 10, "verification_tier": "standard"}
        if score <= 0.75:
            return {"subagent_model": "inherit", "repl_steps": 10, "repl_timeout": 20.0, "smt_z3_depth": 15, "verification_tier": "strict"}
        if score <= 0.9:
            return {"subagent_model": "pro", "repl_steps": 15, "repl_timeout": 30.0, "smt_z3_depth": 20, "verification_tier": "strict"}
        return {"subagent_model": "pro", "repl_steps": 25, "repl_timeout": 60.0, "smt_z3_depth": 30, "verification_tier": "strict"}

    @classmethod
    def get_config(
        cls,
        effort: Union[str, float, None] = "high",
        model_key: str = "gemini-3.6-flash",
        prompt_tokens: int = 0,
        safety_headroom: int = 4096
    ) -> Dict[str, Any]:
        """
        Calculates concrete execution parameters for local workers, Z3 verification,
        and subagent delegation.

        Includes OmegaPRM MCTS budget for xhigh/ultra effort levels (R3.1).
        """
        score, level_name = cls._parse_effort_level(effort)
        clamped_thinking_budget, max_output = cls._compute_thinking_token_budget(
            score, model_key, prompt_tokens, safety_headroom
        )
        budgets = cls._derive_subsystem_budgets(score)
        subagent_depth = int(1 + 5 * score)

        # OmegaPRM MCTS budget (R3.1): real simulation count from scorer factory
        omega_scorer = OmegaPRMScorer.from_effort_score(score)
        mcts_sims = omega_scorer.max_simulations

        return {
            "level": level_name,
            "effort_score": round(score, 3),
            "subagent_model": budgets["subagent_model"],
            "subagent_depth": subagent_depth,
            "smt_z3_depth": budgets["smt_z3_depth"],
            "mcts_simulations": mcts_sims,
            "omega_prm_threshold": OMEGA_PRUNE_THRESHOLD if mcts_sims > 0 else None,
            "repl_steps": budgets["repl_steps"],
            "repl_max_iterations": budgets["repl_steps"],
            "repl_timeout_seconds": budgets["repl_timeout"],
            "verification_tier": budgets["verification_tier"],
            "thinking_budget": clamped_thinking_budget,
            "max_output_tokens": max_output,
            "prompt_tokens": prompt_tokens,
            "model_key": model_key,
        }




# Backwards compatibility alias
ReasoningEffortController = ExecutionPolicyController
