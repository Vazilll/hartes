"""
labs.deepmind.funsearch_evolver.evolver
=======================================
FunSearch 4-Island Evolutionary Coordinator.
Coordinates 4 asynchronous islands with periodic elite migration,
isolated worktree execution via AntigravityWorktreeSandbox, and MAP-Elites archives.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from labs.deepmind.funsearch_evolver.archive import CodeCandidate
from labs.deepmind.funsearch_evolver.evaluator import FunSearchEvaluator
from labs.deepmind.funsearch_evolver.island import Island

logger = logging.getLogger("labs.deepmind.funsearch_evolver.evolver")


class FourIslandEvolver:
    """
    Coordinates 4 distinct genetic islands with ring migration policy.
    Leverages AntigravityWorktreeSandbox for isolated evaluations.
    """

    def __init__(
        self,
        sandbox: Optional[Any] = None,
        llm: Optional[Any] = None,
        num_islands: int = 4,
        migration_interval: int = 10,
    ):
        self.num_islands = num_islands
        self.migration_interval = migration_interval
        self.islands = [Island(island_id=i, llm=llm) for i in range(num_islands)]
        self.evaluator = FunSearchEvaluator(sandbox=sandbox)
        self.total_evaluations: int = 0

    def seed_initial_candidate(self, code: str, problem_spec: str = "default") -> None:
        """Seeds all islands with an initial baseline candidate."""
        score, c_dim, p_dim = self.evaluator.evaluate(code)
        for island in self.islands:
            candidate = CodeCandidate(
                candidate_id=f"seed_isl{island.island_id}",
                code=code,
                fitness_score=score,
                complexity_dim=c_dim,
                performance_dim=p_dim,
            )
            island.add_candidate(candidate)

    async def evolve(
        self,
        problem_spec: str,
        n_iterations: int = 20,
        test_suite_fn: Optional[Callable[[str], float]] = None,
    ) -> Optional[CodeCandidate]:
        """
        Executes evolutionary loop across all 4 islands.
        Returns the overall best candidate discovered.
        """
        for iteration in range(1, n_iterations + 1):
            for island in self.islands:
                candidate = await island.mutate_best(problem_spec)
                fitness, c_dim, p_dim = self.evaluator.evaluate(candidate.code, test_suite_fn=test_suite_fn)
                island.update(candidate, fitness, c_dim, p_dim)
                self.total_evaluations += 1

            # Periodic elite migration across islands (Ring topology: 0 -> 1 -> 2 -> 3 -> 0)
            if iteration % self.migration_interval == 0:
                self._migrate_best_across_islands()

        return self.get_best_candidate()

    def _migrate_best_across_islands(self) -> None:
        """Transfers the best elite from island i to island (i+1)%num_islands."""
        elites = [isl.get_best() for isl in self.islands]
        for i in range(self.num_islands):
            donor_elite = elites[i]
            target_island = self.islands[(i + 1) % self.num_islands]
            if donor_elite:
                target_island.add_candidate(donor_elite)
        logger.info("[FunSearch] Ring migration complete across %d islands", self.num_islands)

    def get_best_candidate(self) -> Optional[CodeCandidate]:
        """Finds global best candidate across all island archives."""
        best_candidates = [isl.get_best() for isl in self.islands if isl.get_best() is not None]
        if not best_candidates:
            return None
        return max(best_candidates, key=lambda c: c.fitness_score)

    @property
    def statistics(self) -> Dict[str, Any]:
        """Returns evolutionary telemetry across islands."""
        coverages = [isl.archive.get_coverage_ratio() for isl in self.islands]
        best_candidate = self.get_best_candidate()
        return {
            "total_islands": self.num_islands,
            "total_evaluations": self.total_evaluations,
            "island_coverages": coverages,
            "global_best_fitness": best_candidate.fitness_score if best_candidate else 0.0,
            "global_best_id": best_candidate.candidate_id if best_candidate else None,
        }
