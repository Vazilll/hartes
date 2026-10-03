# MASTER SYSTEM REVIEW 2026 — Vazus SuperGraph OS + Hermes ecosystem

> Составлено: 17.08.2026, Hermes Agent (deepseek-v4-flash)
> Статус: АКТУАЛЬНО на вечер 17.08 (раздел 6 (Memory/KG) дополняется по завершении 5-го исследования)
> Назначение: полная карта систем, аудит, точки доводки, готовый промпт для запуска сильной модели со всеми MCP

---

## 1. КАРТА СИСТЕМ (инвентаризация на 17.08.2026)

### 1.1 Железо/Окружение
- Windows 11, Intel CPU+GPU, локально, privacy-first
- Python 3.14 (системный) + venv C:\vazus\.venv (PyTorch, OpenVINO, sqlite-vec, cv2, fastmcp)
- Ollama на 127.0.0.1:11434 (легаси custom-провайдер), Node v24 (npx/npm глобально)

### 1.2 Vazus SuperGraph OS (C:\vazus, git, 7253a8d + staged/WIP)
- Ядро: vazus_core/
  - engine/ — subagent_framework (async, asyncio.timeout(300)), unified_reasoning_pipeline (4 фазы: AST prune → SMT Z3 → Concordia jury → синтез), supergraph_master_orchestrator, llm_client (адаптер :5001, agy-маппинг)
  - memory/ — auto_improver (рефлексия, уроки, 768D вектора), hebbian, facts (memory_facts_v2 bi-temporal)
  - verification/ — evidence_jury (0 LLM), dual_jury (evidence-first), critic_jury (fail-closed), concordia_jury (кворум >=66%), smt_z3_verifier, ast_pruner, precommit_gate (5-tier), git_provenance, safety_guardrail
  - evolution/ — darwinian evolution
  - embeddings.py — 768D: OpenVINO NPU / Google GenAI / SHA256 fallback, AVX-512+NumPy cosine
  - integrations/ (google, finance, health), hermes_agent_engine.py, rust_embedder_bridge.py, hardware_profiler.py, codemods/
- workers/ — self_healing_repl, subagent_reflexion, repl_engine
- services/ — memory (vazus.db), inference, finance_agent, health_agent, gomcp (Go), vision, rust_embedder
- apps/ — android_app, android_cli_app; harness/autonomy; labs/ (research); knowledge/ (mirea, projects, telegram)
- tests/ — 685 passed (зелёный прогон 17.08 вечером, `-m "not slow"`)

### 1.3 MCP-серверы Hermes (5 подключено, 91+ инструментов)
- vazus-organic (15 инструментов) — память, эволюция кода, jury, SMT Z3, индексация, mem0
- ckb (27) — code intelligence: SCIP-граф, символы, call graph, blast radius, hotspots
- sequential-thinking (1) — декомпозиция рассуждений [ДОБАВЛЕН 17.08]
- playwright-mcp (24) — браузер: скриншоты, формы, скрейпинг [ДОБАВЛЕН 17.08, глобальный npm-установщик]
- colab-mcp (1) — Google Colab Cloud GPU/ноутбуки [ДОБАВЛЕН 17.08, colab-mcp.exe в venv]

### 1.4 Модельные провайдеры / мосты
- Hermes: opencode-go / deepseek-v4-flash (повседневка) — рабочий
- agentrouter.org (плагин + прокси :5012, AGENTROUTER_API_KEY, секция providers в config.yaml): claude-opus-4-8, claude-opus-5, gpt-5.6-sol — для КОРОТКИХ сессий (длинные режет фильтром sensitive words, HTTP 500)
- agy CLI v1.1.13 + адаптер :5001 — IDE-квоты (gemini-3.7-flash, 5000 req/day) — Tier-1 мозг Vazus
- dsh (DeepSeek Harness) ~/.dsh — providers=settings.yaml, cordis.patch.yml (HMR), валидация dsh --profile web --dump-config
- Deep Research контур: scripts/subagent_research_bridge.py (ddg) + адаптер :5001 — работает (google 429)
- контекст-компактор: scripts/context_compaction.py (summary-милстоуны, адаптер :5001)

### 1.5 Документация/процессы
- docs/AG2_*.md — брифы для обсуждения с Antigravity 2 (правило: архитектурное решение не финально до обсуждения)
- AG2_FULLSYSTEM_AUDIT_PROMPT.md — старый аудит-промпт (Antigravity-платформа) — ЗАМЕНЁН на SYSANALYST_PROMPT.md (Hermes+MCP)
- AGENTS.md — контракт для автономных кодинг-агентов; прекоммит-гейт (AST/безопасность/Z3/жюри/pytest)
- cron: 1 задача — vazus-health-watchdog (ежедневно 09:00, silent-подход)

---

