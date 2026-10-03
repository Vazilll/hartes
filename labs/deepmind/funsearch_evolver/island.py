"""
labs.deepmind.funsearch_evolver.island
======================================
Individual Island representation in the 4-Island FunSearch architecture.
Maintains a local MAP-Elites archive and mutates candidates via LLM prompts.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from labs.deepmind.funsearch_evolver.archive import CodeCandidate, MapElitesArchive

logger = logging.getLogger("labs.deepmind.funsearch_evolver.island")


class Island:
    """An isolated evolutionary island with local population diversity."""

    def __init__(self, island_id: int, llm: Optional[Any] = None, grid_size: int = 5):
        self.island_id = island_id
        self.llm = llm
        self.archive = MapElitesArchive(grid_dim_x=grid_size, grid_dim_y=grid_size)
        self.generation: int = 0

    def get_best(self) -> Optional[CodeCandidate]:
        """Returns the highest fitness elite in this island."""
        return self.archive.get_best_candidate()

    def add_candidate(self, candidate: CodeCandidate) -> bool:
        """Inserts candidate into the island's MAP-Elites archive."""
        return self.archive.add_candidate(candidate)

    async def mutate_best(self, problem_spec: str = "") -> CodeCandidate:
        """Mutates the best candidate or samples an elite to generate an offspring candidate."""
        self.generation += 1
        best = self.archive.sample_candidate() or self.get_best()

        base_code = best.code if best else "def solve():\n    return 42"
        mutated_code = base_code

        # 1. LLM mutation if engine provided
        if self.llm is not None:
            try:
                prompt = (
                    f"You are FunSearch Island #{self.island_id} mutating a Python function for problem: {problem_spec}\n"
                    f"Current implementation:\n```python\n{base_code}\n```\n"
                    f"Generate an improved, mutated version of the function that achieves higher performance."
                )
                if hasattr(self.llm, "generate_async"):
                    res = await self.llm.generate_async(prompt)
                elif hasattr(self.llm, "generate"):
                    res = self.llm.generate(prompt)
                else:
                    res = ""

                if res and isinstance(res, str) and "def " in res:
                    mutated_code = res.strip()
            except Exception as e:
                logger.debug("LLM mutation fallback on island %d: %s", self.island_id, e)

        # 2. Synthetic genetic perturbation if no LLM output
        if mutated_code == base_code:
            mutated_code = f"# Island {self.island_id} Gen {self.generation}\n" + base_code

        cid = f"isl{self.island_id}_gen{self.generation}_{str(uuid.uuid4())[:6]}"
        return CodeCandidate(candidate_id=cid, code=mutated_code, fitness_score=0.0)

    def update(self, candidate: CodeCandidate, fitness: float, complexity_dim: int = 0, perf_dim: int = 0) -> bool:
        """Updates candidate attributes and adds to the archive."""
        candidate.fitness_score = fitness
        candidate.complexity_dim = complexity_dim
        candidate.performance_dim = perf_dim
        return self.archive.add_candidate(candidate)
