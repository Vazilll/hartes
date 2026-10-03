# Ответ на вопрос Local-First пакета — решение архитектора (Hermes)

> Отправь это в Antigravity как финальное решение по вопросу.

## Решение

Ни один из трёх вариантов не принимаем буквально. Принимаем урезанный пакет «Tier-1 только»:

1. **Главный LLM-мозг харнеса = Antigravity SDK** (google-antigravity v0.1.10, уже установлен, образец рабочего клиента — rlm/clients/antigravity.py). Сессионная квота IDE, без внешних платных ключей.
2. **Vision и Jules закрываем под opt-in гейты (0 по умолчанию)** — VAZUS_VISION_ALLOW_CLOUD=1 и VAZUS_JULES_LIVE=1. Локальные фолбэки остаются (pix2text для vision; для Jules гвард под pytest уже сделан, проверь).
3. **.gitignore**: добавить .adapter_key (файл сейчас не существует, но subagent_rlm_bridge его читает — если появится с ключом, утечёт).
4. **Система дебатов** внедряем по файловому протоколу: .agents/debates/ + DEBATE_INDEX.md + теги [AGY]/[Hermes], память через существующий TARS-хук в vazus.db + wiki.
5. **Локальные модели (Ollama / llama.cpp, Tier 0) — ОТЛОЖЕНЫ.** Не ставить ollama, не собирать llama.cpp, не тянуть .gguf. Вернёмся к Tier 0 только после того, как Tier 1 докажет себя в бою: с работающим мозгом Tier 0 потом сделаем лучше и быстрее.

## Задачи (с критериями приёмки, без «сухих SUCCESS»)

### A. llm_client: Tier-1 цепочка
Файл vazus_core/engine/llm_client.py, функция async_generate_llm. Порядок бэкендов:
1. Antigravity SDK (Agent / LocalAgentConfig, по образцу AntigravityClient.acompletion) — основной путь.
2. Gemini REST — ТОЛЬКО при явном VAZUS_LLM_ALLOW_CLOUD=1.
3. Детерминированный мок с пометкой MOCK в ответе (когда нет ни SDK-сессии, ни opt-in).
Приёмка: живой вызов SDK с реальным ответом (текст ответа + latency в отчёте). Мок не выдавать за живой ответ.

### B. Concordia Jury через Tier-1
Jury (concordia_jury.py) голосует через async_generate_llm → после A голоса автоматически станут реальными SDK-вызовами. Приёмка: один живой прогон vote_async с тремя реальными голосами и честным ratio (не мок-PASS).

### C. Сабагент rlm_code_engineer на SDK
scripts/subagent_rlm_bridge.py: дефолт backend="antigravity" (не "openai"+адаптер 127.0.0.1:5001). Адаптер оставить как опциональный фолбэк. Приёмка: один реальный (не dry_run) прогон маленькой задачи через RLM-цикл на SDK-квоте.

### D. Opt-in гейты
- google_multimodal_vision: VAZUS_VISION_ALLOW_CLOUD=1 включает genai-путь, иначе только локальный pix2text.
- Jules: гвард уже есть (PYTEST_CURRENT_TEST / VAZUS_JULES_OFFLINE / VAZUS_JULES_LIVE) — проверить, что прод не ходит в облако без явного VAZUS_JULES_LIVE=1.
Приёмка: тест, что облачные пути не вызываются без флагов.

### E. .gitignore
Добавить .adapter_key и любые будущие файлы токенов (паттерн .key / .token на уровне корня, точечно, не широко).

### F. Дебаты
Создать .agents/debates/: шаблон раунда (AGY/THESIS → HERMES/REBUTTAL → JOINT/SYNTHESIS, frontmatter tags [AGY, Hermes], status open/resolved), DEBATE_INDEX.md (тема | статус | последний раунд | ссылка). TARS-хук: парсить теги [AGY]/[Hermes] при коммите раунда в vazus.db/wiki. Раунд ≤ 150 строк.

### G. Приёмка пакета целиком
- Полный pytest: 703/703, 0 падений.
- 6 гейтов пре-коммита на всех изменённых файлах.
- Каждый пункт A–F закоммичен отдельным коммитом с описанием.
- Отчёт: таблица пункт | что сделано | как проверено (команда/вывод) | коммит | числа.

## Запрещено
- Ставить ollama / собирать llama.cpp / качать модели.
- Трогать архив ~/.gemini/antigravity-cli (6.1GB) — решение по нему после живого доказательства Tier-1.
- Выдавать dry_run / mock за реальный результат.
- Коммитить wiki-файлы (их генерит хук сам).

## Примечание
Полный Local-First (Tier 0 на llama.cpp 3-4B под Meteor Lake) — это ПЛАН НА ПОТОМ, осознанно отложенный. Сейчас приоритет — доказать, что SDK-квота работает как основной мозг; тогда локальный тир соберём на готовом фундаменте.
