"""
vazus_core.synthesis.map_elites_archive
=======================================
Multi-dimensional Archive of Phenotypic Elites (MAP-Elites) for Code Evolution.
Enables quality-diversity search over syntactic complexity and runtime performance.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CodeCandidate:
    """Represents a code solution candidate with fitness and behavioral descriptor coordinates."""
    candidate_id: str
    code: str
    fitness_score: float = 0.0
    complexity_dim: int = 0
    performance_dim: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def behavior_coords(self) -> Tuple[int, int]:
        return (self.complexity_dim, self.performance_dim)


class MapElitesArchive:
    """
    2D MAP-Elites archive grid partitioning code candidates by behavioral niches.
    """

    def __init__(self, grid_dim_x: int = 5, grid_dim_y: int = 5):
        self.dim_x = max(1, grid_dim_x)
        self.dim_y = max(1, grid_dim_y)
        # Grid map: (x, y) -> CodeCandidate
        self._grid: Dict[Tuple[int, int], CodeCandidate] = {}

    def _clamp_coords(self, x: int, y: int) -> Tuple[int, int]:
        cx = max(0, min(self.dim_x - 1, x))
        cy = max(0, min(self.dim_y - 1, y))
        return (cx, cy)

    def add_candidate(self, candidate: CodeCandidate) -> bool:
        """
        Attempts to insert or replace candidate in its designated niche.
        Returns True if accepted (new cell or superior fitness), False otherwise.
        """
        coords = self._clamp_coords(candidate.complexity_dim, candidate.performance_dim)
        current = self._grid.get(coords)

        if current is None or candidate.fitness_score > current.fitness_score:
            self._grid[coords] = candidate
            return True
        return False

    def get_best_candidate(self) -> Optional[CodeCandidate]:
        """Returns the highest-fitness elite across the entire archive."""
        if not self._grid:
            return None
        return max(self._grid.values(), key=lambda c: c.fitness_score)

    def get_coverage_ratio(self) -> float:
        """Returns the fraction of archive cells populated by elites [0.0, 1.0]."""
        total_cells = self.dim_x * self.dim_y
        if total_cells == 0:
            return 0.0
        return len(self._grid) / float(total_cells)

    def get_cell(self, x: int, y: int) -> Optional[CodeCandidate]:
        """Retrieves elite at specific coordinate."""
        coords = self._clamp_coords(x, y)
        return self._grid.get(coords)

    def get_all_candidates(self) -> List[CodeCandidate]:
        """Returns list of all active elites in the archive."""
        return list(self._grid.values())

    def sample_candidate(self) -> Optional[CodeCandidate]:
        """Uniformly samples a random elite from populated niches."""
        if not self._grid:
            return None
        return random.choice(list(self._grid.values()))

    def count(self) -> int:
        """Returns number of populated niches."""
        return len(self._grid)
