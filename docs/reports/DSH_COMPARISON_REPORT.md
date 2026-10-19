# Сравнительный отчёт: DeepSeek Harness (dsh) vs Hermes (Nous Research) vs Google Antigravity 2 (AG2)

> Исполнитель: агент DeepSeek Harness (dsh), сессия на Web UI `http://127.0.0.1:3080`.
> Задание: `C:\vazus\docs\DSH_COMPARE_PROMPT.md` (подготовлено Hermes, 17.08.2026).
> Рабочая папка: `C:\vazus`. Дата выполнения: 17.08.2026.
> Статус: ИССЛЕДОВАНИЕ по заданию; вердикты не принимал — это факты и оценки для обсуждения с AG2.

## ⚠️ Важное ограничение выполнения

**Веб-поиск в текущем окружении dsh недоступен.** Инструмент `web_search` дважды вернул
«Authentication Fails, Your api key: ****2R4V is invalid» (попытки 17.08.2026). В соответствии
с разделом 5 задания («Если веб-поиск недоступен в твоём окружении — честно напиши это в отчёте
и выполни разделы 1–2 по локальным файлам»):

- Разделы о **dsh** и **Hermes** выполнены по: (а) собственному рантайму dsh (эта сессия),
  (б) чек-ауту dsh на машине (`%APPDATA%\npm\node_modules\@deepseek-ai\dsh`),
  (в) локальным файлам контура Vazus и Hermes.
- Раздел **AG2** содержит **только локально подтверждённые факты** контура Vazus (файлы
  `C:\vazus\docs\*`, скиллы Hermes, конфиги). Интернет-факты (анонсы Google, обзоры TechCrunch/
  Verge/Ars/HN, тарифы, статус GA, сравнения с Claude Code/Cursor/Codex) **не подтверждены —
  источник недоступен**. Соответственно, URL в разделе AG2 отсутствуют.

---

## 1. Сводная таблица

Оси — по заданию. AG2: помечено «лок.», если факт из локальных файлов контура; «не подтв.» —
требует интернета (недоступен).

