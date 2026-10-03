"""
labs.deepmind.funsearch_evolver
===============================
FunSearch 4-Island Evolutionary Code Generation & Optimization Engine.
"""

from labs.deepmind.funsearch_evolver.archive import CodeCandidate, MapElitesArchive
from labs.deepmind.funsearch_evolver.evaluator import FunSearchEvaluator
from labs.deepmind.funsearch_evolver.evolver import FourIslandEvolver
from labs.deepmind.funsearch_evolver.island import Island

__all__ = [
    "CodeCandidate",
    "MapElitesArchive",
    "FunSearchEvaluator",
    "Island",
    "FourIslandEvolver",
]
