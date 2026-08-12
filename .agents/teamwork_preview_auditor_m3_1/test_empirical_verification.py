import os
import sys
import tempfile
import yaml
import re
from pathlib import Path

# Add C:\vazus to sys.path
sys.path.insert(0, r"C:\vazus")

from vazus_core.zettelkasten_exporter import (
    export_zettelkasten_note,
    export_all_zettelkasten_notes,
    sanitize_zettel_id,
    sanitize_filename,
    format_yaml_frontmatter
)

def run_empirical_verification():
    temp_dir = tempfile.mkdtemp(prefix="forensic_audit_")
    print(f"[Audit Test] Temporary dir: {temp_dir}")

    # Test 1: Single note export
    node = {
        "id": "thesis_forensic_999",
        "name": "Empirical Audit Test Note",
        "statement": "Forensic testing ensures real file creation and frontmatter integrity.",
        "confidence": 0.99,
        "domain": "forensic_audit",
        "ach_status": "CONFIRMED",
        "node_type": "ThesisNode",
        "evidence_sources": ["source_doc_alpha.pdf", "scene_101"],
        "tags": ["audit", "forensic", "zettel"]
    }

    edges = [
        {"source_id": "thesis_forensic_999", "target_id": "node_alpha", "relation": "SUPPORTS"},
        {"source_id": "thesis_forensic_999", "target_id": "node_beta", "relation": "DEPENDS_ON"}
    ]

    out_file = export_zettelkasten_note(node, output_dir=temp_dir, related_edges=edges)
    assert os.path.exists(out_file), f"File {out_file} does not exist!"
    print(f"[PASS] File created: {out_file}")

    content = Path(out_file).read_text(encoding="utf-8")
    assert content.startswith("---"), "Content must start with --- frontmatter"

    # Validate frontmatter parsing with PyYAML
    parts = content.split("---")
    assert len(parts) >= 3, "Frontmatter not bounded by ---"
    fm_raw = parts[1]
    parsed_fm = yaml.safe_load(fm_raw)

    mandatory_keys = ["id", "title", "date", "tags", "domain", "status", "sources"]
    for k in mandatory_keys:
        assert k in parsed_fm, f"Missing key {k} in YAML frontmatter: {parsed_fm}"

    assert parsed_fm["id"] == "Zettel_thesis_forensic_999"
    assert parsed_fm["title"] == "Empirical Audit Test Note"
    assert parsed_fm["domain"] == "forensic_audit"
    assert parsed_fm["status"] == "CONFIRMED"
    print(f"[PASS] YAML Frontmatter correctly parsed: {parsed_fm}")

    # Validate H1 and H2 sections
    assert "# Empirical Audit Test Note" in content
    assert "## Core Claim / Thesis" in content
    assert "## Analytical Evidence & Context" in content
    assert "## Action Checklist" in content
    assert "## Related Notes & Wikilinks" in content
    print("[PASS] Markdown section hierarchy verified")

    # Validate Wikilinks count >= 3
    wikilinks = re.findall(r'\[\[([^\]]+)\]\]', content)
    assert len(wikilinks) >= 3, f"Expected >= 3 Wikilinks, got {len(wikilinks)}: {wikilinks}"
    print(f"[PASS] Wikilinks count: {len(wikilinks)} ({wikilinks})")

    # Validate Action Checklist (- [ ])
    checklist = re.findall(r'-\s*\[\s*\]\s+.+', content)
    assert len(checklist) > 0, f"Expected checklist items, got {checklist}"
    print(f"[PASS] Checklist items count: {len(checklist)}")

    # Test 2: Batch Export
    batch_input = {
        "thesis_nodes": [
            {"id": "b1", "name": "Batch Note 1", "node_type": "ThesisNode"},
            {"id": "b2", "name": "Batch Note 2", "node_type": "ThesisNode"}
        ],
        "protocol_nodes": [
            {"id": "p1", "name": "Batch Protocol 1", "node_type": "ProtocolNode", "steps": ["Step A", "Step B"]}
        ]
    }
    batch_files = export_all_zettelkasten_notes(batch_input, output_dir=temp_dir, auto_reindex=False)
    assert len(batch_files) == 3, f"Expected 3 batch files, got {len(batch_files)}"
    for bf in batch_files:
        assert os.path.exists(bf), f"Batch file missing: {bf}"
    print(f"[PASS] Batch export generated {len(batch_files)} files successfully")

    print("ALL EMPIRICAL AUDIT CHECKS PASSED CLEAN!")

if __name__ == "__main__":
    run_empirical_verification()
