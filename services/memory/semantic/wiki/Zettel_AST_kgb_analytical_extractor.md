---
id: Zettel_AST_kgb_analytical_extractor
title: AST Pruned Skeleton - kgb_analytical_extractor.py
date: 2026-08-15
domain: ast_code
tags: [ast, code, ast_pruner, kgb_analytical_extractor]
status: VERIFIED
sources: [ASTPruner, SuperGraph OS]
---

# AST Pruned Skeleton for `kgb_analytical_extractor.py`

## Core Metrics
- **Total AST Nodes**: 5978
- **Pruned AST Nodes**: 778
- **Token Reduction**: 86.99%
- **Syntax Valid**: `True`

## Pruned Signatures
```python
"""vazus_core/kgb_analytical_extractor.py"""
import os
import sys
import re
import json
import sqlite3
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set, Union
try:
    from vazus_core.memory.embeddings import UnifiedEmbeddingManager
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from vazus_core.memory.embeddings import UnifiedEmbeddingManager
try:
    from vazus_core.memory.multimodal_knowledge import normalize_russian_text
except ImportError:

    def normalize_russian_text(text: str) -> str:
        ...
DEFAULT_DB_PATH = 'C:\\vazus\\services\\memory\\vazus.db'
SECONDARY_DB_PATH = 'C:\\vazus\\services\\memory\\vazus.db'
TERTIARY_DB_PATH = 'C:\\vazus\\services\\memory\\vazus.db'

class ThesisNode:
    """Represents an analytical claim, factual assertion, hypothesis, or scientific thesis."""

    def __init__(self, id: str, name: str, statement: str, confidence: float=0.85, confidence_score: Optional[float]=None, domain: str='kgb_analytics', node_type: str='ThesisNode', ach_status: str='HYPOTHESIS', evidence_sources: Optional[List[str]]=None, source_file: str='', scene_id: str='', start_sec: float=0.0, end_sec: float=0.0, tags: Union[str, List[str]]='iad,thesis', properties: Optional[Dict[str, Any]]=None, embedding_json: Optional[str]=None, node_id: Optional[str]=None):
        ...

    def to_dict(self) -> Dict[str, Any]:
        ...

class ProtocolNode:
    """Represents an operational directive, protocol, step-by-step algorithm, or procedure."""

    def __init__(self, id: str, name: str, action_instruction: str='', steps: Optional[List[str]]=None, prerequisites: Optional[List[str]]=None, sequence_order: int=1, target_outcome: str='', frequency_periodicity: str='', safety_warnings: Optional[List[str]]=None, domain: str='kgb_analytics', node_type: str='ProtocolNode', source_file: str='', scene_id: str='', start_sec: float=0.0, end_sec: float=0.0, tags: Union[str
```

## Related Notes & Wikilinks
- [[Research_SuperGraph_Memory_Wiki_and_AST|SuperGraph Memory & AST Integration]]
- [[RLM_Code_Task_Refactor_AST_pruner|AST Pruner Refactor Task]]
- [[Zettel_AST_kgb_analytical_extractor|Self Reference]]
