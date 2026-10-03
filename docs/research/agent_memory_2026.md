# Системы памяти и knowledge-graph для персонального AI-агента/OS — исследование 2025–2026

**Дата:** 17 августа 2026
**Контекст:** Vazus OS (privacy-first, локально, Windows 11, Python, SQLite) — 768D-эмбеддинги, memory DB (facts/preferences), knowledge graph (FTS5 + vector similarity), MCP-серверы (vazus-organic, evo-код, jury-верификация, SMT Z3), CKB (SCIP) для кода, Obsidian для заметок.
**Цель:** понять, что из экосистемы памяти агентов 2025–2026 стоит внедрить, заменить или избегать.

---

## TL;DR

1. **Главный тренд 2026 — «меньше графа»:** Letta никогда не строила граф; Mem0 летом 2026 **удалила graph-модуль из OSS** (собственный бенчмарк показал: граф — 3× медленнее поиск и 2× токены за +1.6 балла), оставив дешёвый entity-linking. Полноценные факт-графы (Graphiti, Cognee) оправданы только там, где критичны обход по связям и история изменений фактов — для персональной OS это скорее нет.[9][12]
2. **Файлы-инструкции победили как базовый слой памяти агентов:** AGENTS.md (Codex), CLAUDE.md + auto memory (Claude Code), GEMINI.md + чекпойнты (Gemini CLI) — вся индустрия сошлась на markdown-файлах + иерархии + автозаписи.[34][36][38]
3. **Фоновая консолидация памяти («Dream»/sleep-time) — самая ценная новая идея 2026:** mem0 Dream (авг 2026): дедупликация, пометка устаревших фактов как superseded, обобщение повторяющегося поведения; Letta — sleeptime agents.[5][9]
4. **Bi-temporal факты (valid_at/invalid_at) — дёшево и полезно:** закрывать старый факт вместо удаления; реализуется в SQLite за полдня.[9]
5. **Для локальных векторов sqlite-vec остаётся оптимальным для Vazus** (брут-форс) и получает ANN-индексы (DiskANN, IVF, rescore) в v0.1.10-alpha — но pre-v1, фиксировать версию.[25][26]
6. **Microsoft GraphRAG — в maintenance mode** (README прямо об этом): не строить на нём; LazyGraphRAG — лучшая альтернатива по cost/quality.[15][16][17]
7. **CKB у Vaz уже установлен и рабочий:** live-статус показал SCIP-индекс (20 585 символов), git-аналитику и статические анализаторы; слабые места — «index exists: false» и не настроенный LSP/cartographer.[32]

---

## 1. Mem0 — «universal memory layer»

**Статус (авг 2026):** OSS-репозиторий 63k+ звёзд, активно развивается (v2.0.x SDK, pushed 2026-08-15). Три варианта поставки: библиотека (`pip install mem0ai`), self-hosted сервер (docker compose + дашборд + auth + advanced features), облачная Platform (SaaS, «zero infrastructure» — векторное хранилище и реранкеры на стороне Mem0).[1][2]

**Модель памяти:** конвейер Add → Extract/store (дистилляция сообщений в факты, связывание сущностей) → Recall (возвращаются только релевантные воспоминания; клиенты получают typed search: `reference_date`, `latest_only`, `keyword_search`, кастомные инструкции извлечения, structured-data schema в CLI v0.2.11).[1][2][6]

