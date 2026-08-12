# SuperGraph Database Integration Analysis for KGB/FSB Analytical Knowledge Extractor (`vazus_core/kgb_analytical_extractor.py`)

**Explorer**: Explorer 2 (Milestone 2 - Requirement R2)  
**Target Module**: `vazus_core/kgb_analytical_extractor.py`  
**Master Spec**: `C:\vazus\.agents\orchestrator\PROJECT.md`  
**Date**: 2026-07-24  

---

## Executive Summary

This analysis provides the complete architectural design and database integration blueprint for `vazus_core/kgb_analytical_extractor.py`, implementing the **KGB/FSB ИАД (Информационно-Аналитическая Деятельность) + ACH (Analysis of Competing Hypotheses)** analytical knowledge extraction engine. The module extracts structured analytical entities (`ThesisNode` and `ProtocolNode`) from multimodal transcripts, Telegram discussions, and memory wiki notes, binding them via explicit graph relations (`CAUSES`, `REQUIRES`, `CONTRADICTS`) and 768D Gemini vector embeddings into SQLite SuperGraph databases (`vazus.db` and `dnts.db`).

---

## 1. SuperGraph Graph Relation Mapping Architecture

The KGB/FSB analytical extractor decomposes raw texts (audio/video `MediaScene` transcripts, `TelegramMessage` threads, or `WikiNote` documents) into two fundamental node types and three primary semantic graph edge types.

### 1.1 Target Node Types

1. **`ThesisNode`** (Analytical Claim / Hypothesis / Cause-Effect Assertion):
   - **Definition**: Represents an analytical proposition, causal hypothesis, biological mechanism, or factual claim derived from source text.
   - **Node ID Format**: `thesis:<slug>` (e.g. `thesis:d3_cypt27b1_leydig_steroidogenesis`)
   - **Domain**: `"kgb_analytics"`
   - **Node Type**: `"ThesisNode"`
   - **Key Attributes**:
     - `name`: Short human-readable title (e.g., "Vitamin D3 upregulation of StAR/CYP11A1 in Leydig cells").
     - `description`: Textual summary of the thesis and underlying evidence.
     - `tags`: `"kgb,analytics,thesis,steroidogenesis"`
     - `properties`: JSON object containing:
       - `confidence_score`: float (0.0 to 1.0)
       - `source_origin`: string (`"MediaScene"`, `"TelegramMessage"`, or `"WikiNote"`)
       - `source_id`: string (e.g., `"scene_a1b2c3d4"` or `"tg_msg_course_123"`)
       - `ach_weight`: float (Analysis of Competing Hypotheses consistency score)
       - `keywords`: list of key terms

2. **`ProtocolNode`** (Actionable Operational Guideline / Regimen / Step / Rule):
   - **Definition**: Represents a concrete, actionable protocol, dosage recommendation, intervention step, or operational rule derived from source text.
   - **Node ID Format**: `protocol:<slug>` (e.g. `protocol:magnesium_d3_cofactor_regimen`)
   - **Domain**: `"kgb_analytics"`
   - **Node Type**: `"ProtocolNode"`
   - **Key Attributes**:
     - `name`: Short title (e.g., "Pulsed Boron 6-10mg 2w ON / 1w OFF Protocol").
     - `description`: Step-by-step description of the protocol.
     - `tags`: `"kgb,analytics,protocol,intervention"`
     - `properties`: JSON object containing:
       - `action_steps`: list of actionable instructions
       - `target_outcome`: target biochemical or operational outcome
       - `dosage_or_parameters`: dict of parameters
       - `safety_warnings`: list of warnings or contraindications
       - `source_id`: string origin

---

### 1.2 Edge Relation Detection Logic (`CAUSES`, `REQUIRES`, `CONTRADICTS`)

The extractor automatically detects and populates three core analytical edge relations between nodes:

```
  [ThesisNode A]  ====== CAUSES ======>  [ThesisNode / ProtocolNode B]
  [ProtocolNode A] ==== REQUIRES =====>  [ProtocolNode / ThesisNode B]
  [ThesisNode A] <==== CONTRADICTS ====> [ThesisNode B] (Bi-directional)
```

#### A. `CAUSES` (Causal Links)
- **Semantic Definition**: Entity A produces, stimulates, activates, increases, or leads to Entity B ($A \rightarrow B$).
- **Detection Logic**:
  1. **NLP Pattern Matchers (Russian & English)**:
     - Phrases: `"приводит к"`, `"вызывает"`, `"стимулирует"`, `"повышает"`, `"увеличивает"`, `"следствием является"`, `"ведет к"`, `"causes"`, `"triggers"`, `"leads to"`, `"results in"`, `"stimulates"`, `"boosts"`.
  2. **Directional Assignment**:
     - Source ($A$): Stimulus, intervention, upstream mechanism, or causative agent.
     - Target ($B$): Response, downstream effect, or physiological outcome.
  3. **Strength Score ($S_{\text{CAUSES}}$)**:
     $$S_{\text{CAUSES}} = 0.40 \cdot \text{cos\_sim}(v_A, v_B) + 0.40 \cdot W_{\text{pattern}} + 0.20 \cdot W_{\text{proximity}}$$
     Where $W_{\text{pattern}} \in [0.5, 1.0]$ based on explicit causal keyword matching, and $\text{cos\_sim}$ is the 768D vector similarity between node descriptions.

