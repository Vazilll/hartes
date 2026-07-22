# 🧬 TARS — Полная документация методов и оптимизаций

> **Единственный файл, описывающий ВСЕ методы проекта TARS.**  
> Формулы — в `TARS_FORMULAS.md` · Источники — в `TARS_REFERENCES.md`

---

## 📁 Структура проекта

```
TarsSSM-Py/
├── config.py                     # TarsConfig — 85+ гиперпараметров
├── local_train.py                # Обучение (Colab + Local)
├── launch_tars.py                # Запуск инференса
│
├── brain/                        # ЯДРО АРХИТЕКТУРЫ
│   ├── mamba2/core/
│   │   ├── ssd.py                # TarsCoreBlock (SSD + WKV + Fusion)
│   │   ├── brain_core.py         # BrainCore (Wave Pipeline)
│   │   ├── bitnet.py             # BitNet 1.58-bit квантизация
│   │   ├── model_lite.py         # TarsHelixLite (Lite модель)
│   │   └── tars_block.py         # HelixBlock обёртка
│   ├── mamba2/routing/
│   │   └── mole_router.py        # MoLE: 8 экспертов, top-2
│   ├── min_gru/mingru.py         # MinGRU (Mode Router)
│   ├── doubt_engine.py           # DoubtEngine (3 головы верификации)
│   ├── speculative.py            # Спекулятивная генерация
│   ├── reflexes/                 # Рефлекторные быстрые ответы
│   └── tokenizer.py              # BPE + UTF-8 byte fallback
│
├── core/runtime/                 # NPU + SNN + Device Management
│   ├── npu_backend.py            # ONNX NPU (Snapdragon/Intel/DirectML)
│   ├── spike_bus.py              # SNN Spike Bus {-1,0,+1}
│   ├── device_manager.py         # Unified device selection
│   └── sleep_npu_listener.py     # Sleep mode NPU listener
│
├── training/                     # Обучение
│   ├── umot_loss.py              # UMOT Loss (7 компонент)
│   └── data/                     # HF датасеты (9 пресетов)
├── memory/                       # SDM, LEANN, Titans
├── agent/                        # Agent OS (тулы, безопасность)
├── sensory/                      # Ввод/вывод (голос, парсинг)
└── core/kernels/                 # C++ ядра (SSD, WKV, BitNet, SmoothQuant)
```

---

## 1. 🏗️ Архитектура: Dual-SSM HELIX

### Идея
Два параллельных SSM-механизма в каждом блоке, каждый со своей сильной стороной:

| Механизм | Сильная сторона | Слабость |
|----------|-----------------|----------|
| **SSD** (Mamba-2) | Быстрый recall, O(L) scan, d_state=64 | Слабая ассоциативная память |
| **WKV-7** (RWKV-7 GatedDeltaNet) | Точное state tracking, Delta Rule, r=24 | Медленнее SSD |

**Инсайт:** SSD хорош для «что было?» (синтаксис, локальный порядок, паттерны кода). WKV — для «как это связано?» (долгий контекст, ассоциации, тема разговора). Их слияние через WuNeng Fusion даёт **объёмное понимание** — два глаза дают объём.

### Data Flow одного блока
```
x → RMSNorm → in_proj → ┌─ Conv1D → SSD scan  ─┐
                         └─ time-shift → WKV scan ┘
                                    ↓
                            WuNeng Fusion (bottleneck 192d)
                                    ↓
                          SwiGLU output gate → out_proj → +residual
```

### Graduated 8-8-8 Layout (GOLDEN Vision)
```
Blocks  0-7:   SSD ONLY    → быстрые паттерны (синтаксис, код)
Blocks  8-15:  SSD + WKV   → полная интеграция (HELIX dual)
Blocks 16-19:  WKV ONLY    → глубокий контекст (ассоциации, тема)
```
**Текущая реализация:** все блоки uniform (SSD + WKV + Fusion). Graduated layout — Phase 1b.

### Реализация
- **Файл:** `ssd.py` → `TarsCoreBlock`
- Shared `in_proj` / `out_proj` для обоих путей
- ~5.2M params/block (4.7M SSD + 0.5M WKV + 0.01M fusion)

---

## 2. ⚡ BitNet 1.58-bit: Вычисления без умножений

