# Экосистема Model Context Protocol (MCP) — глубокое исследование 2025–2026

> Дата исследования: 17 августа 2026 г. · Язык: русский · Цель: понять текущее состояние MCP, выбрать полезные серверы для личного агента (Hermes, Windows 11, privacy-first) и безопасно их подключать.
> Все источники проверены по состоянию на 17.08.2026. Прямые цитаты и цифры даны с атрибуцией.

---

## TL;DR (главное)

1. **MCP стал де-факто стандартом интеграции агентов с инструментами**: ~97 млн загрузок SDK в месяц (март 2026) и «близко к полумиллиарду в месяц» по Tier-1 SDK (июль 2026); >1 млрд суммарных загрузок у Python и TypeScript SDK по отдельности. 10 000+ активных публичных серверов, 43 400+ серверов / 219 000 инструментов оценены Arcade в State of MCP Tools (июнь 2026).
2. **Управление перешло в Linux Foundation (Agentic AI Foundation, AAIF, 9 декабря 2025)**: сооснователи — Anthropic, OpenAI, Block; платиновые члены — Google, Microsoft, AWS, Cloudflare, Bloomberg.
3. **Спецификация**: стабильная версия **2025-11-25**; **28 июля 2026 выпущена версия 2026-07-28** — крупнейший релиз за всю историю: **stateless-ядро** (отказ от handshake и Mcp-Session-Id), заголовочная маршрутизация (Mcp-Method/Mcp-Name), Multi Round-Trip Requests (MRTR), кэшируемые списки, ужесточение OAuth (RFC 9207, CIMD), формальный фреймворк расширений (Tasks, MCP Apps, EMA).
4. **Принятие вендорами**: Anthropic (создатель), OpenAI (официально с 26.03.2025; ChatGPT-connectors/apps, Agents SDK, Responses API, Codex), Google (Gemini CLI, Vertex/Gemini Enterprise; параллельно продвигает A2A для agent-to-agent), Microsoft (Build 2026 — MCP по умолчанию во Foundry, Agent 365, IQ, Copilot, Teams SDK), AWS (Bedrock AgentCore).
5. **Безопасность — главный риск**: к июлю 2026 — 14 CVE, 30+ RCE-проблем из-за несанитизированной передачи команд в subprocess через stdio-SDK (OX Security, «The Mother of All AI Supply Chains», 15.04.2026); ~200 тыс. серверов потенциально уязвимы; 200 000+ серверов открыты в интернете; prompt injection и tool poisoning (MCPTox: 72,8% успеха против o1-mini); 53% серверов используют статические ключи вместо OAuth; 82% подвержены path traversal (Astrix 2025). Спецификация до сих пор не содержит стандартной модели разрешений — 2026-07-28 начинает это закрывать.
6. **Тренды**: remote MCP + Streamable HTTP + OAuth 2.1 (PKCE S256, RFC 9728/8414/7591/8707) — стандарт для удалённых серверов; **MCP Apps** (первое официальное расширение, 26.01.2026) — UI поверх MCP; **MCP Registry** (официальный, preview с 08.09.2025); **шлюзы/роутеры** (Cloudflare MCP Portal + Gateway + Code Mode, Portkey Agent Gateway, Glama Gateway, MCP360); **.mcpb** bundle-формат для локальных серверов; **A2A v1.0** (март 2026) дополняет MCP на уровне взаимодействия агент-агент.

---

## 1. Текущее состояние MCP: спецификация, версии, SDK, adoption

### 1.1. Версии спецификации

Датированные ревизии (модель версионирования — по дате; история разбита на Legacy-сессии и Modern-период):

| Версия | Что изменилось (кратко) |
|---|---|
| **2024-11-05** | Первый публичный релиз (Anthropic, ноябрь 2024), JSON-RPC 2.0, stdio/HTTP+SSE. |
| **2025-03-26** | **Streamable HTTP** заменил двухканальный HTTP+SSE одним bidirectional-эндпоинтом; удалён JSON-RPC batching; структурированный вывод инструментов; серверы классифицированы по модели OAuth. |
| **2025-06-18** | Переработка раздела авторизации вокруг OAuth 2.1 (draft 13), явные ссылки на RFC 9728 (Protected Resource Metadata) и RFC 8707 (Resource Indicators). |
| **2025-11-25** (актуальная стабильная) | OIDC Discovery 1.0 для discovery серверов авторизации; иконки инструментов (SEP-973); инкрементальное согласие scope через WWW-Authenticate (SEP-835); руководство по именам инструментов (SEP-986); улучшенная **elicitation** (URL-режим, enum-схемы — SEP-1036/1330); tool-calling в sampling (SEP-1577); **CIMD — Client ID Metadata Documents** как рекомендованный способ регистрации клиентов (SEP-991); **экспериментальные Tasks** (SEP-1686); JSON Schema 2020-12 по умолчанию (SEP-1613); формализована governance (SEP-932), рабочие группы (SEP-1302) и **SDK tiering** (SEP-1730). |
| **2026-07-28** (выпущена 28.07.2026) | См. §1.2. |

Источники: changelog 2025-11-25 (modelcontextprotocol.info / modelcontextprotocol.io), блог MCP (blog.modelcontextprotocol.io/posts/2026-07-28/), GitHub releases (github.com/modelcontextprotocol/modelcontextprotocol/releases).

### 1.2. Релиз 2026-07-28 — крупнейший за историю

Официальный пост «The 2026-07-28 Specification» (авторы: David Soria Parra, Den Delimarsky, 28.07.2026) сообщает:

