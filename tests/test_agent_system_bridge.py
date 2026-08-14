"""
tests/test_agent_system_bridge.py — Unit tests for vazus_core.agent_system_bridge module.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from vazus_core.agent_system_bridge import (
    AgentRoleSpec,
    OpenAgentSystemOrchestrator
)


def test_agent_role_and_task_dag():
    orchestrator = OpenAgentSystemOrchestrator()

    # 1. Register agent roles
    researcher = AgentRoleSpec(
        name="code_researcher",
        role_title="Senior Code Researcher",
        goal="Discover code architecture bottlenecks",
        backstory="Expert software architect."
    )
    coder = AgentRoleSpec(
        name="refactoring_engineer",
        role_title="Senior Refactoring Engineer",
        goal="Refactor bottlenecks into high-speed C/Rust extensions",
        backstory="Expert C++/Rust performance engineer."
    )
    orchestrator.register_agent_role(researcher)
    orchestrator.register_agent_role(coder)

    # 2. Create tasks with dependencies (Task 2 depends on Task 1)
    task1 = orchestrator.create_task(
        task_id="t1_research",
        description="Audit AST performance",
        expected_output="List of slow functions",
        assigned_agent="code_researcher"
    )
    task2 = orchestrator.create_task(
        task_id="t2_refactor",
        description="Refactor slow functions",
        expected_output="Optimized C/Rust code",
        assigned_agent="refactoring_engineer",
        dependencies=["t1_research"]
    )

    # 3. Check executable tasks
    exec_tasks = orchestrator.get_executable_tasks()
    assert len(exec_tasks) == 1
    assert exec_tasks[0].task_id == "t1_research"

    # 4. Execute Task 1
    output1 = orchestrator.execute_task(
        "t1_research",
        executor_fn=lambda _role, task: "Found slow function compute_similarity"
    )
    assert output1 == "Found slow function compute_similarity"
    assert task1.status == "COMPLETED"

    # 5. Check executable tasks again (Task 2 should now be ready)
    exec_tasks_next = orchestrator.get_executable_tasks()
    assert len(exec_tasks_next) == 1
    assert exec_tasks_next[0].task_id == "t2_refactor"

    # 6. Execute Task 2
    output2 = orchestrator.execute_task(
        "t2_refactor",
        executor_fn=lambda _role, task: "Refactored via BLAS & USearch SIMD"
    )
    assert output2 == "Refactored via BLAS & USearch SIMD"
    assert task2.status == "COMPLETED"
