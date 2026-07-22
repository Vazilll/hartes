#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  TARS HELIX — Colab Test Script
═══════════════════════════════════════════════════════════════

Run this on Google Colab to verify the full model pipeline.

Usage (Colab cell):
    !pip install torch einops
    !python colab_test.py

Tests:
  1. Model instantiation (TarsHelixFull + TarsHelixLite)
  2. Forward pass with random data
  3. Loss computation
  4. Autoregressive generation (5 tokens)
  5. Parameter count & graduated layout verification
"""

import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
logger = logging.getLogger("TARS.Test")

# ═══════════════════════════════════════
# 0. Environment check
# ═══════════════════════════════════════
try:
    import torch
    logger.info(f"PyTorch {torch.__version__}")
    logger.info(f"CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
        logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB")
except ImportError:
    print("ERROR: PyTorch not installed. Run: pip install torch")
    sys.exit(1)

try:
    import einops
except ImportError:
    print("ERROR: einops not installed. Run: pip install einops")
    sys.exit(1)

# Add project root to path
import os
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
dtype = torch.float32  # Use fp32 for testing stability


def test_full_model():
    """Test TarsHelixFull — graduated layout + MoLE + PersonalityAdapter."""
    from config import TarsConfig
    from brain.mamba2.core.model_full import TarsHelixFull
    
    logger.info("=" * 60)
    logger.info("TEST 1: TarsHelixFull instantiation")
    logger.info("=" * 60)
    
    # Small config for quick testing
    cfg = TarsConfig(
        d_model=256,        # Reduced for testing (prod: 1024)
        n_layers=10,        # Reduced for testing (prod: 20)
        vocab_size=1024,    # Reduced for testing (prod: 48256)
        d_state=32,         # Reduced (prod: 64)
        headdim=32,         # Reduced (prod: 64)
        expand=2,
        ngroups=1,
        chunk_size=16,
        quant_mode="fp16",
        graduated_layout=True,
        mole_every_n=2,     # More frequent for test coverage
        n_experts=4,
        expert_rank=4,
        top_k_experts=2,
        personality_style_dim=64,
        personality_max_passes=2,
    )
    
    t0 = time.time()
    model = TarsHelixFull(cfg).to(device)
    t_init = time.time() - t0
    
    n_params = sum(p.numel() for p in model.parameters())
    logger.info(f"Model created in {t_init:.2f}s")
    logger.info(f"Parameters: {n_params/1e6:.2f}M")
    
    # Verify graduated layout
    for i, block in enumerate(model.blocks):
        mode = block.block_mode
        has_mole = block.mole is not None
        logger.info(f"  Block {i:2d}: mode={mode:4s}, MoLE={'✅' if has_mole else '❌'}")
    
    # ═══ Test 2: Forward pass ═══
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Forward pass")
    logger.info("=" * 60)
    
    B, L = 2, 64  # batch=2, seq_len=64
    input_ids = torch.randint(0, cfg.vocab_size, (B, L), device=device)
    labels = torch.randint(0, cfg.vocab_size, (B, L), device=device)
    
    t0 = time.time()
    with torch.amp.autocast(device_type=str(device), enabled=(device.type == 'cuda')):
        result = model(input_ids, labels=labels)
    t_fwd = time.time() - t0
    
    logits = result['logits']
    loss = result['loss']
    aux_loss = result['aux_loss']
    
    logger.info(f"Forward pass: {t_fwd*1000:.0f}ms")
    logger.info(f"Logits shape: {logits.shape}")
    logger.info(f"Loss: {loss.item():.4f} (LM: {result['lm_loss'].item():.4f}, Aux: {aux_loss.item():.4f})")
    
    assert logits.shape == (B, L, cfg.vocab_size), f"Wrong shape: {logits.shape}"
    assert not torch.isnan(loss), "Loss is NaN!"
    assert not torch.isinf(loss), "Loss is Inf!"
    logger.info("✅ Forward pass OK")
    
    # ═══ Test 3: Backward pass ═══
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Backward pass")
    logger.info("=" * 60)
    
    t0 = time.time()
    loss.backward()
    t_bwd = time.time() - t0
    
    # Check for NaN gradients
    nan_grads = 0
    total_grads = 0
    for name, p in model.named_parameters():
        if p.grad is not None:
            total_grads += 1
            if torch.isnan(p.grad).any():
                nan_grads += 1
                logger.warning(f"NaN gradient in {name}")
    
    logger.info(f"Backward pass: {t_bwd*1000:.0f}ms")
    logger.info(f"Gradients: {total_grads} params, {nan_grads} NaN")
    assert nan_grads == 0, f"{nan_grads} parameters have NaN gradients!"
    logger.info("✅ Backward pass OK")
    
    # ═══ Test 4: Generation ═══
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Generation (5 tokens)")
    logger.info("=" * 60)
    
    prompt = torch.randint(0, cfg.vocab_size, (1, 8), device=device)
    
    t0 = time.time()
    generated = model.generate(prompt, max_new_tokens=5, temperature=1.0, top_k=10)
    t_gen = time.time() - t0
    
    logger.info(f"Generation: {t_gen*1000:.0f}ms for 5 tokens")
    logger.info(f"Prompt: {prompt.shape} → Generated: {generated.shape}")
    assert generated.shape[1] >= prompt.shape[1] + 1, "No tokens generated!"
    logger.info("✅ Generation OK")
    
    # ═══ Test 5: PersonalityAdapter stats ═══
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: PersonalityAdapter")
    logger.info("=" * 60)
    
    logger.info(f"Avg convergence passes: {model.personality.avg_passes:.1f}")
    logger.info(f"Style embed norm: {model.personality.style_embed.norm().item():.4f}")
    logger.info("✅ PersonalityAdapter OK")
    
    return model


def test_lite_model():
    """Test TarsHelixLite for comparison."""
    from config import TarsConfig
    from brain.mamba2.core.model_lite import TarsHelixLite
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: TarsHelixLite (comparison)")
    logger.info("=" * 60)
    
    cfg = TarsConfig(
        d_model=256,
        n_layers=10,
        vocab_size=1024,
        d_state=32,
        headdim=32,
        quant_mode="fp16",
    )
    
    model = TarsHelixLite(cfg).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    logger.info(f"LITE params: {n_params/1e6:.2f}M")
    
    B, L = 2, 64
    input_ids = torch.randint(0, cfg.vocab_size, (B, L), device=device)
    labels = torch.randint(0, cfg.vocab_size, (B, L), device=device)
    
    result = model(input_ids, labels=labels)
    logger.info(f"LITE loss: {result['loss'].item():.4f}")
    logger.info("✅ TarsHelixLite OK")


def test_production_size():
    """Test with production dimensions (dry run on CPU)."""
    from config import TarsConfig
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST 7: Production config (dry param count)")
    logger.info("=" * 60)
    
    cfg = TarsConfig()  # Default = production params
    
    # Calculate expected param count without instantiating (saves RAM)
    d = cfg.d_model
    V = cfg.vocab_size
    L = cfg.n_layers
    expand = cfg.expand
    d_inner = d * expand
    d_state = cfg.d_state
    nheads = d_inner // cfg.headdim
    ngroups = cfg.ngroups
    
    # Embedding: V × d (shared with LM head)
    emb_params = V * d
    
    # Per block (approximate): in_proj + conv + SSD params + WKV params + fusion + out_proj
    d_mamba = 2 * d_inner + 2 * ngroups * d_state + nheads
    d_rwkv = 5 * d_state
    in_proj = d * (d_mamba + d_rwkv)
    conv_params = (d_inner + 2 * ngroups * d_state) * 4  # conv1d kernel=4
    out_proj = d_inner * d
    norm_params = d
    fusion_params = d_inner * 2 * 192 + 192 * d_inner  # bottleneck
    swiglu = d_inner * d_inner
    block_params = in_proj + conv_params + out_proj + norm_params + fusion_params + swiglu
    
    # MoLE per block (every 4): each expert = 2 × d × rank, 8 experts + router
    n_mole_blocks = L // cfg.mole_every_n
    mole_per = 8 * 2 * d * cfg.expert_rank + d * 8  # experts + router
    
    total_approx = emb_params + L * block_params + n_mole_blocks * mole_per + d  # + final_norm
    
    logger.info(f"Production config: d={d}, L={L}, V={V}")
    logger.info(f"Estimated params: {total_approx/1e6:.0f}M")
    logger.info(f"Embedding: {emb_params/1e6:.1f}M")
    logger.info(f"Per block: ~{block_params/1e6:.1f}M × {L} = {L*block_params/1e6:.0f}M")
    logger.info(f"MoLE: {n_mole_blocks} blocks × ~{mole_per/1e3:.0f}K = {n_mole_blocks*mole_per/1e6:.1f}M")
    logger.info("✅ Production size estimated")


if __name__ == "__main__":
    logger.info("🧬 TARS HELIX — Full Pipeline Test")
    logger.info(f"Device: {device}")
    logger.info("")
    
    try:
        model = test_full_model()
        test_lite_model()
        test_production_size()
        
        logger.info("\n" + "=" * 60)
        logger.info("🎉 ALL TESTS PASSED")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
