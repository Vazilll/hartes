"""
tests/test_memory_footprint_optimizer.py
========================================
Тесты для модуля MemoryFootprintOptimizer и его интеграции с SiliconOrchestrator:
1. Проверка конфигураций профилей (EDGE_LOW_VRAM, BALANCED, CLOUD_OFFLOAD_MAX).
2. Валидация опций Ollama (ограничение контекста, квантованный KV-кэш).
3. Проверка статических шейпов и настроек NPU OpenVINO.
4. Расчет теоретического расхода памяти и процентов экономии VRAM.
5. Интеграция с SiliconOrchestrator (метаданные, маршрутизация, эскалация при переполнении бюджета).
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path("C:/vazus")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.engine.memory_footprint_optimizer import (
    MemoryFootprintOptimizer,
    HardwareProfile,
    DEFAULT_PROFILES,
)
from vazus_core.engine.silicon_orchestrator import SiliconOrchestrator


def test_default_profiles_and_switching():
    """Проверяет переключение профилей и корректность параметров."""
    optimizer = MemoryFootprintOptimizer(profile=HardwareProfile.EDGE_LOW_VRAM)
    assert optimizer.profile == HardwareProfile.EDGE_LOW_VRAM
    assert optimizer.config.num_ctx == 2048
    assert optimizer.config.low_vram is True
    assert optimizer.config.f16_kv is False

    optimizer.set_profile(HardwareProfile.BALANCED)
    assert optimizer.profile == HardwareProfile.BALANCED
    assert optimizer.config.num_ctx == 4096
    assert optimizer.config.low_vram is False

    optimizer.set_profile(HardwareProfile.CLOUD_OFFLOAD_MAX)
    assert optimizer.profile == HardwareProfile.CLOUD_OFFLOAD_MAX
    assert optimizer.config.num_ctx == 1024
    assert optimizer.config.offload_token_threshold == 500


def test_ollama_options_generation():
    """Проверяет формирование словаря options для Ollama API."""
    optimizer = MemoryFootprintOptimizer(profile=HardwareProfile.EDGE_LOW_VRAM)
    opts = optimizer.get_ollama_options(model_name="gemma4:e2b")

    assert opts["num_ctx"] == 2048
    assert opts["low_vram"] is True
    assert opts["f16_kv"] is False
    assert opts["num_predict"] == 128
    assert opts["num_thread"] == 4

    # Проверка для Recurrent / Griffin модели (линейная память O(1))
    opts_recurrent = optimizer.get_ollama_options(model_name="recurrent_gemma_2b")
    assert opts_recurrent["num_ctx"] == 4096  # расширенный контекст без риска OOM


def test_openvino_config_npu():
    """Проверяет генерацию конфигурации OpenVINO NPU со статическими шейпами."""
    optimizer = MemoryFootprintOptimizer()
    cfg_npu = optimizer.get_openvino_config(device="NPU")

    assert cfg_npu["STATIC_SHAPES"] is True
    assert cfg_npu["BATCH_SIZE"] == 1
    assert cfg_npu["MAX_SEQ_LEN"] == 128
    assert cfg_npu["PERFORMANCE_HINT"] == "LATENCY"
    assert cfg_npu["ESTIMATED_NPU_RAM_MB"] > 0

    cfg_gpu = optimizer.get_openvino_config(device="GPU")
    assert cfg_gpu["PERFORMANCE_HINT"] == "THROUGHPUT"


def test_memory_footprint_estimation():
    """Проверяет математический расчет экономии VRAM."""
    optimizer = MemoryFootprintOptimizer(profile=HardwareProfile.EDGE_LOW_VRAM)
    est = optimizer.estimate_memory_footprint(model_name="gemma4:e2b", quantized_kv=True)

    assert est["weights_int4_mb"] == 1250.0
    assert est["kv_cache_mb"] > 0
    assert est["total_footprint_mb"] < 2000.0  # Укладывается в бюджет < 2 ГБ!
    assert est["savings_percentage"] > 70.0    # Экономия более 70% относительно 32k FP16
    assert est["context_budget"] == 2048


def test_should_offload_to_cloud():
    """Проверяет логику эскалации в облако при риске OOM или профиле Zero VRAM."""
    optimizer = MemoryFootprintOptimizer(profile=HardwareProfile.EDGE_LOW_VRAM)

    # Короткий промпт — помещается локально
    offload, _ = optimizer.should_offload_to_cloud("Привет, как дела?")
    assert offload is False

    # Очень длинный промпт (>1500 токенов) — эскалация в облако
    long_prompt = "слово " * 1600
    offload, reason = optimizer.should_offload_to_cloud(long_prompt)
    assert offload is True
    assert "Превышен порог" in reason

    # Профиль CLOUD_OFFLOAD_MAX всегда эскалирует в облако (Zero VRAM)
    optimizer.set_profile(HardwareProfile.CLOUD_OFFLOAD_MAX)
    offload_cloud, reason_cloud = optimizer.should_offload_to_cloud("Любой запрос")
    assert offload_cloud is True
    assert "CLOUD_OFFLOAD_MAX" in reason_cloud


def test_silicon_orchestrator_with_optimizer(tmp_path):
    """Интеграционный тест: SiliconOrchestrator использует оптимизатор памяти."""
    db_file = str(tmp_path / "test_silicon_opt.db")
    orch = SiliconOrchestrator(
        db_path=db_file,
        footprint_profile=HardwareProfile.EDGE_LOW_VRAM,
    )

    assert orch.optimizer.profile == HardwareProfile.EDGE_LOW_VRAM

    # Проверка получения профиля и плана
    profile_stats = orch.get_memory_profile_stats()
    assert profile_stats["active_profile"] == "EDGE_LOW_VRAM"
    assert profile_stats["ollama_options"]["num_ctx"] == 2048

    plan = orch.get_heterogeneous_plan()
    assert "tier_1_sensory_npu" in plan
    assert "tier_2_flash_gpu" in plan
    assert "tier_3_cloud_antigravity" in plan

    # Обработка запроса
    with patch.object(orch, "_generate_local", return_value=("Локальный ответ", "MOCK_DEVICE", 10, 15.0, 1.0)):
        output = orch.process("Краткий запрос")
        assert output.memory_footprint_metadata["active_profile"] == "EDGE_LOW_VRAM"
        assert "footprint_estimate" in output.memory_footprint_metadata
        assert output.memory_footprint_metadata["footprint_estimate"]["total_footprint_mb"] < 2000.0
