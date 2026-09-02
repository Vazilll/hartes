# Project: Gemma 4 E2B IT NPU Deployment & J-Space Bus Integration

## Architecture
Gemma 4 E2B IT NPU Runtime on Intel Core Ultra (Meteor Lake `Intel(R) AI Boost` NPU 3720) via OpenVINO 2026.3.0.
The subsystem comprises:
1. **Model & Compiler Layer**: OpenVINO IR model (`OpenVINO/gemma-4-E2B-it-int4-ov` / INT4 asymmetric quantized) compiled for `NPU` device with persistent driver blob caching (`CACHE_DIR`), `NPU_TURBO=True`, `NPU_TILES=2`, `PERFORMANCE_HINT=LATENCY`, and static shape bounding (`[1, 128]` to `[1, 2048]`).
2. **Inference & Telemetry Engine (`vazus_core/engine/gemma4_npu_engine.py`)**: Programmatic Python runtime providing asynchronous non-blocking infer request dispatch (`infer_request.start_async()`, `infer_request.wait()`), streaming token generation with low latency, background CPU utilization tracking (`psutil` background sampler), and power efficiency profiling (sub-5W TDP, CPU load <= 10%).
3. **J-Space Cognitive Bus Tap (`vazus_core/global_j_workspace.py`)**: Direct forward-pass internal activation extraction from the pre-LM-head RMSNorm / hidden states, projected and $L_2$-normalized to 768-dimensional unit vectors ($\|v\|_2 \approx 1.0$) for zero-overhead multi-agent cognitive broadcasting.
4. **4-Tier E2E Verification Benchmark (`tests/test_gemma4_npu.py`)**: Dual-mode standalone CLI & pytest verification suite validating NPU target execution, <=10% CPU load, >=10 t/s throughput, unit-normalized activations, and zero regressions.

