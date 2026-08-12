"""
vazus_core/zettelkasten_exporter.py
Automated Zettelkasten Obsidian Wiki Exporter for vazus SuperGraph OS (Milestone 3 R3).

Converts ИАД ThesisNode/ProtocolNode analytical entities, graph relations, and SuperGraph
database records into structured, interlinked Obsidian Markdown Zettelkasten notes with:
1. Valid YAML frontmatter (id, title, date, tags, domain, status, sources)
2. H1 Title & Structured H2 Sections (Core Claim/Protocol, Analytical Evidence, Action Checklist, Related Notes & Wikilinks)
3. >= 3 bidirectional [[Wikilinks]] connecting graph entities/concepts
4. Action Checklist items (- [ ])
5. SuperGraph re-indexing integration (SuperGraphLinker)
"""

import os
import sys
import re
import json
import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set, Union

DEFAULT_WIKI_DIR = r"C:\vazus\services\memory\semantic\wiki"
DEFAULT_DB_PATH = r"C:\vazus\vazus.db"
if not Path(DEFAULT_DB_PATH).exists() and Path(r"C:\vazus\services\memory\vazus.db").exists():
    DEFAULT_DB_PATH = r"C:\vazus\services\memory\vazus.db"

# Try importing SuperGraphLinker
try:
    from vazus_core.supergraph_linker import SuperGraphLinker
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from vazus_core.supergraph_linker import SuperGraphLinker
    except ImportError:
        SuperGraphLinker = None


def sanitize_zettel_id(raw_id: str) -> str:
    """
    Sanitizes raw entity ID or title into a standard Zettel ID string: 'Zettel_<clean_identifier>'.
    """
    if not raw_id:
        raw_id = "entity_unknown"

    clean = re.sub(r'[^\w\-]', '_', str(raw_id).strip())
    clean = re.sub(r'_+', '_', clean).strip('_')

    if not clean:
        clean = "note"

    if clean.startswith("Zettel_"):
        return clean
    elif clean.startswith("zettel_"):
        return "Zettel_" + clean[7:]
    else:
        return f"Zettel_{clean}"


def sanitize_filename(name_or_id: str) -> str:
    """
    Sanitizes a string for use as a safe filename ending with .md.
    """
    z_id = sanitize_zettel_id(name_or_id)
    return f"{z_id}.md"


def format_yaml_frontmatter(metadata: Dict[str, Any]) -> str:
    """
    Formats a dictionary into clean, valid YAML frontmatter block enclosed in --- delimiters.
    Mandatory fields: id, title, date, tags, domain, status, sources.
    """
    z_id = metadata.get("id", "Zettel_unknown")
    title = str(metadata.get("title", "Untitled Zettel Note")).replace('"', '\\"')
    date_str = metadata.get("date") or datetime.date.today().isoformat()
    domain = metadata.get("domain", "kgb_analytics")
    status = metadata.get("status", "HYPOTHESIS")

    # Format tags list
    raw_tags = metadata.get("tags", ["iad", "thesis", "memory"])
    if isinstance(raw_tags, str):
        tags_list = [t.strip() for t in raw_tags.split(",") if t.strip()]
    elif isinstance(raw_tags, (list, set, tuple)):
        tags_list = [str(t).strip() for t in raw_tags if str(t).strip()]
    else:
        tags_list = ["iad", "zettel"]

    if "iad" not in tags_list:
        tags_list.insert(0, "iad")
    if "zettel" not in tags_list:
        tags_list.append("zettel")

    # Format sources list
    raw_sources = metadata.get("sources", ["SuperGraph Database Index"])
    if isinstance(raw_sources, str):
        sources_list = [s.strip() for s in raw_sources.split(",") if s.strip()]
    elif isinstance(raw_sources, (list, set, tuple)):
        sources_list = [str(s).strip() for s in raw_sources if str(s).strip()]
    else:
        sources_list = ["SuperGraph Database Index"]

    if not sources_list:
        sources_list = ["SuperGraph Database Index"]

    lines = [
        "---",
        f"id: {z_id}",
        f'title: "{title}"',
        f"date: {date_str}",
        "tags:"
    ]
    for tag in tags_list:
        lines.append(f"  - {tag}")

    lines.append(f"domain: {domain}")
    lines.append(f"status: {status}")
    lines.append("sources:")
    for src in sources_list:
        src_clean = str(src).replace("\\", "/").replace('"', '\\"')
        lines.append(f'  - "{src_clean}"')

    lines.append("---")
    return "\n".join(lines)


