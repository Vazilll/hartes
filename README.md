# 🧪 Vazus — Лаборатория Архитектур ИИ и Экспериментов над Весами

> **Назначение репозитория:** Изолированный исследовательский полигон для разработки, сравнения и тестирования всех современных архитектур нейросетей (текстовых, визуальных, генеративных, голосовых дуплексных и адаптивных во время теста), а также **Weight-Space Programming** (прямого чтения, компиляции и хирургии весов без градиентного спуска).  
> **Границы:** Вся продуктовая обвязка, дашборд, память (`vazus.db`) и гипервизор вынесены в **Harnet** (`/home/tarhes/Проекты/harnet`).

---

## 🗂️ 12 Полочек Архитектур ИИ (По Моменту Применения, Плюсам и Минусам)

Полный каталог с формулами, разбором достоинств/недостатков и таблицей выбора: **[`tars/architectures/CATALOG.md`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/CATALOG.md)**

1. **Полочка 1 — Прямое программирование и хирургия весов (`Weight-Space Programming`)**:
   - Ручная компиляция алгоритмов и динамических систем в веса Трансформера (`0` шагов обучения) + `SVD`-хирургия петель зацикливания: [`tars/training/weight_space_programming.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/training/weight_space_programming.py)
2. **Полочка 2 — Пространства состояний (`SSM-3 / Mamba-3` & `Mamba-2 SSD`)**:
   - Комплекснозначное вращение фазы $\bar{A}_t = e^{(-\alpha + i\theta)\Delta t}$ для счёта чётности и сверхдлинных потоков: [`Mamba3Block`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/subquadratic_hybrids.py#L43-L139), [`tars/training/mamba2_ssd.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/training/mamba2_ssd.py)
3. **Полочка 3 — Матричные дельта-сети (`RWKV-7 "Goose"` & `Gated DeltaNet`)**:
   - Точечное стирание старого значения ключа и запись нового в матричную память $S_t$: [`RWKV7GooseBlock`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/subquadratic_hybrids.py#L146-L202), [`GatedDeltaNetBlock`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/subquadratic_hybrids.py#L205-L254)
4. **Полочка 4 — Гибриды `3:1` (`SSM / DeltaNet / RWKV` + `Full Attention`)**:
   - Чередование 3 быстрых слоёв $O(1)$ с 1 якорным слоем полного внимания для безошибочного поиска: [`HybridSequenceModel`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/subquadratic_hybrids.py#L279-L315)
5. **Полочка 5 — Понимание картинок, видео и физики мира (`Vision & World Encoders`)**:
   - `VMamba` (2D 4-направленное сканирование), `ViT / SigLIP`, `ConvNeXt` и латентный предсказатель мира `I-JEPA / V-JEPA`: [`VisionCrossScanSSM`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/modality_shelves.py#L23-L79), [`JEPALatentPredictor`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/modality_shelves.py#L82-L120)
6. **Полочка 6 — Генерация медиа (`Rectified Flow Matching`, `DiT`, `Next-Scale VAR`)**:
   - Прямолинейные потоки `Rectified Flow` (генерация за 4 шага Эйлера вместо 50 шагов диффузии): [`RectifiedFlowGenerator`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/modality_shelves.py#L127-L169)
7. **Полочка 7 — Реальное общение и голосовой полный дуплекс (`Moshi Dual-Stream` & `RVQ`)**:
   - Одновременное слушание и речь без задержки (`<150 мс`) со скрытым внутренним монологом и многоуровневым аудиокодеком `RVQ`: [`FullDuplexDialogBlock`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/modality_shelves.py#L202-L249), [`ResidualVectorQuantizer`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/modality_shelves.py#L176-L199)
8. **Полочка 8 — Глубокое мышление, латентные рассуждения и диффузионный текст (`RLVR`, `Coconut`, `dLLM`, `RRN`)**:
   - [`tars/training/rlvr_trainer.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/training/rlvr_trainer.py), [`tars/brain/rrn.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/brain/rrn.py), [`tars/brain/doubt_engine.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/brain/doubt_engine.py)
9. **Полочка 9 — Память во время теста и непрерывное время (`Titans / TTT` & `Liquid CfC`)**:
   - Быстрые веса, обучающиеся прямо в диалоге от сигнала удивления (`surprise`), и жидкие нейросети `CfC` с аналитическим решением ОДУ для роботов/датчиков: [`TitansSurpriseMemoryBlock`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/modality_shelves.py#L256-L312), [`LiquidCfCBlock`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/architectures/modality_shelves.py#L315-L341)
10. **Полочка 10 — Разреженные эксперты и научные сети (`MoE`, `MoD`, `KAN`)**:
    - [`tars/brain/moe.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/brain/moe.py), [`tars/brain/mamba2/mixture_of_depths.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/brain/mamba2/mixture_of_depths.py)
11. **Полочка 11 — Экстремальное сжатие для CPU/NPU (`BitNet b1.58`, `minGRU`, `Spiking`)**:
    - [`tars/training/bitnet_b158.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/training/bitnet_b158.py), [`tars/brain/min_gru/mingru.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/brain/min_gru/mingru.py), [`tars/brain/spiking/spiking_synapse.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/brain/spiking/spiking_synapse.py)
12. **Полочка 12 — Оптимизаторы и выравнивание (`Muon`, `DPO`, `KTO`, `Distillation`)**:
    - [`tars/training/muon_optimizer.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/training/muon_optimizer.py), [`tars/training/dpo_trainer.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/training/dpo_trainer.py), [`tars/training/kto_trainer.py`](file:///home/tarhes/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/vazus/tars/training/kto_trainer.py)

---

## ⚡ Быстрый запуск стендов

```bash
# 1. Сравнение Mamba-2 (real), Mamba-3 (SSM-3), RWKV-7 ("Goose"), Gated DeltaNet и 3:1 Hybrid:
/home/tarhes/Проекты/harnet/.venv/bin/python tars/architectures/subquadratic_hybrids.py

# 2. Проверка мультимодальных и специализированных полочек (Vision VMamba + I-JEPA, Rectified Flow, Duplex Moshi, Titans + Liquid CfC):
/home/tarhes/Проекты/harnet/.venv/bin/python tars/architectures/modality_shelves.py

# 3. Эксперименты по Weight-Space Programming (чтение, компиляция и хирургия весов с 0 градиентов):
/home/tarhes/Проекты/harnet/.venv/bin/python tars/training/weight_space_programming.py
```
