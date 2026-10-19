# Vazus OS — Канонические реестры (Canonical Registries)

Дата обновления: 2026-08-18. Единый источник правды по путям и конфигурациям. При расхождении —
верить этому документу, остальное считать устаревшим.

## MCP-реестр
- Канонический для Antigravity (AG2): `~/.gemini/config/mcp_config.json` (пины версий обязательны, @latest запрещён).
- Проектный (для IDE-агентов, Cursor/Claude): `C:\vazus\.mcp.json` (пины версий обязательны).
- Собственные серверы Vazus:
  - `code-quality` (`scripts/mcp_servers/code_quality_mcp.py`): 11 инструментов (ast-grep, grit, radon CC/MI, wily, pyinstrument, candidate_harvester, pydeps, detect_clones, get_improvement_suggestions).
  - `vazus-organic` (`scripts/mcp_servers/vazus_organic_mcp.py`): 15 инструментов (память, mem0, SMT Z3, Jury, evolution, ast_prune, recall, record_insight).
  - `ckb` (`ckb.cmd mcp`): 27 инструментов (SCIP, symbols, call-graph, blast radius, hotspots).
  - `supergraph` (`scripts/mcp_servers/supergraph_mcp.py`): trace_path, detect_blast_radius, query_symbol_lineage.
  - `semgrep` (`scripts/mcp_servers/semgrep_mcp.py`): scan, pattern_search.
- Хранилище схем AG2: `~/.gemini/antigravity/mcp/<name>/`.
- Hermes: собственный MCP-клиент (`hermes mcp`).

## Скиллы
- Antigravity (agent skills): `~/.gemini/config/skills/` — читает `dynamic_skill_dispatcher` (768D).
- Antigravity (builtin): `~/.gemini/antigravity/builtin/skills/` — системные.
- Swarm-скиллы: `C:\vazus\.agents\skills\` — для декларативного движка роя.
- Hermes: `~/AppData/Local/hermes/skills/` — локальные скиллы Hermes.
- Манифесты и DDL: общий DDL схем вынесен в `vazus_core/analysis/kg_schema.py`.

## Память и Базы Данных
- Каноничная БД: `C:\vazus\services\memory\vazus.db` (SQLite WAL mode, vec0 768D, FTS5, KG-граф, bi-temporal `memory_facts_v2`, `code_clones`, `improvement_suggestions`).
  Переменная окружения: `VAZUS_DB_PATH`.
- Wiki: `services/memory/semantic/wiki/` — синхронизируется хуками (`Commits/<sha>.md`, `ADR_*.md`, `Research_*.md`).
- 768D векторное пространство: `vazus_core/embeddings.py` (OpenVINO NPU, Google GenAI, AVX-512 + NumPy cosine similarity).

## 8-Tier Прекоммит-Гейт (precommit_gate.py)
1. **Gate 1**: AST Syntax (`ast.parse`) + Security Scan (секреты AIzaSy/sk-, запрет `os.system`/`shell=True`, защита от reward hacking в тестах).
2. **Gate 2**: Targeted Pytest (маппинг exact-имен + AST импортов, таймаут `VAZUS_GATE_TEST_TIMEOUT=300`).
3. **Gate 3**: SMT Z3 Formal Contracts (Hoare-контракты, depth=10, SAT = блок).
4. **Gate 4a**: Deterministic EvidenceJury (0 LLM вызовов, решение на основе твёрдых доказательств).
5. **Gate 4**: Critic Jury (LLM эскалация для UNVERIFIED, батч из 2 вызовов, таймаут `VAZUS_GATE_JURY_TIMEOUT=120`, fail-closed).
6. **Gate 5**: Dead Code Detection (Vulture ≥90% confidence, пропуск third-party).
7. **Gate 6**: Fast Static Lint (Ruff F401, F821 undefined names, F841 unused locals, E9 syntax).
8. **Gate 6b (opt-in)**: Deep Scan (`deptry`, `pip-audit`, `bandit`).
9. **Gate 7 (opt-in)**: Type Check (`mypy --python-version 3.11`).
10. **Gate 8 (advisory)**: Proactive Suggestion Engine (Observer-Planner сканирование complexity/clones/print/md5/dead_code → запись в `vazus.db`).

## Порты и Сетевой Контур
- `system_daemon`: 8765 HTTP (`VAZUS_DAEMON_PORT`).
- `Vision WS`: 8766 (`VAZUS_VISION_WS_PORT`).
- `CKB daemon`: 9120 (token в `.ckb/token.txt`).
- `IDE Adapter / Model Gateway`: 5001 (agy/Gemini 3.7 Flash IDE quota adapter).
- `AgentRouter Proxy`: 5012.
