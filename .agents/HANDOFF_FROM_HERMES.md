# HANDOFF FROM HERMES → ANTIGRAVITY
Дата: 2026-08-14
От: Hermes Agent (Nous Research v0.20.1, сессия аудита)
Кому: Antigravity 2.0 (Google DeepMind) / Vazus SuperGraph OS

---

## 1. Что уже сделано со стороны Hermes

- Hermes подключён к Vazus через нативный MCP-клиент (`~/.hermes` → config.yaml):
  - `vazus-organic` — 9 инструментов (recall, mem0, ast_prune, smt_z3, index, author_skill, evolve...)
  - `ckb` — 25 инструментов (explore, searchSymbols, analyzeImpact, getArchitecture...)
- Живая проверка: `vazus_organic_recall` работает (реальные результаты из services/memory/vazus.db).
- Создан Hermes-скилл `vazus-os-integration` (категория vazus) с правилами shared memory.

## 2. Обнаруженная проблема: CKB cold-start hang

- Диагностика: `initialize` отвечает мгновенно (serverInfo: ckb v9.3.0), но
  `tools/call getStatus` не отвечает >60s после старта процесса (Hermes-вызов упёрся в 300s таймаут).
- Гипотеза: getStatus дергает все бэкенды (SCIP index 20MB + LSP health + git) без внутреннего таймаута на холодном кэше.
- ЗАДАЧА: добавить в ckb внутренний таймаут на проверку бэкендов (~10-15s) + кэш health-статуса (TTL 30s). Легкие инструменты (searchSymbols/explore) должны работать сразу.

## 3. Задачи для Antigravity (по приоритету)

### P0
1. **vazus_darwinian_evolve — песочница.** Сейчас мутированный код исполняется через plain `subprocess.run(pytest)` без изоляции. Переиспользовать `ZeroTrustSubprocessREPL` (Win32 Job Object + memory cap, require_kernel_sandbox=True) и `AntigravityWorktreeSandbox` из vazus_core. Запрет сети внутри evolve-процесса.
2. **CKB daemon token.** `.ckb/config.json`: `daemon.auth.enabled: true`, `token: ""` — заполнить токен (или tokenFile), проверить проверку на стороне демона, остаться на bind localhost.
3. **Пины версий npx.** В `~/.gemini/config/mcp_config.json`: `@playwright/mcp` и `@modelcontextprotocol/server-sequential-thinking@latest` → зафиксировать конкретные версии.

### P1
4. **Langfuse.** `scripts/langfuse_bridge.py` указывает на внешний IP `213.165.36.252:3000`. Решение: локальный host или отключить (конфликт с privacy-first).
5. **memory_facts_v2 — миграция хуков.** `post_invocation_hook.py` / `stop_hook.py` должны писать через новую схему с `status=UNTRUSTED_OBSERVATION`, `provenance`, `source_agent='antigravity'`, `content_hash`. Промоушен в VERIFIED_FACT — только по протоколу (тест/ADR/подтверждение пользователя).
6. **Event bridge Hermes↔Antigravity.** Предложение: при Stop-хуке писать `session_summary` факт с `source_agent='antigravity'`; Hermes читает через vazus_organic_recall — так обе системы видят завершённые задачи друг друга без обмена сырыми транскриптами.
7. **labs/git_open (553MB, untracked, 7 вложенных .git-клонов).** Уже добавлен в .gitignore. Решение: вынести за пределы рабочей копии (напр. C:\vazus\external\ или архив) — держать в корне workspace не нужно.
8. **Старые ветки.** `feature/lab-anthropic|deepmind|mit|openai` заморожены на 4df4454 (нет уникальных коммитов) — удалить после сверки. `feature/embedding-models` имеет уникальный коммит 231a94d — решить: слить или архивировать. `sandbox/arch_test-*` — остатки worktree; `git worktree prune`.
9. **deepseek-harness.** Изучить: клонировать `deepseek-ai/deepseek-harness` в labs/, разобрать Cordis (spatiotemporal composability), выписать 3-5 заимствуемых паттернов в заметку. НЕ интегрировать в прод (developer preview, breaking changes).

## 4. Совместный протокол памяти (Hermes + Antigravity + Vazus)

- Читать до записи: всегда сначала recall/mem0_search.
- В общую БД пишутся ТОЛЬКО верифицированные факты. Гипотезы → UNTRUSTED_OBSERVATION.
- Личные предпочтения пользователя → локальная память агента (Hermes MEMORY.md / AG mem0), не дублировать в vazus без причины.
- Каноничная БД: C:\vazus\services\memory\vazus.db. Других копий нет (корневой дубликат удалён).
- Хуки: единственный источник — ~/.gemini/config/hooks.json (проектный и плагинный — disabled).

## 5. Что Hermes НЕ перенимает от Antigravity (сознательно)

- Автоаппрув инструментов (у Hermes: approvals.mode smart, redact_secrets).
- Самомодифицирующийся AGENTS.md (у Hermes скиллы проходят curator, AGENTS.md — статичный).
- Silent mock-fallback LLM (уже устранён у вас коммитом 1e657f8 — отлично).
