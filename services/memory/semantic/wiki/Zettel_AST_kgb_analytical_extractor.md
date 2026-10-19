---
id: Zettel_AST_kgb_analytical_extractor
title: AST Pruned Skeleton - kgb_analytical_extractor.py
date: 2026-10-05
domain: ast_code
tags: [ast, code, ast_pruner, kgb_analytical_extractor]
status: VERIFIED
sources: [ASTPruner, SuperGraph OS]
---

# AST Pruned Skeleton for `kgb_analytical_extractor.py`

## Core Metrics
- **Total AST Nodes**: 10322
- **Pruned AST Nodes**: 2115
- **Token Reduction**: 79.51%
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
        if not text:
            return ""
        text = re.sub(r'\[[^\]]*\]', ' ', text)
        text = re.sub(r'\(\s*(?:музыка|смех|аплодисменты|шум|кашель|вздох|пауза|тишина|laughter|music|applause)\s*\)', ' ', text, flags=re.I)
        text = text.replace('\xa0', ' ').replace('\u200b', '')
        return re.sub(r'\s+', ' ', text).strip()

DEFAULT_DB_PATH = os.environ.get("VAZUS_DB_PATH", r"C:\vazus\services\memory\vazus.db")

SECONDARY_DB_PATH = os.environ.get("VAZUS_DB_PATH", r"C:\vazus\services\memory\vazus.db")

TERTIARY_DB_PATH = os.environ.get("VAZUS_DB_PATH", r"C:\vazus\services\memory\vazus.db")

class ThesisNode:
    """Represents an analytical claim, factual assertion, hypothesis, or scientific thesis."""
    def __init__(
        self,
        id: str,
        name: str,
        statement: str,
        *,
        confidence: float=0.85,
        confidence_score: Optional[float]=None,
        domain: str="kgb_analytics",
        node_type: str="ThesisNode",
        ach_status: str="HYPOTHESIS",
        evidence_sources: Optional[List[str]]=None,
        source_file: str="",
        scene_id: str="",
        start_sec: float=0.0,
        end_sec: float=0.0,
        tags: Union[str, List[str]]="iad,thesis",
        properties: Optional[Dict[str, Any]]=None,
        embedding_json: Optional[str]=None,
        node_id: Optional[str]=None
    ):
        .
```

## Related Notes & Wikilinks
- [[Research_SuperGraph_Memory_Wiki_and_AST|SuperGraph Memory & AST Integration]]
- [[RLM_Code_Task_Refactor_AST_pruner|AST Pruner Refactor Task]]
- [[Zettel_AST_kgb_analytical_extractor|Self Reference]]
