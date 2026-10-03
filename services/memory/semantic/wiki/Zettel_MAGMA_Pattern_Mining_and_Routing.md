---
id: Zettel_MAGMA_Pattern_Mining_and_Routing
title: Multi-Agent Graph Memory Architecture (MAGMA), Structural Pattern Mining, and Dynamic Tool Routing
domain: agent_architecture
status: VERIFIED
created_at: 2026-08-18T19:35:00
tags:
  - magma
  - hebbian_learning
  - pattern_mining
  - code_health
  - dynamic_tool_routing
  - sota_2026
---

# Multi-Agent Graph Memory Architecture (MAGMA), Pattern Mining, and Dynamic Tool Routing

## 1. MAGMA 4-Graph Memory Engine

Архитектура памяти **MAGMA** разделяет граф знаний на 4 ортогональных типа связей в таблице `kg_edges` базы `vazus.db`:

1. **`entity`**: Синтаксические зависимости AST (структуры Go, классы Python, методы, сигнатуры).
2. **`causal`**: Причинно-следственные связи архитектурных решений (ADR) и обоснований («Почему выбран SQLite WAL вместо PostgreSQL?»).
3. **`temporal`**: Хронологическая последовательность мутаций кода и версий («Когда был добавлен кольцевой буфер?»).
4. **`semantic`**: 768-мерная косинусная близость векторов эмбеддингов (Google Gemini Embedding 2 / Gemma 300M).

### Хеббовское усиление связей (Hebbian Co-Retrieval)
При совместном извлечении двух узлов в рамках одной задачи вес ребра между ними динамически усиливается:
$$w_{new} = \min\left(1.0, w_{old} + \eta \cdot (1.0 - w_{old})\right)$$
где $\eta = 0.05$ — скорость обучения (learning rate).

### Экспоненциальное затухание (Exponential Decay)
Устаревшие и неиспользуемые связи ослабевают с течением времени согласно периоду полураспада $t_{half} = 30$ дней:
$$w(t) = w_0 \cdot \exp\left(-\frac{\ln 2}{t_{half}} \cdot \Delta t\right)$$
Ребра с весом $w(t) < 0.05$ автоматически удаляются из базы данных.

---

## 2. Structural Pattern Miner & Code Health Engine

Модуль [`pattern_miner.py`](file:///C:/vazus/vazus_core/analysis/pattern_miner.py) реализует статический анализ исходного кода на базе `tree-sitter-go` и `ast` (Python) для обнаружения:

### Выявляемые паттерны:
* **Go**: Concurrency Worker Pool, Circular Ring Buffer, Mutex-Guarded State, Context-Bound Lifetime.
* **Python**: ContextManager (RAII), AsyncGenerator Stream, Visitor Pattern.

### Формула Code Health Score ($H \in [0.0, 10.0]$):
$$H = 10.0 - 1.5 \cdot N_{CC > 10} - 1.0 \cdot N_{depth > 3} - 0.5 \cdot N_{params > 4} - 1.0 \cdot N_{lines > 50}$$

Критерий **AI-Ready Code**: $H \ge 9.5$. При $H < 9.5$ система автоматически формирует рекомендации по рефакторингу (`Extract Method`).

---

## 3. Dynamic Semantic Tool Router

Модуль [`dynamic_tool_router.py`](file:///C:/vazus/vazus_core/routing/dynamic_tool_router.py) устраняет проблему «MCP Token Bloat»:
* **Progressive Schema Disclosure**: Вместо загрузки 50+ JSON-схем в системный промпт (съедающих 40–50% контекста), в контекст передается только роутер. По запросу пользователя подбираются $\le 3$ наиболее релевантных инструмента на основе 768-D векторов.
* **Server-Side JSON Projection**: Серверная фильтрация отсекает сырые байты, вложенные эмбеддинги и обрезает списки логов, экономя до $85\%$ токенов ответа.

---

## Связанные заметки:
* [[Zettel_AST_ast_pruner]]
* [[Zettel_Mission_Aegis_Omni_Distributed_Health_Reactor]]
* [[Zettel_SMT_Z3_Formal_Verification]]
* [[Zettel_Async_Worktree_Sandbox]]
