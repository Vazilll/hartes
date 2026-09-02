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
import re
import json
import logging
import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set, Union

logger = logging.getLogger("vazus_core.zettelkasten_exporter")

try:
    from vazus_core.engine.config import settings as _settings
    DEFAULT_WIKI_DIR = str(_settings.WIKI_DIR)
    DEFAULT_DB_PATH = str(_settings.VAZUS_DB_PATH)
except ImportError:
    DEFAULT_WIKI_DIR = os.getenv("VAZUS_WIKI_DIR", r"C:\vazus\services\memory\semantic\wiki")
    DEFAULT_DB_PATH = os.getenv("VAZUS_DB_PATH", r"C:\vazus\services\memory\vazus.db")

# Try importing SuperGraphLinker via canonical path only
try:
    from vazus_core.engine.supergraph_linker import SuperGraphLinker
except ImportError:
    SuperGraphLinker = None


def sanitize_zettel_id(raw_id: str) -> str:
    """Sanitizes raw entity ID or title into a standard Zettel ID string: 'Zettel_<clean_identifier>'."""
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


def sanitize_filename(zettel_id: str) -> str:
    """Sanitizes Zettel ID into safe filename ending with .md."""
    clean = re.sub(r'[\\/*?:"<>|]', "", zettel_id)
    if not clean.endswith(".md"):
        clean += ".md"
    return clean


def format_yaml_frontmatter(metadata: Dict[str, Any]) -> str:
    """Generates standard YAML frontmatter block for Obsidian Zettelkasten notes."""
    z_id = metadata.get("id", "Zettel_entity_unknown")
    title = metadata.get("title", "Untitled Note").replace('"', '\\"')
    date_str = metadata.get("date", datetime.date.today().isoformat())
    domain = metadata.get("domain", "kgb_analytics")
    status = metadata.get("status", "HYPOTHESIS")

    raw_tags = metadata.get("tags", ["iad", "zettel"])
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

    raw_sources = metadata.get("sources", ["SuperGraph Database Index"])
    if isinstance(raw_sources, str):
        sources_list = [s.strip() for s in raw_sources.split(",") if s.strip()]
    elif isinstance(raw_sources, (list, set, tuple)):
        sources_list = [str(s).strip() for s in raw_sources if str(s).strip()]
    else:
        sources_list = ["SuperGraph Database Index"]

    if not sources_list:
        sources_list = ["SuperGraph Database Index"]

    lines = ["---", f"id: {z_id}", f'title: "{title}"', f"date: {date_str}", "tags:"]
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
    """Normalizes entity dict or object into standardized dict format."""
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

    props = d.get("properties", {})
    if isinstance(props, str):
        try:
            props = json.loads(props)
        except Exception as e:
            logger.debug("parse properties in extract entity fields non-fatal: %s", e)
            props = {}
    elif not isinstance(props, dict):
        props = {}

    d["properties_dict"] = props
    return d


def _build_note_sections(e: dict, name: str, node_type: str, domain: str, status: str, zettel_id: str) -> list[str]:
    """Builds the H2 core claim, analytical evidence, and action checklist lines."""
    lines = []
    if node_type == "ProtocolNode":
        lines.extend(["## Protocol Directives", f"> **Operational Directive**: {e.get('action_instruction') or name}", ""])
    else:
        lines.extend(["## Core Claim / Thesis", f"> **Thesis Assertion**: {e.get('statement') or name}", ""])

    confidence = e.get("confidence") or e.get("confidence_score") or 0.85
    lines.extend([
        "## Analytical Evidence & Context",
        f"- **Confidence Score**: `{confidence:.2f}`",
        f"- **ACH Status**: `{status}`",
        f"- **Entity Type**: `{node_type}`",
        f"- **Domain Context**: `{domain}`"
    ])
    start_sec = e.get("start_sec", 0.0)
    end_sec = e.get("end_sec", 0.0)
    if start_sec > 0 or end_sec > 0:
        lines.append(f"- **Media Scene Offset**: `{start_sec:.1f}s - {end_sec:.1f}s`")

    steps = e.get("steps") or e.get("properties_dict", {}).get("steps", [])
    if steps and isinstance(steps, list):
        lines.append("\n### Operational Steps:")
        for idx, step in enumerate(steps, 1):
            lines.append(f"{idx}. {step}")

    safety = e.get("safety_warnings") or e.get("properties_dict", {}).get("safety_warnings", [])
    if safety and isinstance(safety, list):
        lines.append("\n### Safety & Risk Warnings:")
        for warn in safety:
            lines.append(f"- ⚠️ **Warning**: {warn}")

    periodicity = e.get("frequency_periodicity") or e.get("properties_dict", {}).get("frequency_periodicity", "")
    if periodicity:
        lines.append(f"- **Frequency / Periodicity**: `{periodicity}`")

    lines.extend([
        "", "## Action Checklist",
        f"- [ ] Verify empirical evidence and source provenance for `{zettel_id}`",
        f"- [ ] Conduct ACH matrix re-evaluation under updated `{status}` framework"
    ])
    if steps and isinstance(steps, list):
        for idx, step in enumerate(steps, 1):
            lines.append(f"- [ ] Execute Step {idx}: {str(step)[:100].replace(chr(10), ' ')}")
    else:
        lines.append(f"- [ ] Audit operational safety directives and protocol compliance for `{name[:50]}`")
    lines.append("")
    return lines


