"""
vazus.labs.cremniy_automation — Cremniy C++ Engine Core & 768D Vector Space Integration.

This package provides:
- FileDataBuffer: Thread-safe, 64KB LRU chunk-cached binary buffer with dirty byte overlays and transactional undo/redo.
- ModuleManager: Thread-safe singleton registry mapping category string groups to module factories.
- DisassemblerEngine: Structured disassembly structures and backends (radare2/rizin with python fallbacks).
- HexEditorWrapper: Visual document model wrapping FileDataBuffer with range-based metadata & styling.
- CremniySuperGraphExtractor: 768D Gemini vector space indexer & query engine in vazus.db (cremniy_disasm domain).
"""

from labs.vaz_custom.cremniy_automation.cremniy_engine import (
    FileDataBuffer,
    ModuleManager,
    ModuleDescription,
    DisasmInstruction,
    DisasmSection,
    DisasmFunction,
    DisasmString,
    DisassemblerEngine,
    HexEditorWrapper,
    CremniySuperGraphExtractor,
)

__all__ = [
    "FileDataBuffer",
    "ModuleManager",
    "ModuleDescription",
    "DisasmInstruction",
    "DisasmSection",
    "DisasmFunction",
    "DisasmString",
    "DisassemblerEngine",
    "HexEditorWrapper",
    "CremniySuperGraphExtractor",
]
