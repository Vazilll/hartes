"""
Unit tests for DeepSeek DSec Task Slicing & Synthetic Adversarial Generator.
"""

import time
import pytest
from vazus_autonomous_harness.flywheel.dsec_slicer import (
    DSecTaskSlicer,
    DSecAdversarialGenerator,
    TaskSlice,
)


def test_dsec_task_slicer_basic_execution():
    slicer = DSecTaskSlicer(default_timeout_sec=2.0)
    slice_obj = TaskSlice(
        slice_id="test_slice_1",
        task_id="test_task_1",
        stage_name="STAGE_COMPUTE",
        timeout_sec=2.0,
    )

    def simple_add(a: int, b: int) -> int:
        return a + b

    result = slicer.execute_slice(slice_obj, simple_add, 10, 20)
    assert result.success is True
    assert result.status == "COMPLETED"
    assert result.output == 30
    assert result.execution_time_ms >= 0.0
    assert slice_obj.status == "COMPLETED"


def test_dsec_task_slicer_timeout_isolation():
    slicer = DSecTaskSlicer()
    slice_obj = TaskSlice(
        slice_id="timeout_slice",
        task_id="test_task_timeout",
        stage_name="INFINITE_LOOP",
        timeout_sec=0.2,  # 200 ms timeout
    )

    def slow_function():
        time.sleep(1.0)
        return "done"

    result = slicer.execute_slice(slice_obj, slow_function)
    assert result.success is False
    assert result.status == "TIMEOUT"
    assert "exceeded bounded timeout" in result.error
    assert slice_obj.status == "TIMEOUT"


def test_dsec_task_slicer_pipeline_execution():
    slicer = DSecTaskSlicer()

    def step1(ctx):
        return {"data": [1, 2, 3]}

    def step2(ctx):
        total = sum(ctx.get("data", []))
        return {"sum": total}

    pipeline = [
        ("fetch_data", step1, 1.0),
        ("aggregate", step2, 1.0),
    ]

    res = slicer.execute_pipeline("pipe_001", pipeline, initial_context={"user": "zhukov"})
    assert res["overall_success"] is True
    assert res["completed_slices"] == 2
    assert res["final_context"]["sum"] == 6
    assert res["final_context"]["user"] == "zhukov"


def test_dsec_adversarial_generator_scenarios():
    gen = DSecAdversarialGenerator()
    code = """
def calculate_grade(points: int) -> str:
    \"\"\"
    :requires: points >= 0
    :ensures: result != ''
    \"\"\"
    if points >= 85:
        return 'A'
    return 'B'
"""
    scenarios = gen.generate_scenarios_for_code(code)
    assert len(scenarios) >= 8

    report = gen.test_candidate_adversarially(code, scenarios)
    assert report.total_scenarios >= 8
    assert report.robustness_score >= 80.0
    assert report.is_safe_to_promote is True


def test_dsec_adversarial_generator_blocks_lethal_ast():
    gen = DSecAdversarialGenerator()
    lethal_code = """
def malicious_worker(cmd: str):
    eval(cmd)
"""
    report = gen.test_candidate_adversarially(lethal_code)
    assert report.is_safe_to_promote is False
    assert report.failed_count >= 1
    violations = [v for v in report.violations if v["category"] == "AST_MUTATION_INTEGRITY"]
    assert len(violations) >= 1
    assert "eval" in violations[0]["reason"]
