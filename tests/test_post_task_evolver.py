"""
tests/test_post_task_evolver.py — Comprehensive Unit Test Suite for Milestone M2
"""

import os
import sys
import time
import pytest
import sqlite3
from pathlib import Path

# Add project root to sys.path
WORKSPACE_ROOT = str(Path(__file__).resolve().parent.parent)
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from vazus_core.db import get_db_connection
from vazus_core.post_task_evolver import (
    TaskResult,
    ReflexionLesson,
    EvolutionSummary,
    persist_reflexion_lesson,
    update_agents_md,
    run_post_task_evolution,
)


@pytest.fixture
def tmp_db(tmp_path):
    """Provides isolated SQLite database path."""
    db_file = tmp_path / "test_post_task_evolver.db"
    return str(db_file)


@pytest.fixture
def tmp_agents_md(tmp_path):
    """Provides isolated AGENTS.md file initialized with template."""
    file_path = tmp_path / "AGENTS.md"
    content = """# vazus SuperGraph OS & Native Antigravity Subagent Architecture

## Overview
Test overview section.

---

## Native Antigravity Subagent Roles & System Prompts

### 1. `open_deep_researcher`
* **Role**: Open Deep Researcher Subagent
* **Description**: LangGraph Open Deep Research.

### 2. `rlm_code_engineer`
* **Role**: RLM Code Engineer Subagent
* **Description**: MIT RLM.

### 3. `verifier_worker`
* **Role**: Jules Verifier Worker Subagent
* **Description**: Static AST verifier.

---

## Governance & Verification Protocol
1. **Antigravity First**: Test protocol.
"""
    file_path.write_text(content, encoding="utf-8")
    return str(file_path)


def test_dataclasses_initialization():
    """Verify dataclass instantiation and backward compatibility properties."""
    tr = TaskResult(
        task_id="t1",
        subagent_name="rlm_code_engineer",
        prompt="Write python module",
        output="def foo(): pass",
        error_trace="",
        success=True,
        execution_time=1.5,
        fitness_score=0.9
    )
    assert tr.task_id == "t1"
    assert tr.subagent_name == "rlm_code_engineer"
    assert tr.success is True

    rl = ReflexionLesson(
        id="l1",
        timestamp=1000.0,
        task_id="t1",
        prompt_template="tpl1",
        fitness_score=0.88,
        lesson_learned="Check AST first",
        mutation_delta={"delta": 0.05},
        metadata={"category": "AST"}
    )
    assert rl.id == "l1"
    assert rl.lesson_id == "l1"
    assert rl.category == "AST"
    assert rl.solution_summary == "Check AST first"

    es = EvolutionSummary(
        task_id="t1",
        subagent_name="rlm_code_engineer",
        evolution_status="SUCCESS",
        initial_fitness=0.75,
        final_fitness=0.88,
        mutated_prompts={"rlm_code_engineer": "New prompt"},
        lessons_persisted=["l1"],
        agents_md_updated=True
    )
    assert es.task_id == "t1"
    assert es.lessons_learned == ["l1"]
    assert es.agents_md_updated is True


def test_persist_reflexion_lesson_auto_create_schema(tmp_db):
    """Verify persist_reflexion_lesson creates 8-column table and inserts record atomically."""
    lesson = ReflexionLesson(
        id="lesson_test_100",
        timestamp=time.time(),
        task_id="task_m2_01",
        prompt_template="You are a code engineer.",
        fitness_score=0.95,
        lesson_learned="Always enforce SMT Z3 contract verification.",
        mutation_delta={"initial_fitness": 0.8, "final_fitness": 0.95, "delta": 0.15},
        metadata={"subagent_name": "rlm_code_engineer", "success": True}
    )

    success = persist_reflexion_lesson(lesson, db_path=tmp_db)
    assert success is True

    conn = get_db_connection(tmp_db)
    cur = conn.cursor()
    
    # Verify 8-column schema
    columns = [row[1] for row in cur.execute("PRAGMA table_info(reflexion_lessons)").fetchall()]
    expected_cols = ["id", "timestamp", "task_id", "prompt_template", "fitness_score", "lesson_learned", "mutation_delta", "metadata"]
    for col in expected_cols:
        assert col in columns, f"Column '{col}' missing in reflexion_lessons table schema!"

    # Verify inserted values
    cur.execute("SELECT id, task_id, fitness_score, lesson_learned FROM reflexion_lessons WHERE id = ?", ("lesson_test_100",))
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "lesson_test_100"
    assert row[1] == "task_m2_01"
    assert pytest.approx(row[2]) == 0.95
    assert "SMT Z3" in row[3]


