"""
tests/test_raytsystem_supergraph.py — Integration test validating vazus SuperGraph OS performance on C:/vazus/labs/raytsystem.

Verifies:
1. AST Pruner signature validation and token economy reduction on raytsystem Python modules.
2. 768D vector space embedding generation for raytsystem code & metadata.
3. 4-Component Hybrid Metric calculation (S_cosine, S_fts, S_structural, S_provenance) for raytsystem.
4. SQLite persistence of raytsystem nodes and hybrid edges in vazus.db.
"""

import sys
import json
from pathlib import Path

VAZUS_DIR = Path("C:/vazus")
if str(VAZUS_DIR) not in sys.path:
    sys.path.insert(0, str(VAZUS_DIR))

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from vazus_core.ast_pruner import ASTPruner
from vazus_core.embeddings import UnifiedGoogleEmbedder
from vazus_core.supergraph_linker import SuperGraphLinker

RAYTSYSTEM_DIR = VAZUS_DIR / "labs" / "raytsystem" / "src" / "raytsystem"


def run_raytsystem_verification(db_path=None):
    print("=" * 70)
    print("🧪 SUPERGRAPH OS INTEGRATION TEST ON C:/vazus/labs/raytsystem")
    print("=" * 70)

    db_file = db_path or r"C:\vazus\services\memory\vazus.db"

    # 1. AST Pruning & Signature Validation
    print("\n1. Testing AST Pruner on raytsystem modules...")
    target_files = ["agent_policy.py", "checkpoint_guard.py", "control.py", "universe.py", "cli.py"]
    
    total_raw_bytes = 0
    total_pruned_bytes = 0

    for fname in target_files:
        fpath = RAYTSYSTEM_DIR / fname
        if not fpath.exists():
            print(f"   ⚠️ File not found: {fname}")
            continue
        
        content = fpath.read_text(encoding="utf-8")
        is_valid = ASTPruner.validate_signatures(content)
        assert is_valid, f"Syntax Error in {fname}"

        pruned = ASTPruner.prune_ast(content)
        raw_size = len(content.encode("utf-8"))
        pruned_size = len(pruned.encode("utf-8"))

        total_raw_bytes += raw_size
        total_pruned_bytes += pruned_size

        print(f"   - {fname:22s} | Valid AST: ✅ | Raw: {raw_size:6d}B | Pruned: {pruned_size:6d}B")

    reduction = (1 - (total_pruned_bytes / total_raw_bytes)) * 100 if total_raw_bytes > 0 else 0
    print(f"   ✅ AST Token Economy Reduction for raytsystem: {reduction:.2f}%")

    # 2. 768D Vector Space Embeddings
    print("\n2. Testing 768D Vector Embedder on raytsystem specs...")
    embedder = UnifiedGoogleEmbedder(dimension=768)
    
    sample_code_spec = "class AgentPolicyManager: handles governance, checkpoint guarding, and platform security policies in raytsystem"
    sample_doc_spec = "Raytsystem Security & Governance: Automated policy enforcement and agent execution safety"

    vec_code = embedder.embed_query(sample_code_spec, db_path=db_file)
    vec_doc = embedder.embed_query(sample_doc_spec, db_path=db_file)

    assert len(vec_code) == 768, f"Expected 768D vector, got {len(vec_code)}"
    assert len(vec_doc) == 768, f"Expected 768D vector, got {len(vec_doc)}"
    print(f"   - Code Spec Vector Dim: {len(vec_code)} | Doc Spec Vector Dim: {len(vec_doc)}")
    print("   ✅ 768D Embeddings generated for raytsystem.")

    # 3. Hybrid Metric Linker
    print("\n3. Testing SuperGraph Hybrid Linker for raytsystem...")
    linker = SuperGraphLinker(db_path=db_file)

    node_rayt_code = {
        "id": "rayt:agent_policy",
        "name": "AgentPolicyManager",
        "domain": "raytsystem_code",
        "node_type": "Class",
        "description": sample_code_spec,
        "source_file": "labs/raytsystem/src/raytsystem/agent_policy.py",
        "community": 2,
        "tags": "raytsystem,policy,governance,agent"
    }

    node_rayt_doc = {
        "id": "rayt:security_doc",
        "name": "Raytsystem Governance",
        "domain": "raytsystem_docs",
        "node_type": "DocNote",
        "description": sample_doc_spec,
        "source_file": "labs/raytsystem/AGENTS.md",
        "community": 2,
        "tags": "raytsystem,security,governance,doc"
    }

    metrics = linker.compute_hybrid_metric(node_rayt_code, node_rayt_doc, vec_code, vec_doc)
    print(f"   - S_cosine:      {metrics['s_cosine']:.4f}")
    print(f"   - S_fts:         {metrics['s_fts']:.4f}")
    print(f"   - S_structural:  {metrics['s_structural']:.4f}")
    print(f"   - S_provenance:  {metrics['s_provenance']:.4f}")
    print(f"   - Total Hybrid Score S(u, v): {metrics['total_score']:.4f}")

    assert metrics['total_score'] > 0.30, "Expected significant hybrid similarity score"
    print("   ✅ SuperGraph Hybrid Metric verified for raytsystem.")

    # 4. Database Persistence
    print("\n4. Verifying Persistence of raytsystem nodes in vazus.db...")
    with linker._get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO kg_nodes (id, name, domain, node_type, description, tags, properties, embedding_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            node_rayt_code["id"],
            node_rayt_code["name"],
            node_rayt_code["domain"],
            node_rayt_code["node_type"],
            node_rayt_code["description"],
            node_rayt_code["tags"],
            json.dumps({"source_file": node_rayt_code["source_file"]}),
            json.dumps(vec_code)
        ))

        conn.execute("""
            INSERT OR REPLACE INTO kg_edges (source_id, target_id, relation, strength, properties)
            VALUES (?, ?, ?, ?, ?)
        """, (
            node_rayt_code["id"],
            node_rayt_doc["id"],
            "RAYTSYSTEM_SUPERGRAPH_LINK",
            metrics["total_score"],
            json.dumps({"vector_dim": 768, "metrics": metrics})
        ))
        conn.commit()

        # Query verification
        row = conn.execute("SELECT * FROM kg_edges WHERE relation = 'RAYTSYSTEM_SUPERGRAPH_LINK'").fetchone()
        assert row is not None, "Failed to locate stored raytsystem edge in vazus.db"
        print(f"   - Edge stored: {row['source_id']} -> {row['target_id']} (strength: {row['strength']:.4f})")

    print("\n" + "=" * 70)
    print("🎉 RAYTSYSTEM SUPERGRAPH OS INTEGRATION TEST PASSED!")
    print("=" * 70)


def test_raytsystem_supergraph(tmp_path):
    run_raytsystem_verification(db_path=str(tmp_path / "test_rayt.db"))


if __name__ == "__main__":
    run_raytsystem_verification()