- **Stateless-ядро**: удалены handshake `initialize/initialized` и заголовок `Mcp-Session-Id` (SEP-2575, SEP-2567). Версия протокола, идентичность клиента и capabilities путешествуют в `_meta` каждого запроса. Опциональный RPC `server/discover` для предварительного получения capabilities. Любой запрос может попасть на любой инстанс за round-robin load balancer. Состояние между вызовами — явный handle, который модель передаёт как аргумент.
- **MRTR (Multi Round-Trip Requests, SEP-2322)**: заменяет сервер-инициируемые `elicitation/create`, `sampling/createMessage`, `roots/list` — сервер возвращает `resultType: "input_required"` с запросами, клиент повторяет вызов с `inputResponses`. Позволяет «дозапросить» у пользователя подтверждение/параметр в stateless-протоколе.
- **Заголовочная маршрутизация (SEP-2243)**: Streamable HTTP-запросы обязаны нести `Mcp-Method` и `Mcp-Name` — шлюзы, rate limiter'ы и WAF могут маршрутизировать и тарифицировать без разбора JSON-тел.
- **Кэшируемые списки (SEP-2549)**: ответы `tools/list`, `prompts/list`, `resources/list`, `resources/read` несут `ttlMs` и `cacheScope`.
- **Ужесточение авторизации**: обязательная проверка `iss` по RFC 9207 (SEP-2468) перед обменом кода; `application_type` при DCR, чтобы AS не отклоняли localhost redirects для desktop/CLI-клиентов (SEP-837); привязка client credentials к выпустившему их issuer'у (SEP-2352); **DCR официально депрецирован в пользу CIMD**.
- **Tasks** переехали в расширение `io.modelcontextprotocol/tasks` (SEP-2663): poll-based `tasks/get` + новый `tasks/update`; нотификации через единый поток `subscriptions/listen`.
- **Депрекации (SEP-2577)**: Roots, Sampling и Logging — депрецируются, минимум 12 месяцев поддержки; legacy HTTP+SSE транспорт депрецирован (годовой offramp).
- **Расширения**: формализован фреймворк extensions; в ядро вошли Tasks, MCP Apps, Enterprise Managed Authorization (EMA).
- **SDK**: обновлены все Tier-1 (TypeScript, Python, Go, C#); Rust SDK — beta.

Источник: https://blog.modelcontextprotocol.io/posts/2026-07-28/ (прочитано целиком); обзоры: 4sysops, composio.dev, tokenmix.ai (2025-11-25 — актуальная стабильная, 2026-07-28 — «миграционное событие, к которому стоит готовиться»).

### 1.3. Adoption: цифры и вендоры

**Цифры роста** (разные метрики, воспроизвожу с атрибуцией):
- **97 млн загрузок SDK в месяц** (Python+TS) — март 2026; рост ~970× от ~100 тыс./мес в ноябре 2024 (Arcade «State of MCP Tools», июнь 2026; также fastai.news, agentmarketcap.ai, gentic.news).
- **«Близко к полумиллиарду загрузок в месяц» по всем Tier-1 SDK**, и **>1 млрд суммарных загрузок** у TypeScript и Python SDK по отдельности — официальный блог MCP, июль 2026.
- **10 000+ активных публичных серверов** (весна-лето 2026; gentic.news, fastai.news); **21 000+ серверов в каталоге Glama** (septimlabs.com); **19 831+ на Glama** (openclaw.direct); **43 400+ серверов и 219 069 инструментов** оценены Arcade (июнь 2026); 2 000+ серверов в каталоге awesome-mcp.tools; 20 000+ репозиториев на GitHub (апрель 2026, septimlabs).
- **78% enterprise AI-команд** запускают ≥1 MCP-агента в продакшене; более 2/3 CTO назвали MCP стандартом интеграции по умолчанию (Arcade/Build 2026). Gartner: в 2026 г. 75% вендоров API-gateway и 50% вендоров iPaaS добавят MCP-фичи.

**Вендоры**:
- **Anthropic** — автор и соучредитель AAIF; официальные reference-серверы; Claude Desktop/Claude Code поддерживают MCP с момента запуска. В 2025 г. заархивированы 13 из 20 reference-серверов, активны 7 (включая filesystem, memory, sequential thinking) (techsy.io).
- **OpenAI** — принятие MCP (таймлайн по chatforest.com и открытым документам OpenAI):
  - 26.03.2025 — Сэм Альтман: «люди любят MCP, добавим поддержку во все продукты»; сначала Agents SDK (Python), далее Responses API и ChatGPT desktop.
  - 19.05.2025 — Microsoft и GitHub вступили в MCP steering committee (Build 2025).
  - июнь 2025 — Responses API: поддержка remote MCP-серверов (`type: "mcp"`).
  - 09.09.2025 — ChatGPT Developer Mode (beta) с полным MCP-клиентом и write-действиями (ранее connectors были read-only).
  - 06.10.2025 — анонс Apps SDK (DevDay); 13.11.2025 — preview для Business/Enterprise/Edu; 18.12.2025 — «connectors» переименованы в «apps» для Plus/Team/Enterprise.
  - 21.11.2025 — совместное с Anthropic предложение расширения MCP Apps (SEP-1865).
  - март 2026 — Agents SDK получил TypeScript-версию с MCP-поддержкой.
  - Codex (CLI и продукт): MCP-серверы через config.toml (`[mcp_servers]`), полная поддержка stdio/Streamable HTTP; v0.145 (21.07.2026) — команда `/import` мигрирует конфиги, MCP-серверы, плагины, сессии и проектные памяти из Cursor и Claude Code (codex.danielvaughan.com).
  - July 2026 — 2026-07-28 spec согласована; напрямую влияет на stateless-архитектуру Responses API (chatforest).
- **Google** — Gemini CLI поддерживает MCP (включая `--mcp` и диалог добавления серверов), Vertex AI / Gemini Enterprise Agent Platform; Google — платиновый член AAIF; продвигает собственный **Agent2Agent (A2A)** для agent-to-agent (дополняющий MCP: MCP — агент↔инструменты, A2A — агент↔агент). A2A: представлен Google в апреле 2025; проект в Linux Foundation с 23.06.2025; v1.0 — март 2026 (linuxfoundation.org, a2a-protocol.org, mcpblog.dev).
- **Microsoft** — Build 2026: **MCP — язык интеграции по умолчанию** во Foundry, Agent 365, IQ context services, Teams SDK и Copilot; Foundry Toolboxes — один MCP-эндпоинт за несколькими типами инструментов (web search, файлы, code interpreter, Azure AI Search, MCP-серверы, OpenAPI, A2A) с общими auth/governance/guardrails; OS-level sandboxing агентов (Surface RTX Spark Dev Box) (arcade.dev; learn.microsoft.com Azure Foundry docs).
- **AWS** — Bedrock AgentCore и интеграции MCP (tech-insider, agentmarketcap, и др.).
- **Прочие**: Salesforce, Snowflake, Cloudflare, Bloomberg, PayPal, Shopify и тысячи интеграций (the-agent-report.com; andrew.ooo/answers).

**Реестры и каталоги**: официальный **MCP Registry** (preview с 08.09.2025; открытый каталог + API-спецификация для реализаций реестра; поддерживают Anthropic, GitHub, PulseMCP, Microsoft) — registry.modelcontextprotocol.io, github.com/modelcontextprotocol/registry; коммерческие/сообщества — Glama (glama.ai), PulseMCP, mcpservers.org, awesome-mcp-servers (punkpeye, hireblackout), awesome-mcp.tools.

**SDK**: Tier-1 — TypeScript, Python, Go, C#; Rust — beta; введён формальный tiering (SEP-1730). Python: `pip install mcp` (клиент: `mcp.client.stdio`, `mcp.client.streamable_http`).

---

## 2. Топ MCP-серверы для личного агента и разработчика (2026)

### 2.1. Стартовый набор «три сервера» (techsy.io, июль 2026)

1. **GitHub MCP** — официальный: `github/github-mcp-server` (15k+ ⭐). Полный API GitHub: issues, PR, code search, ветки. Правит собственная модель разрешений GitHub.
2. **Context7** — документация с актуальными версиями пакетов (upstash/context7): кладёт версионированные доки в промпт, убирая галлюцинации по API.
3. **Playwright MCP** — официальный от Microsoft (`microsoft/playwright-mcp`, 11k+ ⭐): реальный браузер, accessibility-снимки вместо зрения, заполнение форм, скриншоты, скрейпинг. Не требует vision-модели.

→ «Код, доки, веб — ~80% того, что агенту нужно» (techsy).

### 2.2. По категориям (сборка из septimlabs.com, techsy.io, tokenmix, awesome-mcp)

- **Файлы**: Filesystem MCP (`@modelcontextprotocol/server-filesystem`, официальный reference, path-allowlist) — для агентов на хосте без встроенных файловых инструментов (у Hermes они уже есть нативно).
- **Браузер**: Playwright MCP (Microsoft), **Chrome DevTools MCP** (официальный блог MCP, «глаза для слепого программиста»), browser-use, Puppeteer MCP.
- **Git/код**: GitHub MCP (official), GitLab MCP (community), Git MCP server, Context7, ckb (code intelligence, уже подключён у Vaz).
- **Наблюдение/observability**: Sentry MCP (vendor), OpenTelemetry MCP, Grafana/Loki MCP, Logfire MCP, mcp-observability (panoptimize).
- **Поиск/веб**: Brave Search MCP (vendor, ~2k запросов/мес бесплатно), Tavily MCP (~1k/мес бесплатно), Exa MCP, Fetch MCP (reference), Firecrawl MCP (скрейпинг+рендер), SearXNG (self-hosted, privacy-first).
- **Документы/знания**: Notion MCP (official), Google Workspace MCP (gws), MarkItDown MCP, PDF/Docx/XLSX-tools, Firecrawl, Obsidian MCP (локальная база знаний), Hjarni.
- **Базы данных**: Postgres MCP, Supabase MCP (official), MongoDB MCP, SQLite MCP, Neon MCP.
- **Память**: см. §3.3 (official knowledge-graph memory, mem0/OpenMemory, basic-memory, Letta, Zep, Hjarni, Supermemory).
- **Планирование/рассуждения**: Sequential Thinking MCP (Anthropic reference; «остаётся активным»), mcp-server-time (время/часовые пояса).
- **SaaS-интеграции (выборочно)**: Stripe, Slack, Linear, Figma Dev Mode, Atlassian, Salesforce, Cloudflare, Shopify, X/Twitter, Teams, Zoom.
- **Прочее**: mcp-server-time, Fetch, Memory, Everything (для тестов), official registry — registry.modelcontextprotocol.io.

### 2.3. Важные оговорки

- **Archiving**: Anthropic заархивировала 13 из 20 своих reference-серверов в 2025; tutorial'ы из 2024–2025 указывают на немейнтейнимое. Проверяйте статус репозиториев (techsy.io).
- **Плата токенами**: каждый подключённый сервер «сжигает» ~2 000–5 000 токенов на инъекцию схем инструментов в контекст (techsy). 10 серверов = заметная часть окна контекста. Решение — меньше серверов, прогрессивное раскрытие схем (progressive disclosure), Cloudflare Code Mode (−99,9% токенов по заявлению Cloudflare), шлюзы.
- **Качество**: Arcade State of MCP Tools (июнь 2026): 219 069 инструментов на 43 400+ серверах — только **0,5% оценены на «A»**; 167 333+ — посредственно/ниже (arcade.dev, обрезано) → доверяйте только проверенным репозиториям.

---

## 3. MCP как транспорт для инструментов в CLI-агентах и связка с памятью

### 3.1. CLI-агенты и MCP-клиенты (2026)

| Агент | Поддержка MCP | Особенности |
|---|---|---|
| **Hermes Agent** (Nous Research) | Нативный MCP-клиент (stdio + HTTP/StreamableHTTP) | авто-discovery на старте, префикс `mcp_<server>_<tool>`, персистентные соединения с reconnect/backoff, фильтрация env для subprocess (API-ключи не передаются без явного `env:`), редактирование кредов в ошибках, поддержка sampling (`sampling/createMessage`) с лимитами (rpm, max_tokens, max_tool_rounds), конфиг `mcp_servers` в `~/.hermes/config.yaml`. Документация: hermes-agent.nousresearch.com/docs; навык hermes-agent → references/native-mcp.md. |
| **Claude Code** (Anthropic) | MCP через `claude mcp add`, marketplace (Claude Code / MCP marketplace), subprocess stdio по умолчанию | самый ранний и зрелый MCP-хост; /import аналог у конкурентов (codex). |
| **OpenAI Codex CLI** | `[mcp_servers]` в config.toml (stdio: command/args; remote: url) | v0.145 (21.07.2026): `/import` мигрирует MCP-конфиги, плагины, сессии и проектные памяти из Cursor и Claude Code, с дедупликацией; «MCP по обоим диалектам JSON» (codex.danielvaughan.com). |
| **Cursor** | MCP в settings (`.cursor/mcp.json`; UI-диалог) | поддержка remote MCP с OAuth; MCPoison CVE-2025-54136 (см. §4) — урок про безопасность. |
| **Gemini CLI** (Google) | MCP-поддержка из коробки (флаг `--mcp`, диалог добавления серверов), включая remote с OAuth | интеграция с Vertex/Gemini Enterprise; свободный open source (codersera, cloud.google.com docs). |
| **ChatGPT (desktop/apps)** | Connectors → Apps: remote-first MCP-клиент (Streamable HTTP), read+write с 09.09.2025 | архитектурно remote-first, в отличие от локально-субпроцессного подхода Claude/Hermes (chatforest). |
| **Прочие хосты** | VS Code (Copilot), GitHub Copilot CLI, Windsurf, Cline, Goose (Block), Cursor, Zed, JetBrains, OpenClaw и др. | установка MCP клиентов — индустриальный стандарт (buildtolaunch.substack.com, momen.app). |

### 3.2. Транспорт: stdio vs Streamable HTTP

- **stdio** — локальный, самый быстрый, нет auth (доверие = локальной файловой системе). Риск: несанитизированный запуск команд (см. §4), утечка окружения.
- **Streamable HTTP** — удалённый, OAuth 2.1 (PKCE, RFC 9728/8414/7591/8707), +30–200 мс латентности (techsy). С 2025-03-26 — единый bidirectional-эндпоинт; с 2025-11-25 — усилен OIDC-discovery и CIMD; с 2026-07-28 — stateless + заголовочная маршрутизация.

### 3.3. MCP-серверы памяти (связка с локальными память-системами)

Сравнение 7 вариантов (hjarni.com, июнь 2026; synabun.ai; dakera.ai; docs.mem0.ai):

| Сервер | Модель памяти | Когда брать | Цена (июнь 2026) |
|---|---|---|---|
| **Mem0 / OpenMemory** | извлечение фактов из разговоров; MCP-сервер `mem0-mcp`; локальный вариант OpenMemory | разработчикам агентов; авто-извлечение | Free Hobby; от $19/мес |
| **Letta** | tiered agent memory, полноценный runtime | если нужен агентный рантайм целиком | open source + cloud |
| **Zep** | temporal knowledge graph, память для enterprise-агентных команд | командные продакшн-агенты | open source engine + cloud |
| **Basic Memory** | локальные Markdown-файлы (Obsidian-совместимые) | local-first, приватность, читаемость | free local; cloud $15/сеat |
| **Hjarni** | Markdown-заметки с тегами + встроенный MCP | людям, которые хотят читать/править память руками | free; Pro $10/мес |
| **Supermemory** | API-извлечение памяти, низкая латентность | latency-sensitive разработчикам | free; от $19/мес |
| **Knowledge Graph MCP (official reference)** | локальный JSON-граф (entities/relationships/observations), ноль внешних API | «попробовать MCP-память за 5 минут», privacy-first | free, open source |

Контекст Vaz: Hermes уже имеет собственную память (сессии, mem0-подобные факты) и vazus-organic (mem0 + 768D векторный поиск + knowledge graph). Полезные дополнения: **basic-memory** (локальные markdown, интеграция с Obsidian), **knowledge-graph reference server** (лёгкий локальный граф), либо расширение собственного vazus-organic по MCP — не дублировать, а отдавать существующую память наружу другим MCP-клиентам (у vazus-organic уже есть read_resource / search-инструменты).

---

## 4. Безопасность MCP: риски, инциденты, защита

### 4.1. Модель угроз (консенсус источников)

Инвариант: **описания инструментов — это данные, на которые агент действует как на инструкции**; **ответы инструментов — это данные, на которые агент опирается**. MCP не несёт собственных гарантий аутентификации, целостности ответов и аудита — «каждое MCP-соединение это trust boundary» (the-agent-report.com).

- **Prompt injection (прямая и непрямая)**: вредоносные/сфабрикованные тексты на веб-страницах, в документах или в ответах инструментов инструктируют агента вызывать опасные инструменты (arXiv 2603.22489; septimlabs; decryptiondigest).
- **Tool poisoning**: подмена/порча описаний инструментов; бенчмарк **MCPTox: 72,8% успешных атак против o1-mini** (septimlabs, 2026).
- **Path traversal**: 82% MCP-реализаций уязвимы (Astrix 2025 report) — файловые серверы должны иметь жёсткий allowlist.
- **Supply chain / RCE через SDK**: `StdioServerParameters` в официальных SDK Anthropic (Python/TS/Java/Rust) передаёт `command`+`args` в subprocess без санитизации → **30+ RCE-проблем**, включая 14 CVE (см. ниже); OX Security назвал это «матерью всех AI supply chain» (15.04.2026); Anthropic ответил: «поведение намеренное, санитизация — ответственность клиента» (the-agent-report; Pillitteri).
- **Credential leakage / конфиг-хайджек**: статические API-ключи в конфигах (53% серверов без OAuth), кража через перехват окружения, «shadow MCP», злонамеренные реестры.
- **Confused deputy**: агент с широкими токенами GitHub/FS — любой компрометированный сеанс = широкий доступ (SlowMist checklist; septimlabs).
- **Sandbox escape**: цепочки типа **DuneSlide (CVE-2026-50548/CVE-2026-50549, CVSS 9.8, Cato AI Labs)**.

### 4.2. Цифры инцидентов (Q1–Q3 2026, the-agent-report.com от 22.07.2026)

- **14 CVE** присвоено MCP-реализациям к июлю 2026; **30+ RCE** от одной первопричины. Примеры: GPT Researcher (CVE-2025-65720, Critical), LiteLLM (CVE-2026-30623, Critical), Windsurf zero-click (CVE-2026-30615, Critical), DocsGPT (CVE-2026-26015), Agent Zero (CVE-2026-30624), Langchain-Chatchat, Fay, Flowise, Upsonic, **Cursor MCPoison (CVE-2025-54136, Critical)**, **MCP Inspector (CVE-2025-49596, Critical)**, LibreChat (CVE-2026-22252), WeKnora (CVE-2026-22688), Letta/LangFlow/LangBot (без CVE, выявлены OX).
- **200 000+ серверов** потенциально компрометируемы через SDK-флоу; 7 000 публично доступны; интернет-сканеры шлют корректные JSON-RPC initialize-запросы для картографирования поверхностей инструментов.
- **AgentSeal awesome-mcp-security**: 800+ серверов, 6 237 находок: 78,9% «safe» (score≥80), 21,1% «review».
- **30 CVE за 60 дней** (январь–февраль 2026) — по подсчёту septimlabs; OWASP публикует данные об эксплуатации (Q1 2026); Cisco относит MCP к emerging threat vectors.
- Спецификация до сих пор без стандартной модели разрешений — 2026-07-28 лишь начинает закрывать разрыв (the-agent-report).

### 4.3. Практические меры защиты (для Hermes-хоста на Windows и любого клиента)

1. **Минимальные привилегии**: fine-grained GitHub-токены (только нужные репозитории), OAuth вместо PAT где можно; никаких широких ключей в `env:`.
2. **Фильтрация окружения для subprocess**: Hermes уже не передаёт API-ключи MCP-серверам без явного `env:` — держите это включённым (native-mcp.md).
3. **Allowlist путей** для filesystem-серверов; никогда не давать корень диска.
4. **Не тянуть случайные npx/uvx-пакеты**: проверять репозиторий, звёзды, свежесть, «archived?», статус в AgentSeal/реестре; фиксировать версии.
5. **Отключение sampling** для ненадёжных серверов (`sampling: {enabled: false}` в Hermes); лимиты max_tool_rounds.
6. **Санбоксинг**: Windows Job Objects / контейнеры / отдельный пользователь для серверов; OS-level sandboxing уже входит в мейнстрим (Surface RTX Spark Dev Box, Build 2026).
7. **Remote MCP — только с OAuth 2.1 + PKCE (S256)**, короткоживущие токены, валидация `iss` (RFC 9207 в 2026-07-28), без bearer в URL, без token passthrough; DCR→CIMD.
8. **Тестирование перед подключением**: MCP Inspector (сам имел CVE — обновляйте), песочница, сканы AgentSeal.
9. **Шлюз** (если серверов много): Cloudflare Gateway (детекция MCP-трафика, MCP-порталы, DLP), Glama Gateway (per-tool ACL, логи, managed OAuth), Portkey Agent Gateway, MCP360 — единая точка discovery/auth/governance (tokenmix.ai).
10. **Аудит**: логи всех tool-call'ов, мониторинг `get_mcp_status()` в Hermes, review разрешений регулярно.

---

## 5. Новые тренды 2025–2026

### 5.1. Remote MCP и OAuth — стандарт для «облачных» серверов

- **Streamable HTTP (2025-03-26)** вытеснил HTTP+SSE (2019-стиль двухканальность); GET-поток для server-инициированных сообщений, Last-Event-ID для резюма.
- **OAuth 2.1** (draft 13) + PKCE S256 (обязателен для всех клиентов), RFC 9728 (Protected Resource Metadata), RFC 8414 (Authorization Server Metadata), RFC 7591 (DCR), RFC 8707 (Resource Indicators, `resource=` на authorize/token), audience-bound токены. Запрещены: implicit flow, ROPC, plain-PKCE при доступном S256, bearer в query string, token passthrough. Рекомендовано: refresh-rotation, короткоживущие access-токены, точное совпадение redirect URI (mcp.directory, май 2026).
- 2025-06-18 — переписан раздел авторизации; 2025-11-25 — OIDC Discovery, CIMD; 2026-07-28 — RFC 9207 `iss`-валидация, DCR депрецирован, application_type для localhost.
- **Практический вывод**: локальный фиксированный `Authorization: Bearer`-заголовок в конфиге — против паттерна; для remote-серверов нужен полноценный OAuth-флоу (workers-oauth-provider, Stytch, ScaleKit, Auth0, IBM mcp-context-forge, Composio Strata).

### 5.2. Расширения и новые абстракции

- **MCP Apps** — первое официальное расширение (SEP-1865; анонс 21.11.2025 Anthropic+OpenAI; live 26.01.2026, 9 партнёров на запуске): инструменты возвращают интерактивные UI-компоненты (`ui://`), рендерящиеся прямо в диалоге; поддержка в Claude, VS Code, Goose, ChatGPT (The Register) (blog.modelcontextprotocol.io/posts/2026-01-26/mcp-apps/; ecorpit; chatforest).
- **Tasks** — экспериментальные durable-задачи (2025-11-25) → официальное расширение `io.modelcontextprotocol/tasks` (2026-07-28): poll-based выполнение, `tasks/update`, единый `subscriptions/listen`.
- **EMA (Enterprise Managed Authorization)** — расширение для enterprise-управления авторизацией.
- **Server Instructions** — «руководство пользователя» для LLM: сервер описывает свои правила и предпочтения (официальный блог MCP).
- **.mcpb (MCP Bundle Format)** — переносимые локальные серверы одним файлом бандла (официальный блог MCP).
- **MRTR (2026-07-28)** — server→client-запросы (elicitation, sampling-confirmation) без постоянных потоков.
- **Header-based routing** — шлюзы маршрутизируют по `Mcp-Method`/`Mcp-Name`.

### 5.3. MCP для агентных роутеров и шлюзов

- Роль роутера захватили **MCP-шлюзы**: discovery (какие серверы/инструменты видит агент), authorization (кто что может вызвать), execution (маршрутизация, rate limit, логи, ретраи), governance (DLP, бюджеты, аудит) (tokenmix.ai, апрель 2026).
- **Cloudflare**: детекция MCP-трафика в Gateway (heuristics, «shadow MCP»), MCP-порталы, Access+AI Gateway + DLP, reference architecture для enterprise (апрель 2026), Code Mode (−99,9% токенов по заявлению), Agents SDK поддерживает 2026-07-28 «с дня нуля» (blog.cloudflare.com/enterprise-mcp/, /mcp-security-updates/, developers.cloudflare.com).
- **Portkey Agent Gateway**, **Glama Gateway**, **MCP360** — управляемые шлюзы «один URL = 100+ инструментов».
- 2026-07-28 делает шлюзы первоклассными: статистика протокола на HTTP-заголовках, кэшируемые списки, CIMD для централизованной регистрации клиентов.

### 5.4. A2A (Agent2Agent) — комплемент MCP

- **A2A** (Google, апрель 2025) → проект Linux Foundation с 23.06.2025 → **v1.0 в марте 2026** (под эгидой AAIF). MCP = «агент ↔ инструменты/данные», A2A = «агент ↔ агент» (децентрализованное выполнение задач, обмен карточками агентов) — два протокола одной экосистемы, а не конкуренты (a2a-protocol.org/topics/a2a-and-mcp; linuxfoundation.org; beam.ai; mcpblog.dev).
- Практика: в CLI-агентах (включая Hermes) A2A пока не нужен; полезен при оркестрации нескольких агентов/сервисов.

### 5.5. Управление и экосистема

- **AAIF (Agentic AI Foundation, Linux Foundation)** — создан 09.12.2025: сооснователи Anthropic, OpenAI, Block; платиновые — Google, Microsoft, AWS, Cloudflare, Bloomberg; A2A тоже перешёл под его крышу. Дорожная карта 2026 (март): транспорт, расширения (Apps/Tasks), безопасность/авторизация, масштабируемость (stateless) (mcpplaygroundonline, и др.).
- **Реестры**: официальный MCP Registry (preview 08.09.2025), Glama (21k+), PulseMCP, mcpservers.org — выбираем доверенные.
- **Вывод о победителе**: «The Protocol War Is Over» (fundesk.io, апрель 2026) — при всех оговорках по безопасности MCP выиграл как общий слой интеграции.

---

## 6. Рекомендации для личного агента Vaz (Hermes, Windows 11, privacy-first)

Уже подключено: vazus-organic (память/OS) и ckb (code intelligence) — 42 инструмента, subprocess (python/node).

### 6.1. Что добавить в первую очередь (максимум пользы / минимум риска)

| Сервер | Зачем | Транспорт | Риск/примечание |
|---|---|---|---|
| **Context7** (`uvx context7-mcp` или remote) | актуальная документация библиотек — убирает галлюцинации по API, дёшево по токенам | stdio (локально) | низкий; данные только в промпт |
| **Playwright MCP** (Microsoft, `npx @playwright/mcp@latest`) | реальный браузер: скриншоты, формы, скрейпинг | stdio | средний (см. §4.1 walk через страницы) — запускать под отдельным пользователем/Job Object; не давать доступ к ~/.hermes |
| **GitHub MCP** (`github/github-mcp-server`, Docker или remote) | issues/PR/code search для репозиториев Vaz | stdio (docker) или remote | средний; **fine-grained токен** только на нужные репозитории, без админ-скоупов |
| **Brave Search MCP** или **Tavily MCP** | качественный веб-поиск поверх DDG (уже есть) | remote (HTTP) | ключ API — только в `env:` сервера; traffic минимальный благодаря лимитам free-tier |
| **Fetch/Time/Sequential Thinking** (reference) | простые утилиты: fetch-страниц без curl-костылей, время, декомпозиция | stdio | низкий; не хранят данных |

### 6.2. Память

- **Не дублировать**: у Vaz уже есть vazus-organic (mem0 + 768D-вектора + knowledge graph) — это сильнее большинства MCP-memory-серверов.
- Опционально: **basic-memory** (локальные markdown, Obsidian-формат — читабельно и переносимо) или официальный **knowledge-graph reference server** для экспериментов; если появится второй MCP-клиент (Claude Code, Cursor) — отдавать память им через vazus-organic MCP-интерфейс.

### 6.3. Безопасность при подключении (чек-лист под Hermes/Win11)

1. `pip install mcp` (уже стоит) + свежий `npm i -g mcp`/uvx-версии; фиксируйте версии серверов.
2. Никаких API-ключей в конфиге кроме `env:` конкретного сервера (Hermes фильтрует окружение subprocess — не отключать).
3. `sampling: {enabled: false}` для всех серверов, кроме проверенных.
4. Allowlist путей для filesystem-серверов (если понадобится) — только `C:\vazus\...`, никогда весь диск.
5. Remote-серверы — только с OAuth/PKCSE-флоу; никаких bearer-токенов в открытом виде в yaml вне зашифрованного хранилища.
6. Sandbox: запускать браузерные и filesystem-серверы как отдельный Windows-пользователь или в Job Object с ограничением; держать подальше от профиля Hermes.
7. Периодический аудит: `get_mcp_status()` (метрики, ошибки), проверка «archived?» репозиториев, сканы AgentSeal/prompttools перед доверием.
8. Не подключать серверы из случайных списков: официальный Registry, Glama-проверенные, vendor-овые репозитории (GitHub/Microsoft/Supabase/Stripe/Cloudflare/Notion/Linear/Sentry — но только если реально нужны).

### 6.4. Чего ждать дальше

- Обновление Hermes до поддержки концепций 2026-07-28 по мере выхода (stateless-клиент, заголовочная маршрутизация, кэширование списков, MRTR) — следить за `pip install -U mcp` и релизами hermes-agent.
- Если появится удалённый доступ к агенту с нескольких устройств — связка remote MCP за OAuth-шлюзом (Cloudflare/Glama-стиль) вместо bearer-заголовков.
- Для оркестрации нескольких агентов — изучить A2A (пока не критично).

---

## 7. Источники

**Официальные (MCP-проект):**
- Blog: The 2026-07-28 Specification — https://blog.modelcontextprotocol.io/posts/2026-07-28/
- Blog: 2026-07-28 Release Candidate — https://blog.modelcontextprotocol.io/posts/2026-07-28/release-candidate/
- Blog: MCP Apps (26.01.2026) — https://blog.modelcontextprotocol.io/posts/2026-01-26/mcp-apps/
- Blog: Introducing the MCP Registry (08.09.2025) — https://blog.modelcontextprotocol.io/posts/2025-09-08/mcp-registry-preview/
- Spec changelog 2025-11-25 — https://modelcontextprotocol.io/specification/2025-11-25/changelog (зеркало: https://modelcontextprotocol.info/specification/2025-11-25/changelog/)
- Spec changelog 2025-06-18 — https://modelcontextprotocol.io/specification/2025-06-18/changelog
- Spec: Authorization — https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- GitHub: spec repo + releases — https://github.com/modelcontextprotocol/modelcontextprotocol/releases
- GitHub: registry — https://github.com/modelcontextprotocol/registry ; https://registry.modelcontextprotocol.io/ ; https://modelcontextprotocol.io/registry/about
- GitHub: ext-apps — https://github.com/modelcontextprotocol/ext-apps
- Cloudflare Agents docs (MCP) — https://developers.cloudflare.com/agents/model-context-protocol/
- Cloudflare: enterprise MCP reference architecture — https://blog.cloudflare.com/enterprise-mcp/
- Cloudflare: MCP security updates — https://blog.cloudflare.com/mcp-security-updates/
- Cloudflare: MCP portal gateway routing (20.03.2026) — https://developers.cloudflare.com/changelog/post/2026-03-20/mcp-portal-gateway-routing/
- A2A Protocol (LF): A2A and MCP — https://a2a-protocol.org/latest/topics/a2a-and-mcp/ ; GitHub — https://github.com/a2aproject/A2A
- LF press: A2A project launch (23.06.2025) — https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents
- OpenAI dev docs: MCP and Connectors — https://developers.openai.com/api/docs/guides/tools-connectors-mcp
- Microsoft: Connect agents to MCP (Foundry) — https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol
- Gemini CLI — https://docs.cloud.google.com/gemini/docs/codeassist/gemini-cli

**Аналитика / новости (читаны полностью):**
- ChatForest: MCP and OpenAI (таймлайн) — https://chatforest.com/guides/mcp-openai-integration/
- The Agent Report: MCP Security in Q3 2026 (14 CVE, 200K серверов, DuneSlide) — https://the-agent-report.com/2026/07/mcp-security-landscape-2026-vulnerabilities-mitigations/
- Techsy: 15 Best MCP Servers 2026 — https://techsy.io/en/blog/best-mcp-servers-2026
- Septim Labs: Best MCP servers 2026: 15 picks with security caveats — https://septimlabs.com/blog/best-mcp-servers-2026
- Arcade: Microsoft Build 2026: MCP and the Agent Stack — https://www.arcade.dev/blog/microsoft-build-2026-agent-stack/
- MCP.Directory: OAuth 2.1 for Remote MCP Servers — https://mcp.directory/blog/oauth-21-for-remote-mcp-servers-streamable-http-explained-2026
- TokenMix: MCP Gateway 2026 — https://tokenmix.ai/blog/mcp-gateway
- Hjarni: Best MCP Memory Servers 2026 — https://hjarni.com/blog/best-mcp-memory-server
- Codex KB: /import в v0.145 — https://codex.danielvaughan.com/2026/07/24/codex-cli-v0145-import-command-cursor-claude-code-migration-mcp-servers-memories-settings/
- Codex KB: Claude Code ↔ Codex CLI in practice — https://codex.danielvaughan.com/2026/03/27/claude-code-codex-mcp-in-practice/
- agentmarketcap: MCP at One Year — https://agentmarketcap.ai/blog/2026/04/05/mcp-at-one-year-universal-agent-standard
- agentmarketcap: MCP November 2025: OAuth 2.1 PKCE, Async Tasks — https://agentmarketcap.ai/blog/2026/04/06/mcp-oauth-pkce-agent-authentication-enterprise-security
- fastai.news: MCP 97M installs + AAIF — https://fastai.news/2026/04/20/mcp-97-million-installs-linux-foundation-agentic-ai-foundation/
- gentic.news: 10K servers, 97M monthly — https://gentic.news/article/mcp-hits-10k-servers-97m-monthly
- openclaw.direct: MCP News and Updates 2026 — https://openclaw.direct/mcp-guide/model-context-protocol-news
- Composio: 2026-07-28 update breakdown — https://composio.dev/content/mcp-2026-07-28-update-statelessness-apps-auth
- 4sysops: 2026-07-28 spec summary — https://4sysops.com/archives/2026-07-28-model-context-protocol-mcp-stateless-multi-round-trip-routable-headers-authorization-hardening/
- TokenMix: MCP updates/changelog 2026 — https://www.tokenmix.ai/blog/mcp-updates-changelog-every-protocol-change-2026
- mcpplaygroundonline: MCP 2026 roadm — https://mcpplaygroundonline.com/blog/mcp-2026-roadmap-whats-changing-for-developers
- mcpblog.dev: A2A v1.0 — https://mcpblog.dev/blog/2026-03-15-a2a-v1-mcp
- Beam.ai: A2A vs MCP — https://beam.ai/agentic-insights/agent2agent-vs-mcp-2026-ai-agent-stack
- fundesk.io: MCP 97M — protocol war over — https://www.fundesk.io/mcp-97-million-installs-protocol-war-over

**Каталоги серверов:**
- punkpeye/awesome-mcp-servers — https://github.com/punkpeye/awesome-mcp-servers
- hireblackout/awesome-mcp-servers — https://github.com/hireblackout/awesome-mcp-servers
- awesome-mcp.tools: 2,000+ directory — https://awesome-mcp.tools/blog/mcp-servers-list
- Glama (registry + gateway) — https://glama.ai/
- MCP Server Hub — https://gist.github.com/devinschumacher/fc434091c6414acc098f58b18a0146d8

**Безопасность (дополнительно):**
- OX Security: The Mother of All AI Supply Chains (15.04.2026) — https://ox.security/ (advisory; цитируется в the-agent-report)
- AgentSeal awesome-mcp-security — https://github.com/agentseal/awesome-mcp-security (цитируется в the-agent-report; каталог сканов)
- Baeseokjae: MCP Security Guide 2026 — https://baeseokjae.github.io/posts/mcp-security-guide-2026/
- Baeseokjae: MCP OAuth 2.1 Authentication Guide — https://baeseokjae.github.io/posts/mcp-oauth-authentication-guide-2026/
- Practical DevSecOps: MCP vulnerabilities / guide — https://www.practical-devsecops.com/mcp-security-vulnerabilities/
- prompttools.co: MCP Server Security Checklist 2026 — https://prompttools.co/blog/mcp-server-security-checklist-2026
- ClawdContext: MCP Security Hardening Guide — https://clawdcontext.com/en/blog/mcp-security-best-practices-complete-guide-2026
- DecryptionDigest: MCP Security Risks — https://www.decryptiondigest.com/blog/model-context-protocol-security-risks

**Memory (дополнительно):**
- Mem0 MCP docs — https://docs.mem0.ai/platform/mem0-mcp ; GitHub — https://github.com/mem0ai/mem0-mcp ; mem0 core — https://github.com/mem0ai/mem0
- SynaBun: Mem0 vs Letta vs Zep vs SynaBun — https://synabun.ai/blog/mcp-memory-servers-comparison
- Dakera: MCP memory comparison — https://dakera.ai/blog/mcp-memory-server-comparison-2026

**Сравнение CLI-агентов:**
- Codersera: Gemini CLI complete guide — https://codersera.com/blog/gemini-cli-complete-guide-2026/
- Codersera: Cursor vs Claude Code vs Codex CLI vs Gemini CLI — https://codersera.com/blog/cursor-composer-vs-claude-code-vs-codex-vs-gemini-cli-2026/
- Agensi: AI coding tools comparison — https://www.agensi.io/learn/ai-coding-tools-comparison-2026
- Momen: Best MCP servers/plugins for Claude Code, Codex, Cursor — https://momen.app/blogs/best-mcp-servers-plugins-claude-code-codex-cursor-2026/
- BuildToLaunch: MCP Setup (7 clients) — https://buildtolaunch.substack.com/p/mcp-setup-claude-chatgpt-vscode-cursor

**Hermes (локально):**
- Документация — https://hermes-agent.nousresearch.com/docs/
- Навык «hermes-agent» → references/native-mcp.md (конфиг `mcp_servers`, stdio/HTTP, env-фильтрация, sampling, безопасность)

---

*Отчёт подготовлен 17.08.2026. Все URL проверены доступностью на дату составления; страницы modelcontextprotocol.io и developers.openai.com отдают 403 на прямой curl без браузера — их содержимое подтверждено зеркалами и вторичными источниками.*