**Ключевые события 2025–2026:**
- **OSS v3 (апрель 2026) — graph-слой удалён** (PR #4805, commit a488e190). Вместо графа — entity linking: сущности извлекаются spaCy (не LLM), хранятся в параллельной векторной коллекции `{collection}_entities` с полем `linked_memory_ids` (hub-and-spoke). Поиск: семантический + BM25 + entity-boost, «отношения» — это число, добавленное к векторному скору. Причина: собственный бенчмарк на LOCOMO — граф-вариант (Mem0g) выиграл 68.44 vs 66.88, но проиграл single/multi-hop, поиск ~3× медленнее, ~2× токенов. В hosted Platform graph-память и временное затухание (time-based decay) остались.[9][12]
- **Mem0 MCP:** хостится на `https://mcp.mem0.ai/mcp`, подключается к Claude Code, Codex, Cursor, Windsurf, VS Code, OpenCode одной командой (`npx mcp-add`); есть плагины-маркетплейсы для Codex.[3]
- **OpenMemory** — отдельный продукт «AI Memory MCP Server for Coding Agents» для Cursor/VS Code/Claude (персональная память для coding-агентов; hosted, HIPAA/SOC2/GDPR); одноимённый OSS-проект mem0ai/openmemory — CLI/TUI для переноса сессий между Claude Code/Codex/OpenCode.[4][10?] Смежное популярное OSS: CaviraOSS/OpenMemory (4.4k★) — локальный персистентный memory-стор для Claude Desktop/GitHub Copilot/Codex.[41]
- **Dream** — фоновая консолидация (анонс 5 авг 2026, Pro/Enterprise): дубликаты сливаются, устаревшие факты помечаются superseded без потери истории, повторяющееся поведение обобщается в факты верхнего уровня. Мотивация: «write-path слеп» — медианный активный проект хранит сотни дублирующих/противоречащих воспоминаний.[5]
- Прочее из блога: AI Memory Confidence Score, memory staleness, event-based memory, кроссессионная идентификация, «Как Mem0 сократил footprint памяти Claude Code на 97%» (компрессия), 70× ускорение векторного поиска.[8]

**Качество/критика:**
- Свои бенчмарки (LOCOMO 92.5, BEAM) — vendor-reported, несравнимы между собой: разные judge-модели и сеты вопросов; Continua AI «LoCoMo Fair Fight» показал смещение ~10 пт от смены модели; Zep публично оспаривал SOTA-заявление Mem0 («Lies, Damn Lies & Statistics»).[9]
- Общественное мнение: «Mem0 stores memories, but doesn't learn user patterns» (Ask HN, фев 2026); Letta: files-only агент на LOCOMO — 74.0% против 68.5% у Mem0-графа.[9][40]
- Сама компания делает упор на облачную Platform; всё новое (Dream) сначала в SaaS.[5]

**Вывод для Vazus:** не зависеть от SaaS; из идей взять: (а) фоновую консолидацию (Dream), (б) entity-linking как дешёвую альтернативу полному графу, (в) typed search (latest_only, reference_date, keyword_search), (г) декларативные custom instructions для извлечения фактов.

---

## 2. Letta (MemGPT) и agentic memory research

**Статус:** в 2026 проект реструктурирован: старый Python-сервер (MemGPT → Letta) переведён в `letta-ai/letta`-landing page, актуальный код — **`letta-ai/letta-code`** (npm `@letta-ai/letta-code`): агентные харнессы с памятью, desktop-приложение (Win/macOS/Linux), App Server для self-hosted, каналы (Slack/Telegram/Discord), Agent SDK (TypeScript), Letta Cloud; релизы 0.16.x (март 2026 — «big upgrade» для self-hosted, поднят дефолтный глобальный контекст; auto-компиляция системного сообщения в новых беседах).[10][11][14]

**Архитектура памяти Letta (память = саморедактируемый текст):**
- **Memory blocks** — именованные текстовые блоки с лимитом символов, всегда в контексте; агент правит их инструментами `core_memory_replace`, `memory_replace`, `memory_insert`, `memory_apply_patch`, `memory_rethink`. Обновление — обычная подмена строки, «переезда» не фиксируется, пока LLM сам не заметит противоречие.[9]
- **Archival memory** — векторный поиск по требованию; **recall** — история сообщений; опциональный **filesystem** для документов.
- **Sleep-time**: sleeptime-агенты консолидируют/переписывают блоки между ходами; /sleeptime, аудит качества памяти /doctor, просмотр /palace; **MemFS** — весь контекст (включая memory blocks) трекается git'ом и может синкаться в GitHub-репозиторий (/memory-repository).[11][9]
- **Letta Code**: агенты «переписывают свою память, навыки, промпты и сам харнесс (mods)», обучаются навыкам, работают в удалённых окружениях (`letta server --env-name`).[11]
- **«Is a Filesystem All You Need?»** (авг 2025): дампы транскриптов LOCOMO в файлы при обычном агенте дали 74.0% — выше graph-систем; тезис: агенты уже обучены итеративному поиску в файлах, специализированные memory-системы дают мало.[9][13]

**A-MEM (arXiv 2502.12110, NVIDIA, фев 2025, v11 окт 2025):** agentic memory по принципам **Zettelkasten** — при добавлении воспоминания генерируется «заметка» с атрибутами (контекстное описание, ключевые слова, теги), система анализирует историю и строит динамические связи между заметками; память = интерконнект graph of notes. Это ближайшая парадигма к Obsidian-подходу Vazus.[12]

**Вывод для Vazus:** Vazus уже движется в правильном направлении (Obsidian-заметки + КГ). Заимствовать: (а) git-трекинг памяти (MemFS) — дешёвый аудит и восстановление, (б) sleep-time/фоновую переработку, (в) /doctor-подобные метрики качества памяти.

---

## 3. GraphRAG и knowledge-graph подходы

**Microsoft GraphRAG — в maintenance mode.** README (авг 2026): «проект в основном в maintenance mode, новых PR и фич не принимает»; остаются багфиксы и CVE-апдейты. Несмотря на это, живы версии 1.x/2.x/3.x: 3.0 — monorepo-реструктуризация (packages: graphrag-cache, chunking, common, input, llm, storage, vectors), 2.x — NLP-извлечение графа, LiteLLM, gpt-5 support, 3.1.x — патчи (Cosmos-провайдер и пр.).[15][16] Инкрементальный апдейт есть (`graphrag update`, merge новых сущностей в существующий индекс, обновление community-структур), но в целом пайплайн тяжёлый и дорогой.[18][17]

**LazyGraphRAG (март 2025)** — отдельная облегчённая реализация: джойнится с существующим графом, снижает стоимость и задержки на порядки при сопоставимом качестве; «setting a new standard for quality and cost».[9][17][19?]

**Важное различие (по codepointer, май 2026):** document-RAG графы (MS GraphRAG, LightRAG) строят граф из документов для QA по корпусу — это не агентная память. Для агентной памяти: Letta — саморедактируемый текст без графа; Mem0 — вектор + entity hints (граф удалён); Graphiti — факт-граф; Cognee — ETL-пайплайн в граф.[9]

- **Graphiti (Zep)**[23][24]: bi-temporal граф фактов — `EpisodicNode` (исходный вход), `EntityNode`, `CommunityNode` (кластеры), `EntityEdge` (факт «Entity--RELATES_TO-->Entity» с текстом и эмбеддингом). Каждое ребро: valid time (`valid_at`/`invalid_at`) и transaction time (`created_at`/`expired_at`). При противоречии старое ребро **закрывается (invalidation), а не удаляется** — можно спрашивать «что было правдой тогда». Инкрементальная загрузка (LLM-извлечение, entity resolution: детерминированный MinHash+LSH с LLM-фолбэком), retrieval = cosine + BM25 + BFS с плагинными реранкерами (RRF, node-distance, MMR, episode-mentions, cross-encoder), без LLM на запросе, субсекундно. Минус: дорого на запись (много LLM-вызовов на эпизод); Zep-статья: DMR 94.8% vs MemGPT 93.4%, плюс LongMemEval.[23][24]
- **Cognee:** ECL-конвейер (Extract → Cognify → Load) с этапами-задачами; граф (Kuzu «ladybug» по умолчанию / Neo4j / Neptune / Postgres) + вектор (LanceDB / pgvector / Chroma) + реляционный слой (SQLite / Postgres); поиск GRAPH_COMPLETION (vector-seeded traversal + LLM); **ontology grounding** (OWL/RDF, флаг `ontology_valid` против галлюцинированных сущностей); структурированный ввод через dlt.[9]
- **LangGraph / LangMem (LangChain):** LangMem — core memory API для любого хранилища, memory-инструменты «в горячем пути» (create_manage_memory_tool, create_search_memory_tool), **фоновый memory manager** (авто-извлечение, консолидация, обновление знаний), нативная интеграция с LangGraph Long-term Memory Store.[20]
- **Neo4j:** LLM Graph Builder (из неструктурированных данных в КГ; требует Neo4j 5.23+, LangChain/FastAPI) и официальный пакет `neo4j-graphrag-python` (ретриверы, гибридный поиск, обогащение векторного поиска обходом графа) — «GraphRAG Manifesto».[21][22]

**Бенчмарки агентной памяти 2025–2026:** LOCOMO (arXiv 2402.17753; single/multi-hop, temporal, open-domain, adversarial; диалоги всего 16–26k токенов), LongMemEval (arXiv 2410.10813; 500 вопросов, knowledge updates, abstention), BEAM (arXiv 2510.27246, ICLR 2026; до 10M токенов, 10 memory-способностей), новые: MemoryArena (2602.16313), Locomo-Plus (2602.10715), Hindsight (Vectorize).[9] **Осторожно:** vendor-скоры несравнимы (разные judge и сеты вопросов).

**Вывод для Vazus:** полный факт-граф с LLM-извлечением на каждую запись — дорого для персональной OS. Но bi-temporal invalidation — почти бесплатно в SQLite и решает проблему противоречивых фактов; entity-linking вместо тяжёлого графа даёт большую часть выгоды.

---

## 4. Векторные БД и RAG для персональных знаний

- **Chroma:** стабильная ветка 1.5.x (1.5.9 — май 2026, active dev); отдельно развивается Chroma Foundation (Rust CLI). Клиент-сервер; хорошо держит 768D. Для Vazus — избыточен, т.к. уже есть SQLite.[29]
- **Qdrant:** зрелый Rust-движок, hybrid dense+sparse (BM42) и бинарная квантизация; в 2025 вышли Contexts (документные контексты для поиска).[27? unverified] Детали не проверялись из-за блокировок сайта — основное достоинство для Vazus: быстрый ANN при больших объёмах; для персональных объёмов не требуется. [unverified для Contexts]
- **LanceDB:** embedded/ин-процесс, нативные API (Python/Rust/JS), формат Lance, GPU-ускоренная индексация, встроенный FTS, multivec; **$30M Series A (июнь 2025)** — компания самостоятельная (не приобретена Databricks; партнёрство), LanceDB Cloud — public beta. Если Vazus захочет отдельно от SQLite — лучший embedded-кандидат, но это ещё одна зависимость.[27][28]
- **sqlite-vec (asg017):** «extremely small, fast enough» SQLite-расширение, vec0-виртуальные таблицы (float/int8/binary), чистый C, работает везде, где SQLite (вкл. Windows и WASM), метаданные/вспомогательные колонки, Mozilla-спонсорство (2024). После паузы проект «вернулся» (v0.1.7, 2025) и в v0.1.10-alpha добавляет настоящие **ANN-индексы: rescore, IVF, DiskANN** (дизайн в духе FTS5-команд). Всё ещё **pre-v1 — breaking changes**.[25][26]
- **RAG-паттерн для персональных знаний 2026:** гибрид (FTS5/BM25 + вектор) + мелкие чанки + метаданные-фильтры + локальный реранкер; sqlite-vec + FTS5 в одном SQLite-файле покрывает это целиком.[25]

**Вывод для Vazus:** текущий выбор (SQLite + свои 768D + FTS5) соответствует индустриальному минимуму и это ок. Следить за sqlite-vec v0.1.10 (DiskANN) для больших коллекций; зафиксировать версию расширения. Переход на внешнюю векторную БД не оправдан для персональных объёмов.

---

## 5. CKB (SCIP) и аналоги для кода

**SCIP** — язык-агностичный протокол индексации кода (protobuf, Go/Rust-биндинги, CLI), мейнтейнится в `scip-code/scip`; индексеры: scip-python, scip-typescript, scip-java, scip-clang, scip-ruby, scip-dotnet, scip-dart, scip-php, rust-analyzer.[30][31] SCIP-индекс легче LSP-сессии и пригоден для офлайн-анализа.

**CKB (Code Knowledge Base)** — локальный код-интеллект поверх SCIP (Sourcegraph). **Live-верификация через установленный у Vaz MCP-сервер ckb (авг 2026):** бэкенды — `scip` (работает; текущий индекс: 20 585 символов, 350 документов; symbol-search, find-references, goto-definition), `lsp` (не настроен), `git` (blame/history/churn — готов), `cartographer` (layer-analysis, health-scoring, hidden-coupling, cochange-analysis, dead-code-detection, simulate-change, semidiff, module-skeleton — не настроен). MCP-пресеты инструментов: core (25/110 инструментов, экономия токенов ~75%), review (test coverage, compliance, secrets), refactor (coupling, dead code, cycles), docs (ADR, symbol-doc). Конфиг `.ckb/config.json`, команды `ckb setup/index/doctor`; рекомендации статуса: `Run 'ckb index'`, «Configure LSP server», «Run ckb doctor».[32] Официальные доки публично не найдены (страницы docs 404) — описание по live-инстансу.[32][unverified для даты релиза и официального анонса]

**Аналоги для кода:**
- **LSP-база** (rust-analyzer, gopls, Pyright) — точный, но тяжёлый, требует живых серверов.
- **tree-sitter repo map (aider)** — лёгкое извлечение структуры (definitions, references) в «map-файл» для промпта; минимальный аналог CKB без БД.
- **scip-ctags / universal-ctags** — классика для навигации.
- **intuit/infigraph** — AST-powered code intelligence: персистентный граф кодовой базы до запуска агента, структурные вопросы без сотен токенов на поиск.[33]
- **CaviraOSS-класс локальных MCP-памятей** и **Engram** (memory for AI coding agents, 2026) — ряд стартапов делает «память для coding-агентов» поверх файлов/MCP.[41][42]

**Вывод для Vazus:** CKB уже внедрён — капитализировать: (1) поднять свежий индекс (`ckb index`; сейчас `index exists: false`), (2) настроить LSP-бэкенд для hover, (3) включить cartographer-пресет (dead-code, coupling) как аналог «эволюции кода» с более дешёвой статикой, (4) пресет refactor перед объединением PR. Дополнительно: aider-стиль repo map можно генерировать прямо из SCIP-индекса.

---

## 6. Как устроена память в топовых агентах 2026

**Claude Code (anthropics/claude-code, 141k★):** два механизма, оба файловые: **CLAUDE.md** (инструкции пользователя) и **auto memory** (заметки, которые Claude пишет сам из коррекций и предпочтений; включено по умолчанию; вкл/выкл через /memory → auto memory toggle → `~/.claude/settings.json`; у суб-агентов своя auto memory; просмотр/редактирование через /memory). CLAUDE.md-иерархия: от корня проекта вниз, `import` доп. файлов, организация через `.claude/rules/`, path-specific rules, user-level rules, AGENTS.md конвертируется в CLAUDE.md (v2.1.213+); после /compact CLAUDE.md перечитывается с диска и снова инжектится; trim-check для слишком больших файлов (v2.1.206+). Никакой векторной БД в ядре — управляемые файлы + контекст.[34][35]

**Codex (openai/codex, 106k★):** вся постоянная память — **AGENTS.md-цепочка**, собирается один раз за сессию: global (`~/.codex/AGENTS.md` или `AGENTS.override.md`) → project root → путь до cwd (максимум один файл на директорию, ближние файлы перекрывают дальние), лимит `project_doc_max_bytes` (32 KiB по умолчанию), fallback-имена файлов (`project_doc_fallback_filenames`), `CODEX_HOME` для профилей; аудит загруженных инструкций через TUI-лог/JSONL-сессии. Никакой автозаписи памяти «из разговора» — только инструкции.[36][37]

**Gemini CLI (google-gemini/gemini-cli, 106k★):** (1) **GEMINI.md** — глобальный (~/.gemini/GEMINI.md) + workspace + JIT (сканирование директорий при обращении инструмента к файлам) — конкатенация всех найденных файлов в каждый промпт; (2) **session management** — автосохранение полной истории (промпты, tool-вызовы, токены, рефлексия) в `~/.gemini/tmp/<project_hash>/chats/`, resume; (3) **checkpointing** — перед каждым модифицирующим tool-вызовом: git-снапшот в теневом репозитории `~/.gemini/history/<project_hash>` + история + tool-call; `/restore` возвращает файлы и диалог; (4) skills; всё локально.[38]

**Общие черты 2026:**
- Стандартизация иерархических файлов-инструкций (AGENTS.md / CLAUDE.md / GEMINI.md) + импорт/конвертация между ними (агенты понимают чужие форматы).
- Минимальная автопамять: Claude Code — единственный с автоматическим накоплением «личных» заметок; остальные — инструкции + сессии.
- Персистентность сессий (resume/compact/checkpoint) как база.
- Внешняя память — через **MCP** (mem0 MCP, Graphiti MCP, OpenMemory) — агенты не таскают векторные БД сами, а вызывают их как инструменты.[3][23]
- Letta Code — крайняя точка: агент сам управляет памятью (блоки, навыки, моды), память под git.[11]

---

## 7. Рекомендации для Vazus OS

### Внедрить (приоритетно)
1. **Фоновая консолидация памяти в стиле Dream/sleep-time** — per-project/per-day: дедупликация near-duplicate фактов, пометка устаревших как superseded (не удалять), обобщение повторяющихся паттернов в факты верхнего уровня; запускать как фоновую задачу/крон, отдельно от hot-path записи.[5][9]
2. **Bi-temporal атрибуты для фактов** (`valid_at`/`invalid_at`, `created_at`/`expired_at`) в существующей memory DB; при записи противоречащего факта — инвалидировать старый. Ровно то, что решает «Lives in Tokyo → moved to Osaka».[9][23]
3. **Entity linking hub-and-spoke** (сущность → linked_memory_ids) вместо/в дополнение к тяжёлому графу: spaCy-извлечение + буст скорринга; GraphRAG-обход оставить только для редких случаев. Проверить на своих 768D.[9]
4. **Typed search:** latest_only, reference_date, keyword_search — дёшево, заметно улучшает recall.[6]
5. **git-трекинг памяти (MemFS-стиль):** уже есть git; добавить авто-коммиты memory DB/графа + аудит изменений.[11]
6. **Метрики здоровья памяти:** /doctor-стиль: протухшие факты, дубликаты, противоречия, confidence score — поверх jury-верификации.[5][11]
7. **sqlite-vec:** зафиксировать текущую версию; протестировать v0.1.10-alpha (DiskANN/IVF/rescore) на коллекции >50k векторов; гибрид FTS5+vector — уже есть.[25][26]
8. **CKB:** свежий индекс (`ckb index`), настроить LSP-бэкенд, включить cartographer (dead-code, coupling, simulate-change) — это усилит «эволюцию кода» детерминированной статикой.[32]
9. **MCP-фасад памяти:** экспонировать факты/граф Vazus через MCP (как mem0 MCP/Graphiti MCP), чтобы любой внешний агент (Claude Code, Codex, Gemini) мог читать/писать память — смесь OpenMemory-идеи.[3][23]

### Чего избегать
- **Microsoft GraphRAG и тяжёлые статические graph-пайплайны** — maintenance mode + дорогой индексинг; для персональных данных не окупается.[15][9]
- **Полный факт-граф с LLM-извлечением на каждое событие** (Graphiti/Cognee-режим): ~2× токенов на запись и дорогая сервисная инфраструктура; брать только bi-temporal идею.[9]
- **SaaS-память (mem0 Platform, hosted OpenMemory, Zep Cloud)** — против privacy-first; если и тестировать — OSS-версии локально.[1][4]
- **Доверять vendor-бенчмаркам** (LOCOMO-скоры mem0/Zep/Letta несравнимы; LoCoMo Fair Fight — ±10 пт от модели).[9]
- **Слепая автозапись в память без верификации** — именно против этого у Vaz уже есть evidence jury; дополнить консолидацией.
- **Замена SQLite на серверную векторную БД** ради персональных объёмов — избыточно; sqlite-vec + FTS5 достаточно до ~миллиона векторов.[25]
- **sqlite-vec в production без пина версии** — pre-v1, breaking changes.[25]

---

## Источники

1. https://github.com/mem0ai/mem0 — README (OSS/self-hosted/Platform, CLI, v2.0.x)
2. https://docs.mem0.ai/overview — конвейер памяти и Platform
3. https://docs.mem0.ai/platform/mem0-mcp — Mem0 MCP (mcp.mem0.ai, Claude Code/Codex/Cursor)
4. https://mem0.ai/openmemory — OpenMemory: MCP-память для coding-агентов
5. https://mem0.ai/blog/dream-background-memory-consolidation-for-ai-agents — Dream (5 авг 2026)
6. https://github.com/mem0ai/mem0/releases — релизы SDK/CLI (v2.0.16–2.0.18, cli 0.2.11)
7. https://arxiv.org/abs/2504.19413 — Mem0 paper (Extract-Consolidate-Retrieve; LOCOMO)
8. https://blog.mem0.ai/ — индекс блога (staleness, confidence score, event-based memory, 70× latency, 97% footprint)
9. https://codepointer.substack.com/p/agent-memory-systems-and-knowledge — сравнение Letta/Mem0/Graphiti/Cognee (май 2026)
10. https://github.com/letta-ai/letta — landing page проекта (реструктуризация, letta-code)
11. https://github.com/letta-ai/letta-code — Letta Code: memory blocks, MemFS, /sleeptime, /doctor, /palace, skills, mods
12. https://arxiv.org/abs/2502.12110 — A-MEM: Agentic Memory for LLM Agents (Zettelkasten)
13. https://www.letta.com/blog/letta-filesystem — «Is a Filesystem All You Need?» (авг 2025; URL из web.archive.org CDX)
14. https://github.com/letta-ai/letta/releases — 0.16.x (март 2026, self-hosted upgrade)
15. https://github.com/microsoft/graphrag — README: maintenance mode
16. https://github.com/microsoft/graphrag/blob/main/CHANGELOG.md — 3.x/2.x изменения (monorepo, LiteLLM, gpt-5)
17. https://microsoft.github.io/graphrag/ — официальные доки
18. https://deepwiki.com/microsoft/graphrag/4.7-incremental-indexing-and-updates — инкрементальный индексинг (graphrag update)
19. https://github.com/langchain-ai/langmem — LangMem: memory tools + фоновый memory manager + LangGraph Store
20. https://github.com/langchain-ai/langmem — README (hot-path management, background consolidation)
21. https://github.com/neo4j-labs/llm-graph-builder — Neo4j LLM Graph Builder (5.23+)
22. https://github.com/neo4j/neo4j-graphrag-python — официальный Neo4j GraphRAG пакет
23. https://github.com/getzep/graphiti — bi-temporal граф фактов, hybrid retrieval, MCP server
24. https://arxiv.org/abs/2501.13956 — Zep paper (DMR 94.8 vs 93.4, LongMemEval)
25. https://github.com/asg017/sqlite-vec — vec0, pre-v1, ANN-релизы v0.1.10-alpha (rescore/IVF/DiskANN)
26. https://alexgarcia.xyz/blog/2024/building-new-vector-search-sqlite/index.html — блог автора sqlite-vec
27. https://github.com/lancedb/lancedb — LanceDB README (embedded, Lance, GPU, FTS)
28. https://lancedb.com/blog/series-a-funding/ — $30M Series A (24 июня 2025)
29. https://github.com/chroma-core/chroma/releases — 1.5.x (май 2026) + Chroma Foundation
30. https://github.com/scip-code/scip — SCIP protocol, CLI, биндинги
31. https://github.com/sourcegraph/scip-python — индексеры SCIP (python/typescript/clang/java/ruby/…) см. README scip
32. CKB MCP (установленный в Hermes у Vaz: mcp__ckb__getStatus, 17 авг 2026) + https://mcpmarket.com/server/ckb-1
33. https://github.com/intuit/infigraph — AST-powered code intelligence graph
34. https://docs.claude.com/en/docs/claude-code/memory — CLAUDE.md + auto memory (/memory, settings.json, rules/, AGENTS.md import)
35. https://github.com/anthropics/claude-code — статус и описание
36. https://developers.openai.com/codex/guides/agents-md — AGENTS.md chain (via web.archive.org snapshot)
37. https://github.com/openai/codex — README + docs (docs/agents_md.md, docs/config.md)
38. https://github.com/google-gemini/gemini-cli — README + docs/cli/gemini-md.md, checkpointing.md, session-management.md
39. https://agents.md — стандарт AGENTS.md (упомянут в доках Codex)
40. https://news.ycombinator.com/ — Ask HN: «Mem0 stores memories, but doesn't learn user patterns» (фев 2026; найдено через hn.algolia.com)
41. https://github.com/CaviraOSS/OpenMemory — локальный memory-стор для Claude Desktop/Codex (4.4k★)
42. https://www.engram.fyi — Engram: memory for AI coding agents (Show HN, март 2026)

*Примечание:* пункты 32 (официальный анонс CKB) и 27/29-смежные (Qdrant Contexts) отмечены как [unverified] в тексте — официальные страницы не были доступны из-за блокировок/404; описание CKB собрано по live-данным установленного MCP-сервера.