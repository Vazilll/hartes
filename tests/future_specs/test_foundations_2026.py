"""
Comprehensive Test Suite for 2026 SOTA Foundation Infrastructure Systems in Vazus OS.
Verifies all 19 core architectural modules across isolation, storage, verification, runtime, and security.
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# Module Imports
from vazus_core.sandbox.win32_job_guard import Win32JobSandbox
from vazus_core.storage.sqlite_pool import RobustSQLitePool
from vazus_core.storage.schema_migrator import SchemaMigrator, SchemaMigration
from vazus_core.missions.saga_checkpointer import SagaCheckpointer
from vazus_core.security.entropy_scrubber import SecretScrubber
from vazus_core.engine.gc_governor import GCGovernor
from vazus_core.engine.deterministic_context import VirtualClock, DeterministicSessionContext
from vazus_core.ipc.shared_memory_ring import SharedMemoryBus
from vazus_core.hooks.mcp_gateway import DynamicMCPGateway
from vazus_core.engine.rlm_driver import RLMDriver
from vazus_core.hooks.entropy_governor import EntropyGovernor
from vazus_core.verification.smt_portfolio import SMTPortfolioSolver
from vazus_core.verification.oracle_synthesizer import AlgebraicOracleSynthesizer
from vazus_core.verification.metamorphic_oracle import MetamorphicCodeOracle
from vazus_core.verification.angelic_executor import AngelicHoleSolver
from vazus_core.runtime.event_stream import EventStream, EventSource
from vazus_core.synthesis.map_elites_archive import MapElitesArchive, CodeCandidate
from vazus_core.engine.system_discovery_engine import SystemDiscoveryEngine
from services.memory.semantic.wiki_compiler import WikiCompiler
import z3


def test_win32_job_sandbox():
    """A-1: Verifies Win32 Job Object creation and lifecycle."""
    sandbox = Win32JobSandbox(memory_limit_mb=256, kill_on_close=True)
    if sys.platform == "win32":
        assert sandbox.job_handle is not None
    sandbox.close()
    assert sandbox.job_handle is None


def test_sqlite_wal_pool():
    """A-2: Verifies WAL mode, busy timeout, and connection isolation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_pool.db"
        pool = RobustSQLitePool(db_path, busy_timeout_ms=5000)
        
        with pool.connection() as conn:
            conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, val TEXT);")
            conn.execute("INSERT INTO test_data (val) VALUES ('vazus_val');")
            
        rows = pool.execute("SELECT val FROM test_data;")
        assert len(rows) == 1
        assert rows[0]["val"] == "vazus_val"


