# AGENTS.md — Vazus SuperGraph OS Agent Contract & Quality Governance

## 🎯 Purpose & Scope
This document defines the formal behavioral contract and quality invariants for autonomous AI coding agents (Antigravity, Claude Code, RLM Coder, Jules) operating within the `C:\vazus` workspace.

---

## 1. 🛡️ The AI-Friendly Code Quality Standard (Code Health $\ge 9.5$)
Research shows that when AI coding assistants operate on unhealthy code, defect risk increases by over 60%. To maintain high predictability and prevent quality debt:
- **Mandatory Target**: Every modified module must maintain an objective **Code Health Score $\ge 9.5 / 10.0$**.
- **Cyclomatic Complexity**: All functions in Python, Go, and C/C++ must strictly satisfy $CC \le 10$ (McCabe threshold).
- **Zero Stubs**: Never introduce `pass`, `...`, `raise NotImplementedError`, or fake placeholder returns in production code.

---

## 2. 🌐 Intent-Aware Navigation & AST-Level Retrieval
- **Never Dump Raw Codebases**: Do NOT dump raw multi-thousand-line files into context windows.
- **Use Multi-Language AST Pruning**: Use `UniversalASTPruner` (supporting Python, Go, C/C++) to extract high-efficiency signature skeletons (>75% token reduction).
- **Symbolic Grounding**: Use Codebase Memory MCP (`cbm`) and `Code Knowledge Backend (ckb)` to trace call graphs and symbol definitions before proposing edits.

---

## 3. 🚦 11-Tier Pre-Commit Quality Gate Pipeline
Before finalizing any code mutation or declaring task completion, every change MUST pass all 11 tiers of `vazus_core/verification/precommit_gate.py`:
1. **Gate 1**: AST Syntax & Anti-Pattern Security (0 stubs, 0 API keys, 0 `shell=True`).
2. **Gate 2**: Targeted Pytest via AST Import Tracing (100% test pass rate).
3. **Gate 3**: SMT Z3 Formal Hoare Contract Proofs (UNSAT counterexamples).
4. **Gate 4a/4**: 0-LLM Deterministic EvidenceJury & Concordia Critic Jury.
5. **Gate 5**: Dead Code Elimination via Vulture ($\ge 90\%$ confidence).
6. **Gate 6**: Fast Static Linting via Ruff (`F401`, `F821`, `E9`).
7. **Gate 7**: Strict Typechecking via Mypy.
8. **Gate 8**: Token-Optimized AST Signature Preservation.
9. **Gate 10**: Radon Cyclomatic Complexity ($CC \le 10$ enforcement).
10. **Gate 11**: Graph Structural Invariants & Phantom Import Prevention (Eliminates *The Patchwork Problem*).

---

## 4. 🎛️ NotebookLM & RAG Offloading Protocol
- For large-scale multi-document synthesis (50+ papers, large PDF books, deep internet research), offload processing to **Google NotebookLM MCP** (`gemini-notebook-mcp` / `nlm CLI`).
- Store verified domain findings into `vazus.db` (56 tables, FTS5 + 768-dim vector embeddings) and link via `[[wikilinks]]`.

---

## 5. 🧹 Zero Artifact Accumulation
- Clean up all temporary `.py` test scripts and scratch files immediately upon completing each task.