| Ось | dsh (DeepSeek Harness) | Hermes (Nous Research) | Google Antigravity 2 (AG2) |
|---|---|---|---|
| **Архитектура и расширяемость** | Node.js/TypeScript. Cordis-основа: «всё — плагин», нет привилегированного ядра; регистрации = обратимые эффекты (unwind). Композиция profile → bundle → patch-слои (profile → home → `--patch`); `--dump-config` показывает собранное дерево. Одноимённые пакеты npm `@deepseek-ai/dsh-*` (~60 шт. в зависимостях CLI). | Python, CLI-first. Расширения: скиллы (`SKILL.md` с YAML-фронтматтером), MCP-серверы (vazus-organic, ckb), плагины, персоны, гейтвеи-платформы. Патч-слоёв и hot-swap нет (по самоописанию — перезапуск). | Агентный IDE (десктоп), хост-платформа контура («Google Antigravity 2.0 (AG2)» — лок. файл `AG2_FULLSYSTEM_AUDIT_PROMPT.md`); примитивы субагентов `define_subagent`/`invoke_subagent`, `manage_task`, `ask_question`, Auxiliary Pane, slash-команды `/goal /schedule /grill-me /teamwork-preview /learn` (лок.). GA/версии — не подтв. |
| **Рантайм и модель исполнения** | Агентный цикл поверх append-only журналов `session/*`; лаунчер: `dsh web` (Web UI :3080), `dsh --profile headless "job"`, `dsh plugin` (pnpm), 4 агент-пресета (в поставке: standard, code, minimal, cordis). Модель по умолчанию — DeepSeek API; кастомные OpenAI-совместимые эндпоинты заявлены (не проверял в этой сессии). | Диалоговый агент в терминале (git-bash/Windows); модель из конфига: провайдер `opencode-go`, `https://opencode.ai/zen/go/v1`, дефолт **deepseek-v4-flash**, `api_mode: chat_completions`, `reasoning_effort: ultra`, `max_turns: 150` (конфиг). Терминал: local + docker-параметры; браузер; стоп-гварды циклов (warn/hard-stop); делегирование до 50 итераций; сжатие контекста (threshold 0.5 → 0.2); prompt-caching 5 мин (конфиг). | Доступ к моделям через **IDE-сессионную квоту** (0 внешних платежей): CLI `agy` v1.1.13 (`%LOCALAPPDATA%\agy\bin\agy.exe`) и SDK `google-antigravity` v0.1.10 (лок.). Модели по квоте: Gemini 3.1 Pro (High), Gemini 3.5/3.6/3.7 Flash (High), Claude Opus 4.6 / Sonnet 4.6 (Thinking), GPT-OSS 120B (Medium); вызов ≈ 40–45 с (лок. скилл agy-cli-backend). |
| **Память и сессии** | Append-only `SessionEvent`-лог; session projection; spill больших выводов во временные файлы (наблюдал в этой сессии: `%TEMP%\dsh-spill-*\session-*\*.txt`); цели (goal) с раундами в пределах сессии; **кросс-сессионной персистентной памяти пользователя не наблюдаю**. | Персистентная память, инжект в каждый ход (`memory_enabled`, лимиты 2200/1375 симв., `flush_min_turns: 6`, `nudge_interval: 10` — конфиг) + `vazus.db`: KG (`kg_nodes`/`kg_edges`), 768D векторы (`vec_kg_nodes`, sqlite-vec vec0 float[768]), FTS5 (`organic_insights_fts`), mem0-факты, `memory_facts_v2`, диалоги/трассы, `skill_registry`, рефлексия-уроки (см. раздел 3). | Память контура ведётся в `vazus.db` (тот же KG/768D/FTS5) + brain-архив транскриптов `~/.gemini/antigravity-cli` (6.1 ГБ, 513 brain-папок, 31 215 записей — лок. файл `vazus_skill_architecture.md`); verdicts фиксируются в vazus.db. |
| **Интерфейсы (CLI/Web/IDE)** | **Web UI :3080** (этот GUI), headless-режим, CLI-лаунчер; Python SDK — заявлено во внешнем брифе Hermes, из чек-аута не подтверждаю. | CLI-first; гейтвеи доставки: telegram, discord, slack, teams, whatsapp, signal, google_chat, homeassistant, qqbot, yuanbao, cli (`platform_toolsets` — конфиг). Собственного Web UI нет (по самоописанию; локально не найдено). | IDE (десктоп) + CLI `agy`; MCP-реестр `~/.gemini/config/mcp_config.json`; скиллы `~/.gemini/config/skills/` и builtin `~/.gemini/antigravity/builtin/skills/` (лок. файл `REGISTRIES.md`). |
| **Автономность и само-модификация** | Горячая перекомпоновка плагинов без рестарта (Cordis unwind) — декларировано и заложено в загрузчик (патч-слои, `--patch`). HMR клиентских плагинов — при живом dev-сервере; иначе пересборка + refresh. Goal-раунды дают автономное продолжение задач. | Автономные циклы Vazus: генерация SKILL.md из транскриптов (`auto_skill_engine.py`), рефлексия/уроки, дебаты AGY/Hermes файловым протоколом (лок. файлы). Само-модификация ядра Hermes — не встроена (внешние циклы контура, по самоописанию). | Субагентная матрица (3 агента: Planner/RLM_Coder/Verifier_Worker) + кворум ≥66% + жюри (лок. `AG2_FULLSYSTEM_AUDIT_PROMPT.md`); IDE-квота — основной «мозг» контура. |
| **Безопасность и приватность** | Песочницы: файловая политика (здесь `workspace-write`), pwsh-песочница (read-only = ConstrainedLanguage; внешним программам запрещены named pipes и piped stdio → EPERM; документированная граница), approval-политика fail-closed. Телеметрия: выключатель `DSH_TELEMETRY_DISABLED` + строка-флаг `session-telemetry-otel` (проверено в `lib/profile-boot-DG5t9aNs.js`); профиль работает и без телеметрии. | Локальность: свои бэкенды (agy-квоты IDE, адаптер :5001), opt-in гейты на облако по умолчанию 0: `VAZUS_LLM_ALLOW_CLOUD=1`, `VAZUS_VISION_ALLOW_CLOUD=1`, `VAZUS_JULES_LIVE=1` (лок. `TIER1_BRIEF_FOR_AG2.md`); `protected_whitelist` в vazus.db; запрет секретов в репо. | Zero-trust политики, fail-closed hooks (`~/.gemini/config/hooks.json`: pre/post_tool_hook), запрет `google.genai`/`os.system`/`shutil.rmtree` в жюри (лок. `concordia_jury.py`); 6-уровневый precommit-гейт (AST → pytest → SMT Z3 → Jury ≥66% → vulture → ruff). |
| **Экосистема плагинов/скиллов** | Плагины npm `@deepseek-ai/dsh-*` (bundle'ы, профили, скиллы `SKILL.md` — dsh-skill-filesystem), 4 агент-пресета; скиллы из каталога сессии (mirea, vazus-*). Пока экосистема 4-дневная (по внешнему брифу). | 100+ `SKILL.md` в 15+ категориях (research, github, productivity, mlops, devops, smart-home, apple, media, creative, email, software-development, autonomous-ai-agents, note-taking, social-media, **vazus**), 768D-диспетчер скиллов (3 тира: keyword → вектор → effort), MCP: vazus-organic, ckb (+ в контуре AG2: colab, playwright, sequential-thinking). | MCP-реестр контура (ckb, vazus-organic, colab, playwright, sequential-thinking — лок.); скиллы AG2: frontmatter-валидные SKILL.md, `dynamic_skill_dispatcher` (768D) читает `~/.gemini/config/skills/` (лок. `REGISTRIES.md`). |
| **Зрелость и риски** | **0.1.0-rc.6 (prerelease, RC)**; README прямо обещает breaking changes. Риски: свежесть, модельная зависимость (по умолчанию облако DeepSeek), Node/TS против Python-стека; в этом прогоне суб-агенты падали без результата, веб-поиск не работает (см. §2). Звёзды/форки из внешнего брифа (130 872★/13 102 fork) — не подтв. | По самоописанию — production, зрелый тулсет; локально: 703/703 pytest (TIER1), бенчмарки AST-прунинга 78–88% (`docs/BENCHMARK_REPORT.md`). Риски: перезапуск для смены конфига/плагинов (по самоописанию), нет Web UI, нет патч-слоёв. | Статус GA, регионы, тарифы, обзоры — **не подтв.** (интернет недоступен). Контурно: IDE-квота работает (лок. скрипты/скиллы), ROI one-call ≈ 40–45 с. |

---

## 2. dsh о себе — честная самооценка

### 2.1 Кто я (что реально работает — проверено в этой сессии)

- **Файловые инструменты**: read (с номерами строк), write, edit (literal-замена), glob, grep —
  работают; большие результаты спиваются в `%TEMP%\dsh-spill-*` (наблюдал при glob по чек-ауту).
- **PowerShell через песочницу**: `pwsh -Command` работает; для сложных аргументов потребовался
  `--%` (PowerShell съедает вложенные кавычки); read-only осмотр SQLite в режиме `file:...?mode=ro`
  прошёл успешно (vazus.db — не тронут).
- **Goal-механика**: цель создана, раундовое продолжение задекларировано; todo-планирование работает.
- **Скиллы**: каталог сессии загружается; dsh имеет штатный механизм скиллов
  (`@deepseek-ai/dsh-skill-filesystem`).
- **Сборка/пакет dsh**: подтверждаю лаунчер (`dsh web`, `--profile headless`, `plugin`, `--patch`,
  `--dump-config`/`--dump-default-config`), профиль = упорядоченный стек bundle-патч-слоёв,
  пресеты `standard/code/minimal/cordis` (creative в поставке нет), телеметрию с программным
  выключателем `DSH_TELEMETRY_DISABLED`.

### 2.2 Что у меня есть «на борту» (задекларировано в рантайме, частично не запускалось в этой сессии)

- Субагенты (изолированные контексты, фоновые), workflow-оркестрация (fan-out из JS-скрипта),
  ralph (свежие дети на общем workspace), goal-раунды, plan mode, session projection, time context,
  token meter, `dsh-mcp-client`, `dsh-headless`, `dsh-web-app`, компакция контекста
  (`dsh-compaction-basic`, `tool-result-pruner`).

### 2.3 Честные ограничения и риски developer preview (rc.6)

1. **Версия 0.1.0-rc.6 — кандидат в релиз, pre-release.** В README прямо предупреждают о
   breaking changes. Строить прод-инфраструктуру на rc.6 сейчас нельзя — согласен с вердиктом
   `AG2_DSH_BRIEF.md §8` («принимать в контур как компонент: НЕТ»).
2. **Нестабильность исполнения, наблюдаемая в этом прогоне**: оба делегированных субагента
   завершились без результата («failed before it finished», без финального сообщения). Вывод:
   в текущем развёртывании субагентный трек ненадёжен — не полагаться на него без повторного
   прогона. Workflow/ralph в этой сессии не запускались (не могу подтвердить их работоспособность).
3. **Веб-поиск не работает**: `web_search` → «Authentication Fails, api key ****2R4V invalid».
   Интернет-исследования из dsh в этой среде невозможны (что и ограничило раздел AG2).
4. **Windows-песочница — жёсткие границы**: внешним программам запрещено открывать named pipes;
   программа, захватывающая stdout через piped stdio (`stdio: 'pipe'`), ловит EPERM — это
   документированный предел, а не баг; read-only режим pwsh — ConstrainedLanguage (нет COM,
   .NET-статики, `Add-Type`, рефлексии).
5. **GUI — не standalone**: `apps/web` — Vite-оболочка, живёт только под `dsh web` (инжекция
   `window.__DSH_BOOT__`); клиентские плагины без живого HMR-watcher требуют пересборки и refresh.
6. **Нет кросс-сессионной памяти пользователя** (в отличие от Hermes с инжектом фактов в каждый
   ход); нет гейтвеев доставки (Telegram и т.п.) и cron-джобов «из коробки».
7. **Не проверено/не подтверждаю**: Python SDK (упомянут во внешнем брифе; из npm-пакета не виден),
   счётчики GitHub (звёзды/форки), поведение кастомных OpenAI-эндпоинтов (гипотеза :5001 из брифа
   не тестировалась), HMR клиентских плагинов (watcher не запускал).
8. **Модельная зависимость по умолчанию**: промпты уходят в облако DeepSeek, если не настроен
   кастомный эндпоинт/телеметрия не выключена — для privacy-first нужен custom endpoint +
   `DSH_TELEMETRY_DISABLED` (механизм проверен в коде).

### 2.4 Что у меня получилось в рамках этого задания (контроль честности)

Успешно: чтение локальных материалов (в т.ч. вне workspace — конфиг Hermes, чек-аут dsh), read-only
осмотр vazus.db, верификация конфигурации Hermes против самоописания, фиксация фактов AG2 из локальных
файлов, запись этого отчёта. Провалы: 2 попытки веб-поиска, 2 субагента — все зафиксированы выше.

---

## 3. Hermes — проверенное описание и расхождения с самоописанием

Источники проверки: `C:\Users\Vaz\AppData\Local\hermes\config.yaml`,
`C:\Users\Vaz\AppData\Local\hermes\skills\` (101 `SKILL.md`, 16 категорий),
`C:\vazus\vazus_core\vazus_skill_architecture.md`, `C:\vazus\vazus_core\verification\concordia_jury.py`,
`C:\vazus\scripts\agy_openai_adapter.py`, `C:\vazus\docs\*` (PROJECT, TIER1, AG2_*, BENCHMARK,
5LAYERS, REGISTRIES), read-only схема `C:\vazus\services\memory\vazus.db`.

### 3.1 Проверка пунктов самоописания (раздел 2 задания)

| Пункт самоописания | Статус | Доказательство / расхождение |
|---|---|---|
| Ядро: диалоговый агент с инструментами в терминале; модель через конфиг, любые провайдеры | ✅ подтверждено | `config.yaml`: `provider: opencode-go`, `base_url: https://opencode.ai/zen/go/v1`, `api_mode: chat_completions`. **Расхождение**: самоописание называло модель «deepseek-v4-pro», фактически в конфиге `default: deepseek-v4-flash` (забавно: та же модель, что у dsh в этой сессии). |
| Инструменты: терминал (git-bash), файловые операции | ✅ подтверждено | `terminal: backend: local`, `cwd: .`, docker-параметры контейнера (cpu/mem/disk/persistent), таймауты; code_execution. |
| Браузер (Browser Use CLI, CDP) | ⚠️ частично | В конфиге есть секция `browser (inactivity_timeout: 120)`, но именно Browser Use/CDP не подтверждается ни одним файлом — «не подтверждено». |
| Делегирование суб-агентам (изолированные контексты, батчи) | ✅ подтверждено | `delegation.max_iterations: 50`; в контуре — `subagent_framework.py`, `subagent_dialogues`/`subagent_memory_traces` в vazus.db. |
| Cron-джобы (локальные + доставка в мессенджеры) | ❌ не подтверждено | В config.yaml/скиллах локально не найдено. Гейтвеи есть (ниже), но cron-секции нет. |
| Память, поиск по истории сессий (SQLite + FTS5) | ✅ подтверждено | `memory_enabled`, лимиты, nudge; в vazus.db — `dialogue_traces`, `organic_insights_fts` (FTS5, porter), `kg_nodes`+`vec_kg_nodes` (sqlite-vec 768D), `mem0_facts`, `memory_facts_v2`, `memory_promotion_log`, `llm_cache`. |
| Text-to-speech / stt | ✅ подтверждено | `stt.enabled: true` (local `base` / openai whisper-1), `voice.auto_tts: true`. |
| MCP-клиент: vazus-organic и CKB | ✅ подтверждено | `mcp_servers: vazus-organic` (C:/vazus/scripts/vazus_organic_mcp.py) и `ckb` (ckb.cmd mcp); инструменты `mcp_vazus_organic_*`/`mcp_ckb_*` — в скилле `vazus-os-integration`. |
| Расширения: скиллы (SKILL.md, фронтматтер), плагины, профили | ✅/⚠️ | Скиллы: ✅ (101 SKILL.md, 16 категорий; канонический фронтматтер name/description/version/author/license/metadata). «Профили» как изолированные наборы скиллов/памяти: ⚠️ в конфиге видны только `personalities` (11 персон: catgirl, noir, pirate, philosopher и т.д.), изолированных профилей не обнаружено. Плагины: не проверяемо по файлам. |
| 15+ категорий скиллов | ✅ подтверждено | Категории: autonomous-ai-agents, creative, devops, email, github, media, mlops, note-taking, productivity, research, smart-home, software-development, vazus, social-media, apple (+ research/polymarket). Итого 16. |
| Память персистентная, инжект в каждый ход | ✅ подтверждено | Конфиг + архитектура `context_memory_engine.py` (`<persistent_context>`, 768D recall ≥0.70) и `dynamic_skill_dispatcher.py` (инжект только top-k скиллов, AST-прунинг). |
| Доставка: CLI + гейтвеи (Telegram и др.) | ✅ подтверждено | `platform_toolsets`: cli, discord, google_chat, homeassistant, qqbot, signal, slack, teams, telegram, whatsapp, yuanbao. |
| Роль в контуре: оператор Vazus OS, брифы AG2_*, чинка кода, ведомости, подключение внешних систем | ✅ подтверждено | Авторские брифы `docs/AG2_DSH_BRIEF.md`, `AG2_CKB_FIX_BRIEF.md`, `TIER1_BRIEF_FOR_AG2.md`, `AG2_CODE_INTELLIGENCE_5LAYERS.md`; скилл `ag2-decision-briefs` (процесс research → brief → AG2 → verdict: «решение не финально до обсуждения с AG2»); скилл `external-tool-evaluation`. |
| Слабые стороны: перезапуск конфигов, нет Web UI, нет патч-слоёв, нет встроенной само-модификации | ✅/⚠️ | Локально неопровержимо: Web UI действительно не найден (CLI-тулсеты), патч-слоёв в структуре конфига нет. «Перезапуск для смены конфига» — не могу опровергнуть/подтвердить из файлов (нет механизма hot-reload в конфиге). Само-модификация: вне ядра — да, через `auto_skill_engine.py` и внешние циклы. |

### 3.2 Что Hermes реально делает в контуре (сводка по файлам)

- **LLM-бэкенд по лестнице тиров**: Tier-1 agy CLI (IDE-квота) → Tier-1b `google.antigravity`
  SDK (v0.1.10) → Tier-2 Gemini REST (только при `VAZUS_LLM_ALLOW_CLOUD=1`) → Tier-3 детерминированный
  mock (помечается `[MOCK]`; `is_test_mode()` выключает) — `vazus_core/engine/llm_client.py`
  (скилл `agy-cli-backend`).
- **OpenAI-совместимый адаптер** `scripts/agy_openai_adapter.py` на `127.0.0.1:5001` (/v1/chat/completions):
  маппинг модельных ключей → официальные agy-модели (Claude/Gemini/GPT-OSS по квоте IDE), промпт
  передаётся аргументом CLI (баг agy: `-p -` на Windows даёт пустой промпт — зафиксирован в скилле).
- **Конкордия-жюри** `concordia_jury.py`: 3 независимых LLM-голоса (Planner, RLM_Coder, Verifier_Worker)
  через `asyncio.gather` (~41 с), кворум ≥66%, обязательны AST-валидность, SMT Z3-контракты,
  архитектурные границы (запрет `google.genai`, `os.system`, `shutil.rmtree`).
- **Память и знания**: `vazus.db` (схема прочитана read-only) — KG, 768D векторы (sqlite-vec),
  FTS5-инсайты, mem0, рефлексия-уроки (`reflexion_lessons`, `legacy_reflexion_lessons`),
  `skill_registry`, `skill_usage_scores`, диалоги/трассы субагентов, доменные данные
  (finance, freelance, mirea, nutrition, Google Gmail/Sheets).
- **Само-производство скиллов**: `auto_skill_engine.py` (TranscriptAnalyzer: векторная кластеризация
  ≥0.82 и траектории >12 шагов; SkillGenerator; SrillSyntacticValidator) → регистрация в
  `~/.gemini/config/skills/` и 768D-индекс (Project Sentinel, `docs/PROJECT.md`).
- **Дебаты AGY/Hermes** (файловый протокол `.agents/debates/` + `DEBATE_INDEX.md`, теги [AGY]/[Hermes],
  раунд ≤150 строк) и TARS-хуки в vazus.db (скилл отсутствует как файл, но описан в TIER1).
- **Операционка**: бенчмарки (AST-прунинг 78–88%, см. BENCHMARK_REPORT), precommit-гейты
  (AST → pytest → SMT Z3 → Jury → vulture → ruff; +6b: deptry/pip-audit/bandit при
  `VAZUS_GATE_DEEP_SCAN=1`), worktree-песочница, `protected_whitelist`.

### 3.3 Сводка расхождений с самоописанием

1. **Модель**: заявлена «deepseek-v4-pro», фактически `deepseek-v4-flash` (opencode-go). 
2. **Cron-джобы**: в локальных материалах не подтверждены (самоописание утверждает их наличие).
3. **Browser Use CLI/CDP**: не подтверждено (есть только секция `browser` с таймаутом простоя).
4. **Профили**: не обнаружены как изолированные наборы; есть только персоны в конфиге.
5. Остальные пункты самоописания подтверждены с высокой детализацией (см. таблицу 3.1).

---

## 4. AG2 (Google Antigravity 2) — факты и уровень подтверждённости

**Ограничение (честно)**: раздел 3 задания («данные собери в интернете») выполнить не удалось —
веб-поиск недоступен (ошибка авторизации ключа, 2 попытки). Поэтому здесь только факты,
**проверенные по локальным файлам контура Vazus**; всё требующее интернета помечено
**«не подтверждено»** и требует повторного исследования при доступном поиске.

### 4.1 Подтверждено локально (файл-источник указан)

- Хост-платформа контура — **Google Antigravity 2.0 (AG2)**: аудит-протокол заявляет «Host Platform:
  Google Antigravity 2.0 (AG2)», «Specification Version: 2026.2-PROD» (`docs/AG2_FULLSYSTEM_AUDIT_PROMPT.md`).
- AG2 — **агентный IDE (десктоп)**, «Tier-1 мозг» контура; dsh и AG2 **не конкуренты**: dsh — рантайм,
  AG2 — среда разработки агентов, комплементарны (`docs/AG2_DSH_BRIEF.md §4`).
- **Доступ к моделям через IDE-сессионную квоту, 0 внешних платежей**: CLI `agy` v1.1.13
  (`%LOCALAPPDATA%\agy\bin\agy.exe`) и SDK `google-antigravity` v0.1.10 (образец клиента —
  `labs/mit/rlm-mit/rlm/clients/antigravity.py`) (скилл `agy-cli-backend`, `TIER1_BRIEF_FOR_AG2.md`).
- Модели по квоте: **Gemini 3.1 Pro (High), Gemini 3.5/3.6/3.7 Flash (High), Claude Opus 4.6 (Thinking),
  Claude Sonnet 4.6 (Thinking), GPT-OSS 120B (Medium)**; вызов ≈ 40–45 с (скилл `agy-cli-backend`).
- Артефакты AG2 на машине: `~/.gemini/antigravity-cli` (brain-архив 6.1 ГБ: 513 brain-папок,
  31 215 транскрипт-строк; 55 кластеров зацикливаний, 2 707 еrror-логов — `vazus_skill_architecture.md §2.1`),
  `~/.gemini/config/mcp_config.json`, `~/.gemini/config/skills/`, `~/.gemini/antigravity/builtin/skills/`
  (`docs/REGISTRIES.md`), `~/.gemini/config/hooks.json` (fail-closed).
- Примитивы AG2: `define_subagent`/`invoke_subagent`, `send_message` (conversationID, реактивное
  пробуждение), `manage_task`, `ask_question`, Auxiliary Pane, slash-команды `/goal /schedule
  /grill-me /teamwork-preview /learn` (`AG2_FULLSYSTEM_AUDIT_PROMPT.md`, `REGISTRIES.md`).
- MCP-реестр контура под AG2: **ckb, vazus-organic, colab, playwright, sequential-thinking**
  (`AG2_FULLSYSTEM_AUDIT_PROMPT.md §1.3`).
- Контурная верификация на AG2: quorum ≥66%, SMT Z3-контракты, 768D-выравнивание, AST, zero-secrets
  (`AG2_FULLSYSTEM_AUDIT_PROMPT.md`); бенчмарки: 703/703 pytest, AST-экономия 78–88%
  (`TIER1_BRIEF_FOR_AG2.md`, `BENCHMARK_REPORT.md`).

### 4.2 Не подтверждено (требуется интернет)

- Официальные анонсы Google (blog.google / Google Labs), страница продукта — **не подтверждено**.
- Возможности/статус GA/early-access, регионы, доступность, версии «Antigravity 2»/«Google Antigravity
  agentic IDE» (в т.ч. различение с кастомными «AG2»-форками) — **не подтверждено**.
- Обзоры TechCrunch / The Verge / Ars Technica / Hacker News — **не подтверждено**.
- Сравнения AG2 vs Claude Code / Cursor / Codex — **не подтверждено**.
- Тарифы и квоты публичные — **не подтверждено**.
> Рекомендация: повторный прогон этого раздела при рабочем веб-поиске (или в среде Hermes, где
> browser_exec доступен — см. скилл `ag2-decision-briefs`, там же процедура gather фактов).

---

## 5. Вывод: кто в чём сильнее, пересечения, что позаимствовать

### 5.1 Сильные стороны

- **dsh** — архитектура: ноль привилегированного ядра, обратимые эффекты (unwind), патч-слои,
  hot-swap плагинов без рестарта; свой Web UI (:3080); песочницы и политики безопасности с
  fail-closed approval; goal-раунды/workflow для автономной работы; append-only SessionEvent-логи
  (тот же паттерн «долговечных фактов», что и жюри-А в Vazus). Главный минус — свежесть (rc.6)
  и текущая нестабильность в прогоне (субагенты, веб).
- **Hermes** — зрелость и полнота: персистентная память с инжектом в каждый ход (768D + FTS5 +
  mem0), 100+ скиллов, MCP (vazus-organic, ckb), гейтвеи доставки (Telegram и др.), TTS/STT,
  делегирование, авто-генерация скиллов, контурная интеграция (agy-квоты, жюри, дебаты, 6 гейтов).
  Рабочая лошадка контура.
- **AG2** — IDE-среда разработки агентов: сессионные квоты на топ-модели (Gemini + Claude) без
  внешних платежей, нативные примитивы субагентов и UX (Auxiliary Pane, slash-команды), MCP-реестр.
  В контуре — признанный «мозг» и площадка для вердиктов по брифам Hermes.

### 5.2 Пересечения

- Все три — агентные системы «модель + инструменты + память»; философски dsh и Hermes конкурируют
  за роль «харнесс» (Node/TS vs Python), а AG2 — среда, где такие харнессы живут. dsh↔AG2
  комплементарны (рантайм ↔ IDE); Hermes↔AG2 уже образуют пару «исследователь → площадка вердиктов».
- Общий паттерн: «долговечные факты» (SessionEvent-лог dsh ≙ жюри-А/кг Vazus), скиллы-инструкции
  (SKILL.md у Hermes ≙ скиллы dsh), MCP-интеграция.

### 5.3 Что позаимствовать

**dsh ← Hermes:**
1. Персистентную память с инжектом фактов в каждый ход + FTS-поиск по истории сессий (у dsh этого
   нет; у Hermes — `memory_facts_v2`, `mem0_facts`, FTS5).
2. Гейтвеи доставки (Telegram/Slack) для автономных джоб и уведомлений (dsh — только UI/headless).
3. Политику opt-in облачных вызовов по умолчанию 0 (приватность) и честное маркирование моков.
4. Богатый каталог скиллов и авто-генерацию скиллов из транскриптов (у dsh механика скиллов есть,
   у Hermes — процесс производства и 768D-диспетчер).
5. TTS/STT и браузерную автоматизацию как инструменты.

**dsh ← AG2:**
1. Модель «IDE-квота»: подключение dsh к `agy_openai_adapter.py` (:5001/v1) как кастомного
   OpenAI-эндпоинта — гипотеза `AG2_DSH_BRIEF.md §7` (дешёвый тест, не проверен в этой сессии).
2. Нативные субагентные примитивы и UX-практики (Auxiliary Pane, slash-команды).

**Hermes ← dsh:**
1. Горячую перекомпоновку без рестарта (Cordis unwind) — устранить главную слабость «перезапуск
   для смены конфига/плагинов».
2. Патч-слои (bundle → profile → home → `--patch` + `--dump-config`) вместо ручной правки конфига —
   как системный примитив уровня `.vazus_ci.yaml`.
3. Web UI — закрыть отсутствие интерфейса у CLI-агента.

**Vazus ← dsh (уже отмечено в `AG2_DSH_BRIEF.md §5`):** паттерн обратимых эффектов как кандидат в
ревизию 5-слойной архитектуры (L2 dynamic / L5 memory); ответ на «чёрные дыры» №5 (самовыпиливание)
и №7 (каскад поломок); двухжюрийность append-only лога.

### 5.4 Практические рекомендации (совпадают с `AG2_DSH_BRIEF.md §8`, подтверждаю)

- Установить dsh для теста: **ДА** (npx-однострочник, MIT, Node уже есть, локальный UI; риск низкий
  при изоляции от прода).
- Принимать dsh в контур Vazus как компонент: **НЕТ** — до стабилизации (пост-rc.6, без честной
  проверки субагентов/веба на этой машине) и вердикта AG2.
- Прогнать дешёвый тест: dsh web → кастомный эндпоинт `127.0.0.1:5001/v1` (адаптер Hermes) —
  проверить работу dsh на квоте IDE без DeepSeek API. Включить `DSH_TELEMETRY_DISABLED`.

---

## 6. Источники

### Локальные файлы (прочитаны в ходе исследования)

- `C:\vazus\docs\DSH_COMPARE_PROMPT.md` — задание.
- `C:\vazus\docs\AG2_DSH_BRIEF.md` — разбор dsh Hermes'ом, сравнения, гипотеза :5001, рекомендация.
- `C:\vazus\docs\AG2_CODE_INTELLIGENCE_5LAYERS.md` — 5-слойная архитектура контроля кода.
- `C:\vazus\docs\AG2_CKB_FIX_BRIEF.md`, `C:\vazus\docs\TIER1_BRIEF_FOR_AG2.md` — задачи/решения для AG2.
- `C:\vazus\docs\AG2_FULLSYSTEM_AUDIT_PROMPT.md` — аудит Vazus на платформе Google Antigravity 2.0.
- `C:\vazus\docs\PROJECT.md`, `ORIGINAL_REQUEST.md`, `BENCHMARK_REPORT.md`, `REGISTRIES.md` — контур.
- `C:\vazus\vazus_core\vazus_skill_architecture.md` — динамический диспетчер скиллов, аудит транскриптов.
- `C:\vazus\vazus_core\verification\concordia_jury.py` — 3-голосовое жюри (≥66%, SMT Z3, AST).
- `C:\vazus\scripts\agy_openai_adapter.py` — OpenAI-совместимый адаптер :5001 над agy CLI.
- `C:\vazus\services\memory\vazus.db` — схема прочитана **строго read-only** (`mode=ro`): KG,
  vec_kg_nodes (768D), FTS5, mem0, reflexion, skill_registry и др.
- `C:\Users\Vaz\AppData\Local\hermes\config.yaml` — конфиг Hermes (модель, память, гейтвеи, MCP).
- `C:\Users\Vaz\AppData\Local\hermes\skills\**\SKILL.md` — 101 скилл, 16 категорий; детально изучены
  `vazus\vazus-os-integration`, `vazus\agy-cli-backend`, `vazus\ag2-decision-briefs`.

### Чек-аут dsh (только чтение)

- `%APPDATA%\npm\node_modules\@deepseek-ai\dsh\package.json` — версия 0.1.0-rc.6, список пакетов-плагинов.
- `README.md` — профили, патч-слои, `--dump-config`, `dsh web`/`headless`/`plugin`.
- `lib\bin.js` — грамматика лаунчера; `lib\profile-boot-DG5t9aNs.js` — телеметрия
  (`DSH_TELEMETRY_DISABLED`, `session-telemetry-otel`).
- `config\agent-presets\` — пресеты standard/code/minimal/cordis.

### Наблюдения рантайма (эта сессия, dsh на :3080)

- `web_search` (2 попытки): «Authentication Fails, api key ****2R4V invalid» → интернет-исследования недоступны.
- Субагенты (2 запуска): завершились без результата и без финального сообщения.
- Функционировали: read/write/edit/glob/grep, pwsh (в т.ч. read-only SQLite `mode=ro`), goal, todo,
  spill больших результатов в `%TEMP%\dsh-spill-*`.

### Внешние URL

**Отсутствуют** — веб-поиск в среде dsh недоступен; все факты AG2 — локальные (раздел 4.1).
Повторное интернет-исследование требуется при рабочем поиске (или через browser_exec Hermes).

---
*Отчёт подготовлен агентом dsh 17.08.2026 по заданию `C:\vazus\docs\DSH_COMPARE_PROMPT.md`.*
*Ничего в `C:\vazus` не изменялось, кроме создания настоящего файла отчёта; `vazus.db` открывался только read-only.*

---

## 7. ДОПОЛНЕНИЕ HERMES (17.08.2026, после аудита отчёта)

Добавлено агентом Hermes: (а) интернет-раздел по AG2, который dsh не смог
выполнить (его веб-поиск сломан — инвалидный ключ), и (б) результаты
верификации отчёта dsh по первоисточникам.

### 7.1 Аудит отчёта dsh (факты перепроверены Hermes)

Подтверждено:
- Версия 0.1.0-rc.6, 61 зависимость, bin lib/bin.js, пресеты
  standard/code/minimal/cordis (creative в поставке действительно нет —
  в статье 3dnews был заявлен, у dsh точнее) — проверено по package.json.
- «Ничего не изменял» — правда: mtime изменённых файлов в C:\vazus
  (run_topology_and_interface_audit.py, hebbian_tools_manifest.json,
  wiki-файлы) — 15.08, ДО запуска dsh (17.08). Отчёт — единственный новый
  файл (git: ?? docs/DSH_COMPARISON_REPORT.md).
- Spill-каталоги %TEMP%\dsh-spill-* существуют — сессия реально работала.
- Чтение config.yaml точно: default deepseek-v4-flash, provider opencode-go,
  reasoning_effort ultra.
- Локальные AG2-факты dsh (agy v1.1.13, SDK google-antigravity v0.1.10,
  примитивы define_subagent/invoke_subagent, slash-команды /goal /schedule
  /grill-me, brain-архив 6.1 ГБ) — совпадают с официальным блогом Google
  (см. 7.2) и памятью контура.

Ошибки/неточности dsh:
1. «Cron у Hermes не подтверждено» — НЕВЕРНО: каталог
   C:\Users\Vaz\AppData\Local\hermes\cron\ существует (executions.db,
   output, ticker_heartbeat); инструмент cronjob есть в тулсете Hermes.
   dsh просто не заглянул в каталог профиля.
2. «101 SKILL.md» — фактически 95 (пересчитано find'ом). Завышение на 6.
3. «Расхождение: self-описание говорит deepseek-v4-pro, конфиг — flash» —
   интерпретация dsh неверна: текущая сессия Hermes реально работает на
   deepseek-v4-pro (модель сессии), а в config.yaml записан дефолт flash.
   Это разные вещи; ошибки в моём самоописании нет.
4. «Browser Use/CDP не подтверждено» — частично: в конфиге его нет, но
   инструмент browser_exec (Browser Use CLI + CDP) есть в тулсете Hermes
   и реально работает (этим дополнением и проверено).
5. «AG2 — агентный IDE (десктоп)» — НЕТОЧНО: по официальному блогу
   Antigravity 2.0 — отдельное десктоп-приложение БЕЗ IDE («there is no
   IDE»); IDE — отдельный продукт (Antigravity IDE). Локальный аудит-файл
   контура этого не уточнял, dsh экстраполировал.
6. «Профили не обнаружены» — верно для этой машины (profiles/ не
   существует, только personalities). Претензий нет.

Общий вердикт по отчёту dsh: честный самоотчёт, хорошая дисциплина
(всё непроверенное помечено), единственная содержательная ошибка — вывод
про cron, остальное — интерпретации. Рекомендации dsh совпадают с
AG2_DSH_BRIEF.md.

### 7.2 AG2: интернет-факты из первоисточников (заполняет пробел раздела 4)

- Анонс: «Introducing Google Antigravity 2.0», блог Google Antigravity,
  19.05.2026 — https://antigravity.google/blog/introducing-google-antigravity-2
- Продуктовая страница: https://antigravity.google/product/antigravity-2
- Линейка продуктов: Antigravity 2.0 (десктоп-платформа агентов),
  Antigravity CLI, Antigravity IDE, Antigravity SDK.

Ключевые факты (из официального блога):
- Antigravity 2.0 — отдельное standalone-десктоп-приложение (macOS, Linux,
  Windows), «there is no IDE»; полностью отдельное от Antigravity IDE
  приложение, сохранившее принципы поверхности Agent Manager.
- Доступно для enterprises, работает на последних Gemini-моделях.
- Динамические субагенты: главный агент сам определяет и вызывает
  субагентов (параллелизм, изоляция контекста).
- Асинхронные задачи (не блокируют главного агента).
- JSON hooks: перехват и контроль поведения агента.
- Scheduled Tasks: cron-триггеры вызова агентов по расписанию.
- Проекты вместо workspace: разговор группируется по «проекту» (несколько
  папок + свои настройки и скоуп разрешений).
- Slash-команды: /goal (до полного завершения без вопросов), /grill-me
  (уточняющие вопросы до старта), /schedule (разовый/рекуррентный запуск),
  /browser (явное включение браузера).
- Live voice transcription (Gemini Audio-модели).
- Antigravity IDE запущен в ноябре 2025; Agent Manager — его вторая
  поверхность; 2.0 — переход от «кодинга» к «knowledge work».
- Глобальные/воркспейсные Skills, MCP и JSON Hooks (страница продукта).

Сопутствующее:
- Gemini CLI прекращает обслуживание 18.06.2026 → миграция на Antigravity
  CLI (agy) — https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/
- 9to5google (19.05.2026): Antigravity 2.0 — полноценная агентная среда
  разработки; Gemini 3.5 Flash — frontier-уровень по цене фракции
  — https://9to5google.com/2026/05/19/google-antigravity-agentic-developer-suite/
- Гайд (buildfastwithai.com): на I/O 2026 Antigravity стал
  «five-surface agent platform» — https://www.buildfastwithai.com/blogs/google-antigravity-2-0-developer-guide-2026

Пересечение с нашим контуром: локальные файлы контура (примитивы
субагентов, /goal /schedule /grill-me, JSON hooks, MCP-реестр) точно
соответствуют официальному 2.0 — наш контур работает на официальном AG2.
Scheduled Tasks AG2 — прямой аналог cron-джобов Hermes (та же ось
сравнения: у dsh штатного планировщика в отчёте не заявлено).

### 7.3 Уточнённый вывод (с учётом 7.2)

dsh ↔ AG2 не конкуренты (рантайм ↔ платформа), Hermes ↔ AG2 уже работают
парой. Взаимные заимствования из раздела 5.3 отчёта остаются в силе,
плюс: Scheduled Tasks и JSON hooks AG2 стоят в списке кандидатов для
контура Vazus наравне с патч-слоями dsh.