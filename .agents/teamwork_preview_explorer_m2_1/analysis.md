# Architectural Requirements & Methodology Analysis for `vazus_core/kgb_analytical_extractor.py`
**Module**: Milestone 2 — R2: KGB/FSB Analytical Knowledge Extractor (ИАД + ACH)  
**Author**: Explorer 1  
**Target File**: `C:\vazus\vazus_core\kgb_analytical_extractor.py`  
**Database Targets**: `C:\vazus\vazus.db` and `C:\vazus\services\memory\vazus.db` (`kg_nodes`, `kg_edges` with 768D embeddings)

---

## 1. Executive Summary & Objective

Milestone 2 (R2) introduces the **KGB/FSB Analytical Knowledge Extractor** (`kgb_analytical_extractor.py`), designed to transform raw audio/video scene transcripts (produced by `vazus_core/multimodal_knowledge.py`) or plain text inputs into structured knowledge graphs in SQLite (`vazus.db`).

The extractor operationalizes two intelligence methodologies:
1. **КГБ/ФСБ ИАД (Информационно-Аналитическая Диагностика / Information-Analytical Diagnostics)**: Decomposing narrative content into atomic declarative assertions (`ThesisNode`) and imperative operational rules/directives (`ProtocolNode`).
2. **ACH (Analysis of Competing Hypotheses - Richards J. Heuer Jr.)**: Evaluating evidence consistency/inconsistency matrices across competing analytical hypotheses, heavily scoring logical contradictions (`CONTRADICTS`).

---

## 2. KGB/FSB ИАД & ACH Methodology Design

### 2.1 Information-Analytical Diagnostics (ИАД) Framework

The ИАД methodology addresses the problem of narrative noise, subjective framing, and cognitive biases in intelligence transcripts. Instead of storing large paragraph text, ИАД applies atomic extraction:

```
                          [ Raw Scene / Text Input ]
                                      │
                                      ▼
                        [ Text Normalization & Tokenization ]
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼                                         ▼
        [ Declarative Claims ]                    [ Imperative Directives ]
                 │                                         │
                 ▼                                         ▼
          [ ThesisNode ]                           [ ProtocolNode ]
                 │                                         │
                 └────────────────────┬────────────────────┘
                                      ▼
                 [ Relationship Engine (CAUSES, REQUIRES, CONTRADICTS) ]
                                      │
                                      ▼
                 [ 768D Embedding & SQLite SuperGraph Indexing ]
```

#### Key Diagnostic Principles:
1. **Atomic Independence**: Every `ThesisNode` and `ProtocolNode` must be a self-contained proposition capable of independent validation, vector indexing, and active recall testing.
2. **Categorical Separation**:
   - **Fact/Analytical Thesis (`ThesisNode`)**: What IS true or hypothesized about reality (e.g., *"Magnesium deficiency impairs hepatic CYP2R1 hydroxylation"*).
   - **Operational Protocol (`ProtocolNode`)**: What SHOULD BE DONE (e.g., *"Take 400mg Magnesium Glycinate daily 30 minutes before sleep"*).
3. **Certainty Weighting**: Each extracted node is assigned a confidence score $C \in [0.0, 1.0]$ based on modal verbs, source credibility, and linguistic certainty markers.

---

### 2.2 Analysis of Competing Hypotheses (ACH) Framework

ACH is an intelligence analysis standard designed by Richards Heuer to eliminate confirmation bias.

#### Analytical Workflow in `kgb_analytical_extractor.py`:
1. **Hypothesis Matrix Construction**:
   Given hypotheses $H = \{H_1, H_2, \dots, H_n\}$ and extracted evidence nodes $E = \{E_1, E_2, \dots, E_m\}$ (where $E_i$ are `ThesisNode` instances from scenes).
2. **Consistency Evaluation ($M_{i, j}$)**:
   For each evidence item $E_i$ and hypothesis $H_j$:
   - $+1.0$ ($C$ - Consistent / Supporting)
   - $0.0$ ($N$ - Neutral / Irrelevant)
   - $-1.0$ ($I$ - Inconsistent / Contradictory)