## 2. АУДИТ-ВЫВОДЫ (17.08.2026)

### 2.1 Исправлено за вечер
1. 8 падавших тестов (jury): новый fail-closed контракт (mock LLM = абстенция = отказ) — тесты обновлены на явные голоса, добавлен тест абстенции → 685 passed
2. UnicodeDecodeError cp1252 (кириллица из сабпроцессов): явный utf-8/errors=replace в self_healing_repl, evidence_jury, git_provenance
3. /model для agentrouter: продублирована секция providers.agentrouter в config.yaml (без неё пикер показывает, но переключение падает — баг Hermes)
4. TERMINAL_CWD deprecation: задан terminal.cwd в конфиге
5. Watchdog vazus_health_watchdog.py + cron 09:00: мосты :5001/:5012, ключевые файлы, целостность БД (обе OK: 17 и 51 таблиц)
6. 3 новых MCP-сервера в Hermes (playwright-mcp 24 инструмента — через глобальный npm из-за битого npx-кэша; colab-mcp через colab-mcp.exe; sequential-thinking через npx)

### 2.2 Открытые риски
1. agentrouter: цензура контента на длинных сессиях — НЕ вешать критичные процессы; лечится вариантом A (прокси с суммаризацией) или C (свой new-api/LiteLLM на VPS) — см. раздел 8
2. Секции providers в config нет у остальных плагин-провайдеров — если захочется /model на них — дублировать секцию
3. Google API-ключ без биллинга: Deep Research на google поиске 429 — остаёмся на ddg
4. Легаси: ~/.hermes/config.yaml (ollama) + закомментированный TERMINAL_CWD в .env — почистить
5. Playwright MCP и colab-mcp требуют: браузер (npx playwright install) и Google-авторизацию (hermes mcp login colab-mcp)

---

## 3. СТРАТЕГИЯ СЖАТИЯ КОНТЕКСТА (практическая, по research-отчёту №4)

### 3.1 Принципы
1. Компакция — первый рычаг: авто-суммаризация при ~85% окна, структурированный формат сводки (что сделано / текущее состояние / следующие шаги / точные пути и цифры)
2. Context rot: модели хуже работают с >50-100K токенов — длинная история не бесплатна даже при большом окне
3. Файловая память (NOTES.md/PROGRESS.md) почти бесплатна и переживает сессии — писать статус в файлы, а не держать в окне
4. Субагенты изолируют грязный контекст: поиск/исследование — в субагенте, в главный чат только резюме
5. Context eviction: чистить старые tool-выводы и завершённые подзадачи (30-60% окна)
6. Сильные модели — только на чистых коротких сессиях (agentrouter); тяжёлая работа — deepseek-v4-flash/gemini-3.7-flash; сильные — точечно

### 3.2 Конкретный план
- [ ] Обновить scripts/context_compaction.py: порог по токенам, формат сводки по TL;DR из раздела 4, привязка к Hermes-событиям
- [ ] Клиентский прокси с суммаризацией истории для agentrouter (вариант A из исследования №8) — чтобы длинные сессии не упирались в sensitive words
- [ ] Периодическая выгрузка статуса Vazus OS в файл памяти (C:\vazus\workspace\STATE.md) — один файл вместо длинной истории
- [ ] Пользоваться ckb/vazus-organic для точечных вопросов по коду/памяти вместо таскания исходников в чат

---

## 4..8. РЕЗУЛЬТАТЫ ИССЛЕДОВАНИЙ (5 параллельных агентов, отчёты с источниками в C:\vazus\docs\research\)

### 4. Контекст-компрессия 2026 (context_compression_2026.md, 45 KB)
TL;DR: компакция — первый рычаг (авто-суммаризация при заполнении окна, структурированный формат сводки); context rot: модель хуже использует длинный контекст; файловая память (NOTES.md/PROGRESS.md/CLAUDE.md) почти бесплатна и переживает сессии; субагенты изолируют грязный контекст; context eviction освобождает 30-60% окна; mem0/Letta/Zep решают память МЕЖДУ сессиями, не внутри; для роутера с лимитами: сессии короткие, сильные модели — точечно на чистых сессиях.

### 5. Провайдеры/роутеры 2026 (model_providers_2026.md, 33 KB)
TL;DR: OpenRouter — стандарт (5.5% комиссия); kluster.ai закрылся; топ-бюджет: GLM-5.2:free, Nemotron 3 Ultra :free (1М контекст); 2026 = год разделения подписок (Anthropic вынесла Agent SDK из обычной подписки); китайские гейтвеи дёшево, но dangerous; DeepSeek V4 подорожал (peak/off-peak с 17.08.2026). Рекомендации Vaz: укрепить бесплатный стек (agy IDE-квоты + opencode-go), один платный бюджетный канал (GLM Coding Plan ~$18/мес), пересчитать бюджет deepseek. Каталоги: freellm.net, awesome-freellm-apis (442+ API).

