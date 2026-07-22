# 📐 TARS — Полный сборник формул

> **Все формулы проекта. Каждая — с контекстом, файлом и статусом.**  
> Методы — в `TARS_METHODS.md` · Источники — в `TARS_REFERENCES.md`

**Обозначения:** ✅ реализовано · 🔶 Phase 2+ · σ=sigmoid · ⊙=поэлементно · ⊗=outer product

---

## 1. SSD (Mamba-2 Structured State-Space Duality)

### 1.1 ✅ Параллельная форма (training)
```
A_cumsum = cumsum(A · Δt)                         
L = exp(segsum(A))                                  — intra-chunk matrix
Y_diag = Σ_s C_l · B_s · L_{ls} · X_s              — intra-chunk
decay = exp(A_last - A_cumsum)                       — inter-chunk decay
states = Σ B · decay · X                            — inter-chunk states
Y = Y_diag + Y_off                                  — final output
```
**Файл:** [ssd.py:132-215](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L132-L215)

### 1.2 ✅ Рекуррентная форма (inference L=1)
```
h_new = exp(A · Δt) · h_old + outer(x · Δt, B)     — state update
y = inner(C, h_new) + D · x                         — readout + skip
```
**Файл:** [ssd.py:107-129](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L107-L129)

### 1.3 ✅ Segsum (stable)
```
x_masked = x · tril(ones, diag=-1)
x_segsum = cumsum(x_masked) · tril(ones, diag=0)    — −∞ outside mask
```
**Файл:** [ssd.py:96-104](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L96-L104)

### 1.4 ✅ Discretization
```
Δt = softplus(W_dt · x + bias)                      — Δt > 0 guaranteed
A = -exp(A_log)                                      — A_log ~ log(Uniform[1,16])
```
**Файл:** [ssd.py:499-507, 612, 650](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L499-L507)

---

## 2. WKV-7 (RWKV-7 GatedDeltaNet)

### 2.1 ✅ Preprocessing
```
r = σ(r_raw)                                        — receptance ∈ (0,1)
w = exp(-exp(w_raw + w_gate))                       — double-exp decay ∈ (0,1)
α = σ(bonus_raw)                                    — learning rate ∈ (0,1)
```
**Файл:** [ssd.py:746-750](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L746-L750)

### 2.2 ✅ β Gate (Gated DeltaNet)
```
β = σ(W_β · k)                                      — adaptive balance
w_gated = β · w                                      — β high → preserve state
α_gated = (1-β) · α                                  — β low → learn aggressively
```
**Файл:** [ssd.py:754-756](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L754-L756)

### 2.3 ✅ Delta Rule + Update
```
Δ = v - S · k                                        — prediction error (2nd order)
S' = w_gated ⊙ S + α_gated · k ⊗ Δ                 — state update
y = r ⊙ (S' · k)                                    — gated readout
```
**Файл:** [ssd.py:262-292](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L262-L292)

### 2.4 ✅ Time-Shift Mixing
```
u_shifted = concat(x_prev, u[:, :-1])
u_mixed = u · mix + u_shifted · (1 - mix)           — learnable per-dim
```
**Файл:** [ssd.py:586-589](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L586-L589)

---

## 3. WuNeng Fusion

### 3.1 ✅ Bottleneck Fusion (per-block)
```
gate = σ(W_up(GELU(W_down([y_ssd; y_wkv]))))        — 2d→192→d→σ
y = gate ⊙ y_ssd + (1-gate) ⊙ y_wkv
```
**Файл:** [ssd.py:529-534, 767-768](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L529-L534)

### 3.2 ✅ Wave Consolidation (per-wave)
```
α = σ(W_gate · [h_left; h_right])                   — dim-wise gate
x = (1-α) · x_left + α · x_right                    — gated merge
fusion = W₂(GELU(W₁([h_left; h_right])))            — 2d→192→d
reflex = tanh(W_reflex · concat)
output = RMSNorm(x + s_fuse · fusion + s_reflex · reflex)
```
**Файл:** [brain_core.py:104-163](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L104-L163)

---

## 4. BitNet 1.58-bit