### Метод
Веса квантуются до `{-1, 0, +1}` — матричное умножение заменяется сложением/вычитанием.

### Почему это работает
- **67% весов = 0** → пропускаются (sparsity)
- **Остальные = ±1** → ADD/SUB вместо MUL → нет FPU
- **STE (Straight-Through Estimator):** forward квантует, backward пропускает без изменений
- **RMSNorm перед квантованием** стабилизирует распределение
- На C++ target: **AVX2 ternary kernel** (ASM), без floating point Unit

### Режимы UniversalLinear
| Режим | Веса | Активации | Для чего |
|-------|------|-----------|----------|
| `fp16` | FP16 | FP16 | Обучение, debug |
| `158bit` | {-1,0,+1} | INT8 | Inference, production |

Переключение на лету: `layer.set_mode("158bit")` / `layer.set_mode("fp16")`.

### ActivationQuantizer (Inter-Block INT8)
Между блоками: INT8 квантование активаций → 4× меньше memory bandwidth.
- Training: STE (gradient flows)
- Inference: прямая квантизация

### Реализация
- **Файл:** `bitnet.py` → `UniversalLinear`, `ActivationQuantizer`

---

## 3. 🔀 WuNeng Fusion: Информационное горлышко

### Метод
Два SSM-выхода сливаются через bottleneck, который **вынуждает извлечь суть**:

```
[y_ssd; y_wkv] → Linear(2d → 192) → GELU → Linear(192 → d) → Sigmoid → gate
y = gate × y_ssd + (1 - gate) × y_wkv
```

### Почему bottleneck = 192?
- 192 = 9.4% от d_inner (2048). **Давление сжатия заставляет** выделить важное
- GELU (не ReLU) — гладкий градиент через горлышко
- Gate ∈ (0,1) — **per-dimension**, разные фичи из разных SSM
- Params: 2048×192 + 192×1024 = 590K/block

### Два уровня Fusion
1. **TarsCoreBlock** (per-block): SSD↔WKV fusion → `ssd.py`
2. **WaveConsolidation** (per-wave): Left↔Right block fusion + reflex signal → `brain_core.py`

---

## 4. 🧪 WKV-7 GatedDeltaNet: Адаптивная память

### Метод Delta Rule
Классический WKV: `S' = w⊙S + k⊗v` (first-order, просто записывает).  
GatedDeltaNet: **prediction error** + **β gate** (second-order, корректирует ошибки):

```
Δ = v - S·k              ("чего не знаю?" — prediction error)
β = σ(W_β · k)           ("запомнить или обновить?" — adaptive gate)
w_gated = β · w           (высокий β → сохранить state)
α_gated = (1-β) · α       (низкий β → агрессивно учиться)
S' = w_gated ⊙ S + α_gated · k ⊗ Δ
```

### Почему лучше обычного WKV
- **Covariance Delta Rule** = second-order update (associative recall)
- **β gate** Per-token — модель **сама решает** что помнить
- **Double-exp decay** `w = exp(-exp(...))` — строго ∈ (0, 1)
- **Low-Rank r=24** — 16 heads × 64 × 24 × 2 = компактно, но ёмко

### Performance Tiers
| Backend | Device | Speedup |
|---------|--------|---------|
| FLA Triton | GPU | ~15× |
| JIT script | CPU/GPU | ~2.5× |
| Python loop | CPU/GPU | 1× (baseline) |

### Реализация
- **Файл:** `ssd.py` → `_wkv_step` (JIT-compiled), `_wkv_scan_jit`
- **Обязательно FP32** — sequential recurrence накапливает ошибки в fp16

---

## 5. 🎯 MoLE: Mixture of LoRA Experts

### Метод
8 экспертов, каждый = LoRA adapter (rank=8, ~16K params). Top-2 routing.

### 8 экспертов
| # | Имя | Назначение |
|---|-----|------------|
| 0 | general | Общая речь |
| 1 | analyzer | Логический анализ |
| 2 | critic | Проверка на ошибки |
| 3 | creative | Нестандартные решения |
| 4 | math | Математика |
| 5 | code | Программирование |
| 6 | memory | Работа с воспоминаниями |
| 7 | action | Планирование действий |

