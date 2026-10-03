"""
vazus_core :: Gemma 4 VLMPipeline — GPU/CPU инференс с минимальным потреблением
Использует openvino_genai 2026.4+ и полный набор sub-моделей Gemma 4:
  - openvino_language_model            (1.3 GB)
  - openvino_text_embeddings_model     (384 MB)
  - openvino_text_embeddings_per_layer_model  (2.2 GB — per-layer PLE)
  - openvino_vision_embeddings_model   (161 MB)
  - openvino_tokenizer / openvino_detokenizer
"""

import os
import time
import sys
import io

# Fix Windows PowerShell cp1252 → UTF-8 (иначе кириллица крашит print)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Отключаем телеметрию OpenVINO для исключения фоновых SSL-крашей
os.environ["OPENVINO_TELEMETRY_ENABLED"] = "0"
os.environ["OV_ENABLE_PROFILING"] = "0"

import openvino_genai as ov_genai

MODEL_DIR = "C:/vazus/models/gemma-4-e2b-it-int4-ov"

def check_model_complete() -> bool:
    """Проверяет наличие всех нужных файлов."""
    required_bins = [
        "openvino_language_model.bin",
        "openvino_text_embeddings_model.bin",
        "openvino_text_embeddings_per_layer_model.bin",
        "openvino_vision_embeddings_model.bin",
        "openvino_tokenizer.bin",
        "openvino_detokenizer.bin",
    ]
    missing = []
    for f in required_bins:
        p = os.path.join(MODEL_DIR, f)
        if not os.path.exists(p):
            missing.append(f)
    if missing:
        print(f"[!] Missing files: {missing}")
        return False
    return True


def load_pipeline(device: str = "GPU") -> ov_genai.VLMPipeline:
    """
    Загружает VLMPipeline на указанный device с минимальным энергопотреблением.
    device: 'GPU' (iGPU Intel Xe), 'CPU', или 'AUTO'
    """
    device_config: dict = {}

    if device == "GPU":
        device_config = {
            # Один поток — минимум VRAM и памяти
            "NUM_STREAMS": "1",
            # Latency hint — не держать лишних инференс-очередей
            "PERFORMANCE_HINT": "LATENCY",
            # GPU кэш скомпилированных ядер
            "CACHE_DIR": "C:/vazus/models/.ov_cache",
        }
    elif device == "CPU":
        device_config = {
            "NUM_STREAMS": "1",
            "PERFORMANCE_HINT": "LATENCY",
            "INFERENCE_NUM_THREADS": "4",  # 4 потока вместо 16 — меньше энергопотребления
            "ENABLE_CPU_PINNING": "NO",
            "CACHE_DIR": "C:/vazus/models/.ov_cache",
        }

    print(f"[*] Loading VLMPipeline on {device}...", flush=True)
    t0 = time.time()
    pipe = ov_genai.VLMPipeline(MODEL_DIR, device, **device_config)
    print(f"[+] Loaded in {time.time() - t0:.1f}s", flush=True)
    return pipe


def build_gen_config(max_tokens: int = 128, temperature: float = 0.7) -> ov_genai.GenerationConfig:
    """Минимальная конфигурация генерации."""
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = max_tokens
    cfg.temperature = temperature
    cfg.top_p = 0.9
    cfg.do_sample = True
    return cfg


def generate(pipe: ov_genai.VLMPipeline, prompt: str, max_tokens: int = 128) -> str:
    """Запускает генерацию и возвращает текст с метриками."""
    cfg = build_gen_config(max_tokens)
    t0 = time.time()
    result = pipe.generate(prompt, generation_config=cfg)
    elapsed = time.time() - t0
    # Считаем токены по словам (приблизительно)
    approx_tokens = len(result.split())
    tps = approx_tokens / elapsed if elapsed > 0 else 0
    print(f"\n[perf] ~{approx_tokens} words in {elapsed:.1f}s (~{tps:.1f} tok/s)", flush=True)
    return str(result)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gemma 4 VLMPipeline")
    parser.add_argument("--device", default="GPU", choices=["GPU", "CPU", "AUTO"],
                        help="Устройство для инференса")
    parser.add_argument("--prompt", default="Привет! Кратко объясни как работает Intel AI Boost NPU.",
                        help="Промпт для генерации")
    parser.add_argument("--max-tokens", type=int, default=128)
    args = parser.parse_args()

    if not check_model_complete():
        print("[!] Model is incomplete. Please wait for per_layer_model.bin to finish downloading.")
        sys.exit(1)

    print(f"[*] openvino_genai {ov_genai.__version__}", flush=True)
    pipe = load_pipeline(device=args.device)

    print(f"\n[prompt] {args.prompt}\n{'='*60}", flush=True)
    answer = generate(pipe, args.prompt, args.max_tokens)
    print(f"\n[answer] {answer}")
