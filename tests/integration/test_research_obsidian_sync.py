"""
Unit tests for vazus_core.missions.research_obsidian_sync.
"""

from pathlib import Path
from vazus_core.missions.research_obsidian_sync import (
    ResearchObsidianSyncer,
)


def test_research_obsidian_note_creation(tmp_path):
    syncer = ResearchObsidianSyncer(wiki_dir=tmp_path)

    res = syncer.create_atomic_note(
        title="Ring Buffer Mutex Optimization",
        summary="Analysis of lock contention reduction using circular ring buffers with RAII semantics in Go.",
        domain="concurrency",
        tags=["go", "concurrency", "ring_buffer", "low_latency"],
        key_concepts=[
            "Head/Tail modulo arithmetic avoids dynamic allocations",
            "sync.RWMutex minimizes read latency during heavy read-path polling",
        ],
        latex_equations=[
            "tail_{new} = (tail + 1) \\pmod C",
            "size \\le C",
        ],
        code_snippets={
            "go": "type RingBuffer[T any] struct {\n\titems []T\n\tcap int\n}"
        },
        custom_links=["[[Zettel_AST_ast_pruner]]"],
    )

    assert res["success"] is True
    assert res["zettel_id"] == "Zettel_Ring_Buffer_Mutex_Optimization"
    assert Path(res["file_path"]).exists()

    content = Path(res["file_path"]).read_text(encoding="utf-8")
    assert "id: Zettel_Ring_Buffer_Mutex_Optimization" in content
    assert "## 📌 Core Summary" in content
    assert "## 📐 Mathematical Formulation" in content
    assert "## 💻 Implementation & Skeletons" in content
    assert "## 🔗 Bidirectional Wikilinks & References" in content
    assert "[[Zettel_AST_ast_pruner]]" in content


def test_formula_verification():
    syncer = ResearchObsidianSyncer()
    v_res = syncer.verify_formula("x + y = y + x")
    assert v_res.get("verified") is True
    assert v_res.get("is_identity") is True

    v_calc = syncer.verify_formula("x^2 + 2*x + 1")
    assert v_calc.get("verified") is True
    assert "expr" in v_calc