3. **Weighted Inconsistency Scoring ($IS(H_j)$)**:
   $$IS(H_j) = \sum_{i=1}^{m} w(E_i) \cdot \mathbb{I}(E_i \text{ is inconsistent with } H_j)$$
   Where $w(E_i)$ is the node's confidence score and $\mathbb{I}$ is the indicator function for inconsistency (or presence of a `CONTRADICTS` edge).
4. **Diagnostic Value Ranking**:
   The extractor ranks hypotheses in ascending order of inconsistency score (hypotheses with the fewest contradictions are favored).

---

## 3. Scene/Text Atomic Decomposition Rules

### 3.1 `ThesisNode` Extraction Rules
- **Definition**: A declarative statement representing a core claim, factual observation, empirical finding, or analytical thesis.
- **Attributes**:
  - `id`: `thesis_<md5_hash_8>`
  - `name`: Short 3-7 word summary title.
  - `statement`: Verbatim or normalized atomic proposition.
  - `confidence`: Float $0.0 - 1.0$ (default `0.85`).
  - `domain`: `"kgb_analytics"`
  - `node_type`: `"ThesisNode"`
  - `source_file`, `scene_id`, `start_sec`, `end_sec`.
  - `tags`: `"iad,thesis,<topic>"`
- **Linguistic Markers**:
  - Declarative sentence patterns ("X является Y", "показывает, что...", "исследования подтверждают...", "приводит к...", "показатель составляет...").

---

### 3.2 `ProtocolNode` Extraction Rules
- **Definition**: An imperative operational directive, standard operating procedure (SOP), action step, or rule.
- **Attributes**:
  - `id`: `protocol_<md5_hash_8>`
  - `name`: Short 3-7 word protocol title.
  - `action_instruction`: Imperative statement describing exact action to perform.
  - `prerequisites`: List of required conditions or prior steps.
  - `sequence_order`: Integer step number (default `1`).
  - `domain`: `"kgb_analytics"`
  - `node_type`: `"ProtocolNode"`
  - `source_file`, `scene_id`, `start_sec`, `end_sec`.
  - `tags`: `"iad,protocol,<topic>"`
- **Linguistic Markers**:
  - Imperative verbs ("сделайте", "выполните", "необходимо использовать", "шаг 1:", "правило:").

---

### 3.3 Graph Edge Extraction Rules

| Relation | Direction | Semantic Meaning | Trigger Patterns & Heuristics |
|----------|-----------|------------------|-------------------------------|
| `CAUSES` | $Thesis_A \rightarrow Thesis_B$ | Thesis A causes or leads to outcome B | Connectors: "приводит к", "вызывает", "результатом является", "leads to", "causes", "results in". |
| `REQUIRES` | $Node_A \rightarrow Node_B$ | Protocol/Thesis A requires prerequisite condition B | Connectors: "требует", "при условии", "перед тем как", "необходимо сначала", "requires", "prerequisite". |
| `CONTRADICTS` | $Thesis_A \leftrightarrow Thesis_B$ | Thesis A conflicts with or opposes Thesis B | Connectors: "напротив", "в отличие от", "противоречит", "однако", "contradicts". Also triggered by high embedding similarity paired with opposing polarity. |
| `BELONGS_TO` | $Node \rightarrow Scene$ | Node originated from scene | Structural link attaching `ThesisNode`/`ProtocolNode` to `scene_id`. |

---

## 4. Architectural Design for `vazus_core/kgb_analytical_extractor.py`

### 4.1 Class Diagram & Data Schemas

