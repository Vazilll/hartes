---
id: Zettel_AST_config
title: AST Pruned Skeleton - config.py
date: 2026-08-14
domain: ast_code
tags: [ast, code, ast_pruner, config]
status: VERIFIED
sources: [ASTPruner, SuperGraph OS]
---

# AST Pruned Skeleton for `config.py`

## Core Metrics
- **Total AST Nodes**: 620
- **Pruned AST Nodes**: 564
- **Token Reduction**: 9.03%
- **Syntax Valid**: `True`

## Pruned Signatures
```python
"""vazus_core/config.py — Centralized Configuration & Path Normalization Engine."""
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field

@dataclass
class Settings:
    USER_HOME: Path = field(default_factory=Path.home)
    WORKSPACE_DIR: Path = field(default_factory=lambda: Path(os.getenv('VAZUS_WORKSPACE_DIR', str(_get_default_workspace()))).resolve())
    GEMINI_DIR: Path = field(default_factory=lambda: Path(os.getenv('VAZUS_GEMINI_DIR', str(Path.home() / '.gemini'))).resolve())
    GEMINI_CLI_DIR: Path = field(default_factory=lambda: Path(os.getenv('VAZUS_GEMINI_CLI_DIR', str(Path.home() / '.gemini' / 'antigravity-cli'))).resolve())
    GEMINI_SKILLS_DIR: Path = field(default_factory=lambda: Path(os.getenv('VAZUS_GEMINI_SKILLS_DIR', str(Path.home() / '.gemini' / 'config' / 'skills'))).resolve())
    CLI_SUMMARIES_DB: Path = field(default_factory=lambda: Path(os.getenv('VAZUS_CLI_SUMMARIES_DB', str(Path.home() / '.gemini' / 'antigravity-cli' / 'conversation_summaries.db'))).resolve())
    CLI_CONVERSATIONS_DIR: Path = field(default_factory=lambda: Path(os.getenv('VAZUS_CLI_CONVERSATIONS_DIR', str(Path.home() / '.gemini' / 'antigravity-cli' / 'conversations'))).resolve())
    CLI_SETTINGS_FILE: Path = field(default_factory=lambda: Path(os.getenv('VAZUS_CLI_SETTINGS_FILE', str(Path.home() / '.gemini' / 'antigravity-cli' / 'settings.json'))).resolve())
    HERMES_SKILLS_DIR: Path = field(default_factory=lambda: Path(os.getenv('VAZUS_HERMES_SKILLS_DIR', str(Path.home() / 'AppData' / 'Local' / 'hermes' / 'hermes-agent' / 'skills'))).resolve())
    HERMES_CONFIG_FILE: Path = field(default_factory=lambda: Path(os.getenv('VAZUS_HERMES_CONFIG_FILE', str(Path.home() / 'AppData' / 'Local' / 'hermes' / 'config.yaml'))).resolve())
    VAZUS_DB_PATH: Path = field(default_factory=lambda: Path(os.getenv('VAZUS_DB_PATH', str(_get_default_workspace() / 'services' / 'memory' / 'vazus.db'))).resolve())
    WIKI_DIR: Path = field(default_factory=lamb
```

## Related Notes & Wikilinks
- [[Research_SuperGraph_Memory_Wiki_and_AST|SuperGraph Memory & AST Integration]]
- [[RLM_Code_Task_Refactor_AST_pruner|AST Pruner Refactor Task]]
- [[Zettel_AST_config|Self Reference]]
