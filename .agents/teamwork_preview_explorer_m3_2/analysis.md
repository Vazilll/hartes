# Milestone 3 (R3): Automated Zettelkasten Obsidian Wiki Exporter Architecture & Design Analysis

## 1. Executive Summary & Mission Objective
This document presents the detailed architectural design and interface specification for `vazus_core/zettelkasten_exporter.py`, fulfilling **Milestone 3 (R3: Automated Zettelkasten Obsidian Wiki Exporter)** of the `vazus SuperGraph OS`.

The primary role of the exporter is to transform structured Knowledge Graph entities (specifically `ThesisNode`, `ProtocolNode`, and graph relation edges `CAUSES`, `REQUIRES`, `CONTRADICTS`, `BELONGS_TO`) extracted by `vazus_core/kgb_analytical_extractor.py` or stored in SQLite SuperGraph databases (`vazus.db` / `dnts.db`) into human-readable, cross-linked Zettelkasten Markdown notes inside the Obsidian vault (`C:\vazus\services\memory\semantic\wiki\`).

Key features designed:
1. **Zettel Note Generation**: Standardized YAML frontmatter + structured Markdown body + bidirectional Wikilinks (`[[Note Title]]`).
2. **Obsidian Map of Content (MOC)**: Automated updating of `_index.md` with vault metrics, tag index, ACH status summaries, and categorized note listings.
3. **Dual Integration Pipeline**: Direct consumption of `kgb_analytical_extractor.py` in-memory extraction dicts and database synchronization from `vazus.db` / `memory/dnts.db` SQLite `kg_nodes` and `kg_edges` tables.
4. **Robust Path & Sanitization**: Cross-platform path resolution with fallbacks and strict Windows-safe filename sanitization preventing invalid characters and MAX_PATH truncation issues.

---

## 2. Code Architecture & Component Overview (`vazus_core/zettelkasten_exporter.py`)

```
                          ┌──────────────────────────────────────────────────┐
                          │   KGB/FSB ИАД + ACH Analytical Extractor Engine  │
                          │   (vazus_core/kgb_analytical_extractor.py)       │
                          └────────────────────────┬─────────────────────────┘
                                                   │
                                                   ▼
┌─────────────────────────┐               ┌──────────────────────────────────┐
│   SQLite SuperGraph     │               │   In-Memory Extraction Dict      │
│  (vazus.db / dnts.db)   │               │   (ThesisNode, ProtocolNode,     │
│  kg_nodes / kg_edges    │               │   CAUSES/REQUIRES/CONTRADICTS)   │
└────────────┬────────────┘               └────────────────┬─────────────────┘
             │                                             │
             └──────────────────────┬──────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │   ZettelkastenExporter (vazus_core/zettelkasten_exporter.py)│
       │                                                         │
       │  • resolve_wiki_directory()                             │
       │  • sanitize_zettel_filename()                           │
       │  • ZettelNote data model & markdown generator           │
       │  • export_thesis_to_zettel()                            │
       │  • export_protocol_to_zettel()                          │
       │  • export_kgb_result_to_wiki()                          │
       │  • sync_db_to_wiki()                                    │
       │  • update_obsidian_index()                              │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │             Obsidian Wiki Vault Directory               │
       │       (C:\vazus\services\memory\semantic\wiki\)         │
       │                                                         │
       │  • Thesis_<title>_<id>.md                               │
       │  • Protocol_<title>_<id>.md                             │
       │  • ACH_Matrix_<scene_id>.md                             │
       │  • _index.md (Map of Content / Vault Master Index)      │
       └─────────────────────────────────────────────────────────┘
```

---

## 3. Class and Function Interface Specifications

### 3.1 `ZettelNote` Data Class Model
Represents an in-memory intermediate model of a Zettelkasten note before serializing to Markdown.

```python
class ZettelNote:
    """Represents a single Zettelkasten note before Markdown serialization."""
    def __init__(
        self,
        id: str,
        title: str,
        statement_or_instruction: str,
        node_type: str = "ThesisNode",  # ThesisNode | ProtocolNode | SceneContainer | ACHMatrixNote
        domain: str = "kgb_analytics",
        confidence: float = 0.85,
        ach_status: str = "HYPOTHESIS",  # HYPOTHESIS | ACCEPTED | REJECTED | DISPROVED
        source_file: str = "",
        scene_id: str = "",
        tags: Optional[List[str]] = None,
        properties: Optional[Dict[str, Any]] = None,
        causes_links: Optional[List[Tuple[str, float]]] = None,       # [(target_title_or_id, strength)]
        caused_by_links: Optional[List[Tuple[str, float]]] = None,
        requires_links: Optional[List[Tuple[str, float]]] = None,     # [(prereq_title_or_id, strength)]
        required_by_links: Optional[List[Tuple[str, float]]] = None,
        contradicts_links: Optional[List[Tuple[str, float]]] = None,  # [(opposing_title_or_id, strength)]
        belongs_to_links: Optional[List[Tuple[str, float]]] = None,   # [(scene_container_title, strength)]
        created_at: Optional[str] = None
    ):
        self.id = id
        self.title = title
        self.statement_or_instruction = statement_or_instruction
        self.node_type = node_type
        self.domain = domain
        self.confidence = confidence
        self.ach_status = ach_status
        self.source_file = source_file
        self.scene_id = scene_id
        self.tags = tags or ["iad", node_type.lower().replace("node", "")]
        self.properties = properties or {}
        self.causes_links = causes_links or []
        self.caused_by_links = caused_by_links or []
        self.requires_links = requires_links or []
        self.required_by_links = required_by_links or []
        self.contradicts_links = contradicts_links or []
        self.belongs_to_links = belongs_to_links or []
        self.created_at = created_at or time.strftime("%Y-%m-%d %H:%M:%S")

    def to_markdown(self) -> str:
        """Renders the complete Obsidian Markdown content string with YAML frontmatter and [[Wikilinks]]."""
        ...
```

### 3.2 `ZettelkastenExporter` Class Interface

```python
class ZettelkastenExporter:
    """
    Automated Zettelkasten Obsidian Wiki Exporter Engine.
    Converts ThesisNode and ProtocolNode entities into cross-linked Obsidian Markdown notes
    and manages vault indexes.
    """

    def __init__(
        self,
        wiki_dir: Optional[str] = None,
        db_path: str = DEFAULT_DB_PATH,
        auto_index: bool = True
    ):
        self.wiki_dir = resolve_wiki_directory(wiki_dir)
        self.db_path = db_path
        self.auto_index = auto_index

    def export_thesis_to_zettel(
        self,
        thesis: Union[ThesisNode, Dict[str, Any]],
        related_edges: Optional[List[Dict[str, Any]]] = None
    ) -> Path:
        """
        Exports a single ThesisNode (or thesis dict) to an individual Zettel markdown note file.
        Returns the Path to the written markdown file.
        """
        ...

    def export_protocol_to_zettel(
        self,
        protocol: Union[ProtocolNode, Dict[str, Any]],
        related_edges: Optional[List[Dict[str, Any]]] = None
    ) -> Path:
        """
        Exports a single ProtocolNode (or protocol dict) to an individual Zettel markdown note file.
        Returns the Path to the written markdown file.
        """
        ...

    def export_kgb_result_to_wiki(
        self,
        extraction_result: Dict[str, Any],
        update_index: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Processes complete output dictionary from KGBAnalyticalExtractor.extract().
        Translates all nodes and edges into Zettel notes and writes them to wiki_dir.
        Optionally updates _index.md.
        
        Returns:
            Dict containing:
              - status: "SUCCESS"
              - exported_notes_count: int
              - thesis_notes_created: int
              - protocol_notes_created: int
              - ach_matrix_notes_created: int
              - files_written: List[str]
              - index_path: str
        """
        ...

    def export_kb_to_wiki(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        update_index: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        General knowledge base export method for arbitrary node and edge lists.
        """
        ...

    def sync_db_to_wiki(
        self,
        db_path: Optional[str] = None,
        domain: Optional[str] = None,
        update_index: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Queries kg_nodes and kg_edges from SQLite database (vazus.db / dnts.db),
        reconstructs entities and relations, exports all to wiki_dir, and updates _index.md.
        """
        ...

    def update_obsidian_index(self) -> Path:
        """
        Scans wiki_dir for all Markdown notes, parses frontmatter metadata, and generates/overwrites _index.md.
        """
        ...
```

### 3.3 Top-Level Helper Functions Interface

```python
def export_thesis_to_zettel(
    thesis: Union[ThesisNode, Dict[str, Any]],
    wiki_dir: str = DEFAULT_WIKI_DIR
) -> Path:
    """Standalone function to export a single thesis node."""
    exporter = ZettelkastenExporter(wiki_dir=wiki_dir, auto_index=False)
    return exporter.export_thesis_to_zettel(thesis)

def export_kb_to_wiki(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    wiki_dir: str = DEFAULT_WIKI_DIR
) -> Dict[str, Any]:
    """Standalone function to export arbitrary nodes and edges."""
    exporter = ZettelkastenExporter(wiki_dir=wiki_dir)
    return exporter.export_kb_to_wiki(nodes, edges)

def export_kgb_extraction_to_zettel(
    extraction_result: Dict[str, Any],
    wiki_dir: str = DEFAULT_WIKI_DIR
) -> Dict[str, Any]:
    """Standalone function to export KGB extractor output dict."""
    exporter = ZettelkastenExporter(wiki_dir=wiki_dir)
    return exporter.export_kgb_result_to_wiki(extraction_result)

def sync_supergraph_db_to_zettel(
    db_path: str = DEFAULT_DB_PATH,
    wiki_dir: str = DEFAULT_WIKI_DIR
) -> Dict[str, Any]:
    """Standalone function to sync SQLite SuperGraph database to Zettelkasten wiki."""
    exporter = ZettelkastenExporter(wiki_dir=wiki_dir, db_path=db_path)
    return exporter.sync_db_to_wiki(db_path=db_path)

def update_zettelkasten_index(wiki_dir: str = DEFAULT_WIKI_DIR) -> Path:
    """Standalone function to regenerate _index.md for specified wiki directory."""
    exporter = ZettelkastenExporter(wiki_dir=wiki_dir, auto_index=False)
    return exporter.update_obsidian_index()

def sanitize_zettel_filename(title: str, node_id: str = "", max_length: int = 80) -> str:
    """Utility function to sanitize title strings into safe Windows/Linux filenames."""
    ...
```

---

## 4. File System Operations & Directory Resolution

### 4.1 Directory Resolution Order
When instantiating `ZettelkastenExporter`, the target directory is resolved as follows:
1. `requested_path` (if explicitly passed in constructor or helper call).
2. `DEFAULT_WIKI_DIR`: `C:\vazus\services\memory\semantic\wiki` (Primary workspace vault).
3. `SECONDARY_WIKI_DIR`: `C:\vazus\memory\semantic\wiki` (Secondary fallback).
4. `TERTIARY_WIKI_DIR`: `C:\vazus\wiki` (Local project root fallback).

Resolution helper logic:
```python
DEFAULT_WIKI_DIR = r"C:\vazus\services\memory\semantic\wiki"
FALLBACK_WIKI_DIRS = [
    r"C:\vazus\memory\semantic\wiki",
    r"C:\vazus\wiki"
]

def resolve_wiki_directory(requested_path: Optional[str] = None) -> Path:
    if requested_path:
        p = Path(requested_path)
        p.mkdir(parents=True, exist_ok=True)
        return p

    primary = Path(DEFAULT_WIKI_DIR)
    try:
        primary.mkdir(parents=True, exist_ok=True)
        return primary
    except Exception as e:
        sys.stderr.write(f"[Zettelkasten Exporter] Warning: Cannot create primary dir {primary}: {e}\n")

    for fb in FALLBACK_WIKI_DIRS:
        try:
            fb_path = Path(fb)
            fb_path.mkdir(parents=True, exist_ok=True)
            return fb_path
        except Exception:
            continue

    # Final emergency fallback: temporary directory
    tmp_path = Path(tempfile.gettempdir()) / "vazus_wiki"
    tmp_path.mkdir(parents=True, exist_ok=True)
    return tmp_path
```

---

## 5. Filename Sanitization & Collision Prevention

### 5.1 Rules for Filename Sanitization
Windows filesystems impose restrictions:
- Characters prohibited: `< > : " / \ | ? *`
- Reserved names: `CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`.
- Maximum Path length: 260 characters (MAX_PATH limit).

Sanitization function implementation strategy:
```python
def sanitize_zettel_filename(title: str, node_id: str = "", max_length: int = 80) -> str:
    if not title:
        title = node_id or "unnamed_note"
    
    # 1. Normalize punctuation & remove forbidden Windows characters
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', ' ', title)
    
    # 2. Normalize whitespace
    cleaned = re.sub(r'\s+', '_', cleaned.strip())
    
    # 3. Strip leading/trailing dots or underscores
    cleaned = cleaned.strip('._')
    
    # 4. Truncate length
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip('._')
    
    # 5. Append short hash of node_id to prevent collision
    if node_id:
        short_hash = hashlib.md5(node_id.encode('utf-8')).hexdigest()[:6]
        filename = f"{cleaned}_{short_hash}.md"
    else:
        filename = f"{cleaned}.md"
        
    return filename
```

---

## 6. Obsidian MOC Index Generator (`_index.md`)

The `_index.md` file serves as the **Map of Content (MOC)** for Obsidian vaults. It is automatically maintained whenever notes are exported or updated.

### 6.1 `_index.md` Structural Layout

```markdown
# 🗂️ vazus SuperGraph Obsidian Wiki Index

> **Vault Location**: `C:\vazus\services\memory\semantic\wiki`  
> **Last Synchronized**: 2026-07-24 15:57:27  
> **Total Notes Index**: 35  

---

## 📊 Vault Executive Metrics

| Metric Category | Count | Status Overview |
| :--- | :--- | :--- |
| **Total Thesis Notes** | 18 | `#thesis` |
| **Total Protocol Notes** | 12 | `#protocol` |
| **Research & Traces** | 5 | `#research` |
| **ACCEPTED Claims** | 14 | `#ach_accepted` (High Confidence) |
| **REJECTED / DISPROVED Claims** | 4 | `#ach_rejected` (Contradicted) |

---

## 🏷️ Vault Tag Index
- `#iad` — Information-Analytical Diagnostics
- `#thesis` — Fact assertions & scientific claims
- `#protocol` — Action directives & dosage schedules
- `#ach_accepted` — Validated hypotheses
- `#ach_rejected` — Contradicted / rejected hypotheses
- `#causes` — Causal graph relations
- `#requires` — Prerequisite & co-factor relations
- `#contradicts` — Inconsistency graph edges

---

## 💡 Thesis Nodes Index
- [[Thesis_Витамин_D3_стимулирует_остеокальцин_a1b2c3]] — *Confidence*: `0.95` | *Status*: `ACCEPTED`
- [[Thesis_Суставная_разминка_снижает_микротравмы_b2c3d4]] — *Confidence*: `0.90` | *Status*: `ACCEPTED`
- [[Thesis_Монотерапия_Витамином_D3_безопасна_c3d4e5]] — *Confidence*: `0.65` | *Status*: `REJECTED`

---

## ⚙️ Protocol Nodes Index
- [[Protocol_Циклирование_Бора_10_мг_d4e5f6]] — *Periodicity*: `2 недели через 1 неделю`
- [[Protocol_Приём_Витамина_K2_и_Магния_e5f6g7]] — *Safety*: `Во избежание кальцификации`

---

## 📄 Research & Subagent Notes Index
- [[Research_SuperGraph_OS_Architecture]]
- [[M5_Reviewer2_Audit_Note]]
- [[AI_Lessons_and_Mistakes]]
```

---

## 7. Integration with `kgb_analytical_extractor.py` & `vazus.db` Storage

### 7.1 Direct In-Memory Extraction Pipeline
When `extract_kgb_analytics()` executes, it generates a dictionary containing:
- `thesis_nodes`: List of dicts (id, name, statement, confidence, ach_status, source_file, scene_id, tags, properties)
- `protocol_nodes`: List of dicts (id, name, action_instruction, steps, frequency_periodicity, safety_warnings, tags, properties)
- `causes_edges`, `requires_edges`, `contradicts_edges`, `belongs_to_edges`
- `ach_matrix_summary`: ACH hypothesis matrix evaluation dict

`export_kgb_result_to_wiki()` takes this payload and:
1. Maps node IDs to formatted Zettel note filenames.
2. Formats bidirectional Wikilinks:
   - CAUSES: `[[Thesis_B]] (Strength: 0.90)` in Thesis A, and `[[Thesis_A]]` in Thesis B under `Caused By`.
   - REQUIRES: `[[Protocol_B]] (Strength: 0.85)` in Thesis A, and `[[Thesis_A]]` in Protocol B under `Required By`.
   - CONTRADICTS: `[[Thesis_C]] (Strength: 0.95)` in Thesis A, and `[[Thesis_A]]` in Thesis C under `Contradicts`.
3. Writes individual Zettel `.md` files for all nodes.
4. Generates an ACH matrix note `ACH_Matrix_<scene_id>.md` rendering a markdown table of evidence vs hypotheses.
5. Invokes `update_obsidian_index()`.

### 7.2 SQLite Database Storage Sync (`vazus.db` / `dnts.db`)
`sync_db_to_wiki(db_path)` reads from:
- Table `kg_nodes`: `(id, name, domain, node_type, description, tags, properties, embedding_json)`
- Table `kg_edges`: `(source_id, target_id, relation, strength, properties)`

It deserializes JSON `properties` column, reconstructs adjacency graph, generates corresponding Zettel Notes, and writes them to `wiki_dir`.

---

## 8. Test Suite Strategy (`tests/test_zettelkasten_exporter.py`)

A comprehensive unit and integration test suite will verify:
1. **Directory resolution**: Correct fallback sequence when target paths are specified or omitted.
2. **Filename sanitization**: Windows character removal, length truncation, and collision prevention.
3. **Thesis & Protocol Note formatting**: Frontmatter parsing, Wikilink validity, property serialization.
4. **KGB Extractor output integration**: Converting `extract_kgb_analytics()` output dict to Zettel files.
5. **SuperGraph SQLite DB sync**: Reading `vazus.db` table records and creating Zettel note tree.
6. **Obsidian index update**: Correct generation of `_index.md` table of content.

---

## 9. Conclusion
The proposed architecture for `vazus_core/zettelkasten_exporter.py` provides a clean, robust, and extensible implementation for Milestone 3 (R3). It seamlessly bridges the analytical extraction pipeline (`kgb_analytical_extractor.py`) and persistent storage (`vazus.db` / `dnts.db`) with human-readable Zettelkasten knowledge representation in Obsidian Wiki format (`C:\vazus\services\memory\semantic\wiki\`).