```python
"""
vazus_core/kgb_analytical_extractor.py
KGB/FSB ИАД & ACH Knowledge Extraction Engine for vazus SuperGraph OS.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
import sqlite3
import json
import re
import hashlib
import time
from pathlib import Path

# Embedded 768D vector embedder integration
from vazus_core.embeddings import UnifiedGoogleEmbedder

DEFAULT_DB_PATH = Path("C:/vazus/vazus.db")
SECONDARY_DB_PATH = Path("C:/vazus/services/memory/vazus.db")

@dataclass
class ThesisNode:
    id: str
    name: str
    statement: str
    confidence: float = 0.85
    domain: str = "kgb_analytics"
    node_type: str = "ThesisNode"
    source_file: str = ""
    scene_id: str = ""
    start_sec: float = 0.0
    end_sec: float = 0.0
    tags: str = "iad,thesis"
    properties: Dict[str, Any] = field(default_factory=dict)
    embedding_json: Optional[str] = None

@dataclass
class ProtocolNode:
    id: str
    name: str
    action_instruction: str
    prerequisites: List[str] = field(default_factory=list)
    sequence_order: int = 1
    domain: str = "kgb_analytics"
    node_type: str = "ProtocolNode"
    source_file: str = ""
    scene_id: str = ""
    start_sec: float = 0.0
    end_sec: float = 0.0
    tags: str = "iad,protocol"
    properties: Dict[str, Any] = field(default_factory=dict)
    embedding_json: Optional[str] = None
```

---

### 4.2 Core Engine Class (`KGBAnalyticalExtractor`)