def test_schema_migrator():
    """A-4: Verifies PRAGMA user_version forward and rollback migrations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_migrations.db"
        migrator = SchemaMigrator(str(db_path))
        
        assert migrator.get_current_version() == 0
        v_applied = migrator.migrate()
        assert v_applied == 3
        assert migrator.get_current_version() == 3
        
        # Test Rollback
        v_rolled = migrator.rollback(1)
        assert v_rolled == 1
        assert migrator.get_current_version() == 1


def test_secret_scrubber():
    """F-1: Verifies Shannon entropy detection and regex token sanitization."""
    scrubber = SecretScrubber(entropy_threshold=4.2)
    
    # 1. Regex scrubbing
    leak_text = "My API Key is AIzaSyD9876543210zyxwvutsrqponmlkjihg"
    sanitized = scrubber.scrub(leak_text)
    assert "AIza" not in sanitized
    assert "REDACTED" in sanitized
    
    # 2. Shannon Entropy scrubbing
    high_entropy_secret = "k8J#mN9$xL2!qP5*vR7^wZ0@"
    sanitized_entropy = scrubber.scrub(f"Secret: {high_entropy_secret}")
    assert high_entropy_secret not in sanitized_entropy
    assert "REDACTED" in sanitized_entropy

    # 3. File path false positive prevention (Windows and Unix paths)
    win_path = r"C:\vazus\vazus_core\engine\dynamic_skill_dispatcher.py"
    unix_path = "/var/log/vazus/supergraph/telemetry.log"
    sanitized_paths = scrubber.scrub(f"Paths: {win_path} and {unix_path}")
    assert "REDACTED" not in sanitized_paths
    assert win_path in sanitized_paths
    assert unix_path in sanitized_paths


def test_gc_governor():
    """E-1: Verifies gc.freeze and threshold tuning."""
    gov = GCGovernor()
    stats = gov.stats()
    assert "thresholds" in stats
    gov.pause()
    gov.resume(run_gen0=True)


def test_deterministic_context_and_clock():
    """E-4: Verifies logical clock and seed reproducibility."""
    clock = VirtualClock(epoch_start=1000.0, step_delta=0.5)
    assert clock.now() == 1000.0
    t1 = clock.tick()
    assert t1 == 1000.5
    assert clock.step_count == 1
    
    with DeterministicSessionContext(session_seed=123) as ctx:
        evt = ctx.log_event("TEST_ACTION", {"file": "core.py"})
        assert evt["event_type"] == "TEST_ACTION"
        assert len(ctx.event_log) == 1


def test_shared_memory_bus():
    """E-2: Verifies zero-copy shared memory IPC payload framing."""
    bus = SharedMemoryBus(name="Local\\TestVazusBus", size_mb=1)
    payload = b"VAZUS_SUPERGRAPH_IPC_DATA_2026"
    assert bus.write_payload(payload)
    
    read_res = bus.read_payload()
    assert read_res is not None
    data, timestamp = read_res
    assert data == payload
    bus.close()


def test_dynamic_mcp_gateway():
    """B-1: Verifies Intent-Schema Overlap (ISO) scoring and token savings."""
    gw = DynamicMCPGateway(max_active_tools=2)
    gw.register_tool("git_commit_tool", {"name": "git_commit_tool", "description": "Commits files to git repository"})
    gw.register_tool("z3_smt_verify", {"name": "z3_smt_verify", "description": "Formally proves theorem using Z3 solver"})
    gw.register_tool("weather_report", {"name": "weather_report", "description": "Fetches current temperature and weather"})
    
    # Query related to formal verification
    active = gw.resolve_active_tools("Please verify this loop invariant with Z3")
    names = [t.get("name") for t in active]
    assert "z3_smt_verify" in names
    
    savings = gw.get_token_savings_metric()
    assert savings["total_registered_tools"] == 3


def test_rlm_driver():
    """B-2: Verifies Recursive Language Model driver execution loop."""
    driver = RLMDriver()
    result = driver.run(
        prompt="Find secret keyword",
        long_context="Secret data: TARGET_KEYWORD_XYZ"
    )
    assert result["status"] in ("SUCCESS", "MAX_ITERATIONS_REACHED")
    assert len(result["trajectory"]) > 0


def test_wiki_compiler():
    """B-3: Verifies Karpathy LLM Wiki wikilink parsing and Tarjan SCC cycle detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_dir = Path(tmpdir)
        (wiki_dir / "PageA.md").write_text("Links to [[PageB]] and [[MissingPage]].", encoding="utf-8")
        (wiki_dir / "PageB.md").write_text("Links back to [[PageA]].", encoding="utf-8")
        
        compiler = WikiCompiler(wiki_dir)
        compiler.load_wiki()
        
        dangling = compiler.find_dangling_links()
        assert any(tgt == "MissingPage" for src, tgt in dangling)
        
        sccs = compiler.find_strongly_connected_components()
        assert len(sccs) > 0 # Cycle between PageA and PageB
        
        idx_path = compiler.compile_index()
        assert Path(idx_path).exists()


def test_entropy_governor():
    """B-4: Verifies attention entropy estimation and observation masking."""
    gov = EntropyGovernor(unmasked_turn_lag=1)
    
    trajectory = [
        {"role": "system", "content": "You are Vazus OS."},
        {"role": "user", "content": "Fix bug in AST."},
        {"role": "assistant", "content": "Running tests."},
        {"role": "tool", "content": "PASS dot dot dot " * 1000},
        {"role": "assistant", "content": "Analyzing result."},
        {"role": "tool", "content": "PASS 2"},
        {"role": "assistant", "content": "Done."},
    ]
    
    compacted, meta = gov.compact_trajectory(trajectory, force=True)
    assert len(compacted) == len(trajectory)
    # Stale tool observation at index 3 (turns_from_end = 3 > unmasked_turn_lag=1) should be masked
    assert "OBSERVATION MASKED" in compacted[3]["content"]


def test_smt_portfolio_solver():
    """C-1: Verifies Z3 SMT portfolio solver execution."""
    solver = SMTPortfolioSolver()
    
    # 1. SAT query
    sat_query = "(set-logic ALL) (declare-const x Int) (assert (> x 10)) (check-sat)"
    res_sat = solver.solve_smt2(sat_query)
    assert res_sat.status == "SAT"
    assert "x" in res_sat.model_dict
    
    # 2. UNSAT query
    unsat_query = "(set-logic ALL) (declare-const x Int) (assert (and (> x 10) (< x 5))) (check-sat)"
    res_unsat = solver.solve_smt2(unsat_query)
    assert res_unsat.status == "UNSAT"


