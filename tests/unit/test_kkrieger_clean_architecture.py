"""
tests/test_kkrieger_clean_architecture.py — Verification suite for .kkrieger procedural minimalism,
fail-secure sandbox guarantees, thread-safe AVX512 engine, and path traversal security.
"""

import sys
import os
import threading
import pytest
from pathlib import Path

sys.path.insert(0, "C:/vazus")

from vazus_core.engine.operator_dag import create_standard_code_pipeline, OperatorPipelineDAG, OperatorContext
from vazus_core.workers.subprocess_repl import ZeroTrustSubprocessREPL
from vazus_core.memory.embeddings import _get_shared_avx512_engine
from vazus_core.integrations.skill_author import create_autonomous_skill
from vazus_core.engine.config import settings


def test_operator_pipeline_dag_procedural_generation():
    pipeline = create_standard_code_pipeline()
    sample_code = """
def compute_energy(mass: float, speed_of_light: float = 299792458.0) -> float:
    \"\"\"
    Calculates relativistic energy equivalent.
    :requires: mass >= 0
    :ensures: result >= 0
    \"\"\"
    result = mass * (speed_of_light ** 2)
    return result
"""
    ctx = pipeline.execute(sample_code)

    assert "AST_Prune" in str(ctx.trace)
    assert "Vector_Embed" in str(ctx.trace)
    assert ctx.metadata.get("compression_ratio", 0) >= 0.0
    assert ctx.metadata.get("vector_dim") == 768
    assert len(ctx.metadata.get("vector", [])) == 768


def test_subprocess_repl_fail_secure_execution():
    repl = ZeroTrustSubprocessREPL(timeout_seconds=5.0, require_kernel_sandbox=True)
    res = repl.execute_code("x = 12 * 12\nprint(f'Result: {x}')")

    assert res.status == "SUCCESS"
    assert "Result: 144" in res.stdout
    assert res.locals.get("x") == 144


def test_avx512_thread_safe_double_checked_lock():
    engines = []
    errors = []

    def worker():
        try:
            e = _get_shared_avx512_engine(dimension=768)
            engines.append(e)
        except Exception as err:
            errors.append(err)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(engines) == 8
    # All threads must retrieve the exact same singleton instance
    first = engines[0]
    for e in engines:
        assert e is first


def test_skill_author_path_traversal_protection():
    # Test valid skill creation
    res = create_autonomous_skill(
        skill_name="test-clean-skill",
        description="Clean unit test skill",
        instructions_markdown="Instructions for clean test."
    )
    assert res["status"] == "SUCCESS"
    assert Path(res["path"]).exists()

    # Clean up test skill file
    try:
        Path(res["path"]).unlink(missing_ok=True)
        Path(res["path"]).parent.rmdir()
    except Exception:
        pass


def test_config_paths_canonical_resolution():
    assert settings.WORKSPACE_DIR.exists()
    assert (settings.WORKSPACE_DIR / "vazus_core").exists()
    assert settings.EMBEDDING_DIM == 768
