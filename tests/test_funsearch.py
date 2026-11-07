"""
Tests for DeepMind FunSearch Evolutionary Core in vazus_autonomous_harness.
"""

from vazus_autonomous_harness.flywheel.funsearch_engine import (
    ProgramNode,
    Island,
    ProgramsDatabase,
    FunSearchEngine,
)


def test_island_capacity_and_sampling():
    island = Island(island_id=0, capacity=3)
    p1 = ProgramNode(id="p1", code="def f(): return 1", score=10.0, generation=0, island_id=0)
    p2 = ProgramNode(id="p2", code="def f(): return 2", score=20.0, generation=1, island_id=0)
    p3 = ProgramNode(id="p3", code="def f(): return 3", score=30.0, generation=2, island_id=0)
    p4 = ProgramNode(id="p4", code="def f(): return 4", score=5.0, generation=3, island_id=0)

    for p in [p1, p2, p3, p4]:
        island.add_program(p)

    # Capacity is 3, sorted descending: p3 (30), p2 (20), p1 (10). p4 (5) dropped.
    assert len(island.programs) == 3
    assert [p.id for p in island.programs] == ["p3", "p2", "p1"]

    # Sample best should return one of top programs
    sampled = island.sample_best()
    assert sampled is not None
    assert sampled.score in [10.0, 20.0, 30.0]


def test_programs_database_and_migration():
    db = ProgramsDatabase(num_islands=3, capacity_per_island=5)

    # Add program to island 0
    p0 = ProgramNode(id="hero_0", code="x = 10", score=99.0, generation=1, island_id=0)
    db.add_program(p0)

    assert db.get_best_overall().id == "hero_0"
    assert len(db.islands[0].programs) == 1
    assert len(db.islands[1].programs) == 0

    # Migrate should copy top program of island 0 to island 1
    db.migrate()
    assert len(db.islands[1].programs) == 1
    migrated = db.islands[1].programs[0]
    assert migrated.score == 99.0
    assert migrated.island_id == 1
    assert migrated.metadata.get("migrated_from") == 0


def test_funsearch_engine_evolution_and_smt_gate():
    engine = FunSearchEngine(num_islands=4)

    # Seed the islands
    seed_code = "def solve(n): return n * 2"
    engine.register_seed(seed_code, initial_score=2.0)

    best_seed = engine.db.get_best_overall()
    assert best_seed is not None
    assert best_seed.score == 2.0

    # Evolve candidate with valid code and evaluator
    candidate = "def solve(n): return n * 3"
    evaluator = lambda code: 15.5

    result = engine.evolve_candidate(candidate, evaluator_fn=evaluator, generation=1)
    assert result["accepted"] is True
    assert result["score"] == 15.5
    assert result["latency_ms"] >= 0

    # Best overall should now be the new candidate
    new_best = engine.db.get_best_overall()
    assert new_best.score == 15.5

    # Test error handling when evaluator raises exception
    def failing_eval(code):
        raise ValueError("Intentional syntax/runtime failure")

    fail_res = engine.evolve_candidate("invalid code", evaluator_fn=failing_eval, generation=2)
    assert fail_res["accepted"] is False
    assert "Evaluator exception" in fail_res["reason"]
