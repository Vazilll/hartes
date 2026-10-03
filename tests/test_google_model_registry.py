"""
tests/test_google_model_registry.py
====================================
Test suite for Google Model Registry:
- Registry of verified latest open-source Google models on Hugging Face (2025-2026)
- Role-based retrieval: Code Infilling, Recurrent O(1) Memory, Vision/Computer Use,
  Time-Series Forecasting, Guardrails, J-Space Embeddings.
- Hardware targeting: NPU, GPU Flash, CPU, Cloud.
"""

import pytest
from vazus_core.engine.google_model_registry import (
    GoogleModelRegistry,
    ModelRole,
    GoogleModelSpec,
)


def test_registry_initialization():
    registry = GoogleModelRegistry()
    all_models = registry.list_models()
    assert len(all_models) >= 6


def test_lookup_by_role():
    registry = GoogleModelRegistry()
    
    # RecurrentGemma for O(1) memory
    recurrent = registry.get_by_role(ModelRole.RECURRENT_AGENT_MEMORY)
    assert recurrent is not None
    assert "recurrentgemma" in recurrent.huggingface_repo.lower()
    assert recurrent.state_complexity == "O(1)"

    # PaliGemma 2 for Computer Use / Vision
    vlm = registry.get_by_role(ModelRole.COMPUTER_USE_VISION)
    assert vlm is not None
    assert "paligemma2" in vlm.huggingface_repo.lower()
    assert vlm.multimodal is True

    # CodeGemma for code completion
    coder = registry.get_by_role(ModelRole.CODE_INFILLING)
    assert coder is not None
    assert "codegemma" in coder.huggingface_repo.lower()

    # TimesFM 2.0 for forecasting
    forecaster = registry.get_by_role(ModelRole.TIME_SERIES_FORECASTING)
    assert forecaster is not None
    assert "timesfm" in forecaster.huggingface_repo.lower()

    # EmbeddingGemma for J-Space 768D
    embedder = registry.get_by_role(ModelRole.J_SPACE_EMBEDDINGS)
    assert embedder is not None
    assert "embeddinggemma" in embedder.huggingface_repo.lower()


def test_device_compatibility():
    registry = GoogleModelRegistry()
    npu_models = registry.get_models_for_device("NPU")
    assert len(npu_models) >= 2

    gpu_models = registry.get_models_for_device("GPU")
    assert len(gpu_models) >= 4


def test_prompt_formatting_and_specs():
    registry = GoogleModelRegistry()
    spec = registry.get_model("google/paligemma2-3b-mix-224")
    assert spec is not None
    assert spec.parameters == "3B"
    assert spec.license == "Gemma"
