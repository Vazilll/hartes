# 🧬 TARS HELIX — Единая Техническая Спецификация

> **Версия:** 1.0 — полная карта формул → код  
> **Дата:** 2026-03-11  
> **Источник:** TARS_HELIX_GOLDEN.md + аудит кодовой базы  
> **Принцип:** Каждая формула = конкретная строка кода. Нет "планируется".

---

## 📊 Сводка: Формулы × Реализация

| # | Компонент | Формула | Файл | Статус |
|---|-----------|---------|------|--------|
| 1 | SSD Scan | h'=A·h + B·x, y=C·h + D·x | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L132-L215) | ✅ |
| 2 | SSD Step (L=1) | decay·state + outer(x,B) | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L107-L129) | ✅ |
| 3 | WKV-7 GatedDeltaNet | Δ=v-S·k, S'=w⊙S + α·k⊗Δ | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L262-L292) | ✅ |
| 4 | β Gate (DeltaNet) | β=σ(W·k), w=β·w, α=(1-β)·α | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L752-L756) | ✅ |
| 5 | WKV Vector Decay | w=exp(-exp(w + w_gate)) | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L748) | ✅ |
| 6 | WKV Receptance Gate | r=σ(r_raw) | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L746) | ✅ |
| 7 | WuNeng Fusion (Core) | gate·y_ssd + (1-gate)·y_wkv, gate=σ(Bottleneck(concat)) | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L767-L768) | ✅ |
| 8 | WuNeng Bottleneck | 2d_inner→192→GELU→d_inner | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L529-L534) | ✅ |
| 9 | WuNeng Fusion (Wave) | concat→2d→192→GELU→d, α-gated merge | [brain_core.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L104-L163) | ✅ |
| 10 | SwiGLU Output Gate | y = y_fused * (SiLU(z) ⊙ W_gate(z)) | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L773-L774) | ✅ |
| 11 | RMSNorm | x̂ = γ·x / √(mean(x²)+ε) | [bitnet.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/bitnet.py#L155-L171) | ✅ |
| 12 | BitNet Ternary Quant | γ=mean(\|w\|), w_q=round(clip(w/γ,-1,1)) | [bitnet.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/bitnet.py#L44-L63) | ✅ |
| 13 | INT8 Activation Quant | γ=max(\|x\|)/127, x_q=round(clip(x/γ)) | [bitnet.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/bitnet.py#L66-L82) | ✅ |
| 14 | STE Weight | forward: quantize, backward: pass-through | [bitnet.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/bitnet.py#L89-L103) | ✅ |
| 15 | STE Activation | forward: int8, backward: pass-through | [bitnet.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/bitnet.py#L106-L117) | ✅ |
| 16 | ActivationQuantizer | inter-block INT8 (STE train, direct eval) | [bitnet.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/bitnet.py#L124-L148) | ✅ |
| 17 | RoPE | x·cos(θ) + rotate_half(x)·sin(θ), θ=pos/base^(2i/d) | [brain_core.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L49-L101) | ✅ |
| 18 | MinGRU (Mode Router) | z=σ(W·x), h=(1-z)·h + z·h̃ | [mingru.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/min_gru/mingru.py#L21-L58) | ✅ |
| 19 | Heinsen Log-Space Scan | parallel scan via cumsum+logcumsumexp | [mingru.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/min_gru/mingru.py#L12-L16) | ✅ |
| 20 | MoLE LoRA | ΔW = B·A·x·(α/r) | [mole_router.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/routing/mole_router.py#L21-L39) | ✅ |
| 21 | MoLE Top-K Routing | softmax(topk(gate(h))) | [mole_router.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/routing/mole_router.py#L75-L101) | ✅ |
| 22 | Load Balance Loss | N × Σ(f_i × P_i) | [mole_router.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/routing/mole_router.py#L130-L164) | ✅ |
| 23 | Z-Loss | (logsumexp(logits))² | [mole_router.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/routing/mole_router.py#L166-L169) | ✅ |
| 24 | Rényi Diversity | H_α = log(Σp_i^α)/(1-α), α=2 | [mole_router.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/routing/mole_router.py#L171-L183) | ✅ |
| 25 | DoubtEngine | coherence=σ(W·h), safety=σ(W·h), repeat=σ(W·h) | [doubt_engine.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/doubt_engine.py#L230-L313) | ✅ |
| 26 | Doubt Formula | doubt = 1-min(coh, saf, 1-rep) | [doubt_engine.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/doubt_engine.py#L384-L447) | ✅ |
| 27 | N-gram Repetition | 1 - unique_ngrams/total_ngrams | [doubt_engine.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/doubt_engine.py#L315-L349) | ✅ |
| 28 | Weight Tying | lm_head.weight = embedding.weight | [brain_core.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L438) | ✅ |
| 29 | Vaswani Scaling | x = E(token) × √d_model | [brain_core.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L528) | ✅ |
| 30 | Shared Global Attn (GQA) | QK-norm + learnable temperature | [brain_core.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L202-L252) | ✅ |
| 31 | TTT-LoRA | At test-time: SGD on LoRA A,B for n_steps | [brain_core.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L281-L339) | ✅ |
| 32 | WaveScratchpad | compress→expand, gated injection | [brain_core.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L255-L278) | ✅ |
| 33 | Global Workspace Theory | competition→broadcast→mix | [brain_core.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L166-L199) | ✅ |
| 34 | Hymba Meta-Tokens | learnable KV prepended to SSD | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L548-L558) | ✅ |
| 35 | Memory Injector | fused [h;mem]→gate·signal | [tars_block.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/tars_block.py#L30-L78) | ✅ |
| 36 | NoveltyGate | cosine novelty → skip residual | [tars_block.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/tars_block.py#L186-L191) | ✅ |
| 37 | SafetyGate | regex blacklist, fail-closed | [doubt_engine.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/doubt_engine.py#L82-L223) | ✅ |
| 38 | SNN Spike Bus | ternary spikes {-1,0,+1} + INT8 payload | [spike_bus.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/core/runtime/spike_bus.py) | ✅ |
| 39 | NPU Backend | ONNX tiered fallback (NPU→CUDA→CPU) | [npu_backend.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/core/runtime/npu_backend.py) | ✅ |
| 40 | Sleep Listener | NPU VAD + spike WAKE + prefetch | [sleep_npu_listener.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/core/runtime/sleep_npu_listener.py) | ✅ |
| 41 | Speculative Decode | draft→verify→accept/reject + buffered decode | [speculative.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/speculative.py) | ✅ |
| 42 | Time-Shift Mixing | u_mixed = u·mix + u_shifted·(1-mix) | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L586-L589) | ✅ |
| 43 | CausalConv1d | depthwise conv + Triton fast path | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L218-L255) | ✅ |
| 44 | Segsum (SSD utils) | stable cumsum with tril masks | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L96-L104) | ✅ |

---

## ⚠️ Формулы из GOLDEN, отсутствующие в коде

| # | Формула из GOLDEN | Что требуется | Приоритет |
|---|-------------------|---------------|-----------|
| A1 | **FlashSigmoid**: γ=0.5+0.25·x (no exp) | GOLDEN предлагает FlashSigmoid для SSM decay gate. Код использует `softplus(dt + bias)` для dt — это корректно для Mamba-2 (dt — timestep, не decay). FlashSigmoid применим к Graduated 8-8-8 layout (Phase 2). | 🔶 Phase 2 |
| A2 | **Double Sparsity**: mask=(|h|\>ε), 87% zeros | SwiGLU реализован, но sparse matmul skip (W₃_active) не включён. Текущий код делает dense matmul через gate. | 🔶 Phase 2 |
| A3 | **Graduated 8-8-8 Layout** | GOLDEN: blocks 0-7 SSD only, 8-15 dual, 16-19 WKV only. Реально: все блоки = dual (SSD+WKV+Fusion). Layout-routing отсутствует. | 🔶 Phase 1b |
| A4 | **Early Exit** | confidence = max(softmax(E^T·h)) > 0.9 → skip remaining blocks. Не реализовано. | 🔶 Phase 2 |
| A5 | **Personality Expert always-on α=0.3** | GOLDEN: один MoLE expert всегда активен с весом 0.3. Код: все 8 экспертов равноправны, top-2 routing. | 🟡 Phase 3 |
| A6 | **Arena Allocator** | Rust/C++ bump allocator. Python runtime не использует arena. | 🔵 C++ phase |
| A7 | **EAGLE-3 Speculative** | GOLDEN: из block 10, predict 3 extra. Код: MinGRU draft вместо EAGLE-3. Эффективнее но другая архитектура. | 🟡 Design choice |
| A8 | **Kanerva SDM Memory** | 30K slots, cos_sim. Не реализовано как отдельный модуль. | 🔶 Phase 2 |
| A9 | **Night Cycle DPO** | L=-log σ(β·log_ratio). Training pipeline есть, но Night Cycle с DPO/SPIN не реализован. | 🟡 Phase 3 |
| A10 | **Cooperative STE** | 19% more efficient than standard STE. Текущий STE — стандартный. | 🟡 Phase 3 |
| A11 | **TALS** | Ternary-Aware Label Smoothing. Не реализовано. | 🟡 Phase 3 |
| A12 | **Matryoshka 2-stage retrieval** | Fast e[:64] → Full e[:384]. Не реализовано (нет SDM модуля). | 🔶 Phase 2 |

---

## 🔁 Полный Data Flow (формула → код)

```
                        USER INPUT
                            │
                    ┌───────┴────────┐
                    │  UTF-8 String  │
                    └───────┬────────┘
                            │
                 ┌──────────┴──────────┐
                 │  TarsTokenizer      │  brain/tokenizer.py
                 │  cp1251/BPE encode  │  token_ids: List[int]
                 └──────────┬──────────┘
                            │
                 ┌──────────┴──────────┐
                 │  nn.Embedding       │  brain_core.py:384
                 │  × √d_model         │  brain_core.py:528,610 (Vaswani)
                 │  → x: [B, L, 1024]  │
                 └──────────┬──────────┘
                            │
              ┌─────────────┴─────────────┐
              │  Wave Loop × n_waves      │  brain_core.py:626
              │  ┌─ proj_left(x) ─┐       │
              │  │                │       │
              │  ▼                ▼       │
         TarsBlock[L]        TarsBlock[R] │  tars_block.py:81
              │                │           │
              │  RMSNorm → TarsCoreBlock  │
              │  ┌─── in_proj ────┐       │
              │  │ [Mamba params] │       │  ssd.py:594
              │  │ [RWKV  params] │       │
              │  ├────────────────┤       │
              │  │  SSD SCAN      │       │  ssd.py:676-736
              │  │  h'=A·h+B·x   │       │  Formula #1
              │  │  y=C·h+D·x    │       │
              │  │  + ConvState   │       │  ssd.py:614-641
              │  │  + Meta-Tokens │       │  ssd.py:692-730
              │  ├────────────────┤       │
              │  │  WKV-7 SCAN    │       │  ssd.py:738-758
              │  │  β gate        │       │  Formula #4
              │  │  Δ=v-S·k       │       │  Formula #3
              │  │  S'=w⊙S+α·k⊗Δ│       │
              │  │  y=r⊙(S·k)    │       │
              │  ├────────────────┤       │
              │  │  WuNeng FUSION │       │  ssd.py:764-768
              │  │  2d→192→d     │       │  Formula #7,8
              │  │  gate·ssd+     │       │
              │  │  (1-gate)·wkv  │       │
              │  ├────────────────┤       │
              │  │  SwiGLU output │       │  ssd.py:773-774
              │  │  y*(SiLU(z)⊙  │       │  Formula #10
              │  │   W_gate(z))   │       │
              │  │  out_proj      │       │  ssd.py:776
              │  └────────────────┘       │
              │  + Residual               │  tars_block.py:170
              │  + MoLE (top-2 LoRA)      │  tars_block.py:182
              │  + MemoryInjector         │  tars_block.py:195-200
              │  + ActivationQuantizer    │  tars_block.py:203
              │  (INT8 between blocks)    │  Formula #16
              │                │           │
              └─┬──────────────┘           │
                │                          │
         WaveConsolidation(L, R)          │  brain_core.py:684
              │  α=σ(W·[h_L;h_R])        │  Formula #9
              │  (1-α)·x_L + α·x_R       │
              │  + WuNeng bottleneck       │
              │  + reflex signal           │
              │                            │
              │  SharedGlobalAttention     │  brain_core.py:692-693
              │  (every N-th wave, GQA-4) │  Formula #30
              │                            │
              │  WaveScratchpad.summarize  │  brain_core.py:695
              │  WaveScratchpad.inject     │  brain_core.py:634
              └─────────────┬──────────────┘
                            │
                 ┌──────────┴──────────┐
                 │  RMSNorm (final)    │  brain_core.py:717
                 │  PersonalityAdapter │  brain_core.py:718
                 │  lm_head (tied)     │  brain_core.py:719
                 │  → logits [B,L,V]   │
                 └──────────┬──────────┘
                            │
              ┌─────────────┴─────────────┐
              │  DoubtEngine (optional)    │  doubt_engine.py:230
              │  coherence, safety, repeat │  Formula #25
              │  → pass / flag / block     │  Formula #26
              └─────────────┬──────────────┘
                            │
                 ┌──────────┴──────────┐
                 │  Sampling / Decode  │
                 │  top-k, temperature │
                 │  → next_token_id    │
                 └─────────────────────┘
```

---

## 🔬 Детальные формулы по компонентам

### 1. SSD Scan (Mamba-2 Structured State-Space Duality)

```
Рекуррентная форма (inference L=1):
  h_new = exp(A·dt) × h_old + outer(x·dt, B)    [ssd.py:122-124]
  y = inner(C, h_new) + D·x                       [ssd.py:126-128]

Параллельная форма (training):
  A_cumsum = cumsum(A·dt)                          [ssd.py:182]
  L = exp(segsum(A))                               [ssd.py:185]
  Y_diag = einsum(C, B, L, X)                     [ssd.py:186-187]  (intra-chunk)
  decay_states = exp(A_last - A_cumsum)            [ssd.py:190]
  states = einsum(B, decay, X)                     [ssd.py:191-192]  (inter-chunk)
  decay_chunk = exp(segsum(A_totals))              [ssd.py:199]
  new_states = einsum(decay_chunk, states)          [ssd.py:200-201] (chain recurrence)
  Y_off = einsum(C, states, exp(A_cumsum))         [ssd.py:207-208] (state→output)
  Y = Y_diag + Y_off                              [ssd.py:210]
```

> **FP32 обязательно**: exp(cumsum) overflow в fp16 при cumsum\>11. Все einsum operands cast to `.float()` — bullet-proof от AMP.

### 2. WKV-7 GatedDeltaNet (RWKV-7)

```
Входы: r, k, v, w, bonus = split(in_proj(u_mixed))   [ssd.py:742-744]

Preprocess:
  r = σ(r_raw)                                     [ssd.py:746]     (receptance gate)
  w = exp(-exp(w_raw + w_gate))                    [ssd.py:748]     (double-exp decay)
  α = σ(bonus_raw)                                 [ssd.py:750]     (learning rate)

β Gate (Gated DeltaNet):
  β = σ(W_beta · k)                                [ssd.py:754]
  w_gated = β · w                                   [ssd.py:755]     (preserve if β high)
  α_gated = (1-β) · α                              [ssd.py:756]     (learn if β low)

Delta Rule:
  Δ = v - S·k                                      [ssd.py:287]     (prediction error)
  S' = diag(w_gated)·S + α_gated · k⊗Δ           [ssd.py:289]     (state update)

Output:
  y = r ⊙ (S'·k)                                  [ssd.py:291]     (gated readout)
```

### 3. BitNet 1.58-bit Quantization

```
Weight Quantization:
  γ = mean(|W|)                                    [bitnet.py:58]
  W_q = round(clip(W/γ, -1, 1)) ∈ {-1, 0, +1}   [bitnet.py:61-62]
  W_eff = W_q × γ                                 [bitnet.py:98]    (in STE forward)

Activation Quantization (INT8):
  γ_x = max(|x|, dim=-1) / 127                    [bitnet.py:80]
  x_q = round(clip(x/γ_x, -128, 127))             [bitnet.py:81]
  x_eff = x_q × γ_x                               [bitnet.py:82]

STE (Straight-Through Estimator):
  forward:  quantize(W) → W_q                      [bitnet.py:96]
  backward: ∂L/∂W = ∂L/∂W_q (pass-through)       [bitnet.py:102-103]
```

### 4. MoLE (Mixture of LoRA Experts)

```
LoRA Expert:
  Δ = B·A·x × (α/r)                               [mole_router.py:37-39]
  A: [d, r=8],  B: [r, d],  B.init=zeros          [mole_router.py:34-35]

Routing:
  logits = W_gate · h_mean                         [mole_router.py:91]
  weights, indices = topk(logits, k=2)             [mole_router.py:98]
  weights = softmax(weights)                        [mole_router.py:99]

Auxiliary Losses:
  L_balance = N × Σ(f_i × P_i)                    [mole_router.py:164]    (Switch Transformer)
  L_z = mean(logsumexp(logits)²)                   [mole_router.py:168-169] (ST-MoE Z-Loss)
  H_α = log(Σp_i^α) / (1-α), α=2                 [mole_router.py:181]    (Rényi Collision Entropy)
  L_aux = 0.01·L_balance + 0.001·L_z + 0.01·(-H₂) [mole_router.py:187-189]
```

### 5. MinGRU (Mode Router)

```
Heinsen Parallel Scan:
  a* = cumsum(log_coeffs)                          [mingru.py:13]
  log(h0 + b*) = logcumsumexp(log_values - a*)    [mingru.py:14]
  h = exp(a* + log(h0 + b*))                      [mingru.py:15-16]

Gate:
  log_coeffs = -softplus(gate) = log(1-σ(gate))   [mingru.py:36]
  log_z = -softplus(-gate) = log(σ(gate))          [mingru.py:37]
  log_h̃ = log_g(hidden) = log(ReLU(x)+0.5) or -softplus(-x)  [mingru.py:18-19]
```

### 6. DoubtEngine

```
Neural Heads:
  coherence = σ(W_coh · stem(concat(q_emb, r_emb)))  [doubt_engine.py:304]
  safety    = σ(W_saf · stem(...))                     [doubt_engine.py:305]
  repetition = σ(W_rep · stem(...))                    [doubt_engine.py:306]

N-gram Repetition:
  rep = 1 - unique_4grams / total_4grams              [doubt_engine.py:349]

Verdict:
  coherence < 0.2 OR safety < 0.3 OR rep > 0.9 → BLOCK  [doubt_engine.py:406-411]
  coherence < 0.5 OR safety < 0.6 OR rep > 0.7 → FLAG   [doubt_engine.py:422-427]
  else → PASS
```

### 7. SNN Spike Bus (Inter-Component Signals)

```
Signal = SpikeSignal(type, spike ∈ {-1, 0, +1}, payload: bytes)

INT8 encode/decode:
  value → struct.pack('b', clamp(val, -128, 127))  [spike_bus.py]
  bytes → struct.unpack('b', data)

Bus operations:
  emit(type, spike, payload, source)  → deque
  poll(type) → SpikeSignal or None
  subscribe(type, callback) → auto-trigger
```

### 8. NPU Backend (ONNX Runtime)

```
Detection priority:
  1. QualcommExecutionProvider (Snapdragon X)
  2. OpenVINOExecutionProvider (Intel Meteor Lake)
  3. DmlExecutionProvider (DirectML)
  4. CUDAExecutionProvider
  5. CPUExecutionProvider (always available)

Power estimate:
  NPU: ~5W  |  CPU: ~25W  |  GPU: ~75W
  Sleep mode target: NPU for VAD (~2-5W)
```

---

## 📁 Карта файлов

| Компонент | Файл | Формулы |
|-----------|------|---------|
| SSD + WKV + Fusion Core | [ssd.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py) | #1-10, 42-44 |
| BitNet / RMSNorm | [bitnet.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/bitnet.py) | #11-16 |
| Brain Pipeline | [brain_core.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py) | #9, 17, 28-33 |
| Block Assembly | [tars_block.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/tars_block.py) | #35, 36 |
| MoLE Router | [mole_router.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/routing/mole_router.py) | #20-24 |
| MinGRU | [mingru.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/min_gru/mingru.py) | #18-19 |
| DoubtEngine | [doubt_engine.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/doubt_engine.py) | #25-27, 37 |
| Speculative | [speculative.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/speculative.py) | #41 |
| SNN Spike Bus | [spike_bus.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/core/runtime/spike_bus.py) | #38 |
| NPU Backend | [npu_backend.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/core/runtime/npu_backend.py) | #39 |
| Device Manager | [device_manager.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/core/runtime/device_manager.py) | — |
| Sleep Listener | [sleep_npu_listener.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/core/runtime/sleep_npu_listener.py) | #40 |
| Config | [config.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/config.py) | — |

---

> 🧬 **44 формулы реализованы. 12 отложены (Phase 2-3, C++).**  
> **Каждая ссылка ведёт к конкретной строке кода.**