```python
class KGBAnalyticalExtractor:
    """
    KGB/FSB ИАД + ACH Analytical Extractor.
    Processes scene dicts or raw text, extracts ThesisNode and ProtocolNode entities,
    resolves CAUSES, REQUIRES, CONTRADICTS edges, generates 768D embeddings,
    and persists into kg_nodes & kg_edges in vazus.db.
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH, vector_dim: int = 768):
        self.db_path = Path(db_path)
        self.dim = vector_dim
        self.embedder = UnifiedGoogleEmbedder(dimension=vector_dim)
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensures kg_nodes and kg_edges tables exist in SQLite."""
        for dbp in [self.db_path, SECONDARY_DB_PATH]:
            dbp.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(dbp) as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS kg_nodes (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        domain TEXT,
                        node_type TEXT,
                        description TEXT,
                        tags TEXT,
                        properties TEXT,
                        embedding_json TEXT
                    );

                    CREATE TABLE IF NOT EXISTS kg_edges (
                        source_id TEXT,
                        target_id TEXT,
                        relation TEXT,
                        strength REAL,
                        properties TEXT,
                        PRIMARY KEY (source_id, target_id, relation)
                    );
                """)
                conn.commit()

    def decompose_text_to_nodes(
        self,
        text: str,
        source_file: str = "",
        scene_id: str = "",
        start_sec: float = 0.0,
        end_sec: float = 0.0
    ) -> Tuple[List[ThesisNode], List[ProtocolNode]]:
        """Decomposes transcript into atomic ThesisNodes and ProtocolNodes via regex/heuristics."""
        theses: List[ThesisNode] = []
        protocols: List[ProtocolNode] = []

        if not text or not text.strip():
            return theses, protocols

        # Sentence split (Russian & English sentence boundaries)
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())

        # Patterns
        protocol_patterns = [
            r'\bнеобходимо\b', r'\bследует\b', r'\bобязательно\b', r'\bшаг\b',
            r'\bправило\b', r'\bинструкция\b', r'\bрекомендуется\b', r'\bсделайте\b'
        ]

        causal_patterns = [r'\bприводит к\b', r'\bвызывает\b', r'\bиз-за\b', r'\bрезультатом является\b']

        for idx, sentence in enumerate(sentences):
            sent_clean = sentence.strip()
            if len(sent_clean) < 10:
                continue

            # Check if sentence is imperative / protocol
            is_protocol = any(re.search(pat, sent_clean, re.IGNORECASE) for pat in protocol_patterns)

            node_hash = hashlib.md5(f"{scene_id}:{sent_clean}".encode('utf-8')).hexdigest()[:8]

            if is_protocol:
                protocol_node = ProtocolNode(
                    id=f"protocol_{node_hash}",
                    name=sent_clean[:40] + ("..." if len(sent_clean) > 40 else ""),
                    action_instruction=sent_clean,
                    sequence_order=idx + 1,
                    source_file=source_file,
                    scene_id=scene_id,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    tags="iad,protocol",
                    properties={"raw_sentence": sent_clean}
                )
                protocols.append(protocol_node)
            else:
                # ThesisNode (declarative claim)
                has_causal = any(re.search(pat, sent_clean, re.IGNORECASE) for pat in causal_patterns)
                conf = 0.90 if has_causal else 0.85

                thesis_node = ThesisNode(
                    id=f"thesis_{node_hash}",
                    name=sent_clean[:40] + ("..." if len(sent_clean) > 40 else ""),
                    statement=sent_clean,
                    confidence=conf,
                    source_file=source_file,
                    scene_id=scene_id,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    tags="iad,thesis",
                    properties={"raw_sentence": sent_clean}
                )
                theses.append(thesis_node)

        return theses, protocols

    def extract_graph_edges(
        self,
        theses: List[ThesisNode],
        protocols: List[ProtocolNode],
        scene_id: str = ""
    ) -> List[Dict[str, Any]]:
        """Resolves CAUSES, REQUIRES, CONTRADICTS and BELONGS_TO edges."""
        edges = []

        # 1. Structural BELONGS_TO edges linking nodes to scene_id
        if scene_id:
            for node in (theses + protocols):
                edges.append({
                    "source_id": node.id,
                    "target_id": scene_id,
                    "relation": "BELONGS_TO",
                    "strength": 1.0,
                    "properties": {"extracted_from": scene_id}
                })

        # 2. Sequential / Prerequisite REQUIRES edges between protocols
        for i in range(len(protocols) - 1):
            edges.append({
                "source_id": protocols[i+1].id,
                "target_id": protocols[i].id,
                "relation": "REQUIRES",
                "strength": 0.90,
                "properties": {"prerequisite_step": protocols[i].name}
            })

        # 3. CAUSES and CONTRADICTS detection among theses
        causal_regex = re.compile(r'\b(приводит к|вызывает|результатом является|causes|leads to)\b', re.I)
        contradict_regex = re.compile(r'\b(напротив|противоречит|в отличие от|однако|contradicts)\b', re.I)

        for i, t1 in enumerate(theses):
            for j, t2 in enumerate(theses):
                if i >= j:
                    continue
                
                # Check causal relation
                if causal_regex.search(t1.statement):
                    edges.append({
                        "source_id": t1.id,
                        "target_id": t2.id,
                        "relation": "CAUSES",
                        "strength": 0.85,
                        "properties": {"causal_statement": t1.statement}
                    })

                # Check contradiction
                if contradict_regex.search(t2.statement):
                    edges.append({
                        "source_id": t1.id,
                        "target_id": t2.id,
                        "relation": "CONTRADICTS",
                        "strength": 0.95,
                        "properties": {"contradiction_statement": t2.statement}
                    })

        return edges

    def build_ach_matrix(
        self,
        hypotheses: List[Dict[str, str]],
        evidence_nodes: List[ThesisNode]
    ) -> Dict[str, Any]:
        """
        Constructs an ACH Evaluation Matrix testing hypotheses against evidence nodes.
        Returns inconsistency scores and diagnostic ranking.
        """
        matrix = []
        scores = {h["id"]: 0.0 for h in hypotheses}

        contradict_regex = re.compile(r'\b(не|без|отсутствие|против|opposes|not)\b', re.I)

        for ev in evidence_nodes:
            row = {"evidence_id": ev.id, "evidence_statement": ev.statement, "ratings": {}}
            for h in hypotheses:
                h_text = h["label"]
                # Heuristic consistency check: check negation / contradiction
                if contradict_regex.search(ev.statement) and any(w in h_text for w in ev.statement.split()[:3]):
                    rating = -1.0 # Inconsistent
                    scores[h["id"]] += ev.confidence * 1.0
                elif any(w in h_text for w in ev.statement.split()[:3]):
                    rating = 1.0  # Consistent
                else:
                    rating = 0.0  # Neutral

                row["ratings"][h["id"]] = rating
            matrix.append(row)

        ranked_hypotheses = sorted(scores.items(), key=lambda x: x[1])

        return {
            "matrix": matrix,
            "inconsistency_scores": scores,
            "ranked_hypotheses": [{"hypothesis_id": hid, "inconsistency_score": score} for hid, score in ranked_hypotheses]
        }

    def persist_analytics(
        self,
        theses: List[ThesisNode],
        protocols: List[ProtocolNode],
        edges: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Calculates 768D vector embeddings and persists nodes/edges into vazus.db."""
        all_nodes = theses + protocols
        nodes_persisted = 0
        edges_persisted = 0

        for dbp in [self.db_path, SECONDARY_DB_PATH]:
            with sqlite3.connect(dbp) as conn:
                for node in all_nodes:
                    text_content = node.statement if isinstance(node, ThesisNode) else node.action_instruction
                    emb = self.embedder.get_embedding(f"{node.name} {text_content}")
                    node.embedding_json = json.dumps(emb)

                    props_json = json.dumps(node.properties, ensure_ascii=False)

                    conn.execute("""
                        INSERT OR REPLACE INTO kg_nodes
                        (id, name, domain, node_type, description, tags, properties, embedding_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        node.id,
                        node.name,
                        node.domain,
                        node.node_type,
                        text_content,
                        node.tags,
                        props_json,
                        node.embedding_json
                    ))
                    nodes_persisted += 1

                for edge in edges:
                    props_json = json.dumps(edge.get("properties", {}), ensure_ascii=False)
                    conn.execute("""
                        INSERT OR REPLACE INTO kg_edges
                        (source_id, target_id, relation, strength, properties)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        edge["source_id"],
                        edge["target_id"],
                        edge["relation"],
                        edge.get("strength", 1.0),
                        props_json
                    ))
                    edges_persisted += 1

                conn.commit()

        return {
            "nodes_persisted": len(all_nodes),
            "edges_persisted": len(edges)
        }
```

