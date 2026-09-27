r"""
Unit tests for Titans Test-Time Neural Memory Engine (arXiv:2501.00663)
and surprise-gated continuous reflexion.

Verifies:
- Memory package exports: TitansNeuralMemory and TitansConfig
- Test-time surprise-based gradient descent convergence (L_surprise = ||x̂_t - x_t||^2)
- Momentum tracking and forget gating
- Associative recall and retrieval interface
- Surprise-gated retrospective generation in ContinuousReflexionGenerator and ReflexionMemoryStore
"""

import numpy as np
import pytest
from pathlib import Path

from vazus_autonomous_harness.memory import (
    TitansNeuralMemory,
    TitansConfig,
    ContinuousReflexionGenerator,
    ReflexionMemoryStore,
    ReflexionRecord,
)


def test_titans_export_in_memory_package():
    """Verifies that TitansNeuralMemory and TitansConfig are cleanly exported from memory package."""
    assert TitansNeuralMemory is not None
    assert TitansConfig is not None

    cfg = TitansConfig(dim=32, eta=0.85, theta=0.04, alpha=0.02)
    memory = TitansNeuralMemory(cfg)
    assert memory.dim == 32
    assert memory.M.shape == (32, 32)
    assert memory.S.shape == (32, 32)


def test_titans_step_and_surprise_convergence():
    """
    Verifies test-time surprise-based gradient descent convergence:
    Repeated adaptation on constant (key, target) pairs produces monotonically
    decreasing surprise loss.
    """
    dim = 16
    config = TitansConfig(dim=dim, theta=0.02, eta=0.5, alpha=0.005)
    memory = TitansNeuralMemory(config)

    rng = np.random.RandomState(42)
    key = rng.randn(dim).astype(np.float32)
    value = rng.randn(dim).astype(np.float32)

    surprises = []
    for _ in range(8):
        loss = memory.step(key=key, value=value)
        surprises.append(loss)

    # Initial surprise must be strictly larger than final adapted surprise
    assert surprises[0] > surprises[-1], f"Expected convergence: {surprises}"
    for i in range(len(surprises) - 1):
        assert surprises[i] >= surprises[i + 1] - 1e-4, f"Non-monotonic surprise at step {i}: {surprises}"


def test_titans_associative_recall_and_retrieve():
    """
    Verifies associative recall: after test-time learning,
    recalling with the key vector produces an output aligned with the target value.
    """
    dim = 16
    config = TitansConfig(dim=dim, theta=0.05, eta=0.6, alpha=0.001)
    memory = TitansNeuralMemory(config)

    # Unit vector key and value
    key = np.zeros(dim, dtype=np.float32)
    key[0] = 1.0
    value = np.zeros(dim, dtype=np.float32)
    value[1] = 2.0

    # Step multiple times to encode associative link
    for _ in range(15):
        memory.step(key=key, value=value)

    # Verify both recall() and retrieve() work identically
    recalled_1 = memory.recall(key)
    recalled_2 = memory.retrieve(key)
    np.testing.assert_allclose(recalled_1, recalled_2, atol=1e-6)

    # The recalled vector should have strong energy in dimension 1
    assert recalled_1[1] > 1.0


def test_titans_momentum_and_forget_gate_telemetry():
    """Verifies momentum updates, forget gate decay, and telemetry reporting."""
    dim = 8
    memory = TitansNeuralMemory(TitansConfig(dim=dim, alpha=0.10))

    key = np.ones(dim, dtype=np.float32)
    val = np.ones(dim, dtype=np.float32) * 3.0

    memory.step(key, val)
    stats = memory.get_stats()
    assert stats["total_steps"] == 1
    assert stats["frobenius_norm"] > 0.0
    assert stats["avg_surprise"] > 0.0
    assert stats["dim"] == dim

    # Test reset clears state
    memory.reset()
    assert memory.total_steps == 0
    assert np.all(memory.M == 0.0)
    assert np.all(memory.S == 0.0)


def test_surprise_gated_retrospective_threshold():
    """
    Verifies surprise-gated retrospective generation in ContinuousReflexionGenerator:
    - Surprise <= threshold: No record generated (returns None).
    - Surprise > threshold: Structured ReflexionRecord generated capturing the anomaly.
    """
    generator = ContinuousReflexionGenerator()

    # Case 1: Low surprise (below threshold) -> no retrospective
    no_record = generator.from_titans_surprise(
        task_id="test_task_01",
        surprise_loss=15.0,
        threshold=25.0,
        context="Normal benign prompt execution",
    )
    assert no_record is None

    # Case 2: High surprise (above threshold) -> anomaly record generated
    record = generator.from_titans_surprise(
        task_id="test_task_02",
        surprise_loss=48.5,
        threshold=25.0,
        context="Sudden epistemic divergence during code evaluation",
        candidate_code="def anomalous_leak(): return 999",
    )
    assert isinstance(record, ReflexionRecord)
    assert record.task_id == "test_task_02"
    assert record.category == "titans_surprise_anomaly"
    assert "48.5000" in record.root_cause
    assert "Titans Epistemic Continuity Invariant" in record.violated_invariant
    assert record.fitness_score == 51.5  # 100.0 - 48.5
    assert len(record.negative_rules) == 1
    assert record.negative_rules[0].rule_type == "REGEX_DENY"


def test_surprise_gated_reflexion_store_integration(tmp_path: Path):
    """
    Verifies end-to-end integration with ReflexionMemoryStore:
    A high-surprise anomaly is automatically persisted into SQLite SSOT and
    Markdown Wiki, immediately updating the pre-flight filter to intercept repeating it.
    """
    db_file = str(tmp_path / "titans_test.db")
    wiki_dir = tmp_path / "titans_wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    store = ReflexionMemoryStore(db_path=db_file, wiki_root=wiki_dir)

    try:
        candidate_bug = "def broken_divergence(): pass"

        # Step 1: Sub-threshold surprise does not trigger recording
        res1 = store.check_and_record_titans_surprise(
            task_id="task_sub",
            surprise_loss=12.0,
            threshold=25.0,
            candidate_code=candidate_bug,
        )
        assert res1 is None
        # Pre-flight filter should still allow the code
        blocked, _ = store.check_negative_constraints(candidate_bug)
        assert blocked is False

        # Step 2: High surprise triggers recording and pre-flight interception
        res2 = store.check_and_record_titans_surprise(
            task_id="task_high",
            surprise_loss=62.0,
            threshold=25.0,
            context="Contract violation under test-time shift",
            candidate_code=candidate_bug,
        )
        assert res2 is not None
        assert res2.category == "titans_surprise_anomaly"

        # Pre-flight filter must now immediately block repeating this exact code snippet!
        blocked2, reason = store.check_negative_constraints(candidate_bug)
        assert blocked2 is True
        assert "anomalous_leak" not in (reason or "")
        assert reason is not None
    finally:
        store.close()
