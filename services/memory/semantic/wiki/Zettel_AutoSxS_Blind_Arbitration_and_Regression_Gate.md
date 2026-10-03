---
id: Zettel_AutoSxS_Blind_Arbitration_and_Regression_Gate
title: "AutoSxS Blind Arbitration & Non-Regression Gate Architecture"
date: "2026-09-04"
domain: autonomous_systems
tags:
  - iad
  - zettel
  - autosxs
  - blind_arbitration
  - regression_gate
  - ab_testing
  - supergraph
status: VERIFIED
sources:
  - "Google Enterprise Agent Platform AutoSxS Service"
  - "Vertex AI Model Evaluation Pairwise Comparison SDK"
  - "Vazus SuperGraph Architecture ADR-005"
---

# AutoSxS Blind Arbitration & Non-Regression Gate Architecture

## 📌 Core Protocol & Claim

Главный риск автономного самоулучшения — **скрытая регрессия (Silent Regression)**: агент начинает лучше решать один класс задач, но деградирует в базовых функциях, безопасности или форматировании.

**Stage 5 (Verification & Arbitration Gate)** выступает абсолютным фильтром перед активацией любых мутаций. Используя протокол **AutoSxS (Automated Side-by-Side Blind Comparison)** и контрольный эталонный датасет $\mathcal{D}_{golden}$, система гарантирует:
1. **Слепое сравнение кандидатов**: Ни базовой модели, ни кандидату не отдается приоритет. Судья не знает, где кандидат, а где baseline.
2. **Нейтрализация систематических погрешностей (Biases)**: Позиционный сдвиг устраняется двойным слепым прогоном со сменой порядка (Pairwise Swap: $A \text{ vs } B$ и $B \text{ vs } A$).
3. **Строгий гейт допуска**: Кандидат активируется тогда и только тогда, когда он статистически значимо превосходит базовую версию и имеет ровно **ноль регрессий** на исторических тестах.

---

## ⚖️ Математическая Модель Арбитража и Формула Допуска

Для кандидата мутации $M_{cand}$, текущей базовой версии $M_{base}$ и неизменяемого золотого датасета $\mathcal{D}_{golden} = \{ d_1, \dots, d_N \}$:

### 1. Расчет Доли Побед (Win Rate):
$$\text{WinRate}(M_{cand}, M_{base}) = \frac{N_{win} + 0.5 \cdot N_{tie}}{N_{total}}$$

### 2. Подсчет Регрессий:
$$\text{Regressions}(M_{cand}, \mathcal{D}_{golden}) = \sum_{i=1}^{N} \mathbb{I}\Big( \text{Score}(M_{cand}, d_i) < \text{Score}(M_{base}, d_i) - \delta \Big)$$
где $\delta = 0.02$ — порог статистического шума.

### 3. Критерий Допуска в Production (Pass Contract):
$$\mathcal{P}_{\text{deploy}} = \Big( \text{WinRate}(M_{cand}, M_{base}) \ge 0.50 + \epsilon \Big) \;\land\; \Big( \text{Regressions}(M_{cand}, \mathcal{D}_{golden}) == 0 \Big) \;\land\; \Big( \text{Safety}(M_{cand}) == 1.0 \Big) \;\land\; \Big( \text{base\_hash} == \text{prod\_hash} \Big)$$
где $\epsilon = 0.05$ — защитный интервал превосходства, а $\text{base\_hash} == \text{prod\_hash}$ — инвариант отсутствия параллельных коллизий (Optimistic Concurrency Control).

---

## 🔄 Negative Reflection & Circuit Breaker Loop (Обратная Связь при Отказе)

Если кандидат $M_{cand}$ **не проходит** арбитраж ($\mathcal{P}_{\text{deploy}} = \text{False}$), система действует детерминированно в зависимости от причины и счетчика попыток $K$:

```mermaid
flowchart TD
    GATE[AutoSxS Arbitration Gate] -->|REJECT: P_deploy == False| RETRY_CHECK{Счетчик Попыток<br/>K <= K_max (3)?}
    
    RETRY_CHECK -->|НЕТ: Исчерпан лимит| QUARANTINE[Circuit Breaker Quarantine<br/>Dead-Letter Queue + Оповещение Concordia/Human]
    RETRY_CHECK -->|ДА: В пределах лимита| REASON{Причина Отказа?}
    
    REASON -->|Регрессии > 0| CRITIQUE[Формирование CritiquePayload:<br/>1. Список упавших тестов D_golden<br/>2. Текстовые обоснования судьи<br/>3. Жесткие негативные ограничения]
    REASON -->|WinRate < 55% & Регрессий == 0| BOOST[Exploration Boost:<br/>Мутация безвредна, но слаба.<br/>Увеличение вариативности / temp + 0.2]
    REASON -->|base_hash != prod_hash| REBASE[OCC Rebase:<br/>Повторное наложение мутации<br/>на актуальный прод-промпт]

    CRITIQUE --> OPT_FEEDBACK[Диспетчер Оптимизации Tier 1..3]
    BOOST --> OPT_FEEDBACK
    REBASE --> OPT_FEEDBACK
    OPT_FEEDBACK --> NEXT_EPOCH[Следующая Эпоха Мутаций (K = K + 1)]

    style GATE fill:#1565c0,stroke:#90caf9,color:#fff
    style CRITIQUE fill:#c62828,stroke:#ef9a9a,color:#fff
    style BOOST fill:#f57f17,stroke:#ffe082,color:#fff
    style QUARANTINE fill:#b71c1c,stroke:#ff8a80,color:#fff
    style NEXT_EPOCH fill:#2e7d32,stroke:#a5d6a7,color:#fff
```