def _extract_entity_fields(entity: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """
    Normalizes entity dict or object into standardized dict format.
    """
    if hasattr(entity, "to_dict") and callable(entity.to_dict):
        d = entity.to_dict()
    elif isinstance(entity, dict):
        d = dict(entity)
    else:
        d = {
            "id": getattr(entity, "id", getattr(entity, "node_id", "node_unknown")),
            "name": getattr(entity, "name", "Untitled Node"),
            "node_type": getattr(entity, "node_type", "ThesisNode"),
            "domain": getattr(entity, "domain", "kgb_analytics"),
            "tags": getattr(entity, "tags", "iad,thesis"),
        }

    # Extract properties if nested string or dict
    props = d.get("properties", {})
    if isinstance(props, str):
        try:
            props = json.loads(props)
        except Exception:
            props = {}
    elif not isinstance(props, dict):
        props = {}

    d["properties_dict"] = props
    return d


def export_zettelkasten_note(
    entity_dict: Union[Dict[str, Any], Any],
    output_dir: str = DEFAULT_WIKI_DIR,
    related_edges: Optional[List[Dict[str, Any]]] = None,
    all_nodes_map: Optional[Dict[str, Dict[str, Any]]] = None
) -> str:
    r"""
    Exports an analytical entity (ThesisNode, ProtocolNode, or general node) as a Zettelkasten
    Markdown note in Obsidian format.

    Args:
      entity_dict: Node entity dictionary or object.
      output_dir: Path to wiki output directory. Default: C:\vazus\services\memory\semantic\wiki
      related_edges: Optional list of graph edge dicts connected to this entity.
      all_nodes_map: Optional map of node_id -> node_dict for resolving wikilink target titles.

    Returns:
      Absolute file path string of the exported Markdown note.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    e = _extract_entity_fields(entity_dict)
    raw_id = e.get("id") or e.get("node_id") or "entity_unknown"
    zettel_id = sanitize_zettel_id(raw_id)

    name = e.get("name") or e.get("statement") or e.get("action_instruction") or "Untitled Note"
    node_type = e.get("node_type", "ThesisNode")
    domain = e.get("domain", "kgb_analytics")
    status = e.get("ach_status") or e.get("status") or ("PROTOCOL" if node_type == "ProtocolNode" else "HYPOTHESIS")

    # Sources
    sources = e.get("evidence_sources") or []
    src_file = e.get("source_file") or e.get("properties_dict", {}).get("source_file", "")
    if src_file and src_file not in sources:
        sources.append(src_file)
    scene_id = e.get("scene_id") or e.get("properties_dict", {}).get("scene_id", "")
    if scene_id:
        sources.append(f"Scene: {scene_id}")
    if not sources:
        sources = ["SuperGraph Database Index"]

    # Tags
    tags = e.get("tags", ["iad", "thesis"])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    # Frontmatter
    frontmatter_meta = {
        "id": zettel_id,
        "title": name,
        "date": datetime.date.today().isoformat(),
        "tags": tags,
        "domain": domain,
        "status": status,
        "sources": sources
    }

    # H1 Title
    content_lines = [
        format_yaml_frontmatter(frontmatter_meta),
        "",
        f"# {name}",
        ""
    ]

    # H2 Section 1: Core Claim / Thesis or Protocol Directives
    if node_type == "ProtocolNode":
        content_lines.append("## Protocol Directives")
        instruction = e.get("action_instruction") or name
        content_lines.append(f"> **Operational Directive**: {instruction}")
        content_lines.append("")
    else:
        content_lines.append("## Core Claim / Thesis")
        statement = e.get("statement") or name
        content_lines.append(f"> **Thesis Assertion**: {statement}")
        content_lines.append("")

    # H2 Section 2: Analytical Evidence & Context
    content_lines.append("## Analytical Evidence & Context")
    confidence = e.get("confidence") or e.get("confidence_score") or 0.85
    content_lines.append(f"- **Confidence Score**: `{confidence:.2f}`")
    content_lines.append(f"- **ACH Status**: `{status}`")
    content_lines.append(f"- **Entity Type**: `{node_type}`")
    content_lines.append(f"- **Domain Context**: `{domain}`")

    # Timestamps if available
    start_sec = e.get("start_sec", 0.0)
    end_sec = e.get("end_sec", 0.0)
    if start_sec > 0 or end_sec > 0:
        content_lines.append(f"- **Media Scene Offset**: `{start_sec:.1f}s - {end_sec:.1f}s`")

    # Steps / Safety Warnings if ProtocolNode
    steps = e.get("steps") or e.get("properties_dict", {}).get("steps", [])
    if steps and isinstance(steps, list):
        content_lines.append("\n### Operational Steps:")
        for idx, step in enumerate(steps, 1):
            content_lines.append(f"{idx}. {step}")

    safety = e.get("safety_warnings") or e.get("properties_dict", {}).get("safety_warnings", [])
    if safety and isinstance(safety, list):
        content_lines.append("\n### Safety & Risk Warnings:")
        for warn in safety:
            content_lines.append(f"- ⚠️ **Warning**: {warn}")

    periodicity = e.get("frequency_periodicity") or e.get("properties_dict", {}).get("frequency_periodicity", "")
    if periodicity:
        content_lines.append(f"- **Frequency / Periodicity**: `{periodicity}`")

    content_lines.append("")

    # H2 Section 3: Action Checklist
    content_lines.append("## Action Checklist")
    content_lines.append(f"- [ ] Verify empirical evidence and source provenance for `{zettel_id}`")
    content_lines.append(f"- [ ] Conduct ACH matrix re-evaluation under updated `{status}` framework")

    if steps and isinstance(steps, list):
        for idx, step in enumerate(steps, 1):
            clean_step = str(step)[:100].replace("\n", " ")
            content_lines.append(f"- [ ] Execute Step {idx}: {clean_step}")
    else:
        content_lines.append(f"- [ ] Audit operational safety directives and protocol compliance for `{name[:50]}`")

    content_lines.append("")

    # H2 Section 4: Related Notes & Wikilinks (At least 3 bidirectional Wikilinks)
    content_lines.append("## Related Notes & Wikilinks")

    wikilinks: Set[str] = set()

    # Add links from related_edges
    if related_edges:
        for edge in related_edges:
            src = edge.get("source_id", "")
            tgt = edge.get("target_id", "")
            rel = edge.get("relation", "LINK")

            other_id = tgt if src == raw_id else src
            if not other_id or other_id == raw_id:
                continue

            target_zettel = sanitize_zettel_id(other_id)
            label = rel.replace("_", " ").title()

            if all_nodes_map and other_id in all_nodes_map:
                target_node = all_nodes_map[other_id]
                t_title = target_node.get("name") or target_node.get("statement") or target_zettel
                label = f"{t_title[:40]} ({rel})"

            wikilinks.add(f"- [[{target_zettel}|{label}]]")

    # Domain / Hub concept links to ensure >= 3 [[Wikilinks]] per note
    default_wikilinks = [
        f"- [[Zettel_SuperGraph_Hub|SuperGraph Knowledge Hub]]",
        f"- [[Zettel_Karpathy_Memory_Index|Karpathy Memory Index]]",
        f"- [[Zettel_ACH_Analytical_Framework|ACH Analytical Framework]]",
        f"- [[Zettel_IAD_Decomposition_Protocol|ИAД Operational Protocol]]",
        f"- [[Zettel_{domain}_Overview|{domain.replace('_', ' ').title()} Index]]"
    ]

    for d_link in default_wikilinks:
        if len(wikilinks) >= 3:
            break
        wikilinks.add(d_link)

    for link_item in sorted(wikilinks):
        content_lines.append(link_item)

    content_lines.append("")

    # Write file
    file_name = sanitize_filename(zettel_id)
    file_path = out_path / file_name

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(content_lines))

    return str(file_path.resolve())


def _extract_nodes_and_edges_from_db(
    db_path: str,
    node_types: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Helper function to load analytical nodes and edges from SQLite SuperGraph database (e.g. vazus.db).
    """
    nodes = []
    edges = []
    if not Path(db_path).exists():
        return nodes, edges

    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        if node_types:
            placeholders = ",".join(["?"] * len(node_types))
            sql = f"SELECT id, name, domain, node_type, description, tags, properties FROM kg_nodes WHERE node_type IN ({placeholders})"
            node_rows = c.execute(sql, node_types).fetchall()
        else:
            # Prioritize analytical, thesis, protocol, and wiki nodes
            sql = ("SELECT id, name, domain, node_type, description, tags, properties FROM kg_nodes "
                   "WHERE node_type IN ('ThesisNode', 'ProtocolNode', 'WikiNote', 'WikiSection', 'AnalyticalNode')")
            node_rows = c.execute(sql).fetchall()

            if not node_rows:
                node_rows = c.execute("SELECT id, name, domain, node_type, description, tags, properties FROM kg_nodes LIMIT 500").fetchall()

        for r in node_rows:
            props = json.loads(r["properties"]) if r["properties"] else {}
            nodes.append({
                "id": r["id"],
                "name": r["name"],
                "domain": r["domain"],
                "node_type": r["node_type"],
                "description": r["description"],
                "tags": r["tags"],
                "properties": props,
                "statement": props.get("raw_sentence") or r["description"] or r["name"],
                "action_instruction": props.get("raw_sentence") or r["description"] or r["name"],
                "confidence": props.get("confidence", 0.85),
                "ach_status": props.get("ach_status", "HYPOTHESIS"),
                "source_file": props.get("source_file", ""),
                "scene_id": props.get("scene_id", ""),
                "start_sec": props.get("start_sec", 0.0),
                "end_sec": props.get("end_sec", 0.0),
                "steps": props.get("steps", []),
                "safety_warnings": props.get("safety_warnings", [])
            })

        edge_rows = c.execute("SELECT source_id, target_id, relation, strength, properties FROM kg_edges").fetchall()
        for e in edge_rows:
            edges.append({
                "source_id": e["source_id"],
                "target_id": e["target_id"],
                "relation": e["relation"],
                "strength": e["strength"],
                "properties": json.loads(e["properties"]) if e["properties"] else {}
            })

        conn.close()
    except Exception as ex:
        sys.stderr.write(f"[ZettelkastenExporter] Warning reading DB {db_path}: {ex}\n")

    return nodes, edges


def export_all_zettelkasten_notes(
    extraction_result: Union[Dict[str, Any], List[Dict[str, Any]], str],
    output_dir: str = DEFAULT_WIKI_DIR,
    auto_reindex: bool = True
) -> List[str]:
    r"""
    Exports a batch of analytical entities into Zettelkasten Markdown notes and optionally
    triggers SuperGraph auto-reindexing into vazus.db.

    Args:
      extraction_result: Extraction dictionary (from KGBAnalyticalExtractor), list of node dicts,
                        or SQLite database file path string.
      output_dir: Path to target directory. Default: C:\vazus\services\memory\semantic\wiki
      auto_reindex: If True, invokes SuperGraphLinker to re-index generated notes into vazus.db.

    Returns:
      List of exported file path strings.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    # Handle string path to database
    if isinstance(extraction_result, (str, Path)):
        db_path_str = str(extraction_result)
        if Path(db_path_str).exists() or db_path_str.endswith(".db"):
            nodes, edges = _extract_nodes_and_edges_from_db(db_path_str)
        else:
            nodes = []

    # Handle dict extraction result
    elif isinstance(extraction_result, dict):
        if "nodes" in extraction_result:
            nodes.extend(extraction_result["nodes"])
        if "thesis_nodes" in extraction_result:
            nodes.extend(extraction_result["thesis_nodes"])
        if "protocol_nodes" in extraction_result:
            nodes.extend(extraction_result["protocol_nodes"])

        if "edges" in extraction_result:
            edges.extend(extraction_result["edges"])
        for k in ("causes_edges", "requires_edges", "contradicts_edges", "belongs_to_edges"):
            if k in extraction_result:
                edges.extend(extraction_result[k])

    # Handle list of node dicts
    elif isinstance(extraction_result, list):
        nodes = extraction_result

    # Deduplicate nodes by ID
    unique_nodes: Dict[str, Dict[str, Any]] = {}
    for n in nodes:
        n_dict = _extract_entity_fields(n)
        nid = n_dict.get("id") or n_dict.get("node_id") or f"node_{len(unique_nodes)}"
        if nid not in unique_nodes:
            unique_nodes[nid] = n_dict

    all_nodes_list = list(unique_nodes.values())
    all_nodes_map = {n.get("id"): n for n in all_nodes_list if n.get("id")}

    # Map edges per node
    node_edges_map: Dict[str, List[Dict[str, Any]]] = {}
    for edge in edges:
        s_id = edge.get("source_id")
        t_id = edge.get("target_id")
        if s_id:
            node_edges_map.setdefault(s_id, []).append(edge)
        if t_id:
            node_edges_map.setdefault(t_id, []).append(edge)

    exported_filepaths: List[str] = []
    for node in all_nodes_list:
        nid = node.get("id")
        r_edges = node_edges_map.get(nid, [])
        f_path = export_zettelkasten_note(
            entity_dict=node,
            output_dir=output_dir,
            related_edges=r_edges,
            all_nodes_map=all_nodes_map
        )
        exported_filepaths.append(f_path)

    # SuperGraph Integration (Auto-Reindex)
    if auto_reindex and exported_filepaths:
        try:
            if SuperGraphLinker is not None:
                linker = SuperGraphLinker(
                    db_path=Path(DEFAULT_DB_PATH),
                    wiki_dirs=[out_path]
                )
                linker.run_supergraph_integration()
            else:
                sys.stderr.write("[ZettelkastenExporter] SuperGraphLinker unavailable for auto_reindex.\n")
        except Exception as ex:
            import traceback
            sys.stderr.write(f"[ZettelkastenExporter] Error during SuperGraph re-indexing: {ex}\n{traceback.format_exc()}\n")

    return exported_filepaths