def _build_wikilinks_section(raw_id: str, domain: str, related_edges: Optional[List[Dict[str, Any]]], all_nodes_map: Optional[Dict[str, Dict[str, Any]]]) -> list[str]:
    """Constructs >= 3 bidirectional Wikilinks for the note."""
    wikilinks: Set[str] = set()
    if related_edges:
        for edge in related_edges:
            src = edge.get("source_id", "")
            tgt = edge.get("target_id", "")
            other_id = tgt if src == raw_id else src
            if not other_id or other_id == raw_id:
                continue
            target_zettel = sanitize_zettel_id(other_id)
            label = edge.get("relation", "LINK").replace("_", " ").title()
            if all_nodes_map and other_id in all_nodes_map:
                t_title = all_nodes_map[other_id].get("name") or all_nodes_map[other_id].get("statement") or target_zettel
                label = f"{t_title[:40]} ({edge.get('relation', 'LINK')})"
            wikilinks.add(f"- [[{target_zettel}|{label}]]")

    defaults = [
        "- [[Zettel_SuperGraph_Hub|SuperGraph Knowledge Hub]]",
        "- [[Zettel_Karpathy_Memory_Index|Karpathy Memory Index]]",
        "- [[Zettel_ACH_Analytical_Framework|ACH Analytical Framework]]",
        "- [[Zettel_IAD_Decomposition_Protocol|ИAД Operational Protocol]]",
        f"- [[Zettel_{domain}_Overview|{domain.replace('_', ' ').title()} Index]]"
    ]
    for d_link in defaults:
        if len(wikilinks) >= 3:
            break
        wikilinks.add(d_link)
    return ["## Related Notes & Wikilinks"] + sorted(wikilinks) + [""]


