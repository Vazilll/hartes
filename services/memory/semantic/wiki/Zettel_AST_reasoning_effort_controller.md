---
id: Zettel_AST_reasoning_effort_controller
title: AST Pruned Skeleton - reasoning_effort_controller.py
date: 2026-08-14
domain: ast_code
tags: [ast, code, ast_pruner, reasoning_effort_controller]
status: VERIFIED
sources: [ASTPruner, SuperGraph OS]
---

# AST Pruned Skeleton for `reasoning_effort_controller.py`

## Core Metrics
- **Total AST Nodes**: 485
- **Pruned AST Nodes**: 116
- **Token Reduction**: 76.08%
- **Syntax Valid**: `True`

## Pruned Signatures
```python
"""vazus_core.reasoning_effort_controller — Execution & Orchestration Policy Controller."""
import logging
from typing import Dict, Any, Union
logger = logging.getLogger(__name__)
LEVEL_PRESETS = {'low': 0.1, 'medium': 0.35, 'high': 0.65, 'xhigh': 0.85, 'ultra': 1.0}
MODEL_LIMITS = {'gemini-3.6-flash': {'max_output': 65536, 'context_window': 1048576}, 'gemini-3.1-pro': {'max_output': 65536, 'context_window': 2097152}, 'claude-sonnet-4.6': {'max_output': 128000, 'context_window': 200000}, 'gpt-oss-120b': {'max_output': 16384, 'context_window': 131072}, 'default': {'max_output': 32768, 'context_window': 131072}}

class ExecutionPolicyController:
    """Controller for local execution policies, verification depths, sandbox budgets,"""

    @staticmethod
    def get_config(effort: Union[str, float], model_key: str='gemini-3.6-flash', prompt_tokens: int=0, safety_headroom: int=4096) -> Dict[str, Any]:
        """Calculates concrete execution parameters for local workers, Z3 verification,"""
        ...
ReasoningEffortController = ExecutionPolicyController
```

## Related Notes & Wikilinks
- [[Research_SuperGraph_Memory_Wiki_and_AST|SuperGraph Memory & AST Integration]]
- [[RLM_Code_Task_Refactor_AST_pruner|AST Pruner Refactor Task]]
- [[Zettel_AST_reasoning_effort_controller|Self Reference]]