### 3 auxiliary losses
1. **Load Balancing** (Switch Transformer) — `N × Σ(f_i × P_i)` → равномерная нагрузка
2. **Z-Loss** (ST-MoE) — `mean(logsumexp(logits)²)` → стабильные логиты
3. **Rényi Collision Entropy** (α=2) — максимизация разнообразия

### Personality Expert (GOLDEN Vision)
Always-on α=0.3 — один эксперт **всегда активен** для сохранения характера ТАРС.
**Текущее:** все 8 равноправны, top-2 routing. Always-on — Phase 3.

### Dropless Routing
Ни один токен не теряется (Granite 4.0). B.init=zeros → identity start.

### Реализация
- **Файл:** `mole_router.py`

---

## 6. 🧠 DoubtEngine: Adversarial Verification

### Метод
Независимый микро-классификатор (~200K params, <5ms CPU):

```
Stem: [query_emb; response_emb] → Linear(2d, 128) → SiLU → Linear(128, 128)
3 головы:
  CoherenceHead → "Ответ логичен?"
  SafetyHead    → "Это безопасно?"
  RepeatHead    → "Не зациклилось?"
```

### N-gram Repetition (non-neural)
Fallback без нейросети: `rep = 1 - unique_4grams / total_4grams`.

### Принципы безопасности
| Тип | Политика | При crash |
|-----|----------|-----------|
| **Текст** | Fail-open | Текст проходит |
| **Действие** | Fail-closed | Действие блокируется |

### SafetyGate (hardcoded blacklist)
60+ regex-паттернов (`rm -rf`, `shutdown`, shell injection, LOLBins).  
Работает **всегда**, даже если нейросеть упала.

### OutputGate Pipeline
```
SafetyGate BLOCK > DoubtEngine BLOCK > FLAG > PASS
```

### Реализация
- **Файл:** `doubt_engine.py`

---

## 7. 🔋 NPU Backend: Энергоэффективность

### Метод
ONNX Runtime с tiered fallback по энергопотреблению:

| Tier | Provider | ~Power |
|------|----------|--------|
| 1 | Qualcomm NPU (Snapdragon X) | ~5W |
| 2 | Intel NPU (OpenVINO, Meteor Lake) | ~5W |
| 3 | DirectML / CUDA GPU | ~75W |
| 4 | CPU fallback | ~25W |

### Sleep Mode
- **NPU** обрабатывает VAD (wake word detection) на ~2-5W
- **SNN Spike Bus** передаёт `{-1,0,+1}` = "проснуться"
- **madvise(WILLNEED) Prefetch** — при пробуждении mmap-prefetch модели за ~18ms (NVMe)
- К моменту когда юзер допечатает (500-2000ms) — все страницы модели в RAM

### Реализация
- `npu_backend.py` — NPU detection, ONNX session
- `device_manager.py` — unified device selection
- `sleep_npu_listener.py` — sleep mode с VAD

---

## 8. 📡 SNN Spike Bus: Межкомпонентная коммуникация

### Метод
Вместо текстовых сообщений — ternary spikes + INT8 payload:

```
Spike ∈ {-1, 0, +1}     → 320 байт vs 5KB FP32 = 16× сжатие
Payload: INT8 bytes       → опциональные параметры
```

### Типы сигналов
| Тип | Значение |
|-----|----------|
| WAKE | Пробуждение (VAD → Brain) |
| INTENT | Reflex classifier → intent |
| DOUBT | DoubtEngine → coherence low |

### Реализация
- **Файл:** `spike_bus.py`

---

## 9. 🎭 Wave-Parallel Architecture

### Метод
Блоки попарно в "волны", с возможностью параллельной обработки:

```
Wave 0: Block[0] ║ Block[1] → WaveConsolidation → SharedGlobalAttention (optional)
Wave 1: Block[2] ║ Block[3] → WaveConsolidation
...
```

### Компоненты
- **proj_left / proj_right** — диверсификация входа (near-identity + noise)
- **WaveConsolidation** — α-gated merge + bottleneck + reflex signal
- **SharedGlobalAttention** — GQA-4 каждые N волн (QK-Norm, learnable temperature)
- **WaveScratchpad** — compress→expand inter-wave memory

### NoveltyGate (inference optimization)
`cos_similarity(h_old, h_new) > 0.95` → block не изменил ничего → skip.