def export_zettelkasten_note(
    entity_dict: Union[Dict[str, Any], Any],
    output_dir: str = DEFAULT_WIKI_DIR,
    related_edges: Optional[List[Dict[str, Any]]] = None,
    all_nodes_map: Optional[Dict[str, Dict[str, Any]]] = None
) -> str:
    """Exports an analytical entity as a Zettelkasten Markdown note in Obsidian format."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    e = _extract_entity_fields(entity_dict)
    raw_id = e.get("id") or e.get("node_id") or "entity_unknown"
    zettel_id = sanitize_zettel_id(raw_id)
    name = e.get("name") or e.get("statement") or e.get("action_instruction") or "Untitled Note"
    node_type = e.get("node_type", "ThesisNode")
    domain = e.get("domain", "kgb_analytics")
    status = e.get("ach_status") or e.get("status") or ("PROTOCOL" if node_type == "ProtocolNode" else "HYPOTHESIS")

    sources = e.get("evidence_sources") or []
    src_file = e.get("source_file") or e.get("properties_dict", {}).get("source_file", "")
    if src_file and src_file not in sources:
        sources.append(src_file)
    scene_id = e.get("scene_id") or e.get("properties_dict", {}).get("scene_id", "")
    if scene_id:
        sources.append(f"Scene: {scene_id}")
    if not sources:
        sources = ["SuperGraph Database Index"]

    tags = e.get("tags", ["iad", "thesis"])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    frontmatter = format_yaml_frontmatter({
        "id": zettel_id, "title": name, "date": datetime.date.today().isoformat(),
        "tags": tags, "domain": domain, "status": status, "sources": sources
    })

    content_lines = [frontmatter, "", f"# {name}", ""]
    content_lines.extend(_build_note_sections(e, name, node_type, domain, status, zettel_id))
    content_lines.extend(_build_wikilinks_section(raw_id, domain, related_edges, all_nodes_map))

    file_path = out_path / sanitize_filename(zettel_id)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(content_lines))

    return str(file_path.resolve())


def _query_kg_nodes_from_db(c: sqlite3.Cursor, node_types: Optional[List[str]]) -> List[Dict[str, Any]]:
    """Fetches kg_nodes from database cursor and decodes properties."""
    if node_types:
        placeholders = ",".join(["?"] * len(node_types))
        sql = f"SELECT id, name, domain, node_type, description, tags, properties FROM kg_nodes WHERE node_type IN ({placeholders})"
        node_rows = c.execute(sql, node_types).fetchall()
    else:
        sql = "SELECT id, name, domain, node_type, description, tags, properties FROM kg_nodes WHERE node_type IN ('ThesisNode', 'ProtocolNode', 'WikiNote', 'WikiSection', 'AnalyticalNode')"
        node_rows = c.execute(sql).fetchall()
        if not node_rows:
            node_rows = c.execute("SELECT id, name, domain, node_type, description, tags, properties FROM kg_nodes LIMIT 500").fetchall()

    nodes = []
    for r in node_rows:
        try:
            props = json.loads(r["properties"]) if r["properties"] else {}
        except Exception as e:
            logger.debug("parse properties non-fatal: %s", e)
            props = {}
        nodes.append({
            "id": r["id"], "name": r["name"], "domain": r["domain"],
            "node_type": r["node_type"], "description": r["description"],
            "tags": r["tags"], "properties": props,
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
    return nodes


def _query_kg_edges_from_db(c: sqlite3.Cursor) -> List[Dict[str, Any]]:
    """Fetches and decodes kg_edges from database cursor."""
    edge_rows = c.execute("SELECT source_id, target_id, relation, strength, properties FROM kg_edges").fetchall()
    edges = []
    for e in edge_rows:
        try:
            props = json.loads(e["properties"]) if e["properties"] else {}
        except Exception as ex:
            logger.debug("parse edge properties non-fatal: %s", ex)
            props = {}
        edges.append({
            "source_id": e["source_id"], "target_id": e["target_id"],
            "relation": e["relation"], "strength": e["strength"],
            "properties": props
        })
    return edges


def _extract_nodes_and_edges_from_db(
    db_path: str,
    node_types: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Helper function to load analytical nodes and edges from SQLite SuperGraph database."""
    if not Path(db_path).exists():
        return [], []
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        nodes = _query_kg_nodes_from_db(c, node_types)
        edges = _query_kg_edges_from_db(c)
        conn.close()
        return nodes, edges
    except Exception as ex:
        logger.debug("read DB %s non-fatal: %s", db_path, ex)
        return [], []