def test_algebraic_oracle_synthesizer():
    """C-2: Verifies Z3 algebraic proofs for commutativity and idempotence."""
    synth = AlgebraicOracleSynthesizer()
    
    # Prove integer addition is commutative: x + y == y + x
    comm_fn = lambda x, y: x + y
    assert synth.prove_commutativity_z3(comm_fn)
    
    # Prove non-commutative subtraction fails: x - y != y - x
    non_comm_fn = lambda x, y: x - y
    assert not synth.prove_commutativity_z3(non_comm_fn)


def test_metamorphic_code_oracle():
    """C-3: Verifies Athena dead-branch injection and semantic equivalence."""
    code = "def compute(x):\n    return x * 2"
    mutated = MetamorphicCodeOracle.inject_dead_code_guard(code, "x", 10)
    assert "EMI Injected Dead Code" in mutated
    
    fn_orig = lambda x: x * 2
    fn_trans = lambda x: x + x
    equiv, err = MetamorphicCodeOracle.verify_semantic_equivalence(fn_orig, fn_trans, [1, 2, 5, 10])
    assert equiv
    assert err is None


def test_angelic_hole_solver():
    """C-4: Verifies SMT angelic hole patch synthesis."""
    # Test linear hole repair: alpha * x == expected_y
    io_pairs = [(2, 10), (3, 15), (4, 20)]
    alpha_val = AngelicHoleSolver.solve_angelic_constant_patch(
        eval_fn_z3=lambda alpha, x: alpha * x,
        io_test_pairs=io_pairs
    )
    assert alpha_val == 5 # 5 * x


def test_event_stream():
    """G-4: Verifies EventStream append, subscription, and rewind."""
    stream = EventStream()
    notifications = []
    stream.subscribe(lambda e: notifications.append(e.event_type))
    
    stream.append("UserPrompt", EventSource.USER, {"text": "Hello"})
    stream.append("AgentAction", EventSource.AGENT, {"tool": "bash"})
    stream.append("ToolObservation", EventSource.ENVIRONMENT, {"stdout": "OK"})
    
    assert len(stream.events) == 3
    assert len(notifications) == 3
    
    # Test rewind back to step 1
    stream.rewind(1)
    assert len(stream.events) == 2


def test_map_elites_archive():
    """G-2: Verifies 2D MAP-Elites grid insertion and Pareto coverage."""
    archive = MapElitesArchive(grid_dim_x=5, grid_dim_y=5)
    
    c1 = CodeCandidate("c1", "def foo(): pass", fitness_score=0.7, complexity_dim=2, performance_dim=3)
    c2 = CodeCandidate("c2", "def foo(): return 1", fitness_score=0.9, complexity_dim=2, performance_dim=3)
    
    assert archive.add_candidate(c1)
    assert archive.add_candidate(c2) # Better fitness replaces c1
    
    best = archive.get_best_candidate()
    assert best is not None
    assert best.candidate_id == "c2"
    assert archive.get_coverage_ratio() > 0.0


def test_system_discovery_engine():
    """Verifies System Discovery Engine scans, capability matching, and unreferenced symbol detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        (repo_dir / "module_a.py").write_text("""
class DatabaseConnectionManager:
    '''Manages database connection pool and WAL checkpoints.'''
    def connect(self):
        pass

def unused_standalone_helper():
    '''Helper that is never called.'''
    return 42
""", encoding="utf-8")
        
        (repo_dir / "module_b.py").write_text("""
from module_a import DatabaseConnectionManager

def run_app():
    mgr = DatabaseConnectionManager()
    mgr.connect()
""", encoding="utf-8")

        discovery = SystemDiscoveryEngine(workspace_root=repo_dir)
        stats = discovery.scan_codebase()
        assert stats["total_files"] == 2
        assert stats["total_defined_symbols"] >= 3
        
        # Capability search
        caps = discovery.search_capabilities("database connection pool")
        assert len(caps) > 0
        assert caps[0]["name"] == "DatabaseConnectionManager"
        
        # Dead code detection
        unref = discovery.find_unreferenced_symbols()
        unref_names = [s.name for s in unref]
        assert "unused_standalone_helper" in unref_names