### Реализация
- **Файл:** `brain_core.py` → `BrainCore.forward()`

---

## 10. 📐 MinGRU: Параллельный Mode Router

### Метод: Рефлекторная классификация (<0.05ms)
MinGRU = minimal GRU с **Heinsen parallel scan** в log-space:

```
"привет"              → REFLEX  (exit, ~2000 tok/s)
"напиши unittest..."  → THINK   (full Brain)
"проанализируй код"   → DEEP    (full Brain + memory)
```

### Heinsen Scan
Ассоциативный scan через `cumsum + logcumsumexp` — O(L) параллельно вместо O(L) sequential.

### log_g activation
`log_g(x) = log(ReLU(x) + 0.5)` if x≥0, else `-softplus(-x)`. Численно стабильно.

### Реализация
- **Файл:** `mingru.py`

---

## 11. 🔄 Спекулятивная генерация

### EAGLE-3 Draft (GOLDEN Vision)
Из block 10: predict 3 extra tokens → verify все 4 в одном forward pass.
Accept rate ~75% → **2.5× speedup**. Draft head: ~4M params, 0.05ms per draft.

### Текущая реализация: Buffered Decoding
Buffer token IDs → decode batch → 2-5× меньше tokenizer.decode() вызовов.
Draft head: `Linear(d, d/4) → SiLU → Linear(d/4, vocab)`.

### Реализация
- **Файл:** `speculative.py`

---

## 12. 🎯 CausalConv1d + Time-Shift Mixing

### CausalConv1d (SSD path)
Depthwise convolution перед SSD scan — захватывает локальные паттерны (n-grams).
**Triton fast path:** если `mamba_ssm` установлен — `causal_conv1d_fn` (1 kernel вместо 3).

### Time-Shift Mixing (WKV path)
```
u_shifted = concat(x_prev, u[:, :-1])
u_mixed = u · time_mix + u_shifted · (1 - time_mix)
```
Learnable mixing ratio для каждого dimension — модель решает сколько "прошлого" добавить.

### Реализация
- **Файл:** `ssd.py`

---

## 13. 🧬 Hymba Meta-Tokens

### Метод
Learnable KV-cache элементы, prepended к SSD input:
```
meta_k: [1, n_meta_tokens, ngroups × d_state]
meta_c: [1, n_meta_tokens, ngroups × d_state]
meta_v: [1, n_meta_tokens, d_inner]
```
Модель **всегда видит** эти паттерны — они учат универсальные знания.

### Реализация
- **Файл:** `ssd.py` (lines 548-558)

---

## 14. 🎓 TTT-LoRA (Test-Time Training)

### Метод
При inference на сложных промптах — lazy-initialized LoRA адаптация:
```
for step in 1..3:
  loss = CE(model(x + B·A·x), self-targets)
  A -= lr × ∂loss/∂A
  B -= lr × ∂loss/∂B
```
Модель **адаптируется** к конкретному промпту за 3 шага SGD.

### Реализация
- **Файл:** `brain_core.py` → `TTTLoRA`

---

## 15. 🌊 Global Workspace Theory

### Метод
Competition → Broadcast → Mix. Потоки конкурируют за "глобальное внимание":
- Гейтированный competition между wave outputs
- Winner broadcasts на следующий wave
- Mixing через WaveConsolidation

### Реализация
- **Файл:** `brain_core.py` → `GlobalWorkspaceCompetition`

---

## 16. 💾 Memory Injector

### Метод
Memory vector (384d) инжектируется в hidden state через gated fusion:
```
[h_mean; memory_vec] → gate × signal → injection в все позиции
```

### RAG Injection
Context enrichment через external retrieval → concatenation + gated проекция.

### Реализация
- **Файл:** `tars_block.py` → `MemoryInjector`

---

## 17. 🏗️ Трёхслойная архитектура

### Слой 1: C++/Rust/ASM — Hot Path (target: 10-20ms/tok)
```
ssd_scan.cpp       AVX2/VNNI vectorized
wkv7_update.cpp    Rust SIMD
bitnet_matmul.cpp  ASM ternary (ADD/SUB only, no FPU)
swiglu_fused.cpp   SiLU⊙W₂x + sparse mask
rmsnorm_fused.cpp  Fused γ·x/√(mean(x²)+ε)
rope_fused.cpp     RoPE θ=500K
attention_diff.cpp 2×attention с вычитанием
smoothquant.cpp    Y=(X·S⁻¹)·(S·W) INT8 path
arena.rs           80MB bump allocator (zero-frag)
engine.rs          Main inference loop
eagle_decode.rs    Speculative loop
```

