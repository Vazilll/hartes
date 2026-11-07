"""
vazus_autonomous_harness.flywheel.funsearch_engine — DeepMind FunSearch Evolutionary Discovery Core.

Inspired by Google DeepMind (Nature 2023, Romera-Paredes et al.):
"Mathematical discoveries from program search with large language models".

Components:
1. ProgramsDatabase: Multi-island genetic algorithm memory preventing premature convergence.
2. SMT Z3 Hard Gate: SubstrateGuard formally validates candidate ASTs before evaluation.
3. Evolutionary Loop: Cluster-based sampling -> Mutation -> Formal Filter -> Execution -> Reward Shaping.
"""

import math
import random
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

from vazus_autonomous_harness.skills.substrate_guard import SubstrateGuard

logger = logging.getLogger("vazus.funsearch")


@dataclass
class ProgramNode:
    id: str
    code: str
    score: float  # Higher is better
    generation: int
    island_id: int
    execution_time_ms: float = 0.0
    z3_verified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class Island:
    """An isolated evolutionary population cluster."""
    def __init__(self, island_id: int, capacity: int = 20):
        self.island_id = island_id
        self.capacity = capacity
        self.programs: List[ProgramNode] = []

    def add_program(self, prog: ProgramNode):
        self.programs.append(prog)
        self.programs.sort(key=lambda p: p.score, reverse=True)
        if len(self.programs) > self.capacity:
            self.programs = self.programs[:self.capacity]

    def sample_best(self) -> Optional[ProgramNode]:
        if not self.programs:
            return None
        # Softmax-style exponential ranking bias toward top performers
        weights = [math.exp((len(self.programs) - i) / 5.0) for i in range(len(self.programs))]
        total = sum(weights)
        probs = [w / total for w in weights]
        return random.choices(self.programs, weights=probs, k=1)[0]


class ProgramsDatabase:
    """
    Maintains multiple parallel islands to preserve algorithm diversity
    and support periodic inter-island migration.
    """
    def __init__(self, num_islands: int = 4, capacity_per_island: int = 15):
        self.num_islands = num_islands
        self.islands = [Island(i, capacity=capacity_per_island) for i in range(num_islands)]
        self.total_evaluations = 0

    def add_program(self, prog: ProgramNode):
        self.islands[prog.island_id].add_program(prog)
        self.total_evaluations += 1

    def sample_island(self) -> int:
        return random.randint(0, self.num_islands - 1)

    def get_best_overall(self) -> Optional[ProgramNode]:
        all_progs = [p for isl in self.islands for p in isl.programs]
        if not all_progs:
            return None
        return max(all_progs, key=lambda p: p.score)

    def migrate(self):
        """Cross-pollinate top programs between adjacent islands."""
        for i in range(self.num_islands):
            best = self.islands[i].sample_best()
            if best:
                dest_id = (i + 1) % self.num_islands
                copy_prog = ProgramNode(
                    id=f"{best.id}_migr_{dest_id}",
                    code=best.code,
                    score=best.score,
                    generation=best.generation,
                    island_id=dest_id,
                    execution_time_ms=best.execution_time_ms,
                    z3_verified=best.z3_verified,
                    metadata={"migrated_from": i}
                )
                self.islands[dest_id].add_program(copy_prog)


class FunSearchEngine:
    """
    Autonomous evolutionary engine that pairs SMT Z3 formal verification
    with LLM program mutations to iteratively discover optimal heuristics.
    """
    def __init__(self, num_islands: int = 4):
        self.db = ProgramsDatabase(num_islands=num_islands)
        self.guard = SubstrateGuard()

    def register_seed(self, code: str, initial_score: float = 1.0):
        for i in range(self.db.num_islands):
            seed = ProgramNode(
                id=f"seed_isl_{i}",
                code=code,
                score=initial_score,
                generation=0,
                island_id=i,
                z3_verified=True,
            )
            self.db.add_program(seed)

    def evolve_candidate(
        self,
        candidate_code: str,
        evaluator_fn: Callable[[str], float],
        generation: int = 1,
    ) -> Dict[str, Any]:
        """
        Takes candidate code, runs SMT Z3 substrate validation,
        executes the evaluator, and records the score into the database.
        """
        t0 = time.perf_counter()

        # 1. SMT Z3 Hard Gate Filter (Path jail & command safety check)
        z3_res = self.guard.verify("write_to_file", {
            "TargetFile": "C:/vazus/hartes/candidate.py",
            "CodeContent": candidate_code,
        })

        if z3_res.get("decision") != "allow":
            return {
                "accepted": False,
                "reason": "SMT Z3 Hard Gate Veto",
                "details": z3_res.get("reason"),
                "score": -1.0,
            }

        # 2. Evaluate fitness in sandbox
        try:
            score = evaluator_fn(candidate_code)
            elapsed_ms = (time.perf_counter() - t0) * 1000

            island_id = self.db.sample_island()
            prog_node = ProgramNode(
                id=f"gen_{generation}_{int(time.time()*1000)%100000}",
                code=candidate_code,
                score=score,
                generation=generation,
                island_id=island_id,
                execution_time_ms=elapsed_ms,
                z3_verified=True,
            )
            self.db.add_program(prog_node)

            return {
                "accepted": True,
                "score": score,
                "island_id": island_id,
                "latency_ms": elapsed_ms,
                "program_id": prog_node.id,
            }
        except Exception as e:
            return {
                "accepted": False,
                "reason": f"Evaluator exception: {str(e)}",
                "score": -1.0,
            }