### 6. Память и KG 2026 (agent_memory_2026.md, 35 KB) — ГОТОВО
TL;DR: тренд 2026 — «меньше графа» (Letta без графа, Mem0 удалила graph-модуль из OSS); файлы-инструкции победили как базовый слой памяти агентов (AGENTS.md/CLAUDE.md/checkpoint:files); фоновая консолидация памяти (mem0 Dream, авг 2026: дедупликация, пометки, sleep-time) — самая ценная новая идея; bi-temporal факты (valid_at/invalid_at) — дёшево и полезно (у Vaz уже memory_facts_v2 — верное решение); sqlite-vec остаётся оптимальным для локальных векторов (ANN-индексы DiskANN/IVF уже есть); Microsoft GraphRAG — maintenance mode → LazyGraphRAG как альтернатива; CKB у Vaz уже работает (SCIP-индекс 20 585 символов). ВЫВОД: архитектура Vazus OS (SQLite+768D+факты+wiki) соответствует лучшим практикам 2026; добавить: фоновую консолидацию памяти (аналог Dream) и опционально LazyGraphRAG для больших корпусов знаний.

### 7. MCP-экосистема 2026 (mcp_ecosystem_2026.md, 51 KB)
TL;DR: MCP — стандарт (97M установок/мес, 10K серверов, Linux Foundation AAIF); релиз спецификации 2026-07-28 — крупнейший (stateless, routable headers, авторизация); стартовый набор: Context7 (доки библиотек), Playwright, GitHub, Brave/Tavily search, Sequential Thinking. Память: у Vaz уже vazus-organic (mem0+768D+KG) — НЕ дублировать. Безопасность: фиксировать версии серверов, не отключать env-фильтрацию Hermes, sampling off для ненадёжных, allowlist путей filesystem, только OAuth для remote, аудит репозиториев (AgentSeal/prompttools), не тянуть случайные npx/uvx. СВЯЗАНО сегодня: подключены sequential-thinking, playwright-mcp, colab-mcp → 5 серверов, 91+ инструмент.

### 8. Цензура гейтвеев (gateway_censorship_2026.md, 40 KB)
TL;DR: фильтр живёт в new-api/one-api (sensitive.go): сканирует запрос+ответ детерминированно — длинная сессия рано или поздно задевает; на СВОЁМ инстансе new-api фильтр отключается/настраивается; шифрование/разбиение не помогает (шлюз видит текст); варианты для Vaz: A. клиентский прокси с суммаризацией истории (быстро, дёшево); B. прямые официальные API (без цензуры, от $0.08/M); C. self-hosted new-api/LiteLLM на VPS вне Китая (~€5/мес) + OpenRouter/Anthropic upstream — ОСНОВНОЕ РЕШЕНИЕ для claude-opus/gpt-5.6 на длинных сессиях.

---

## 9. ГОТОВЫЙ ПРОМПТ ДЛЯ СИЛЬНОЙ МОДЕЛИ (запуск со всеми MCP)
Файл: C:\vazus\docs\SYSANALYST_PROMPT.md — 5 фаз: разведка (PROJECT/AGENTS/карта) → ядро (движок/верификация/память, реальные прогоны тестов) → сервисы/интеграции → Hermes-слой (провайдеры/плагины/конфиг) → безопасность → финальный отчёт C:\vazus\docs\SYSTEM_ANALYSIS_REPORT_<дата>.md.
Перед запуском: /new → /model agentrouter/claude-opus-4-8 (чистая короткая сессия, чтобы не словить sensitive words 500) → вставить промпт.

## 10. СТАТУС ДОВОДКИ (вечер 17.08.2026)
- [x] 8 падавших тестов починены + 1 новый → 685 passed (зелёный прогон)
- [x] UnicodeDecodeError cp1252 — utf-8/errors=replace в 3 местах сабпроцесс-спавна
- [x] /model для agentrouter — секция providers.agentrouter в config.yaml
- [x] TERMINAL_CWD deprecation — terminal.cwd задан
- [x] Watchdog + cron 09:00 — мосты, файлы, целостность БД
- [x] MCP: +3 сервера (sequential-thinking, playwright-mcp, colab-mcp) → 5 всего
- [x] 5 интернет-исследований (4 готовы, memory дописывается)
- [ ] Git-коммит кода (в процессе, прекоммит-гейт)
- [ ] .env-гигиена: удалить закомментированный TERMINAL_CWD из HERMES .env; почистить легаси ~/.hermes
- [ ] Внедрить прокси с суммаризацией истории для agentrouter (вариант A)
- [ ] Решить по VPS+new-api/LiteLLM (вариант C) — обсудить с AG2 при желании