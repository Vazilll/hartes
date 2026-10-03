---
id: Zettel_Parametric_Fine_Tuning_LoRA_SFT_DPO
title: "Parametric Fine-Tuning Architecture: LoRA, SFT & DPO"
date: "2026-09-04"
domain: autonomous_systems
tags:
  - iad
  - zettel
  - fine_tuning
  - lora
  - sft
  - dpo
  - peft
  - vertex_ai
  - supergraph
status: VERIFIED
sources:
  - "Google Enterprise Agent Platform Model Tuning SDK"
  - "Vertex AI GenAI Tuning API"
  - "Vazus SuperGraph Architecture ADR-005"
---

# Parametric Fine-Tuning Architecture: LoRA, SFT & DPO

## 📌 Core Protocol & Claim

Когда возможности In-Context адаптации (Tier 1) и промпт-инжиниринга (Tier 2) исчерпаны (метрика не растет, промпт перегружен, или требуется специфический DSL-синтаксис), система прибегает к **Tier 3 (Cold-Path Parametric Adaptation)**.

Параметрическая оптимизация модифицирует веса модели или обучает компактные PEFT-адаптеры (Low-Rank Adaptation, LoRA):
1. **Supervised Fine-Tuning (SFT)**: Обучение базовой модели на валидированных золотых мультитурных траекториях (`node_type='GoldenTrajectory'`), вырабатывающее идеальное следование формату и вызовам инструментов.
2. **Direct Preference Optimization (DPO)**: Прямая оптимизация предпочтений на парах $\langle \text{Prompt}, \text{Chosen Trajectory}, \text{Rejected Trajectory} \rangle$, минимизирующая вероятность повторения системных ошибок без отдельной reward-модели.

---

## 🛠️ Архитектура Пайплайна Дообучения (Tuning Pipeline)

```mermaid
graph TD
    DB[(SuperGraph vazus.db / BigQuery)] --> EXTRACT[Экстрактор Трейсов]
    EXTRACT --> FILTER{Фильтр Качества<br/>Score >= 0.95?}
    
    FILTER -->|Golden Traces| SFT_SET[SFT Датасет JSONL<br/>Мультитурные диалоги]
    FILTER -->|Chosen / Rejected Pairs| DPO_SET[DPO Датасет JSONL<br/>Контрастные пары]

    SFT_SET --> TUNE_JOB[Agent Platform Tuning Job<br/>client.tuning.tune]
    DPO_SET --> TUNE_JOB

    TUNE_JOB --> ARTIFACT[Обученный LoRA Адаптер / Checkpoint]
    ARTIFACT --> REGISTRY[Agent Platform Model Registry]
    REGISTRY --> DEPLOY[Выделенный Эндпоинт (BYOM / Vertex Endpoint)]
    DEPLOY --> AUTOSXS[[Zettel_AutoSxS_Blind_Arbitration_and_Regression_Gate]]
```

---

## 💻 Программный Пайплайн Запуска Обучения (SDK Snippet)

```python
import agentplatform
from agentplatform import types

def launch_parametric_tuning_job(
    project_id: str,
    location: str,
    training_dataset_uri: str,
    base_model: str = "gemini-2.5-flash"
) -> str:
    """Запускает задачу дообучения LoRA адаптера на Google Cloud Vertex AI / Agent Platform."""
    client = agentplatform.Client(project=project_id, location=location)

    # Конфигурация задачи PEFT/LoRA дообучения
    tuning_job = client.tuning.tune(
        base_model=base_model,
        training_dataset=training_dataset_uri,
        tuning_spec=types.TuningSpec(
            hyperparameters=types.SupervisedHyperparameters(
                epoch_count=4,
                learning_rate_multiplier=1.0,
                adapter_size=types.AdapterSize.ADAPTER_SIZE_16  # LoRA Rank r=16
            )
        )
    )
    
    print(f"Tuning job launched successfully: {tuning_job.name}")
    return tuning_job.name
```

---

## 🛡️ Безопасность Весов, Canary Rollouts и Экономика Квот

1. **Экономическая изоляция (Quota Guard)**: Tier 3 активируется ТОЛЬКО по явному подтверждению или при накоплении $\ge 50$ однотипных L1-инцидентов, которые не удалось устранить через Tier 2 за 3 последовательных эпохи.
2. **Canary Deployment**: Новый эндпоинт не переключает 100% трафика сразу. После победы в `AutoSxS` активируется схема постепенного наращивания: $5\% \to 25\% \to 100\%$ с непрерывным мониторингом частоты ошибок в Cloud Logging.
3. **Instant Rollback**: В случае всплеска ошибок на рантайм-телеметрии трафик мгновенно перенаправляется на предыдущую стабильную версию модели за < 500 мс через DNS-роутер Serving Gateway.
4. **Circuit Breaker Quarantine**: Если обученный LoRA-кандидат не проходит гейт `AutoSxS` после $K_{\max} = 3$ последовательных эпох, обучение немедленно блокируется, а кейс помещается в `Quarantine_DeadLetter_Queue` с алертом для Concordia Multi-Agent Jury и инженера.

---

## 📋 Action Checklist
- [x] Определен пайплайн подготовки данных для SFT и DPO форматов.
- [x] Спроектирован интерфейс запуска задач через `client.tuning.tune()`.
- [x] Сформулирован протокол аварийной блокировки при неудачном дообучении (Circuit Breaker Quarantine).
- [ ] Настроить автоматический экспорт валидированных трейсов из `vazus.db` в GCS бакет `gs://vazus-tuning-datasets/`.
- [ ] Разработать canary-контроллер для плавного переключения весов.

---

## 🔗 Related Notes & Wikilinks

- [[Zettel_Continuous_Agent_Self_Improvement_Flywheel]]
- [[ADR_005_CONTINUOUS_AGENT_SELF_IMPROVEMENT_FLYWHEEL]]
- [[Zettel_Three_Tier_Agent_Optimization_Hierarchy]]
- [[Zettel_Dynamic_Few_Shot_In_Context_Learning]]
- [[Zettel_Automated_Prompt_Tuning_and_DSPy_Evolution]]
- [[Zettel_AutoSxS_Blind_Arbitration_and_Regression_Gate]]
- [[Zettel_Closed_Feedback_Loop_Formal_Verification]]
- [[ADR_004_CODE_INTELLIGENCE_5LAYERS]]
