# Рынок AI-модельных роутеров, гейтвеев и бесплатных AI-кодинг-станций — 2025–2026

**Дата исследования:** 17 августа 2026
**Область:** платные роутеры/гейтвеи, бесплатные станции, китайские гейтвеи и цензура, стандарты CLI-агентов 2026, сравнение цена/лимиты/контекст/надёжность.

> ⚠️ Дисклеймер: цены и лимиты в этом отчёте зафиксированы на дату исследования и быстро меняются. Ключевые источники — официальные страницы провайдеров и датированные материалы (июль–август 2026). Перед покупкой сверить с живыми страницами.

---

## TL;DR (главное)

1. **OpenRouter остаётся де-факто стандартом агрегатора**, но берёт 5.5% комиссии на пополнение, не имеет публичного SLA и не гонится за ценой (наценки на маршрутизацию ~25–40 мс). Бесплатный слой существует: **18 моделей :free** (на август 2026), лимиты 20 req/min, 50 req/day без кредитов / 1000 req/day после пополнения ≥ $10.
2. **Бесплатных «станций» стало меньше**: **kluster.ai закрылся** (команда ушла в MITO, видео). Зато появились удобные каталоги: **freellm.net / awesome-freellm-apis** (442+ бесплатных API от 31 провайдера, обновляется ежедневно).
3. **Главные бесплатные/бюджетные опции для кодинга на август 2026**: GLM-5.2:free на OpenRouter (качество #1), Nemotron 3 Ultra :free (1М контекст), Gemini API Free Tier (Flash: ~15 RPM / 1500 RPD; Pro убрали из free в апреле 2026), **GLM Coding Plan** ($18/мес, GLM-5.3/5.2/5-Turbo для Claude Code / OpenCode / Cline / OpenClaw), Grok (~$175 промо-кредитов, Grok 4.1 Fast $0.20/M).
4. **2026 = год «разделения подписок»**: Anthropic с 15 июня 2026 вынесла программное использование Claude (Agent SDK, `claude -p`, сторонние агенты) в отдельный месячный пул кредитов ($20/$100/$200 по тарифу) — интерактивный Claude Code в терминале/IDE не затронут. Эра «арбитража $20-подписки против $500 API-расходов» закончилась.
5. **Китайские гейтвеи (включая agentrouter.org) — дёшево и опасно**: built on new-api/one-api, дешёвые расценки на топовые модели, но типичны фильтры «чувствительных слов» (HTTP 500 вместо внятной ошибки), UA-вайтлисты, режут длинные сессии, нет SLA, полное логирование диалогов.
6. **DeepSeek V4 подорожал — прямо сегодня (17.08.2026)** введено peak/off-peak ценообразование: off-peak = половина peak, cache-hit вход V4 Pro подорожал до +500%. Vaz использует deepseek-v4-flash — стоит пересчитать бюджет.

---

## 1. Платные роутеры и гейтвеи

### 1.1 OpenRouter (эталон)

- Единый OpenAI-совместимый API на сотни моделей, агрегация биллинга, аналитика, fallback-маршрутизация между провайдерами по факту аптайма.
- **Комиссия 5.5%** на пополнение не-криптой (мин. $0.80), 5.0% крипта, **BYOK-наценка 5%**, наценки на маршрутизацию нет (цены = цены провайдеров), оверхед 25–40 мс.
- **Нет публичного SLA** (ToS, секция 16: без гарантий непрерывности; ответственность ограничена $100 или 12 мес. платежей).
- Бесплатный слой: `/openrouter/free` — умный роутер по бесплатным моделям; бесплатные модели субсидируются самим OpenRouter и провайдерами.
- Источники: https://openrouter.ai/models , https://openrouter.ai/docs/faq , https://openrouter.ai/collections/free-models , https://ofox.ai/blog/openrouter-alternatives-2026/

### 1.2 Альтернативы OpenRouter (обзор рынка, март–август 2026)

| Класс | Игроки | Суть |
|---|---|---|
| Гейтвей/прокси (self-host) | **LiteLLM**, Portkey, Helicone, Kong AI Gateway, **Bifrost (Maxim AI)** | полный контроль, нулевая наценка, но самому поддерживать; Bifrost — ультра-низкий оверхед под высокий RPS |
| Облачные гейтвеи | Cloudflare AI Gateway, Vercel AI Gateway, TrueFoundry, Azure AI Foundry, AWS Bedrock, Google Vertex AI | для команд, уже живущих в экосистеме |
| Агрегаторы (один ключ) | **OpenRouter**, **Ofox**, ZenMux, Eden AI, Unify AI, Martian, llmapi.ai | роутинг/балансировка/кредиты; ZenMux — «LLM-страховка» |
| Инференс-провайдеры (дёшево) | **DeepInfra**, **Together AI**, **Fireworks AI**, **Groq** | open-веса почти без наценки, но ограничения по concurrency |
| Роутеры с benchmark-логикой | Unify AI, Martian | выбор лучшей модели под промпт по метрикам/цене |

Ключевые обзоры: https://llmapi.ai/best-openrouter-alternatives-2026-pick-the-right-ai-gateway-for-real-production-work/ , https://www.getmaxim.ai/articles/best-openrouter-alternative-in-2026-a-production-ai-gateway-comparison/ , https://ofox.ai/blog/openrouter-alternatives-2026/

**Ofox (пример прямого конкурента):** 3 нативных SDK-протокола (OpenAI/Anthropic/Gemini), 0% платформенной комиссии, официальные цены DeepSeek (V4 Flash $0.14/$0.28 за 1М; 1М контекст, 384K выход). Обновление 2026-08-17: DeepSeek перевёл всё V4-семейство на peak/off-peak биллинг с 16:00 UTC 16.08.2026.

### 1.3 new-api / one-api и их форки

- **one-api (songquanpeng/one-api)** — «LLM API management & key redistribution», единый API-адаптер под OpenAI/Azure/Anthropic/Gemini/DeepSeek/豆包/ChatGLM/文心一言/讯飞/通义/360/混元; один бинарник, Docker, англ. UI.
  https://github.com/songquanpeng/one-api
- **new-api (QuantumNous/new-api)** — форк one-api, «unified AI model hub»: кросс-конвертация любых LLM в OpenAI/Claude/Gemini-совместимые форматы; ~45.4k звёзд, 10.7k форков на GitHub — **это основа большинства китайских публичных гейтвеев**.
  https://github.com/QuantumNous/new-api
- Публичные инстансы на базе такого ПО: многочисленные «одно-ключ-ко-всему» сайты (agentrouter.org, «API中转站»), обычно с UAZ-ограничениями, ежедневными лимитами и логированием трафика. Публичных стабильных free-инстансов международного уровня нет — все живут «в серой зоне» и периодически умирают/меняют домены.

---

## 2. Бесплатные AI-кодинг-станции (август 2026)

### 2.1 OpenRouter Free Models (18 моделей, 17 августа 2026)

Лимиты: **20 req/min; 50 req/day без кредитов; 1000 req/day после пополнения ≥ $10** (старые данные «200/день» устарели). Карта не нужна. Подписано: free-модели субсидируются и могут ротироваться.

| Модель :free | Провайдер | Контекст | Качество | Примечание |
|---|---|---|---|---|
| z-ai/glm-5.2:free | Z.ai | 128K | 83 (топ-1) | лучший универсал |
| nvidia/nemotron-3-ultra-550b-a55b:free | NVIDIA | **1M** | 61 | агентские сценарии, tools |
| nvidia/nemotron-3.5-lightning:free | NVIDIA | 1M | 37 | быстрый, tools |
| nvidia/nemotron-3-super-120b-a12b:free | NVIDIA | 262K | — | reasoning, 1M по данным buldrr |
| google/gemma-4-31b-it:free | Google | 262K | 47 | vision+tools |
| google/gemma-4-26b-a4b-it:free | Google | 262K | 41 | vision+tools |
| cohere/north-mini-code:free | Cohere | 256K | 32 | агентный кодинг (OpenCode/SWE-Agent) |
| openai/gpt-oss-20b:free | OpenAI | 131K | 24 | лёгкий кодинг |
| poolside/laguna-s-2.1:free | Poolside | 262K | — | кодинг-агент (Terminal-Bench 70.2) |
| poolside/laguna-xs-2.1:free | Poolside | 262K | — | лёгкий агент |
| dots-studio/dots-3-note-preview:free | dots-studio | 512K | — | большой контекст |
| liquid/lfm-2.5-2.6b:free | LiquidAI | 128K | — | лёгкий |
| openrouter/free | OpenRouter | 200K | — | авто-роутер по free |

Полный список: https://openrouter.ai/collections/free-models , агрегированные списки: https://costgoat.com/pricing/openrouter-free-models , https://buldrr.com/openrouter-free-models-list-2026-all-27-models-ranked-tested/
⚠️ Ротация реальна: DeepSeek/Gemini/Mistral :free-моделей на OpenRouter **больше нет** (июль 2026), старые ID из гайдов дают ошибку.

### 2.2 OpenCode Zen / OpenCode Go

- **OpenCode** — open-source (MIT) терминальный агент на Go: ~178K звёзд GitHub, 75+ провайдеров, ~7.5M разработчиков/мес. Своих моделей не требует («free models included»). https://opencode.ai , https://github.com/anomalyco/opencode
- **OpenCode Zen** — курируемый гейтвей от команды OpenCode: протестированные связки модель+провайдер (GPT-5.6 Sol/Terra/Luna, GPT-5.5, 5.4, Codex 5.3 и т.д. через `https://opencode.ai/zen/v1/responses`), pay-as-you-go, пополнение от $20 (+$1.23 комиссия). https://opencode.ai/docs/zen/
- ⚠️ **Надёжность под вопросом**: публичный issue (июль 2026) — Zen/Go `chat/completions` массово отдавали HTTP 500 на все запросы. https://github.com/anomalyco/opencode/issues/35276
- **OpenCode Go** — hosted-сервис для CLI-агентов (то, что использует Vaz); стоит держать как резерв, а не единственный канал.

### 2.3 Бесплатные лимиты больших вендоров

- **GitHub Copilot**: Free = **50 запросов/мес** (с апреля 2026; раньше 2000/мес), Pro $10/мес, Pro+ $39, Business $19/пользователь, Enterprise $39. Приостановлены self-serve-регистрации Copilot Business (22.04.2026).
  https://docs.github.com/copilot/about-github-copilot/plans-for-github-copilot , https://costbench.com/software/ai-coding-assistants/github-copilot/
- **Gemini API Free Tier (Developer tier)**: Flash ~**15 RPM / 1500 RPD**; **Pro убраны из free-тира в апреле 2026**; данные free-тира могут использоваться для обучения; коммерческое использование запрещено. 429 → экспоненциальный backoff.
  https://tinkerllm.com/blog/gemini-api-free-tier-limits-rate-quotas/ , https://www.aifreeapi.com/en/posts/gemini-api-free-tier-complete-guide
- **xAI / Grok**: Grok 4.3 $1.25/$1M, Grok 4.1 Fast $0.20/$1M, 2М-контекст, batch-скидки; **~$175/мес промо-кредитов** для новых аккаунтов (по данным на июнь 2026); потребительские планы — общий недельный пул; API — per-model RPS/TPM.
  https://the-rogue-marketing.github.io/grok-xai-api-pricing-may-2026/ , https://ai-x.chat/guide/grok-usage-limits/ , https://www.ai-toolbox.co/grok-models/grok-pricing-plans-api-2026
- **GLM Coding Plan (Z.ai / Zhipu)**: $18/мес (Lite) — GLM-5.3 / GLM-5.2 (1М контекст) / GLM-5-Turbo внутри Claude Code, Kilo Code, Cline, OpenCode, Clawdbot/OpenClaw; недельные кредиты. **Бесплатно:** GLM-4.5-Flash ($0 на все токены) на публичном API.
  https://z.ai/landing-page/coding-plan , https://www.layer3labs.io/guides/z-ai-pricing , https://codingplan.org/en/plans/glm
- **kluster.ai — ЗАКРЫТ**: «kluster.ai has joined MITO… следующий этап — AI-video creation», бесплатный инференс прекращён. https://kluster.ai
- **Каталоги бесплатных API**: freellm.net (402+ моделей), awesome-freellm-apis (442+ API, 31 провайдер, daily-refresh, одно-клик конфиги для Claude Code/Cursor/Codex/Aider): https://github.com/open-free-llm-api/awesome-freellm-apis
- **Локально**: Ollama по-прежнему стандарт для локальных моделей (плюс llama.cpp/GGUF).

### 2.4 «Бесплатные агенты» (без своего ключа) в 2026

Лучшие по обзорам: **Gemini CLI** (единственный frontier-агент с реально щедрым free-тиром), **Aider** (бенчмарк-лидер, терминал), **Continue / Kilo Code / Cline** (плагины IDE), **OpenCode** (самостоятельный). CoderFile: 5 агентов работают вообще без API-ключа (Ollama + free-тиры).
https://standardcompute.com/best-ai-agent/for/free , https://agentic.ai/best/free-coding-agents , https://coderfile.io/blog/free-ai-coding-agents-no-api-key-2026 , https://github.com/bradAGI/awesome-cli-coding-agents

---

## 3. Китайские гейтвеи: цензура и стабильность (важно для Vaz)

### 3.1 agentrouter.org (текущий источник Vaz)

- Позиционирование: «统一的大模型接口网关» (единый шлюз больших моделей), «лучшие цена и стабильность», заголовок «**designed & developed by New API & One API**» — т.е. продеолжение экосистемы new-api/one-api. https://agentrouter.org
- Эндпоинты: `/v1/chat/completions`, `/v1/responses`, `/v1/messages` (совместимость OpenAI/Anthropic/Gemini), `/v1beta/models`, embeddings/rerank/images/audio.
- Цены (страница /pricing, август 2026): формула `cost = group_rate × model_rate × (prompt_tokens + completion_tokens × completion_rate) / 500000 USD`.
  - gpt-5.6-sol — prompt $4/M, completion $20/M (rate 2x, completion 5x)
  - claude-opus-4-8 — prompt $3/M, completion $15/M (rate 1.5x, completion 5x)
  - claude-opus-5 — prompt $2/M, completion $10/M (rate 1x, completion 5x)
  - Доступно всего 3 модели, группа «default», множитель 1x.
- ⚠️ Наблюдаемые проблемы (подтверждаются опытом Vaz): обрыв длинных сессий по фильтру «чувствительных слов» (sensitive words detection) с **HTTP 500** (типичная китайская практика — маскировать цензуру под внутреннюю ошибку), UA-вайтлисты (пускает только «свои» User-Agent клиенты, чужие/нестандартные — 403/500), отсутствие SLA и бэкапов, вероятное логирование всего трафика (см. ниже langsasec/ai_gateway с «全量对话日志»).

### 3.2 Типовые паттерны китайских гейтвеев (экосистема new-api)

- **Sensitive-word filter**: PerryLink/Sensitive-Word-Filter-CN — высокопроизводительный движок фильтрации китайского текста (детект/маскирование/удаление запрещённых терминов). https://aichina.news/repositories/PerryLink/Sensitive-Word-Filter-CN/
- **ai_gateway (langsasec)**: «全程薅羊毛workbuddy的AI网关» — управление ключами, **белый список (whitelist)**, **лимит потока**, **детекция чувствительных слов**, **полное логирование диалогов**. https://github.com/langsasec/ai_gateway
- Научное направление: IPKE-MoE — распознавание *вариантов* чувствительных слов (обход фильтров). https://www.sciencedirect.com/org/science/article/pii/S154622182600161X
- Контекст: цензура в китайских open-моделях в 2026 остаётся темой — Semafor (29.07.2026) пишет, что дистиллированные версии китайских моделей не наследуют guardrails. https://www.semafor.com/article/07/29/2026/censorship-in-chinese-ai-models-can-be-undone-new-research-shows

**Вывод для Vaz**: agentrouter.org — дёшево и (пока) работает для коротких сессий, но это «серый» сервис без контракта. Для privacy-first и длинных агентских сессий — не основной канал. Митигации: короткие сессии с контекст-компрессией, ретраи на 500, резервный маршрут (OpenRouter/GLM/Zen), не слать чувствительные данные.

---

## 4. Что стало стандартом для CLI-агентов в 2026

### 4.1 Anthropic / Claude Code — главный стандарт интерактивной работы

- **Claude Code**: терминальный агент Anthropic (запущен 2025, к 2026 — де-факто эталон). Тарифы: Pro $20/мес, Max 5x $100, Max 20x $200 (плюс Team/Enterprise). https://claude.com/product/claude-code , https://claude.com/pricing
- **Событие 2026 — «разделение подписок» (15 июня 2026)**:
  - В отдельный месячный пул кредитов выведены: **Claude Agent SDK**, **`claude -p`**, **Claude Code GitHub Actions**, сторонние агенты на Agent SDK (**OpenClaw, Conductor, Zed, Jean**).
  - Кредиты: **Pro $20, Max5x $100, Max20x $200** — не переносятся, списываются по API-ставкам, требуют активации до 15.06.
  - **Интерактивный Claude Code в терминале/IDE НЕ затронут** — остаётся на лимитах подписки.
  - $20 кредита ≈ 6.6M входных / 1.3M выходных токенов Sonnet 4.6 — агентская сессия 100–200K токенов сжигает их быстро.
  - Причина: третьи агенты вне системы prompt-caching («really hard to do sustainably» — Борис Черни); «эра арбитража» ($20-подписка вместо $500 API) закончилась; по оценке Тео Брауна (T3.gg) для CI-инструментов это ~25x-сокращение.
  https://devtoolpicks.com/blog/anthropic-splits-claude-subscriptions-agent-sdk-credit-june-2026
- Фон: в апреле 2026 Anthropic банила сторонних агентов с подписок; кратко тестировала удаление Claude Code из Pro.

### 4.2 OpenAI Codex CLI

- Codex CLI (Rust) 2026: аутентификация — **OAuth / device flow** (стандарт для личного использования), API-ключи для CI, config.toml-профили. https://codex.danielvaughan.com/2026/04/01/codex-cli-authentication-flows-credential-management/
- Известная боль: на Windows device-code OAuth падает из-за Cloudflare-челленджа на auth.openai.com (май 2026) — обход через API-ключ. https://community.openai.com/t/codex-cli-login-fails-on-windows-auth-openai-com-reachable-via-curl-but-oauth-device-auth-fail/1381736

### 4.3 Gemini CLI

- Единственный frontier-агент со щедрым free-тиром (через Developer tier): ~15 RPM / 1500 RPD на Flash. IDE-квоты (в т.ч. то, что Vaz использует через agy :5001 — gemini-3.7-flash, 5000 req/day) — отдельный канал с отдельными лимитами.

### 4.4 Provider-агрегаторы как альтернатива подпискам

- **OpenRouter** (кредиты, free-слой, фолбэки), **OpenCode Zen** (курируемые модели), **GLM Coding Plan** (Z.ai, $18/мес — самый дешёвый заменятель Claude-подписки для кодинга), китайские гейтвеи (дёшево, но цензура).
- Общий тренд: CLI-агенты унифицировались на OpenAI-совместимом `/v1/chat/completions` (и `/v1/responses` для Reasoning) + MCP для инструментов; роутер/агрегатор стал нормальным слоем между агентом и вендорами.

---

## 5. Сравнение: надёжность / цена / лимиты / контекст

### Сводная таблица провайдеров для Vaz (август 2026)

| Провайдер | Тип | Цена (вход/выход $/1M) | Контекст | Лимиты | Надёжность / риски |
|---|---|---|---|---|---|
| **OpenRouter** | агрегатор (кредиты) | цены провайдеров + 5.5% пополнение; free-слой $0 | до 1M (free: Nemotron) | free: 20 rpm, 50/1000 rpd; платно — по модели | высокая, но нет SLA; 429 на free |
| **OpenRouter: GLM-5.2 free** | free-модель | $0 | 128K | 20 rpm / до 1000 rpd | стабилен последние месяцы, топ по качеству |
| **OpenRouter: Nemotron 3 Ultra free** | free-модель | $0 | 1M | 20 rpm / до 1000 rpd | агентские задачи, tools |
| **OpenRouter: Laguna S 2.1 free** | free-модель | $0 | 262K | 20 rpm / до 1000 rpd | кодинг-агент (Terminal-Bench 70.2) |
| **Gemini API Free Tier** | вендор free | $0 | 1M (Flash) | ~15 rpm / 1500 rpd | стабилен; данные идут на обучение; без коммерции; Pro нет в free |
| **Gemini IDE-квоты (через agy :5001)** | вендорная квота | ~$0 | — | ~5000 req/day (по опыту Vaz) | стабильно, лучший «бесплатный» workflow Vaz |
| **GLM Coding Plan** | подписка Z.ai | $18/мес, недельные кредиты | 1M (GLM-5.2) | кредиты недельные | CN-компания, но международный продукт (Z.ai), платно = нет рекламы в обучении |
| **GLM-4.5-Flash (API)** | вендор free | $0 | — | дневные лимиты | самый простой бесплатный вход у Z.ai |
| **Grok API (xAI)** | вендор | 4.3: 1.25; 4.1 Fast: 0.20 | 2M | промо ~$175/мес кредиты; далее платно | молодой, меняется часто |
| **GitHub Copilot Free** | вендор free | $0 | — | **50 req/мес** | почти бесполезно, Pro $10 ок |
| **OpenCode Zen** | агрегатор кураторский | pay-as-you-go от $20 | по моделям (GPT-5.x) | кредиты | **были массовые 500 (июль 2026)** — осторожно |
| **agentrouter.org** | CN-гейтвей (new-api) | gpt-5.6-sol $4/$20; opus-4-8 $3/$15; opus-5 $2/$10 | по моделям | множители группы; UA-лимиты | дёшево, но: sensitive-words 500, UA-вайтлист, режут длинные сессии, логирование, без SLA |
| **DeepSeek API (V4)** | вендор | V4 Flash $0.14/$0.28 (до 17.08); **с 17.08 peak/off-peak, off-peak=½ peak, cache-hit V4 Pro +500%** | 1M / 384K out | стандартные RPD | CN-вендор; цены выросли в разы, следить |
| **Ollama / llama.cpp** | локально | $0 | по модели | железо | максимальная privacy, качество ниже frontier |
| **LiteLLM (self-host)** | гейтвей OSS | $0 (свой ключ) | — | свои | полный контроль, сам хостишь |

### 5.2 Ключевые критерии выбора

- **Надёжность > дешевизна** для агентских длинных сессий: OpenRouter/вендорские API; не CN-гейтвеи.
- **Контекст**: для длинных сессий 1M+ — Nemotron free, Gemini Flash, DeepSeek V4, GLM-5.2; 128–262K — основная масса.
- **Privacy-first**: локально (Ollama) + вендоры без CN-юрисдикции (Google/OpenAI/Anthropic/xAI) с платными тирами (без обучения на данных); избегать CN-гейтвеев для чувствительного кода.
- **Цена**: бесплатно = OpenRouter free (50/1000 rpd) + Gemini Free + GLM-4.5-Flash; ~$18/мес = GLM Coding Plan; ~$20 = Anthropic Pro (интерактив) или Copilot Pro.

---

## 6. Рекомендации для Vaz (топ-3 пути)

1. **Сохранить и укрепить текущий бесплатный стек**: agy на IDE-квотах (gemini-3.7-flash, 5000 req/day) + OpenRouter free-слой (GLM-5.2:free для IQ-задач, Nemotron 3 Ultra:free для длинных контекстов, лимит 50/день → прокачать до 1000 разовым пополнением ≥ $10) + OpenCode Go как резерв. **Снизить зависимость от agentrouter.org** (оставить только для коротких сессий конкретных моделей opus/gpt-5.6-sol, не для агентских длинных).
2. **Выбрать один платный бюджетный канал для тяжёлой агентской работы**: GLM Coding Plan $18/мес (GLM-5.3/5.2 в Claude Code / OpenCode / agy через OpenAI-совместимый endpoint, 1M контекст, недельные кредиты) — самый дешёвый заменятель Anthropic-подписки; либо Anthropic Pro $20/мес, если нужен именно интерактивный Claude Code (помнить: `claude -p` и программный SDK — отдельные кредиты).
3. **Митигировать DeepSeek-подорожание и CN-риски**: пересчитать бюджет на deepseek-v4-flash после peak/off-peak (17.08.2026); для privacy-first трафика — приоритет Google/OpenAI-каналам (Gemini Free/промо), локальному Ollama для черновой генерации; для длинных агентских сессий добавить fallback-цепочку OpenRouter→GLM→Zen с авторетраями на 429/500.

**Что нового стоит попробовать**: freellm.net / awesome-freellm-apis (каталог 442+ бесплатных API, обновляется ежедневно — автоконфиги для Claude Code/Codex/Aider); Grok API промо-кредиты (~$175) пока действуют; OpenRouter `/openrouter/free` авто-роутер; Cohere North Mini Code:free (специализирован под OpenCode/SWE-Agent, 256K); Poolside Laguna S 2.1:free (кодинг-агент); мониторинг цен через CostGoat/aipricing.guru; MCP Apps (новое расширение MCP, январь 2026) для UI-интерфейсов агентов.

---

## 7. Источники (URL)

1. OpenRouter: https://openrouter.ai/models , https://openrouter.ai/collections/free-models , https://openrouter.ai/openrouter/free , https://openrouter.ai/docs/faq
2. Списки бесплатных моделей OpenRouter: https://costgoat.com/pricing/openrouter-free-models (обновл. 17.08.2026), https://buldrr.com/openrouter-free-models-list-2026-all-27-models-ranked-tested/ (25.07.2026), https://www.teamday.ai/blog/best-free-ai-models-openrouter-2026 (18.02.2026)
3. Альтернативы OpenRouter: https://ofox.ai/blog/openrouter-alternatives-2026/ , https://llmapi.ai/best-openrouter-alternatives-2026-pick-the-right-ai-gateway-for-real-production-work/ , https://www.getmaxim.ai/articles/best-openrouter-alternative-in-2026-a-production-ai-gateway-comparison/
4. new-api: https://github.com/QuantumNous/new-api ; one-api: https://github.com/songquanpeng/one-api
5. agentrouter.org: https://agentrouter.org , https://agentrouter.org/pricing
6. Китайские фильтры/гейтвеи: https://aichina.news/repositories/PerryLink/Sensitive-Word-Filter-CN/ , https://github.com/langsasec/ai_gateway , https://www.sciencedirect.com/org/science/article/pii/S154622182600161X , https://www.semafor.com/article/07/29/2026/censorship-in-chinese-ai-models-can-be-undone-new-research-shows , https://abit.ee/en/artificial-intelligence/chinese-ai-censorship-deepseek-baidu-ernie-self-censorship-language-models-china-ai-regulation-en
7. OpenCode: https://opencode.ai , https://opencode.ai/docs/ , https://opencode.ai/docs/zen/ , https://opencode.ai/zen , https://www.openaitoolshub.org/en/blog/opencode-review-terminal-ai-coding , https://nerdleveltech.com/opencode-open-source-ai-coding-agent-explained , https://freeainews.com/open-source/opencode-open-source-ai-coding-agent-2026/ ; Zen 500: https://github.com/anomalyco/opencode/issues/35276
8. Claude Code / Anthropic: https://claude.com/product/claude-code , https://claude.com/pricing , https://devtoolpicks.com/blog/anthropic-splits-claude-subscriptions-agent-sdk-credit-june-2026 , https://automationatlas.io/tools/claude-code/
9. Codex CLI: https://codex.danielvaughan.com/2026/04/01/codex-cli-authentication-flows-credential-management/ , https://community.openai.com/t/codex-cli-login-fails-on-windows-auth-openai-com-reachable-via-curl-but-oauth-device-auth-fail/1381736
10. Gemini free tier: https://tinkerllm.com/blog/gemini-api-free-tier-limits-rate-quotas/ , https://www.aifreeapi.com/en/posts/gemini-api-free-tier-complete-guide , https://aipromptshub.co/blog/gemini-api-free-tier-rate-limits
11. GitHub Copilot: https://docs.github.com/copilot/about-github-copilot/plans-for-github-copilot , https://github.com/features/copilot/plans , https://costbench.com/software/ai-coding-assistants/github-copilot/
12. Grok/xAI: https://the-rogue-marketing.github.io/grok-xai-api-pricing-may-2026/ , https://ai-x.chat/guide/grok-usage-limits/ , https://www.ai-toolbox.co/grok-models/grok-pricing-plans-api-2026
13. GLM/Z.ai: https://z.ai/landing-page/coding-plan , https://www.layer3labs.io/guides/z-ai-pricing , https://codingplan.org/en/plans/glm , https://baeseokjae.github.io/posts/z-ai-api-developer-guide-2026/
14. Каталоги бесплатных API: https://github.com/open-free-llm-api/awesome-freellm-apis , https://freellm.net/models/ , https://github.com/nejib1/Free-LLM , https://publicapis.io/blog/free-llm-apis-for-developers-sfdq
15. kluster.ai закрытие: https://kluster.ai
16. DeepSeek price change: https://pandaily.com/deepseek-v4-api-price-increase-august-17-2026-peak-off-peak-aug2026 , https://www.aipricing.guru/news/deepseek-api-price-increase-warning-august-2026/ , https://www.usagepricing.com/blueprint/activity/deepseek-2026-08-14-price-change
17. Бесплатные агенты/станции: https://standardcompute.com/best-ai-agent/for/free , https://agentic.ai/best/free-coding-agents , https://coderfile.io/blog/free-ai-coding-agents-no-api-key-2026 , https://www.nxcode.io/resources/news/best-free-ai-coding-tools-2026 , https://github.com/bradAGI/awesome-cli-coding-agents , https://codersera.com/blog/ai-coding-agents-complete-guide-2026/
18. MCP Apps (новое в MCP-экосистеме 2026): https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/ , https://github.com/modelcontextprotocol/ext-apps