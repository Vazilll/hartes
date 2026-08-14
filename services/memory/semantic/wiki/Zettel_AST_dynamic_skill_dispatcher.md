---
id: Zettel_AST_dynamic_skill_dispatcher
title: AST Pruned Skeleton - dynamic_skill_dispatcher.py
date: 2026-08-09
domain: ast_code
tags: [ast, code, ast_pruner, dynamic_skill_dispatcher]
status: VERIFIED
sources: [ASTPruner, SuperGraph OS]
---

# AST Pruned Skeleton for `dynamic_skill_dispatcher.py`

## Core Metrics
- **Total AST Nodes**: 2995
- **Pruned AST Nodes**: 799
- **Token Reduction**: 73.32%
- **Syntax Valid**: `True`

## Pruned Signatures
```python
"""
vazus_core.dynamic_skill_dispatcher — Dynamic Skill Loading Architecture & Intent Parsing Dispatcher.

Provides multi-tier intent parsing, AST skill context pruning, transcript loop prevention guardrails,
and context manager protocol (__enter__ / __exit__) for Vazus SuperGraph OS v4.0.
"""
import os
import sys
import re
import math
import glob
import json
import time
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Union
workspace_root = str(Path(__file__).resolve().parent.parent)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)
from vazus_core.embeddings import get_embedding_manager, UnifiedEmbeddingManager
from vazus_core.ast_pruner import ASTPruner
from vazus_core.reasoning_effort_controller import ReasoningEffortController
DEFAULT_SKILLS_DIRS = ['C:\\Users\\Vaz\\.gemini\\config\\skills', 'C:\\vazus']

@dataclass
class SkillMetadata:
    """Dataclass holding metadata and embeddings for a single skill."""
    skill_id: str
    name: str
    description: str
    folder_path: str
    skill_md_path: str
    embedding_768d: Optional[List[float]] = None
    keywords: List[str] = field(default_factory=list)
    raw_content: str = ''
    score: float = 0.0
    tier_scores: Dict[str, float] = field(default_factory=dict)

@dataclass
class SkillContext:
    """Dataclass representing the active loaded skill context."""
    prompt: str
    matched_skills: List[SkillMetadata]
    system_prompt_injection: str
    token_savings_pct: float
    effort_level: str
    prune_mode: str

    @property
    def skill_ids(self) -> List[str]:
        ...

class TranscriptLoopGuardrails:
    """Transcript loop prevention guardrails:"""
    BINARY_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}

    @classmethod
    def validate_view_file_path(cls, file_path: Union[str, Path]) -> Tuple[bool, str]:
        """Validates if file_path is safe for view_file."""
        ...

    
```

## Related Notes & Wikilinks
- [[Research_SuperGraph_Memory_Wiki_and_AST|SuperGraph Memory & AST Integration]]
- [[RLM_Code_Task_Refactor_AST_pruner|AST Pruner Refactor Task]]
- [[Zettel_AST_dynamic_skill_dispatcher|Self Reference]]