---

### 4.3 Interface Function Specification

`extract_kgb_analytics(scene_or_text_dict: Dict[str, Any]) -> Dict[str, Any]`

#### Input Schema:
```json
{
  "scene_id": "scene_a1b2c3d4",
  "source_file": "C:/vazus/knowledge/telegram_courses/media_01.oga",
  "transcript": "Исследования подтверждают, что магний снижает кортизол. Применяйте магний 400мг ежедневно перед сном.",
  "start_sec": 12.0,
  "end_sec": 45.0,
  "hypotheses": [
    {"id": "H1", "label": "Магний улучшает качество сна"},
    {"id": "H2", "label": "Магний не оказывает эффекта на сон"}
  ]
}
```

#### Output Schema:
```json
{
  "scene_id": "scene_a1b2c3d4",
  "theses_extracted": 1,
  "protocols_extracted": 1,
  "edges_extracted": 2,
  "nodes": [
    {
      "id": "thesis_f812a3",
      "node_type": "ThesisNode",
      "name": "Исследования подтверждают, что...",
      "statement": "Исследования подтверждают, что магний снижает кортизол.",
      "confidence": 0.85
    },
    {
      "id": "protocol_91b7e2",
      "node_type": "ProtocolNode",
      "name": "Применяйте магний 400мг ежедневно...",
      "action_instruction": "Применяйте магний 400мг ежедневно перед сном."
    }
  ],
  "edges": [
    {
      "source_id": "thesis_f812a3",
      "target_id": "scene_a1b2c3d4",
      "relation": "BELONGS_TO",
      "strength": 1.0
    },
    {
      "source_id": "protocol_91b7e2",
      "target_id": "thesis_f812a3",
      "relation": "REQUIRES",
      "strength": 0.90
    }
  ],
  "ach_analysis": {
    "ranked_hypotheses": [
      {"hypothesis_id": "H1", "inconsistency_score": 0.0},
      {"hypothesis_id": "H2", "inconsistency_score": 0.85}
    ]
  },
  "status": "SUCCESS"
}
```

---

## 5. Verification & Testing Strategy

1. **Syntax & Type Verification**:
   Ensure `vazus_core/kgb_analytical_extractor.py` passes `python -m py_compile` without warnings or syntax errors.
2. **Database Schema Integrity**:
   Verify that `kg_nodes` stores `node_type IN ('ThesisNode', 'ProtocolNode')` and `kg_edges` stores `relation IN ('CAUSES', 'REQUIRES', 'CONTRADICTS', 'BELONGS_TO')`.
3. **768D Vector Space Alignment**:
   Verify that `embedding_json` is generated using `UnifiedGoogleEmbedder` (768D array) and can be queried via `SuperGraphLinker.search_unified_vector_space()`.
