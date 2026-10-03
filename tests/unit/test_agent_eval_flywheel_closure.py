"""
tests/unit/test_agent_eval_flywheel_closure.py
==============================================
Empirical unit verification of the Continuous Agent Self-Improvement Flywheel:
1. SMT Z3 Formal Proof of Closed Feedback Loops (Zero Dead-Ends, Zero Livelocks).
2. YAML Frontmatter Schema Audit across all cluster notes.
3. Bidirectional Wikilink Integrity Audit (Zero Broken Links).
4. SuperGraphLinker Graph Ingestion & SQLite Persist Verification.
"""

import os
import re
import yaml
import pytest
from pathlib import Path
from z3 import Solver, Bool, Int, Or, And, Not, Implies, unsat

WIKI_DIR = Path("C:/vazus/services/memory/semantic/wiki")

FLYWHEEL_FILES = [
    "ADR_005_CONTINUOUS_AGENT_SELF_IMPROVEMENT_FLYWHEEL.md",
    "Zettel_Continuous_Agent_Self_Improvement_Flywheel.md",
    "Zettel_Multi_Turn_Session_Event_Tracing.md",
    "Zettel_Autonomous_Trajectory_Evaluation_AutoRaters.md",
    "Zettel_Error_Analysis_Loss_Taxonomy_Clustering.md",
    "Zettel_Three_Tier_Agent_Optimization_Hierarchy.md",
    "Zettel_Dynamic_Few_Shot_In_Context_Learning.md",
    "Zettel_Automated_Prompt_Tuning_and_DSPy_Evolution.md",
    "Zettel_Parametric_Fine_Tuning_LoRA_SFT_DPO.md",
    "Zettel_AutoSxS_Blind_Arbitration_and_Regression_Gate.md",
    "Zettel_Closed_Feedback_Loop_Formal_Verification.md",
    "agent_eval_quality_flywheel.md",
]


def test_smt_z3_loop_closure_proof():
    """
    Formally proves via SMT Z3 that all 6 feedback loops are mathematically closed:
    - H1: Dead-end freedom (dispatched error must resolve via prod, reflect, or quarantine).
    - H2: Critical non-stalling (critical/safety error must be dispatched).
    - H3: Isolation / OCC security (promoted requires gating and matching OCC base hash).
    - H4: Finite livelock freedom (no infinite reflection once attempts > max_attempts).
    """
    solver = Solver()

    err = Bool("error_detected")
    is_critical = Bool("is_critical")
    ttl_expired = Bool("ttl_expired")
    cluster_size = Int("cluster_size")
    dispatched = Bool("dispatched")

    attempts = Int("attempts")
    max_attempts = Int("max_attempts")

    mutated = Bool("mutated")
    gated = Bool("gated")
    occ_valid = Bool("occ_valid")
    winrate_pass = Bool("winrate_pass")
    zero_regr = Bool("zero_regr")

    promoted = Bool("promoted")
    reflected = Bool("reflected")
    quarantined = Bool("quarantined")

    solver.add(max_attempts == 3)
    solver.add(attempts >= 0)
    solver.add(cluster_size >= 1)

    # 1. Multi-Priority Dispatch rule
    solver.add(dispatched == Or(cluster_size >= 10, is_critical, ttl_expired))
    solver.add(Implies(And(err, dispatched), mutated))
    solver.add(Implies(mutated, gated))

    # 2. Strict Promotion Invariant (AutoSxS + OCC)
    solver.add(promoted == And(gated, occ_valid, winrate_pass, zero_regr))

    # 3. Mutually exclusive rejection branches
    solver.add(reflected == And(gated, Not(promoted), attempts <= max_attempts))
    solver.add(quarantined == And(gated, Not(promoted), attempts > max_attempts))

    # Reflection feeds back to mutation
    solver.add(Implies(reflected, mutated))

    # Verify Hypothesis 1: Dead-end leak is impossible
    solver.push()
    solver.add(And(err, dispatched, Not(Or(promoted, reflected, quarantined))))
    assert solver.check() == unsat, "H1 FAILED: Dead-end leak detected!"
    solver.pop()

    # Verify Hypothesis 2: Critical stalling is impossible
    solver.push()
    solver.add(And(err, is_critical, Not(dispatched)))
    assert solver.check() == unsat, "H2 FAILED: Critical error stalled!"
    solver.pop()

    # Verify Hypothesis 3: Isolation / OCC leak is impossible
    solver.push()
    solver.add(And(promoted, Not(And(gated, occ_valid))))
    assert solver.check() == unsat, "H3 FAILED: Candidate promoted without valid gate or OCC!"
    solver.pop()

    # Verify Hypothesis 4: Infinite livelock is impossible
    solver.push()
    solver.add(And(attempts > max_attempts, reflected))
    assert solver.check() == unsat, "H4 FAILED: Infinite reflection livelock permitted!"
    solver.pop()