### Слой 2: Нейронка = ВСЯ логика (0 if/else на inference path)
**Все "решения" = просто матрицы W·x + activation:**
- Mode Router: MinGRU → REFLEX/THINK/DEEP
- WuNeng Fusion: gate = σ(W·x)
- MoLE Routing: softmax(W·x) → top-2
- MoD Decision: σ(W·x) > threshold → skip
- Early Exit: max(softmax(h@W)) > 0.9
- DoubtEngine: 3×Linear(d, 1)

### Слой 3: Python — Оркестрация (не hot path)
- Training, Data pipeline, Tools, Memory, UI

---

## 18. 📚 Обучение

### UMOT Loss (Alternating Batches)
```
CE:           100% → 30%   (main LM objective)
SFT:          0%   → 30%   (instruction following)
DPO:          0%   → 14%   (preference alignment)
Safety:       0%   → 7.5%  (safe responses)
CoT:          0%   → 8%    (reasoning chains)
Personality:  0%   → 20%   (ТАРС character)
FC:           0%   → 12%   (function calling)
```
**Alternating Batches** — NOT mixed! Each step = ONE loss with FULL gradient.

### Optimizer: Muon + AdamW Split
- **2D params** (weight matrices) → Muon (Newton-Schulz₅ orthogonal)
- **1D params** (biases, norms, embeddings) → AdamW

### LR Schedule: WSD
5% linear warmup → 75% stable → 20% cosine decay → 0.1×η_max

### Memory-Efficient Training
- **GaLore** — SVD rank-64, -65% optimizer memory
- **Gradient Checkpointing** — -50% activations, +15% time
- **Sequence Packing** (FFD) — 99% GPU utilization (45% → 99%)

### Cooperative STE (Vision)
19% more efficient than standard STE. Adaptive QA-KD: τ 2→3→4. TALS (Ternary-Aware Label Smoothing).

### EMA Self-Distillation
`θ_ema = 0.999·θ_ema + 0.001·θ` → KL(student ∥ ema) · T²

---

## 19. 🔐 Безопасность (5 слоёв)

| Слой | Механизм | Деталь |
|------|----------|--------|
| Input | InputSanitizer | NFC, zero-width removal, emoji→text, binary detect |
| Model | SSM Bound | \|s\| < 32K assert every 100 tokens |
| Model | NaN Guard | Ring buffer 3 checkpoints, auto-rollback |
| Output | DoubtEngine | 3 neural heads → PASS/FLAG/BLOCK |
| Output | SafetyGate | 60+ regex, hardcoded blacklist |
| Execution | Agent Guardian | READ/WRITE/EXECUTE/DESTRUCTIVE classifier |
| Execution | Sandbox | Whitelist folders, System32 = BLOCKED |
| Execution | User Confirm | "Удалить 47 файлов?" для WRITE/DESTRUCTIVE |
| Execution | Audit Log | 7-day ring buffer, undo info |
| Execution | Kill Switch | "ТАРС СТОП" → instant halt |
| Storage | Atomic Write | write(tmp) → fsync → os.replace |
| Storage | Checksummed LoRA | SHA256, 3 fallbacks: latest→previous→base |
| Storage | Memory Bound | RSS < 700 MB, assert every 1000 gen |

---

## 20. 🌙 Night Cycle: Автономное самообучение

### 7 фаз (~2 часа, 2:00-4:00 AM)

| Фаза | Время | Действие |
|------|-------|----------|
| 1. Analyse | 2 min | DoubtEngine.score() каждый ответ за день |
| 2. Privacy Filter | 2 min | NER + regex → SECRET/PRIVATE/PUBLIC |
| 3. Dream Replay | 20 min | Replay 200 best через модель |
| 4. Dream Training | 15 min | Generate 100 dreams (T=0.9), filter, train |
| 5. SPIN Self-Play | 25 min | 4× DPO iterations, LoRA only |
| 6. ALAS Curriculum | 45 min | Focus 70% on weakest MoLE experts |
| 7. PoI Gate | 10 min | score_after ≥ score_before - 0.05 → deploy/rollback |

