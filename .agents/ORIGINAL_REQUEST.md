# Original User Request

## 2026-09-02T15:58:01Z

Deploy and optimize Google's Gemma 4 E2B IT model to run natively on the Intel AI Boost NPU via OpenVINO, achieving sub-5W power consumption, zero host CPU load, and direct activation extraction for the J-Space cognitive bus.

Working directory: C:\vazus
Integrity mode: development

## Requirements

### R1. Native Model Acquisition & OpenVINO NPU Compilation
Acquire Gemma 4 E2B IT weights in an OpenVINO-compatible format (INT4/INT8 quantized) and compile specifically for the `NPU` device (`Intel(R) AI Boost`) on Meteor Lake.

### R2. Programmatic Python Runtime & Hardware Telemetry
Provide a Python inference class in `vazus_core/engine/` that initializes the model on `NPU`, handles generation with streaming, and records CPU core utilization vs NPU activity during token production.

### R3. J-Space Internal Activation Extraction
Expose an interface to capture the internal token embeddings / hidden states from the forward pass without re-encoding, feeding the `GlobalJWorkspace` concept hub.

### R4. Verification Benchmark Script
Provide an automated standalone verification test demonstrating successful generation on the NPU target, verifying output coherence, and proving CPU utilization remains under 10%.

## Acceptance Criteria

### Hardware & Execution Guardrails
- [ ] Model executes targeting device `NPU` (`Intel(R) AI Boost`).
- [ ] Host CPU core load remains <= 10% during active generation.
- [ ] Throughput achieves >= 10 tokens/second on Intel Core Ultra 5 125U.
- [ ] J-Space activation extraction method returns normalized vectors.
- [ ] Standalone test script `tests/test_gemma4_npu.py` passes 100% with exit code 0.