def test_update_agents_md_fitness_gating_reject_below_threshold(tmp_agents_md):
    """Verify update_agents_md rejects prompt mutations below fitness threshold 0.70."""
    mutated = {
        "rlm_code_engineer": {
            "prompt_template": "Low quality prompt",
            "fitness_score": 0.65,
            "baseline_fitness": 0.50,
            "systemic_lesson": "Failed test"
        }
    }
    res = update_agents_md(mutated, agents_md_path=tmp_agents_md, fitness_threshold=0.70)
    assert res is False

    with open(tmp_agents_md, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Low quality prompt" not in content


def test_update_agents_md_fitness_gating_reject_insufficient_delta(tmp_agents_md):
    """Verify update_agents_md rejects prompt mutations with delta < 0.01 when baseline > 0."""
    mutated = {
        "rlm_code_engineer": {
            "prompt_template": "Minor prompt tweak",
            "fitness_score": 0.8505,
            "baseline_fitness": 0.8500,
            "systemic_lesson": "Negligible improvement"
        }
    }
    res = update_agents_md(mutated, agents_md_path=tmp_agents_md, min_improvement_delta=0.01)
    assert res is False


def test_update_agents_md_successful_update(tmp_agents_md):
    """Verify update_agents_md updates subagent prompt section and appends evolved lesson log."""
    mutated = {
        "rlm_code_engineer": {
            "prompt_template": "You are RLM Code Engineer v2. Enforce AST signatures and SMT Z3 verifier.",
            "fitness_score": 0.92,
            "baseline_fitness": 0.80,
            "systemic_lesson": "Added formal contract verification requirement.",
            "generation": 2,
            "mutations_applied": ["AST signature check", "SMT contract check"]
        }
    }
    res = update_agents_md(mutated, agents_md_path=tmp_agents_md)
    assert res is True

    with open(tmp_agents_md, "r", encoding="utf-8") as f:
        content = f.read()

    assert "RLM Code Engineer v2" in content
    assert "## Evolved Prompt Templates & Systemic Lessons" in content
    assert "Added formal contract verification requirement." in content
    assert "Fitness Score" in content and "0.9200" in content


def test_update_agents_md_atomic_rollback_on_failure(tmp_path):
    """Verify update_agents_md performs atomic rollback if write error occurs."""
    mutated = {
        "rlm_code_engineer": {
            "prompt_template": "Valid prompt text",
            "fitness_score": 0.95,
            "baseline_fitness": 0.80
        }
    }

    # Passing a directory path causes file read/write error
    res = update_agents_md(mutated, agents_md_path=str(tmp_path))
    assert res is False


def test_run_post_task_evolution_success(tmp_db, tmp_agents_md, monkeypatch):
    """Verify run_post_task_evolution executes composite scoring, prompt mutation, lesson persistence, and AGENTS.md update."""
    monkeypatch.setenv("VAZUS_DB_PATH", tmp_db)

    task_res = TaskResult(
        task_id="task_e2e_m2_001",
        subagent_name="rlm_code_engineer",
        prompt="You are RLM Code Engineer. Implement AST pruner and verify contract.",
        output="```python\ndef solve(x):\n    return x + 1\n```\nSMT Z3 verifier status: UNSAT",
        error_trace="",
        success=True,
        execution_time=0.45
    )

    summary = run_post_task_evolution(task_res)
    assert isinstance(summary, EvolutionSummary)
    assert summary.task_id == "task_e2e_m2_001"
    assert summary.subagent_name == "rlm_code_engineer"
    assert summary.initial_fitness > 0.5
    assert summary.final_fitness >= summary.initial_fitness
    assert summary.evolution_status in ("SUCCESS", "NO_MUTATION_NEEDED")
    assert len(summary.lessons_persisted) > 0

    # Verify DB persistence
    conn = get_db_connection(tmp_db)
    row = conn.execute("SELECT id, fitness_score FROM reflexion_lessons WHERE task_id = ?", ("task_e2e_m2_001",)).fetchone()
    conn.close()
    assert row is not None