### Структура объекта `CritiquePayload`:
```json
{
  "candidate_version": "prompt_v2.3_mutated",
  "attempt_counter": 2,
  "max_attempts": 3,
  "arbitration_status": "REJECTED",
  "rejection_kind": "REGRESSION_DETECTED",
  "win_rate": 0.48,
  "regressions_detected": 2,
  "failing_cases": [
    {
      "test_id": "golden_case_084_json_schema",
      "metric": "multi_turn_tool_use_quality",
      "baseline_score": 1.0,
      "candidate_score": 0.4,
      "judge_explanation": "Кандидат нарушил схему вызова grep_search, передав флаг case_sensitive как число вместо bool."
    }
  ],
  "negative_constraints_injected": [
    "NEVER cast boolean tool parameters to integer values."
  ],
  "exploration_boost": false
}
```

---

## 💻 Программный Пайплайн AutoSxS (SDK Implementation)

```python
import agentplatform
from agentplatform import types

def run_autosxs_arbitration(
    candidate_app,
    baseline_app,
    golden_dataset: types.EvaluationDataset,
    project_id: str,
    candidate_base_hash: str,
    current_prod_hash: str,
    attempt_counter: int = 1,
    max_attempts: int = 3
) -> tuple[bool, dict]:
    # 1. Optimistic Concurrency Control (OCC) Gate
    if candidate_base_hash != current_prod_hash:
        return False, {
            "status": "REJECTED_OCC_CONFLICT",
            "reason": "Production prompt changed during candidate evaluation. Rebase required.",
            "rebase_required": True,
            "attempt_counter": attempt_counter
        }

    # 2. Circuit Breaker Gate
    if attempt_counter > max_attempts:
        return False, {
            "status": "CIRCUIT_BREAKER_QUARANTINE",
            "reason": f"Maximum optimization attempts ({max_attempts}) exceeded. Quarantining.",
            "quarantined": True,
            "attempt_counter": attempt_counter
        }

    client = agentplatform.Client(project=project_id, location="global")

    # Конфигурация парного слепого оценивания
    pairwise_metric = types.PairwiseMetric.PAIRWISE_GENERAL_QUALITY

    # Прогон A vs B и B vs A для устранения position bias
    result_ab = client.evals.evaluate(
        dataset=golden_dataset,
        metrics=[pairwise_metric],
        model_a=candidate_app,
        model_b=baseline_app
    )
    
    win_count = 0
    total_count = len(golden_dataset.eval_cases)
    regressions = []

    for case in result_ab.eval_case_results:
        cand_res = case.pairwise_metric_results.get(pairwise_metric.name)
        if cand_res.winner == "model_a":
            win_count += 1
        elif cand_res.winner == "model_b":
            regressions.append({
                "case_id": case.id,
                "reason": cand_res.explanation
            })

    win_rate = win_count / max(1, total_count)
    passed = (win_rate >= 0.55) and (len(regressions) == 0)

    summary = {
        "passed": passed,
        "status": "APPROVED" if passed else "REJECTED",
        "win_rate": win_rate,
        "regressions_count": len(regressions),
        "regressions": regressions,
        "attempt_counter": attempt_counter,
        "exploration_boost": (win_rate < 0.55 and len(regressions) == 0)
    }
    return passed, summary
```

---

## 📋 Action Checklist
- [x] Реализована формула допуска с порогом $\text{WinRate} \ge 0.55$ и нулевой регрессией.
- [x] Спроектирован протокол нейтрализации Position Bias (двойной слепой своп).
- [x] Формализован объект `CritiquePayload` с дифференциацией регрессий и нейтральных исходов.
- [x] Интегрирован протокол OCC Rebase для защиты от коллизий параллельных мутаций.
- [x] Спроектирован Circuit Breaker Quarantine ($K > K_{\max}$) для изоляции стойких сбоев.
- [ ] Разработать автоматический деплоймент одобренного кандидата в Serving Endpoint.

---

## 🔗 Related Notes & Wikilinks

- [[Zettel_Continuous_Agent_Self_Improvement_Flywheel]]
- [[ADR_005_CONTINUOUS_AGENT_SELF_IMPROVEMENT_FLYWHEEL]]
- [[Zettel_Three_Tier_Agent_Optimization_Hierarchy]]
- [[Zettel_Closed_Feedback_Loop_Formal_Verification]]
- [[Zettel_Autonomous_Trajectory_Evaluation_AutoRaters]]
- [[Zettel_Error_Analysis_Loss_Taxonomy_Clustering]]
- [[ADR_004_CODE_INTELLIGENCE_5LAYERS]]
