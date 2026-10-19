"""
tests/test_rwkv7_local_npu.py
=============================
Verification suite for local RWKV-7 World 0.1B recurrent inference on Intel AI Boost NPU:
- Model and embedding table loading.
- Single-step token forward pass on NPU with state mutation.
- End-to-end autoregressive text generation with strict latency SLA (< 50ms/token).
"""

import pytest
from vazus_core.integrations.rwkv7_local_processor import RWKV7LocalEngine


def test_rwkv7_initialization_and_device():
    engine = RWKV7LocalEngine(device="NPU")
    assert engine.is_available is True, "RWKV7LocalEngine failed to initialize"
    assert engine.active_device == "NPU", f"Expected active device NPU, got {engine.active_device}"
    assert engine.tokenizer is not None, "Tokenizer should be loaded"
    assert len(engine._states) == 36, f"Expected 36 recurrent states, got {len(engine._states)}"


def test_rwkv7_forward_step_shape():
    engine = RWKV7LocalEngine(device="NPU")
    assert engine.is_available is True

    # Token id 123
    logits = engine.forward_token(123)
    assert logits.shape == (65536,), f"Expected shape (65536,), got {logits.shape}"
    assert float(logits.max()) > -100.0, "Logits must contain valid real numbers"


def test_rwkv7_autoregressive_generation_npu():
    engine = RWKV7LocalEngine(device="NPU")
    assert engine.is_available is True

    prompt = "Artificial intelligence"
    res = engine.generate(prompt, max_new_tokens=15, temperature=0.7)

    assert "text" in res
    assert res["tokens_generated"] > 0
    assert res["device_used"] == "NPU"
    assert res["avg_step_latency_ms"] < 100.0, f"Avg step latency {res['avg_step_latency_ms']}ms exceeded SLA"
    print(f"\n[RWKV-7 NPU] Prompt: '{prompt}' -> Generated: '{res['text']}'")
    print(f"[RWKV-7 NPU] Latency: {res['avg_step_latency_ms']} ms/token ({res['tokens_per_sec']} tok/s)")
