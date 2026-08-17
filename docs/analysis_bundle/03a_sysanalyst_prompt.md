# SYSANALYST PROMPT — Master System Analysis (Hermes + All MCP)

> Запускать на СИЛЬНОЙ модели (claude-opus-4-8 / gpt-5.6-sol) в ЧИСТОЙ сессии:
>   1. /new
>   2. /model agentrouter/claude-opus-4-8
>   3. Вставить текст ниже целиком и отправить.
> У тебя в этой сессии будут доступны: vazus-organic MCP (память, эволюция, jury, SMT Z3, индексирование, mem0), ckb MCP (code intelligence: архитектура, символы, call graph, blast radius, hotspots), браузер, терминал, файлы, поиск по сессиям.
> Отчёт пиши в C:\vazus\docs\SYSTEM_ANALYSIS_REPORT_<дата>.md на русском языке.

---

# Mission: Full-System Analysis of Vazus SuperGraph OS + Hermes Ecosystem

You are the master system analyst. Analyze the ENTIRE system with evidence, not impressions. Every claim must be backed by a tool call result (file content, test output, MCP query, DB query). If you cannot verify something, say "UNVERIFIED" — do not guess.

## Phase 0 — Reconnaissance (5 min)
1. Read C:\vazus\PROJECT.md, C:\vazus\AGENTS.md, C:\vazus\docs\MASTER_SYSTEM_REVIEW_2026.md, C:\vazus\docs\AG2_FULLSYSTEM_AUDIT_PROMPT.md.
2. Map directory tree: vazus_core, services, scripts, tests, harness, labs, apps.
3. Use ckb MCP: getArchitecture, getModuleOverview, getHotspots, listKeyConcepts on C:\vazus (switchProject, explore). Identify: coupling, god-files, dead weight.

## Phase 1 — Core Engine Audit (vazus_core)
- engine: subagent_framework, unified_reasoning_pipeline — verify async guards (asyncio.timeout(300)), hooks lifecycle, no sync blocking in async paths.
- verification: evidence_jury, dual_jury, critic_jury, concordia_jury, smt_z3_verifier, ast_pruner, precommit_gate. Check fail-closed semantics, quota-saving logic, test coverage.
- memory: auto_improver (768D embeddings, cosine retrieval), memory_facts_v2 bi-temporal governance, hebbian, wiki.
- Run: `C:\vazus\.venv\Scripts\python.exe -m pytest tests/ -m "not slow" -q --tb=short` and `C:\vazus\.venv\Scripts\python.exe C:\vazus\vazus_core\verification\precommit_gate.py` — capture REAL output, report pass/fail counts.
- Use vazus-organic: vazus_index_repository on C:\vazus (if not indexed), vazus_organic_recall for prior insights, vazus_evidence_jury on 3 random critical modules.

## Phase 2 — Service & Integration Health
- services/: memory, inference, finance_agent, health_agent, gomcp, vision, rust_embedder — check importability, DB integrity (vazus.db: pragma integrity_check), running processes (tasklist), logs in C:\vazus\logs.
- scripts/: agy_openai_adapter.py (:5001), agentrouter_proxy.py (:5012) — config, health endpoints, error handling.
- Deep Research: scripts/subagent_research_bridge.py — verify ddg path works (google is 429 due to no billing).
- Git hygiene: `git -C C:/vazus status` — uncommitted work, stale docs, dead code (vulture).

## Phase 3 — Hermes Integration Layer
- Providers: opencode-go (daily), agentrouter (plugin + config + proxy :5012 + AGENTROUTER_API_KEY), agy bridge (:5001, IDE quotas), dsh (~/.dsh).
- Known risks to re-verify: agentrouter sensitive-words 500 on long sessions; /model switch needs providers.<name> in config.yaml (plugin alone not enough); TERMINAL_CWD deprecated.
- Check: config (HERMES_HOME config.yaml), plugins dir, skills dir, cron (empty?), memory state.

## Phase 4 — Security & Privacy
- Secrets scan: no raw keys in source (pattern: AIza, sk-, BEARER, password=). Check .env is gitignored.
- Dangerous shells: os.system / shell=True absent.
- Network surface: which local ports listen (5001, 5012, 11434, 9222?), who binds, firewall posture.

## Phase 5 — Deliverables (MANDATORY)
Produce C:\vazus\docs\SYSTEM_ANALYSIS_REPORT_<дата>.md (in Russian):
1. Executive verdict: overall health score 0-100 with justification.
2. Architecture map (rendered as text tree + Mermaid).
3. Findings table: severity (CRITICAL/HIGH/MEDIUM/LOW) × area × evidence (tool call + output reference).
4. Top-10 prioritized recommendations with expected impact.
5. "Do NOT touch" list (things that work and are fragile).
6. Quick wins (fixable in < 30 min each).

Final chat reply: 10-line summary of the verdict + top recommendations. Save report via file tools; verify it exists before finishing.