#### B. `REQUIRES` (Prerequisite / Dependency Links)
- **Semantic Definition**: Entity A requires, depends on, needs, or is conditioned upon Entity B ($A \xrightarrow{\text{requires}} B$).
- **Detection Logic**:
  1. **NLP Pattern Matchers**:
     - Phrases: `"требует"`, `"зависит от"`, `"необходим"`, `"для работы нужен"`, `"без ... невозможно"`, `"при условии"`, `"является пререквизитом"`, `"requires"`, `"depends on"`, `"prerequisite"`, `"contingent upon"`, `"needs"`.
  2. **Domain Dependency Rules**:
     - Enzymatic / Co-factor dependencies: Protocols specifying active Vitamin D synthesis automatically require Magnesium co-factor protocols/theses.
  3. **Strength Score ($S_{\text{REQUIRES}}$)**:
     $$S_{\text{REQUIRES}} = 0.50 \cdot \text{cos\_sim}(v_A, v_B) + 0.50 \cdot W_{\text{prereq\_pattern}}$$

#### C. `CONTRADICTS` (Incompatible Hypotheses / Conflict Links)
- **Semantic Definition**: Entity A contradicts, refutes, opposes, negates, or is mutually exclusive with Entity B ($A \xleftrightarrow{\text{contradicts}} B$).
- **Detection Logic (ACH - Analysis of Competing Hypotheses)**:
  1. **High Semantic Similarity + Directional Antagonism**:
     - Nodes $A$ and $B$ discuss the exact same topic (high 768D vector similarity $\ge 0.65$), but express opposing directional claims (e.g. "increases T" vs "decreases T", "inhibits CYP24A1" vs "activates CYP24A1").
  2. **NLP Negation & Conflict Pattern Matchers**:
     - Phrases: `"противоречит"`, `"опровергает"`, `"несовместим с"`, `"в отличие от"`, `"наоборот"`, `"обратный эффект"`, `"contradicts"`, `"refutes"`, `"incompatible with"`, `"opposes"`.
  3. **ACH Consistency Matrix Scoring**:
     - If Evidence $E$ supports Thesis $A$ while disproving Thesis $B$, an edge `CONTRADICTS` with `strength` proportional to the inconsistency score is created between $A$ and $B$.

---

## 2. Integration with 768D Embeddings & SQLite Database (`vazus.db` / `dnts.db`)

### 2.1 Embedding Manager Integration

`vazus_core/kgb_analytical_extractor.py` integrates seamlessly with `vazus_core.embeddings.UnifiedEmbeddingManager`:
```python
from vazus_core.embeddings import get_embedding_manager

embedder = get_embedding_manager()
vector_768d = embedder.get_embedding(f"{node_name}: {node_description}")
```
- **Dimensionality**: Strictly 768-dim floating point vector serialized as a JSON string `"[0.0123, -0.0456, ...]"` into the `embedding_json` column of `kg_nodes`.
- **Fallback Guarantee**: If offline or without API key, `UnifiedEmbeddingManager` provides deterministic SHA-256 derived 768D fallback vectors, ensuring complete execution stability.

---

### 2.2 Database Persistence Target & Schemas

The extractor writes nodes and edges into:
1. Primary DB: `C:\vazus\services\memory\vazus.db`
2. Fallback Root DB: `C:\vazus\vazus.db`
3. Memory DB Sync: `C:\vazus\memory\dnts.db`

#### Table Schema: `kg_nodes`
```sql
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
```

#### Table Schema: `kg_edges`
```sql
CREATE TABLE IF NOT EXISTS kg_edges (
    source_id TEXT,
    target_id TEXT,
    relation TEXT,
    strength REAL,
    properties TEXT,
    PRIMARY KEY (source_id, target_id, relation)
);
```

#### Provenance Edges (`EXTRACTED_FROM`)
In addition to internal `CAUSES`, `REQUIRES`, `CONTRADICTS` edges, each extracted node creates an `EXTRACTED_FROM` edge pointing back to its parent source entity (`MediaScene`, `TelegramMessage`, or `WikiNote`):
```sql
INSERT OR REPLACE INTO kg_edges (source_id, target_id, relation, strength, properties)
VALUES ('thesis:d3_cypt27b1', 'scene_a1b2c3d4', 'EXTRACTED_FROM', 1.0, '{"origin_type": "MediaScene"}');
```

