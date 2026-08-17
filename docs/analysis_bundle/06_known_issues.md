# 06. KNOWN ISSUES & FINDINGS — что гейт нашёл, что сделано, что открыто

## Почему L1-L3 (cbm/grit/semgrep/viztracer) НЕ внедрены — честно
1. Док «5 слоёв» (08_five_layers_intent.md) датирован 15.08, статус = ПРЕДЛОЖЕНИЕ, «требует обсуждения с AG2». Наш процесс: архитектурное решение не финально до обсуждения с AG2 — установка без решения не делалась.
2. cbm — закрытый C-бинарь (хоть и MIT): нужна процедура доверия (сверка checksums на живой машине) + проверка Defender false positive (Wacatac.B!ml), и не было решено «cbm вместо CKB / свой supergraph-768D — кого развивать». Это не drop-in, а решение.
3. 16-17.08 приоритеты ушли на другое: dsh-сравнение, agentrouter-интеграция (плагин+прокси+фикс цензуры), фиксы гейта.
4. Инструмент ast-grep уже стоит (npm), остальные (grit, semgrep, viztracer, pyinstrument, cbm) — в списке готовых действий (см. 02_gate_design.md §5). Установка каждого — 15-60 мин; внедрение L1 требует решения по доверию.

Вердикт для аналитика: подтвердить/опровергнуть приоритизацию и дать конкретный план внедрения с критериями приёмки.

## Находки гейта за вечер 17.08 (4 раунда — каждый реальный дефект)
R1: safety_guardrail._parse_expr_to_z3 — Z3 sort-mismatch Bool vs Int (`x != 0` на булевом имени) → ФИКС: promotion через z3.If (проверено 5 выражений)
R2: git_provenance.revert_commit — при неудачном `git revert` делал `git checkout <commit>` → отрыв HEAD (detached) → ФИКС: revert --abort + return False (fail-closed); ensure_branch теперь создаёт отсутствующую ветку
R3: 5 файлов с мёртвыми импортами (vulture): smt_equivalence_prover, agentrouter_proxy, watchdog, self_check_5layers, candidate_harvester → вычищено
R4: critic_jury._build_batch_prompt — per-file cap брал BATCH_TOTAL_BUDGET вместо BATCH_CODE_CAP (4000) — большие файлы могли превышать per-file лимиты промпта → ФИКС
+ R3b: ещё 4 файла (codemod_router, libcst_pruner, supergraph_bridge, whitelist_manager) → вычищено

## Инфраструктурные находки
- Адаптер :5001 крутился на системном Python 3.14 (не venv) → 500; перезапущен под venv
- LLM-жюри падало в 429 (Google free-tier 20 req/день) из-за фолбэка мимо agy → Tier-0 адаптер + сериализация
- agentrouter: HTTP 500 «sensitive words detected» на длинных сессиях (фильтр new-api Aho-Corasick над всей историей) — решения в исследовании gateway_censorship (A: прокси с суммаризацией истории; C: свой new-api/LiteLLM ~€5/мес)
- /model-переключение на плагин-провайдеров ломается (resolve_provider_full не видит plugins-реестр) — обходится дублированием секции providers.<name> в config.yaml (баг Hermes)
- UnicodeDecodeError cp1252 на кириллице в subprocess (Windows) — utf-8/errors=replace в местах спавна

## Открытые вопросы (вынести вердикты)
1. cbm vs CKB vs свой supergraph-768D на слое L1 (решение о доверии к бинарю + дублировании)
2. Grit vs ast-grep как основной движок очистки L3 (оба доступны)
3. Что НЕ сказано в доках, но реально: гейт блокирует коммит при недоступном LLM-критике (fail-closed) — правильная ли политика для ночной/автосборки? (Ответ по умолчанию: да, но нужен CI-режим с явным --allow-llm-off для быстрых итераций)
4. Стоит ли поднять свой new-api/LiteLLM (вариант C) для claude-opus/gpt-5.6 без цензуры
5. Свежесть CKB-индекса и темп обновления (слой L1) — следить за STALE-статусом

## Метрики мониторинга (watchdog расширяемый)
- :5001 и :5012 живы (HTTP 401/404 = alive), integrity обеих БД = ok, ключевые файлы на месте