### 4.1 ✅ Weight Quantization
```
γ = mean(|W|)
W_q = round(clip(W/γ, -1, 1)) ∈ {-1, 0, +1}
```
**Файл:** [bitnet.py:44-63](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/bitnet.py#L44-L63)

### 4.2 ✅ Activation Quantization (INT8)
```
γ_x = max(|x|) / 127
x_q = round(clip(x/γ_x, -128, 127))
```
**Файл:** [bitnet.py:66-82](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/bitnet.py#L66-L82)

### 4.3 ✅ STE (Straight-Through Estimator)
```
Forward:   quantize(W)  →  W_q
Backward:  ∂L/∂W = ∂L/∂W_q   (pass-through)
```
**Файл:** [bitnet.py:89-117](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/bitnet.py#L89-L117)

### 4.4 ✅ ActivationQuantizer
```
Train: STE_int8(x)     — gradient flows
Eval:  dequant(quant(x)) — direct
```
**Файл:** [bitnet.py:124-148](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/bitnet.py#L124-L148)

---

## 5. ✅ RMSNorm
```
x̂ = γ · x / √(mean(x²) + ε)
```
**Файл:** [bitnet.py:155-171](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/bitnet.py#L155-L171)

---

## 6. ✅ SwiGLU Output Gate
```
z_gate = SiLU(z) ⊙ W_gate(z)
y = Norm(y_fused ⊙ z_gate)
output = out_proj(y)
```
**Файл:** [ssd.py:773-776](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/ssd.py#L773-L776)

### 🔶 Double Sparsity (Phase 2)
```
mask = (|h| > ε) → 87% zeros (BitNet 67% × activation 60%)
W₃_active = W₃[:, nonzero(mask)] → sparse matmul
```

---

## 7. ✅ RoPE
```
θ_i = pos / base^(2i/d),  base = 500,000
RoPE(x) = x · cos(θ) + rotate_half(x) · sin(θ)
```
**Файл:** [brain_core.py:49-101](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L49-L101)

---

## 8. MoLE

### 8.1 ✅ LoRA Expert
```
Δ = B · A · x × (α/r),  r=8, α=16
A: Kaiming init,  B: zeros
```
**Файл:** [mole_router.py:21-39](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/routing/mole_router.py#L21-L39)

### 8.2 ✅ Top-K Routing
```
logits = W_gate · h_mean
weights = softmax(topk(logits, k=2))
```
**Файл:** [mole_router.py:90-99](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/routing/mole_router.py#L90-L99)

### 8.3 ✅ Load Balance Loss
```
f_i = count(expert_i) / (B×k)
P_i = mean(softmax(logits))_i
L_balance = N × Σ(f_i × P_i)
```
**Файл:** [mole_router.py:150-164](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/routing/mole_router.py#L150-L164)

### 8.4 ✅ Z-Loss
```
L_z = mean(logsumexp(logits)²)
```
**Файл:** [mole_router.py:166-169](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/routing/mole_router.py#L166-L169)

### 8.5 ✅ Rényi Entropy (α=2)
```
H₂ = log(Σp_i²) / (1-2)
L_rényi = -H₂
```
**Файл:** [mole_router.py:178-183](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/routing/mole_router.py#L178-L183)

### 8.6 ✅ Combined Aux Loss
```
L = 0.01·L_balance + 0.001·L_z + 0.01·(-H₂)
```
**Файл:** [mole_router.py:187-189](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/routing/mole_router.py#L187-L189)

---

## 9. MinGRU

### 9.1 ✅ Gate
```
log_coeffs = -softplus(gate) = log(1-σ(gate))
log_z = -softplus(-gate) = log(σ(gate))
log_h̃ = log_g(hidden)
log_values = log_z + log_h̃
```
**Файл:** [mingru.py:36-39](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/min_gru/mingru.py#L36-L39)

### 9.2 ✅ Heinsen Parallel Scan
```
a* = cumsum(log_coeffs, dim=1)
log(h₀+b*) = logcumsumexp(log_values - a*, dim=1)
h = exp(a* + log(h₀+b*))
```
**Файл:** [mingru.py:12-16](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/min_gru/mingru.py#L12-L16)

### 9.3 ✅ log_g activation
```
log_g(x) = log(ReLU(x)+0.5) if x≥0 | -softplus(-x) if x<0
```
**Файл:** [mingru.py:18-19](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/min_gru/mingru.py#L18-L19)

---

## 10. DoubtEngine

### 10.1 ✅ Neural Heads
```
stem = SiLU(Linear(Linear([q_emb; r_emb])))         — [B, 128]
coherence = σ(W_coh · stem)
safety = σ(W_saf · stem)
repetition = σ(W_rep · stem)
```
**Файл:** [doubt_engine.py:278-313](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/doubt_engine.py#L278-L313)

### 10.2 ✅ N-gram Repetition
```
rep = 1 - len(set(ngrams_4)) / len(ngrams_4)
```
**Файл:** [doubt_engine.py:316-349](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/doubt_engine.py#L316-L349)

### 10.3 ✅ Verdict
```
BLOCK: coh<0.2 OR safe<0.3 OR rep>0.9
FLAG:  coh<0.5 OR safe<0.6 OR rep>0.7
PASS:  else.  Actions: FLAG→BLOCK (fail-closed)
```
**Файл:** [doubt_engine.py:384-447](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/doubt_engine.py#L384-L447)

---

## 11. Shared Global Attention

### 11.1 ✅ QK-Norm + Learnable Temperature
```
Q = L2_norm(W_Q · h),  K = L2_norm(W_K · h)
scale = exp(log_temperature)                         — learnable
attn = softmax(Q · K^T × scale) · V
```
**Файл:** [brain_core.py:202-252](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L202-L252)

---

## 12. ✅ TTT-LoRA
```
for step in 1..3:
  loss = CE(model(x + B·A·x), targets)
  A -= lr · ∂loss/∂A,  B -= lr · ∂loss/∂B
```
**Файл:** [brain_core.py:281-339](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L281-L339)

---

## 13. SNN Spike Bus

### 13.1 ✅ Signal
```
spike ∈ {-1, 0, +1}                                  — 1.58 bit
payload: INT8 bytes = struct.pack('b', clamp(v, -128, 127))
```
**Файл:** [spike_bus.py](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/core/runtime/spike_bus.py)

---

## 14. Embedding

### 14.1 ✅ Vaswani Scaling
```
x = E[token_id] × √d_model
```
**Файл:** [brain_core.py:528](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L528)

### 14.2 ✅ Weight Tying
```
lm_head.weight = embedding.weight
```
**Файл:** [brain_core.py:438](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/brain_core.py#L438)

---

## 15. ✅ Memory Injector
```
gate = σ(W_gate([h_mean; mem_vec]))
signal = W_proj([h_mean; mem_vec])
x += (gate · signal).unsqueeze(1)
```
**Файл:** [tars_block.py:53-63](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/tars_block.py#L53-L63)

---

## 16. ✅ NoveltyGate
```
sim = cos_similarity(h_old, h_new)
if sim > 0.95: output = residual (skip, ~0 compute)
```
**Файл:** [tars_block.py:186-191](file:///c:/Users/Public/Tarsfull/TarsSSM-Py/brain/mamba2/core/tars_block.py#L186-L191)

---

## 17. Training Formulas

### 17.1 🔶 UMOT Loss (Alternating Batches)
```
L ∈ {CE, SFT, DPO, Safety, CoT, Personality, FC}
Each step = ONE loss with FULL gradient (не смесь!)
```

### 17.2 🔶 Muon (Newton-Schulz₅)
```
X_{k+1} = X_k · (1.5·I - 0.5·X_k^T·X_k)           — 5 iterations
G_orth = NS₅(G)
W ← W - η · G_orth
```

### 17.3 🔶 AdamW
```
m = β₁·m + (1-β₁)·g
v = β₂·v + (1-β₂)·g²
W ← W·(1-η·λ) - η·m̂/(√v̂+ε)
```

### 17.4 🔶 WSD Schedule
```
5% linear warmup → 75% stable → 20% cosine decay → 0.1×η
```

### 17.5 🔶 EMA Self-Distillation
```
θ_ema = 0.999·θ_ema + 0.001·θ
L_distill = KL(p_student ∥ p_ema) · T²
```

### 17.6 🔶 DPO
```
L = -log σ(β·(log π_θ(y_w)/π_ref(y_w) - log π_θ(y_l)/π_ref(y_l)))
```

### 17.7 🔶 GaLore
```
P = SVD_top_r(∇L), r=64
G_low = P^T · G  →  states in ℝ^{r×n}, -65% memory
```

### 17.8 🔶 Sequence Packing (FFD)
```
sorted_by_length(seqs) → first_fit_decreasing(max=4096)
45% → 99% GPU utilization
```

### 17.9 🔶 Stochastic Depth
```
u ~ Uniform(0,1)
if u < p_drop: y = x                                 — skip block
else: y = Block(x)/(1-p_drop) + x                   — rescaled
```

### 17.10 🔶 Cooperative STE
```
19% more efficient than standard STE
```

### 17.11 🔶 TALS (Ternary-Aware Label Smoothing)
```
target = (1-ε)·one_hot + ε/V                        — zero runtime cost
```

### 17.12 🔶 PCGrad
```
if cos(g_ssd, g_wkv) < 0:
  g_proj = g_ssd - (g_ssd·g_wkv/‖g_wkv‖²)·g_wkv
```

### 17.13 🔶 Safety Contrastive
```
L = max(0, d(anchor,pos) - d(anchor,neg) + margin)
margin = 0.5, 1500 safe + 500 harmful pairs
```

---

## 18. Safety Formulas

### 18.1 🔶 SSM State Bound
```
assert |s| < 32,000    every 100 tokens
```

### 18.2 🔶 Memory Bound
```
assert RSS < 700 MB    every 1000 generations
```

### 18.3 🔶 NaN Guard
```
ring = deque(maxlen=3)
NaN detected → rollback to ring[-1]
```

### 18.4 🔶 Atomic Write
```
write(tmpfile) → fsync → os.replace(tmpfile, target)
```

### 18.5 🔶 Checksummed LoRA
```
SHA256(lora) on every load.  Fallback: latest→previous→base
```

---

## 19. Memory Formulas

### 19.1 🔶 SDM Write/Read
```
cos_sim = (q · addr) / (‖q‖·‖a‖)
top5 = argmax_5(cos_sim)
content[top5] += α·(value - content[top5])
strength[top5] += 1.0
```

### 19.2 🔶 Titans
```
surprise = ‖x - M·x‖²
if surprise > θ: M ← M + η·(x-M·x)·x^T
```

### 19.3 🔶 Matryoshka 2-Stage
```
Fast: e[:64] → top-50  |  Full: e[:384] → top-5
```

### 19.4 🔶 User Twin EMA
```
twin = 0.95·twin + 0.05·observed
```

---

## 20. Inference Optimizations

### 20.1 🔶 Early Exit
```
confidence = max(softmax(E^T · h))
if confidence > 0.9 → emit token, skip remaining blocks
```

### 20.2 🔶 FlashSigmoid
```
γ = 0.5 + 0.25·x      (no exp, linear approximation)
```

### 20.3 🔶 MoD (Mixture of Depths)
```
r = σ(W_r · x)
if r < threshold → skip block (0 compute)
```

### 20.4 🔶 Diff Transformer
```
attn = softmax(Q₁K₁^T/√d) - λ·softmax(Q₂K₂^T/√d)
```

### 20.5 🔶 SmoothQuant
```
Y = (X · S⁻¹) · (S · W)   INT8 matmul path
```

---

## 21. Night Cycle Formulas

### 21.1 🔶 SPIN Self-Play (4 iter)
```
Generate y ~ π_θ(·|x)
DPO: L = -log σ(β·log_ratio)
LoRA only, η = 3.6e-4 (3e-4 × 1.2 STE compensation)
```

### 21.2 🔶 Hindsight Distillation
```
User corrected X→Y: L = CE(model(context), Y)
```

### 21.3 🔶 PoI Gate
```
assert score_after ≥ score_before - 0.05
FAIL → rollback LoRA
```

### 21.4 🔶 CQS
```
CQS = 0.3·coherence + 0.3·relevance + 0.2·safety + 0.2·diversity
```

### 21.5 🔶 SDM Decay
```
strengths *= 0.95   (nightly)
dead = strengths < 0.01 → cleanup if >30%
```

### 21.6 🔶 Weight DNA
```
SVD fingerprint (800 bytes, 0.1s)
drift > 0.3 → WARNING  |  drift > 0.6 → BLOCK
```

---

## 📊 Сводка

| Категория | ✅ | 🔶 | Всего |
|-----------|:---:|:---:|:-----:|
| SSD (Mamba-2) | 4 | 0 | 4 |
| WKV-7 GatedDeltaNet | 4 | 0 | 4 |
| WuNeng Fusion | 2 | 0 | 2 |
| BitNet | 4 | 0 | 4 |
| RMSNorm | 1 | 0 | 1 |
| SwiGLU | 1 | 1 | 2 |
| RoPE | 1 | 0 | 1 |
| MoLE | 6 | 0 | 6 |
| MinGRU | 3 | 0 | 3 |
| DoubtEngine | 3 | 0 | 3 |
| Attention | 1 | 0 | 1 |
| TTT-LoRA | 1 | 0 | 1 |
| Spike Bus | 1 | 0 | 1 |
| Embedding | 2 | 0 | 2 |
| Memory Inject | 1 | 0 | 1 |
| NoveltyGate | 1 | 0 | 1 |
| Training | 0 | 13 | 13 |
| Safety | 0 | 5 | 5 |
| Memory | 0 | 4 | 4 |
| Inference Opt | 0 | 5 | 5 |
| Night Cycle | 0 | 6 | 6 |
| **ИТОГО** | **36** | **34** | **70** |

---

> 📐 **70 формул. 36 реализованы. 34 запланированы (Phase 2-3).**  
> **Каждая ✅ → кликабельная ссылка на строку кода.**
