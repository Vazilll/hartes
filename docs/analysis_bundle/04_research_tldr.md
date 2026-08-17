# 04. RESEARCH TL;DR — выводы 5 интернет-исследований (17.08.2026)
Полные отчёты с URL: ../research/*.md

## Контекст-компрессия (context_compression_2026.md)
- Компакция — первый рычаг (авто-суммаризация при ~80% окна, структурированный формат сводки)
- Context rot: модель хуже использует длинный контекст → короткий контекст важнее вместимости
- Файлы-память (NOTES/PROGRESS/STATE) почти бесплатны и переживают сессии
- Субагенты изолируют грязный контекст (резюме 1-2k токенов в главный чат)
- Context eviction старых tool-выводов освобождает 30-60% окна
- mem0/Letta/Zep — память МЕЖДУ сессиями; для роутера: держать сессии короткими

## Провайдеры/роутеры (model_providers_2026.md)
- OpenRouter — стандарт (5.5% комиссия); kluster.ai закрылся; топ-бюджет: GLM-5.2:free, Nemotron 3 Ultra :free
- 2026: разделение подписок (Anthropic вынесла Agent SDK); DeepSeek V4 подорожал (peak/off-peak с 17.08)
- agentrouter подтверждён как new-api-гейтвей; варианты для Vaz: укрепить бесплатный стек (agy+opencode-go), GLM Coding Plan ~$18/мес как платный канал

## Память и KG (agent_memory_2026.md)
- Тренд «меньше графа»: mem0 убрала graph-модуль (PR #4805), файлы-инструкции победили
- mem0 Dream (авг 2026): фоновая консолидация памяти (дедуп, superseded, summary) — топ-идея
- Bi-temporal факты (valid_at/invalid_at) — правильное направление Vazus (memory_facts_v2 ✓)
- sqlite-vec оптимален локально; Microsoft GraphRAG — maintenance mode → LazyGraphRAG
- Vazus OS соответствует 2026; пробелы: консолидация, инвалидация, entity-linking, свежесть CKB

## MCP (mcp_ecosystem_2026.md)
- MCP — стандарт: 97M установок/мес, 10K серверов, Linux Foundation (AAIF); спека 2026-07-28 (stateless, OAuth)
- Стартовый набор: Context7, Playwright, GitHub, Brave/Tavily, Sequential Thinking
- Безопасность: 14 CVE/30+ RCE, ~200K уязвимых серверов — фикс. версии, env-фильтр, sampling off, allowlist
- У Vaz уже есть: vazus-organic (память) + ckb (код) — не дублировать memory-серверами

## Цензура гейтвеев (gateway_censorship_2026.md)
- 500 «sensitive words» = new-api Aho-Corasick-фильтр над ВСЕЙ историей запроса — детерминированно
- Шифрование/обфускация не работают; на СВОЁМ инстансе фильтр отключается (пустой список слов)
- Варианты: A) клиентский прокси с суммаризацией истории (быстро); B) прямые API (без цензуры, от $0.08/M);
  C) self-hosted new-api/LiteLLM на VPS (~€5/мес) + OpenRouter/Anthropic — ОСНОВНОЕ для длинных сессий