def _collect_nodes_and_edges(extraction_result: Union[Dict[str, Any], List[Dict[str, Any]], str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extracts raw nodes and edges from dict, list, or path."""
    if isinstance(extraction_result, (str, Path)):
        db_path_str = str(extraction_result)
        if Path(db_path_str).exists() or db_path_str.endswith(".db"):
            return _extract_nodes_and_edges_from_db(db_path_str)
        return [], []
    if isinstance(extraction_result, dict):
        nodes, edges = [], []
        for k in ("nodes", "thesis_nodes", "protocol_nodes"):
            if k in extraction_result:
                nodes.extend(extraction_result[k])
        if "edges" in extraction_result:
            edges.extend(extraction_result["edges"])
        for k in ("causes_edges", "requires_edges", "contradicts_edges", "belongs_to_edges"):
            if k in extraction_result:
                edges.extend(extraction_result[k])
        return nodes, edges
    if isinstance(extraction_result, list):
        return list(extraction_result), []
    return [], []


def export_all_zettelkasten_notes(
    extraction_result: Union[Dict[str, Any], List[Dict[str, Any]], str],
    output_dir: str = DEFAULT_WIKI_DIR,
    auto_reindex: bool = True,
    db_path: Optional[Union[str, Path]] = None
) -> List[str]:
    """Exports a batch of analytical entities into Zettelkasten Markdown notes."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    nodes, edges = _collect_nodes_and_edges(extraction_result)

    unique_nodes: Dict[str, Dict[str, Any]] = {}
    for n in nodes:
        n_dict = _extract_entity_fields(n)
        nid = n_dict.get("id") or n_dict.get("node_id") or f"node_{len(unique_nodes)}"
        if nid not in unique_nodes:
            unique_nodes[nid] = n_dict

    all_nodes_list = list(unique_nodes.values())
    all_nodes_map = {n.get("id"): n for n in all_nodes_list if n.get("id")}
    node_edges_map: Dict[str, List[Dict[str, Any]]] = {}
    for edge in edges:
        for endp in ("source_id", "target_id"):
            if edge.get(endp):
                node_edges_map.setdefault(edge[endp], []).append(edge)

    exported_filepaths: List[str] = []
    for node in all_nodes_list:
        f_path = export_zettelkasten_note(
            entity_dict=node, output_dir=output_dir,
            related_edges=node_edges_map.get(node.get("id"), []),
            all_nodes_map=all_nodes_map
        )
        exported_filepaths.append(f_path)

    if auto_reindex and exported_filepaths and SuperGraphLinker is not None:
        try:
            target_db = Path(db_path) if db_path else Path(DEFAULT_DB_PATH)
            linker = SuperGraphLinker(db_path=target_db, wiki_dirs=[out_path])
            linker.run_supergraph_integration()
        except Exception as ex:
            logger.debug("SuperGraph re-indexing non-fatal: %s", ex)

    return exported_filepaths


class ZettelkastenExporter:
    """
    Object-oriented wrapper for Zettelkasten Obsidian Wiki Export.
    """

    def __init__(self, wiki_dir: Union[Path, str] = DEFAULT_WIKI_DIR, db_path: Union[Path, str] = DEFAULT_DB_PATH):
        self.wiki_dir = Path(wiki_dir)
        self.db_path = Path(db_path)
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        (self.wiki_dir / "Commits").mkdir(exist_ok=True)
        (self.wiki_dir / "Insights").mkdir(exist_ok=True)

    def export_note(self, entity_dict: Dict[str, Any], related_edges: Optional[List[Dict[str, Any]]] = None) -> str:
        return export_zettelkasten_note(
            entity_dict=entity_dict,
            output_dir=self.wiki_dir,
            related_edges=related_edges or []
        )

    def export_all(self, extraction_result: Union[Dict[str, Any], List[Dict[str, Any]]], auto_reindex: bool = False) -> List[str]:
        return export_all_zettelkasten_notes(
            extraction_result=extraction_result,
            output_dir=self.wiki_dir,
            auto_reindex=auto_reindex
        )

    def export_commit_note(self, commit_hash: str, message: str, files_changed: List[str], branch: str = "vazus-dev") -> str:
        short_hash = commit_hash[:7] if commit_hash else "unknown"
        fpath = self.wiki_dir / "Commits" / f"{short_hash}.md"
        links = "\n".join(f"- [[{Path(f).stem}]] (`{f}`)" for f in files_changed)
        body = f"""---
type: commit
hash: "{commit_hash}"
branch: "{branch}"
date: "{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
tags:
  - commit
  - provenance
---

# Commit {short_hash}: {message}

## 📁 Modified Components
{links if links else "- No files"}
"""
        fpath.write_text(body, encoding="utf-8")
        return str(fpath)

    def export_insight_note(self, title: str, category: str, content_text: str) -> str:
        clean_title = re.sub(r'[\\/*?:"<>| ]', '_', title)[:60]
        fpath = self.wiki_dir / "Insights" / f"{clean_title}.md"
        body = f"""---
type: insight
category: "{category}"
date: "{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
tags:
  - insight
  - {category}
---

# {title}

## 💡 Summary & Insights
{content_text}
"""
        fpath.write_text(body, encoding="utf-8")
        return str(fpath)