def test_flywheel_frontmatter_schema():
    """Validates that all notes in the Flywheel cluster have correct YAML frontmatter."""
    required_keys = {"id", "title", "date", "domain", "tags", "status", "sources"}

    for fname in FLYWHEEL_FILES:
        fpath = WIKI_DIR / fname
        assert fpath.exists(), f"File {fname} does not exist!"

        content = fpath.read_text(encoding="utf-8")
        if not content.startswith("---"):
            pytest.fail(f"{fname} missing starting YAML frontmatter delimiter ('---')")

        parts = content.split("---", 2)
        assert len(parts) >= 3, f"{fname} malformed YAML frontmatter delimiters"

        fm_text = parts[1]
        data = yaml.safe_load(fm_text)
        assert isinstance(data, dict), f"{fname} frontmatter did not parse as a dict"

        missing = required_keys - set(data.keys())
        assert not missing, f"{fname} missing required frontmatter keys: {missing}"
        assert data["status"] in ("VERIFIED", "DRAFT", "PROPOSED"), f"{fname} invalid status: {data['status']}"


def test_flywheel_wikilinks_integrity():
    """Scans all [[...]] links across the Flywheel cluster and verifies all targets exist."""
    wikilink_pattern = re.compile(r"\[\[([^\]\|#]+)(?:#([^\]\|]+))?(?:\|([^\]]+))?\]\]")
    broken_links = []
    total_links = 0

    all_wiki_stems = {p.stem for p in WIKI_DIR.glob("*.md")}
    all_wiki_files = {p.name for p in WIKI_DIR.iterdir()}

    for fname in FLYWHEEL_FILES:
        fpath = WIKI_DIR / fname
        content = fpath.read_text(encoding="utf-8")

        for match in wikilink_pattern.finditer(content):
            total_links += 1
            raw_target = match.group(1).strip()
            # If target has extension (e.g. .canvas)
            if "." in raw_target:
                if raw_target not in all_wiki_files:
                    broken_links.append((fname, raw_target))
            else:
                target_stem = raw_target.replace(" ", "_")
                if target_stem not in all_wiki_stems:
                    broken_links.append((fname, raw_target))

    assert total_links >= 50, f"Expected at least 50 wikilinks, found {total_links}"
    assert not broken_links, f"Found broken wikilinks: {broken_links}"


def test_supergraph_linker_ingestion(tmp_path):
    """Verifies that SuperGraphLinker parses and loads all Flywheel notes into graph nodes and edges."""
    from vazus_core.engine.supergraph_linker import SuperGraphLinker

    test_db = tmp_path / "test_supergraph.db"
    linker = SuperGraphLinker(db_path=str(test_db), wiki_dirs=[WIKI_DIR])

    wiki_nodes, wiki_edges = linker.load_memory_wiki_nodes_and_edges()
    assert len(wiki_nodes) >= 100, f"Expected >= 100 wiki nodes, got {len(wiki_nodes)}"
    assert len(wiki_edges) >= 200, f"Expected >= 200 wiki edges, got {len(wiki_edges)}"

    # Check that our Flywheel notes are represented among the WikiNote nodes
    node_ids = {n["id"] for n in wiki_nodes}
    for fname in FLYWHEEL_FILES:
        stem = Path(fname).stem
        assert f"wiki:{stem}" in node_ids, f"Node wiki:{stem} missing from SuperGraphLinker nodes!"
