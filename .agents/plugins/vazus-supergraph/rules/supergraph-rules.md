# Vazus SuperGraph OS Plugin Guidelines & Architecture Rules

## 1. Zero Self-Certification Rule
Never claim a task or edit is completed until empirical runtime verification (AST parse, pytest, or SMT Z3 contract proof) returns exit code 0.

## 2. Anti-Looping Circuit Breaker Protocol
If code proposal attempts fail twice or generate identical code hashes, stop the loop immediately, prune AST topology via `vazus_ast_prune`, and escalate reasoning budget.

## 3. Persistent Memory & Anti-Amnesia
All session insights and architectural decisions must be stored into `vazus.db` using 768-dim Google Gemini embeddings and Karpathy LLM Wiki notes.

## 4. Native Tool Protocol
Use native MCP tools (`call_mcp_tool`) directly. Do not invent fake tool calls or fall back to manual shell commands when native tools exist.
