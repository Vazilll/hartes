# 05. LIVE PROBE — свежий срез окружения (17.08.2026 ~20:50, до запуска аналитика)

## Процессы и порты
- 127.0.0.1:5001 — agy OpenAI-адаптер (venv, перезапущен 17.08 после того, как старый крутился на системном Python 3.14 и отдавал 500)
- 127.0.0.1:5012 — agentrouter_proxy (фильтр-прокси: UA-инъекция + strip data:null)
- 127.0.0.1:9222 — Chrome remote-debugging (harness browser-exec)
- 127.0.0.1:11434 — Ollama (легаси)
- agy-процесс активен (обслуживает LLM-вызовы гейта)

## Git
- HEAD: 7253a8d (рабочее дерево с фиксами gated, но НЕ закоммичено — финальный гейт-раунд в фоне)
- Staged WIP: dual_jury, critic_jury, evidence_jury, precommit_gate (изменения), тесты (4 файла), scripts (proxdy, watchdog, research bridge), доки исследовани
- Правило: коммит только после precommit_gate (6-tier) — гейт 4 раза отклонил, каждый раз находя реальные дефекты

## Hermes
- Провайдер: opencode-go / deepseek-v4-flash (повседневка); agentrouter (claude-opus-4-8/5, gpt-5.6-sol) через плагин+config+прокси :5012
- MCP: 5 серверов включено (vazus-organic 15, ckb 27, sequential-thinking 1, playwright-mcp 24, colab-mcp 1) — 68+ инструментов + 42 deferred
- Cron: vazus-health-watchdog (09:00, silent-when-ok; проверяет :5001/:5012, ключевые файлы, integrity обеих БД)

## LLM-инфраструктура Vazus (после фиксов 17.08)
- llm_client Tier-0: HTTP-адаптер :5001 (маппинг через _resolve_agy_model_name) с threading-локом сериализации
- Tier-1: прямой agy CLI (IDE-квоты); Tier-2: Antigravity SDK; Tier-3: cloud REST (только VAZUS_LLM_ALLOW_CLOUD=1) → mock (test)
- Проблема решена: конкурирующие вызовы критика больше НЕ падают в 429 free-tier Gemini (проверено: 2 параллельных вызова → оба OK)

## Ключевые env-параметры гейта
VAZUS_GATE_STRICT_SMT, VAZUS_GATE_STRICT_JURY, VAZUS_GATE_DEEP_SCAN, VAZUS_GATE_STRICT_DEEP, VAZUS_GATE_TEST_TIMEOUT (300), VAZUS_GATE_MAX_TARGET_TESTS (8), VAZUS_LLM_ADAPTER_URL, VAZUS_LLM_SKIP_ADAPTER, VAZUS_LLM_MAX_TOKENS (4096) — см. 02_gate_design.md

## Разное
- Research bridge: ddg (google 429 — ключ без биллинга), модели gemini-3.7-flash через :5001
- Watchdog vazus_health_watchdog.py: обе БД integrity OK; адаптер и прокси живы