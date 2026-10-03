import json
import time
import pytest
from pathlib import Path
from vazus_core.hooks.session_start_hook import run_session_start
from vazus_core.hooks.pre_invocation_hook import run_pre_invocation, auto_disclose_domain_specs

EXPECTED_SPEC_PATHS = [
    Path('C:/vazus/vazus_core/engine/SPEC.md'),
    Path('C:/vazus/vazus_core/memory/SPEC.md'),
    Path('C:/vazus/vazus_core/hooks/SPEC.md'),
    Path('C:/vazus/services/finance_agent/SPEC.md'),
    Path('C:/vazus/services/health_agent/SPEC.md'),
    Path('C:/vazus/services/vision/SPEC.md'),
]

def test_six_canonical_specs_exist_and_conform():
    for spec_path in EXPECTED_SPEC_PATHS:
        assert spec_path.exists(), f'Missing spec: {spec_path}'
        content = spec_path.read_text(encoding='utf-8')
        assert len(content) > 200
        assert '## 1. Core Mission' in content
        assert 'ALLOWED' in content
        assert 'PROHIBITED' in content
        assert '## 2. Public Typed Interface Contracts' in content
        assert '`python' in content
        assert 'Invariant Guarantees' in content
        assert '## 3. Progressive Skill Level' in content
        for lvl in range(1, 6):
            assert f'Level {lvl}' in content
        assert '## 4. Known Bottlenecks' in content

def test_canonical_system_state_manifest():
    manifest_path = Path('C:/vazus/SYSTEM_STATE.json')
    assert manifest_path.exists()
    raw_bytes = manifest_path.read_bytes()
    assert len(raw_bytes) < 5120
    data = json.loads(raw_bytes.decode('utf-8'))
    assert data.get('schema_version') == '1.0.0'
    assert data.get('system_name') == 'Vazus SuperGraph OS'
    assert data.get('health_status') == 'HEALTHY'
    ranks = data.get('subsystem_skill_ranks', {})
    assert len(ranks) == 6

@pytest.mark.anyio
async def test_session_start_hook_sub_50ms():
    # Warmup to ensure GC/allocator jitter from previous tests does not bias SLA measurement
    await run_session_start()
    t0 = time.perf_counter()
    result = await run_session_start()
    dt = (time.perf_counter() - t0) * 1000.0
    assert dt <= 50.0, f"SessionStart latency {dt:.2f}ms exceeds 50ms SLA"
    assert result.get('session_start') is True
    assert 'system_state' in result

def test_pre_invocation_hook_sub_50ms_and_progressive_disclosure():
    t0 = time.perf_counter()
    eval_res = run_pre_invocation([], 'evaluate engine AST pruning and memory facts')
    dt = (time.perf_counter() - t0) * 1000.0
    assert dt <= 50.0
    assert eval_res.get('status') == 'ok'
    disc = auto_disclose_domain_specs('audit financial receipts and health ble')
    assert len(disc) > 100
    assert 'Canonical Domain Contract' in disc