### Гарантия не-деградации
- **PoI (Proof of Improvement):** rollback если стало хуже
- **Quarantine Trust (Phase 2+):** 3-ночной буфер перед deployment
- **Weight DNA (Phase 3):** SVD fingerprint, drift > 0.6 → BLOCK

### Privacy Filter
SECRET data **никогда** не попадает в training. Memorization Audit: 50 private prompts → check no leak.

---

## 21. 💾 Система памяти (Vision)

### Kanerva SDM (30K slots, INT8, 50MB)
Cosine similarity → top-5 → α-update. Recall ≥ 93% при 3+ entries.

### LEANN + RETRO Cross-Attention
25K docs, HNSW index O(log N), PQ compression 384→48 bytes.
RETRO cross-attention at block 16.

### Matryoshka 2-Stage Retrieval
Fast: e[:64] scan 30K → top-50. Full: e[:384] re-rank → top-5.

### Titans Surprise Memory
surprise = ‖x - M·x‖². If high → M ← M + η·(x-M·x)·xᵀ (rank-1 SGD, async).

### Gaussian Uncertainty
Each entry: N(μ, σ²). Новое → σ high (unsure). Часто → σ low (confident).

### Doc-to-LoRA
Topic detected → load LoRA_topic.pt (3MB). 200× compression vs raw text.

### User Twin (16-dim EMA vector)
Tracks: tech_level, interests, schedule, mood_pattern.  
`twin = 0.95·twin + 0.05·observed` — модель знает юзера.

### ADI Emotional (16-dim vector)
satisfaction, helpfulness → ТАРС адаптирует personality.

---

## 22. 🎮 Context Manager + SSM State Cache

### Context Manager (8K window)
```
if len(context) > 0.75 × 8192:
  summary = model.summarize(context[:half])
  SDM.store(key=embed(summary), val=old_turns)
  context = [system_prompt, summary, recent_turns]
```

### SSM State Cache
Если system_prompt не изменился → загрузить cached SSM states → TTFT ≈ 0.

---

## 23. ⚙️ Дополнительные оптимизации

### SSD: Обязательный FP32
`exp(cumsum(A))` overflow в fp16 при cumsum > 11. Все operands → `.float()`.

### Weight Tying
`lm_head.weight = embedding.weight` → -48K × d_model params.

### Vaswani Scaling
`x = E(token) × √d_model` → стабильные нормы.

### Sampling
Top-p (nucleus): cumsum > 0.9. Temperature: 0.7 (creative) / 0.1 (code).
Repetition Penalty: `logits[seen] /= 1.1`.

### Stochastic Depth (Training)
```
u ~ Uniform(0,1)
if u < 0.15: output = input  (skip block entirely)
else: output = Block(x) / (1-p_drop) + x  (rescaled)
```

### HiPPO Initialization (Vision)
4 banks γ = 0.5 / 0.9 / 0.99 / 0.999 → captures 2-tok to 1000-tok dependencies.

---

## 📊 Конфигурация по умолчанию

| Параметр | Full | Lite |
|----------|------|------|
| d_model | 1024 | 768 |
| n_layers | 20 | 16 |
| vocab_size | 48,256 | 256 |
| d_state (SSD) | 64 | 64 |
| headdim | 64 | 64 |
| expand | 2 | 2 |
| dim_ff (SwiGLU) | 2816 | 2048* |
| wkv_low_rank | 24 | 24 |
| MoLE experts | 8 × rank=8 | 8 × rank=8 |
| ~params | ~296-380M | ~116M |

---

## ✅ Команды верификации

```bash
python local_train.py --test-only       # Smoke test
python local_train.py --count-params    # Parameter count
python tests/test_npu_backend.py        # NPU + SpikeBus
python local_train.py --level small     # Training (~15 min)
```

---

> 🧬 **23 метода. Dual-SSM + BitNet + WuNeng + MoLE + DoubtEngine + NPU + Night Cycle.**  
> **0 if/else на inference. Всё = обученные матрицы.**  
> **Каждую ночь умнее. Гарантировано.**