---

## 3. Interface Contract & Specification Matching `PROJECT.md`

`PROJECT.md` specifies the exact interface contract for `vazus_core/kgb_analytical_extractor.py`:

```python
def extract_kgb_analytics(scene_or_text_dict: Dict[str, Any], db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    KGB/FSB ИАД + ACH analytical extractor decomposing transcript scenes, messages, or notes
    into ThesisNode and ProtocolNode entities, and inserting CAUSES, REQUIRES, and CONTRADICTS
    edges into SQLite SuperGraph databases (vazus.db and dnts.db).

    Parameters:
        scene_or_text_dict (Dict): Dictionary containing source input. Supported formats:
            - Single MediaScene dict: {"scene_id": "scene_...", "transcript": "...", "source_file": "..."}
            - Single TelegramMessage dict: {"msg_id": 123, "text": "...", "channel_name": "..."}
            - Batch dict: {"scenes": [...]} or {"messages": [...]} or {"text": "..."}
        db_path (Optional[str]): Target SQLite database path (defaults to C:/vazus/services/memory/vazus.db).

    Returns:
        Dict[str, Any]: Summary dictionary containing:
            - status: "success"
            - thesis_nodes_created: int
            - protocol_nodes_created: int
            - causes_edges_created: int
            - requires_edges_created: int
            - contradicts_edges_created: int
            - total_nodes: int
            - total_edges: int
            - nodes: List[Dict]
            - edges: List[Dict]
    """
```

---

## 4. Concrete Class Blueprint for `vazus_core/kgb_analytical_extractor.py`

```python
"""
vazus_core/kgb_analytical_extractor.py
KGB/FSB ИАД + ACH Analytical Knowledge Extractor for SuperGraph OS.
Decomposes transcripts, discussion threads, and wiki notes into ThesisNode and ProtocolNode,
mapping CAUSES, REQUIRES, and CONTRADICTS relations with 768D Gemini vector embeddings.
"""

import os
import sys
import json
import re
import sqlite3
import hashlib
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

from vazus_core.embeddings import get_embedding_manager


class KGBAnalyticalExtractor:
    """Main KGB/FSB ИАД + ACH Analytical Knowledge Extractor Engine."""

    def __init__(self, db_path: str = "C:/vazus/services/memory/vazus.db"):
        self.db_path = os.path.abspath(db_path).replace('\\', '/')
        self.embedder = get_embedding_manager()
        self.target_dbs = list(dict.fromkeys([
            self.db_path,
            "C:/vazus/services/memory/vazus.db",
            "C:/vazus/vazus.db",
            "C:/vazus/memory/dnts.db"
        ]))

    def parse_text_into_claims(self, text: str) -> List[Dict[str, Any]]:
        """Decomposes raw text into candidate thesis claims and protocol recommendations."""
        # 1. Split into sentences and logical analytical blocks
        # 2. Apply KGB ИАД heuristic & rule-based pattern extraction for hypotheses and protocols
        # 3. Categorize each block as ThesisNode vs ProtocolNode
        ...

    def evaluate_ach_conflicts(self, thesis_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Evaluates ACH (Analysis of Competing Hypotheses) inconsistency matrix to detect CONTRADICTS edges."""
        ...

    def detect_graph_relations(
        self,
        new_nodes: List[Dict[str, Any]],
        existing_nodes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detects CAUSES, REQUIRES, and CONTRADICTS edges using 768D vector similarity and pattern rules."""
        ...

    def extract_and_persist(self, input_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Main execution flow for processing input dict and persisting into SQLite SuperGraph dbs."""
        ...


def extract_kgb_analytics(scene_or_text_dict: Dict[str, Any], db_path: Optional[str] = None) -> Dict[str, Any]:
    extractor = KGBAnalyticalExtractor(db_path=db_path or "C:/vazus/services/memory/vazus.db")
    return extractor.extract_and_persist(scene_or_text_dict)
```

---

## 5. Verification & Downstream Integration

1. **Syntax & Import Check**:
   `python -m py_compile C:\vazus\vazus_core\kgb_analytical_extractor.py`
2. **Unit & Integration Test Suite**:
   Create `tests/test_kgb_analytical_extractor.py` testing extraction from sample transcripts, verifying `ThesisNode`, `ProtocolNode`, `CAUSES`, `REQUIRES`, and `CONTRADICTS` in `vazus.db`.
3. **Downstream Handoff**:
   - Milestone 3 (`zettelkasten_exporter.py`): Queries `ThesisNode` and `ProtocolNode` to create Markdown notes with 3+ `[[Wikilinks]]` in `services/memory/semantic/wiki/`.
   - Milestone 4 (`cognitive_tutor_engine.py`): Converts `ThesisNode` into active recall questions with SM-2 scheduling intervals (1, 3, 7, 21 days).
