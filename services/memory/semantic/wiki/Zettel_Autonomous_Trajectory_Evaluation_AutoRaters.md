---
id: Zettel_Autonomous_Trajectory_Evaluation_AutoRaters
title: "Autonomous Trajectory Evaluation & AutoRaters Architecture"
date: "2026-09-04"
domain: autonomous_systems
tags:
  - iad
  - zettel
  - evaluation
  - autoraters
  - llm_as_judge
  - rubrics
  - agent_quality
status: VERIFIED
sources:
  - "Google Enterprise Agent Platform Metric Registry"
  - "Google GenAI Evaluation SDK client.evals.evaluate"
  - "Vazus SuperGraph OS ADR-005"
---

# Autonomous Trajectory Evaluation & AutoRaters Architecture

## 📌 Core Protocol & Claim

Традиционное модульное тестирование неприменимо к мультитурным агентским системам: стохастичность генерации, нетривиальные пути достижения цели и вариативность аргументов инструментов требуют **гибридной системы автоматической оценки качества траекторий (AutoRaters)**.

В архитектуре Vazus SuperGraph OS и Google Enterprise Agent Platform оценка траекторий объединяет:
1. **Адаптивные мультитурные рубрики** (Server-side AutoRaters), оценивающие глобальную логику и взаимодействие с инструментами.
2. **Статические инварианты** (Grounding, Hallucination, Safety), гарантирующие строгое соответствие контексту и политикам безопасности.
3. **Песочные детерминированные чекеры** (`CodeExecutionMetric`), проверяющие синтаксис, Z3-инварианты и компилируемость артефактов.

---

## 📊 Матрица Метрик Оценки Агентов

| Метрика | Тип Рубрики | Объект Измерения | Критерий Успеха |
|---|---|---|---|
| **`multi_turn_task_success`** | Адаптивная (AutoRater) | Достиг ли агент исходной цели пользователя за всю сессию | $\text{Score} \ge 0.80$ |
| **`multi_turn_trajectory_quality`** | Адаптивная (AutoRater) | Логичность шагов, отсутствие цикличности и избыточных действий | $\text{Score} \ge 0.75$ |
| **`multi_turn_tool_use_quality`** | Адаптивная (AutoRater) | Корректность выбора API, валидность параметров, реакция на ошибки | $\text{Score} \ge 0.85$ |
| **`multi_turn_general_quality`** | Адаптивная (AutoRater) | Общая связность, профессиональный тон и форматирование | $\text{Score} \ge 0.80$ |
| **`grounding`** | Статическая | Отсутствие утверждений, противоречащих предоставленному контексту | $\text{Score} = 1.00$ |
| **`hallucination`** | Статическая | Фактическая проверка выходов инструментов против итогового ответа | $\text{Score} = 1.00$ |
| **`safety`** | Статическая | Соответствие политикам безопасности и предотвращения jailbreak | $\text{Score} = 1.00$ |
| **`final_response_match`** | Сравнительная | Совпадение финального ответа с золотым эталоном (при наличии) | $\text{Score} \ge 0.90$ |

---

## 💻 Программный Пайплайн Оценивания (SDK Snippet)

```python
import agentplatform
from agentplatform import types

def run_trajectory_evaluation(dataset: types.EvaluationDataset, project_id: str, location: str = "global"):
    client = agentplatform.Client(project=project_id, location=location)

    # Набор обязательных метрик для агентского цикла
    metrics = [
        types.RubricMetric.MULTI_TURN_TASK_SUCCESS,
        types.RubricMetric.MULTI_TURN_TRAJECTORY_QUALITY,
        types.RubricMetric.MULTI_TURN_TOOL_USE_QUALITY,
        types.RubricMetric.GROUNDING,
        types.RubricMetric.HALLUCINATION,
        types.RubricMetric.SAFETY,
    ]

    # Запуск авто-оценивания
    eval_result = client.evals.evaluate(
        dataset=dataset,
        metrics=metrics
    )

    # Извлечение результатов и рубричных обоснований (explanations)
    failures = []
    for case in eval_result.eval_case_results:
        for cand in case.response_candidate_results:
            for metric_name, res in cand.metric_results.items():
                if res.score < 0.7:  # Порог отбраковки
                    failures.append({
                        "case_id": getattr(case, "id", "unknown"),
                        "metric": metric_name,
                        "score": res.score,
                        "verdict_explanation": res.explanation
                    })

    return eval_result, failures
```

---

## 🛡️ Контракты Fail-Closed и Детерминизм Оценки

1. **Защита от сглаживания (Strict Thresholding)**: Оценка не усредняется по принципу «в среднем нормально». Если нарушен критический статический инвариант (`safety` или `grounding`), общий вердикт сессии принудительно переводится в `FAIL`, даже при высоком `task_success`.
2. **Нулевая толерантность к галлюцинациям**: Вердикт AutoRater содержит текстовое обоснование (`explanation`), выделяющее конкретный фрагмент трейса, в котором агент совершил недопустимый шаг.
3. **Бесшовный переход в Стадию 3**: Все кейсы с оценками ниже пороговых значений без потерь передаются в сервис кластеризации потерь (`generate_loss_clusters`).

---

## 📋 Action Checklist
- [x] Определен базовый пул метрик для мультитурных сессий (Task Success, Trajectory, Tool Use).
- [x] Реализована строгая фиксация вердиктов рубрик и текстовых объяснений сбоя.
- [ ] Настроить сохранение полных JSON-отчетов и HTML-дашбордов в `artifacts/grade_results/`.
- [ ] Интегрировать авто-эскалацию критических нарушений безопасности в Concordia Jury.

---

## 🔗 Related Notes & Wikilinks

- [[Zettel_Continuous_Agent_Self_Improvement_Flywheel]]
- [[ADR_005_CONTINUOUS_AGENT_SELF_IMPROVEMENT_FLYWHEEL]]
- [[Zettel_Multi_Turn_Session_Event_Tracing]]
- [[Zettel_Error_Analysis_Loss_Taxonomy_Clustering]]
- [[Zettel_Three_Tier_Agent_Optimization_Hierarchy]]
- [[Zettel_AutoSxS_Blind_Arbitration_and_Regression_Gate]]
- [[Zettel_Closed_Feedback_Loop_Formal_Verification]]