```
+--------------------------------------------------------------------------------+
|                        Prompt / Subagent Cognitive Request                     |
+--------------------------------------------------------------------------------+
                                       |
                                       v
+--------------------------------------------------------------------------------+
|                       Gemma4NPUEngine (Python Runtime)                         |
|     (vazus_core/engine/gemma4_npu_engine.py - Streamer, Tokenizer, Telemetry)   |
+--------------------------------------------------------------------------------+
                                       |
        +------------------------------+------------------------------+
        |                                                             |
        v                                                             v
+----------------------------------+          +----------------------------------+
|    Intel(R) AI Boost NPU 3720    |          |  J-Space Activation Tap (768D)   |
|   (OpenVINO Compiled IR Model)   |          |    (Pre-LM Norm -> L2-Norm)      |
|  • INT4 Asymmetric Quantization  |          |  • len(v) == 768, ||v||2 ≈ 1.0   |
|  • 2 Compute Tiles, Turbo Mode   |          |  • Broadcast to GlobalJWorkspace |
|  • Sub-5W, <=10% Host CPU Load   |          +----------------------------------+
|  • >= 10 tokens/second Decode    |
+----------------------------------+
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | OpenVINO NPU Model Acquisition | Acquire Gemma 4 E2B IT OpenVINO INT4 IR model & tokenizer definitions in `C:\vazus\models\` | M1 | Survey Exp 1 |
| 2 | NPU Level Zero Compilation Config | Configure OpenVINO NPU properties (`CACHE_DIR`, `NPU_TURBO`, `NPU_TILES=2`, `LATENCY`) | M1 | Survey Exp 1 |
| 3 | Static Shape Bounding & VPUX Stability | Implement static/bounded input shapes to guarantee Level0 VPUX NPU compiler stability | M1 | Survey Exp 2,3 |
| 4 | Programmatic Engine Interface | Implement `Gemma4NPUEngine` in `vazus_core/engine/gemma4_npu_engine.py` | M2 | Survey Exp 2 |
| 5 | Asynchronous Streaming Generation | Implement `generate_stream()` and `generate()` using non-blocking OpenVINO infer requests | M2 | Survey Exp 2 |
| 6 | Real-time Hardware Telemetry | Implement background CPU utilization sampler ensuring <= 10% host CPU load during generation | M2 | Survey Exp 2 |
| 7 | Direct J-Space Activation Extraction | Extract pre-LM-head hidden states ($h_L$), project to 768D, and $L_2$-normalize ($\|v\|_2 \approx 1.0$) | M3 | Survey Exp 3 |
| 8 | GlobalJWorkspace Concept Broadcast | Feed extracted 768D concepts into `GlobalJWorkspace` without double-forward re-encoding | M3 | Survey Exp 3 |
| 9 | Standalone Benchmark Script | Implement `tests/test_gemma4_npu.py` with 4-tier verification and exit code 0 | M4 | Survey Exp 3 |
| 10 | Dual-Mode E2E Test Suite | Enable both CLI standalone execution with formatted telemetry and full pytest test runner | M4 | Survey Exp 3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Model Acquisition & OpenVINO NPU Compilation | Download/prepare Gemma 4 INT4 IR model, configure NPU properties and blob caching | none | PLANNED |
| M2 | Python Runtime & Telemetry Engine | Implement `Gemma4NPUEngine` in `vazus_core/engine/` with async streaming and CPU load telemetry | M1 | PLANNED |
| M3 | J-Space Activation Extraction & Cognitive Bus | Implement zero-overhead 768D hidden state tap, $L_2$-norm, and `GlobalJWorkspace` integration | M2 | PLANNED |
| M4 | E2E Benchmark Suite & Hardware Verification | Implement `tests/test_gemma4_npu.py` validating >=10 t/s, <=10% CPU, and 100% test pass | M3 | PLANNED |

## Interface Contracts
### `Gemma4NPUEngine` ↔ `vazus_core.engine` & `GlobalJWorkspace`
- **Class**: `Gemma4NPUEngine(model_path: str, device: str = "NPU", cache_dir: Optional[str] = None, max_seq_len: int = 512)`
- **`generate(prompt: str, max_new_tokens: int = 128, temperature: float = 0.7) -> GenerationResult`**
  - Returns `GenerationResult(text: str, tokens_generated: int, throughput_tps: float, cpu_utilization_pct: float, j_space_concept: Optional[JSpaceConcept])`
- **`generate_stream(prompt: str, max_new_tokens: int = 128) -> Iterator[str]`**
  - Yields token strings incrementally as generated on NPU.
- **`extract_j_space_activation(prompt_or_tokens: Union[str, List[int]]) -> List[float]`**
  - Returns 768-dimensional $L_2$-normalized float vector (`len == 768`, $\lvert \|v\|_2 - 1.0 \rvert < 10^{-3}$).
- **`get_telemetry() -> EngineTelemetry`**
  - Returns current device info, NPU tile count, CPU utilization history, and memory stats.

## Code Layout
```
C:\vazus\
├── vazus_core/
│   ├── engine/
│   │   ├── gemma4_npu_engine.py   # Primary Gemma 4 NPU runtime, streaming, telemetry & J-Space tap
│   │   ├── supergraph_bridge.py   # Vector synchronization bridge
│   │   └── llm_client.py          # Unified client bindings
│   ├── global_j_workspace.py      # GlobalJWorkspace concept hub (768D bounded bottleneck K=16)
│   ├── embeddings.py              # 768D embedding vector models
│   └── memory/
│       └── embeddings.py          # Vector sanitization, AVX-512 cosine search
├── models/
│   ├── gemma-4-e2b-it-int4-ov/    # OpenVINO IR model, tokenizers, config
│   └── .ov_cache/                 # Persistent NPU compiled driver blobs (.blob)
├── tests/
│   ├── test_gemma4_npu.py         # Standalone 4-tier benchmark & acceptance verification suite
│   ├── test_j_space_skill_state.py# J-Space cognitive state integration tests
│   └── test_openvino_npu.py       # Base OpenVINO NPU hardware tests
└── .agents/                       # Subagent coordination & audit metadata
```
