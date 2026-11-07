# Vazus — Лаборатория Архитектур ИИ и Экспериментов над Весами

> **Статус:** Изолированный исследовательский полигон архитектур ИИ и алгоритмов обучения.  
> **Примечание:** Вся продуктовая обвязка, гипервизор, NPU-маршрутизатор и персональная память (`vazus_core`, `services/memory/vazus.db`, `gemini_bridge`) перенесены в единую платформу **Harnet** (`/home/tarhes/Проекты/harnet`).

---

## 🎯 Структура Лаборатории

1. **[`tars/architectures/`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures)** — Каталог и эталонные реализации современных субквадратичных и гибридных архитектур:
   - [`CATALOG.md`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/CATALOG.md) — систематизация всех архитектур по 6 полочкам с формулами.
   - [`subquadratic_hybrids.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/subquadratic_hybrids.py) — `Mamba3Block` (`SSM-3`), `RWKV7GooseBlock` (`RWKV-7`), `GatedDeltaNetBlock` и `HybridSequenceModel` (`3:1 Hybrid`).
2. **[`tars/brain/`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/brain)** — Специализированные нейросетевые блоки TARS:
   - `mamba2/` (`ssd.py`, `bitnet.py`, `mixture_of_depths.py`, `mole_router.py`, `tars_block.py`)
   - `min_gru/` (`mingru.py`, `mingru_lm.py`)
   - `rrn.py` (Recurrent Reasoning Network), `doubt_engine.py`, `spiking/`, `omega_core/`
3. **[`tars/training/`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/training)** — Эксперименты над весами и конвейеры обучения:
   - [`weight_space_surgeon.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/training/weight_space_surgeon.py) — Автономный Хирург Весового Пространства (`WeightSpaceSurgeon`) и контур рекурсивной самоэволюции (`AutonomousSelfEvolutionEngine`): диагностика петель рассуждений (`<think>` loops), каузальная локализация столбцов MLP `down_proj`, SVD rank-1 абляция пространства аттрактора за миллисекунды без градиентного спуска (0.016% параметров, прирост до 6x) и гейт Proof-of-Improvement (PoI).
   - [`weight_space_programming.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/training/weight_space_programming.py) — Репликация открытий MIT CSAIL & OpenAI Astra (слепое чтение геометрии задач из весов, компиляция алгоритмов и динамических систем в веса с 0 шагов градиентного спуска, хирургия петель Qwen3.5-0.8B).
   - `night_cycle.py` — Интеграция фазы весовой хирургии в ночной цикл автономного самосовершенствования модели во время простоя.
   - `muon.py`, `lora.py`, `dpo.py`, `umot_loss.py`, `train/` (`train_mamba2.py`, `train_rlvr.py`, `train_dpo.py`, `train_kto.py`, `train_cot.py`).
