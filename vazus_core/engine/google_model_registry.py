"""
vazus_core.engine.google_model_registry
=======================================
Google Open-Weights Model Catalog & Specialized Role Registry for Vazus OS.

Curated from https://huggingface.co/google (2025–2026 releases):
- RecurrentGemma: Griffin linear recurrence with O(1) state complexity for infinite agent loops.
- PaliGemma 2: SigLIP + Gemma 2 VLM for UI grounding, Computer Use, and OCR.
- CodeGemma: Fill-in-the-Middle (FIM) specialized for code completion and test generation.
- EmbeddingGemma: 308M parameter multilingual embeddings directly compatible with J-Space 768D.
- TimesFM 2.0: 500M time-series foundation model with quantile prediction.
- ShieldGemma: Fast 2B safety and guardrail classification.
- Gemma 3 / 4: 128k context multimodal & edge NPU foundation models.

Zero Automatic Downloads Guarantee:
Provides structural metadata, schemas, tokenizer profiles, and routing bindings
without triggering gigabyte-scale downloads to disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ModelRole(str, Enum):
    CODE_INFILLING = "CODE_INFILLING"
    RECURRENT_AGENT_MEMORY = "RECURRENT_AGENT_MEMORY"
    COMPUTER_USE_VISION = "COMPUTER_USE_VISION"
    TIME_SERIES_FORECASTING = "TIME_SERIES_FORECASTING"
    J_SPACE_EMBEDDINGS = "J_SPACE_EMBEDDINGS"
    GUARDRAILS_SYSTEM_ONE = "GUARDRAILS_SYSTEM_ONE"
    MULTIMODAL_REASONING = "MULTIMODAL_REASONING"
    EDGE_NPU_REASONING = "EDGE_NPU_REASONING"


@dataclass
class GoogleModelSpec:
    huggingface_repo: str
    name: str
    role: ModelRole
    parameters: str
    context_window: int
    devices: List[str]  # e.g. ["NPU", "GPU", "CPU"]
    multimodal: bool = False
    state_complexity: str = "O(N)"  # "O(1)" for RecurrentGemma, "O(N)" for Transformers
    description: str = ""
    license: str = "Gemma"


class GoogleModelRegistry:
    """
    Centralized registry of verified Google open models mapped to Vazus OS roles.
    """

    def __init__(self) -> None:
        self._models: Dict[str, GoogleModelSpec] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        catalog = [
            GoogleModelSpec(
                huggingface_repo="google/recurrentgemma-2b-it",
                name="RecurrentGemma 2B IT",
                role=ModelRole.RECURRENT_AGENT_MEMORY,
                parameters="2B",
                context_window=8192,
                devices=["NPU", "GPU", "CPU"],
                multimodal=False,
                state_complexity="O(1)",
                description="Griffin architecture (linear recurrences + local attention). Constant memory footprint during generation, perfect for endless agentic loops.",
                license="Gemma",
            ),
            GoogleModelSpec(
                huggingface_repo="google/paligemma2-3b-mix-224",
                name="PaliGemma 2 3B Mix",
                role=ModelRole.COMPUTER_USE_VISION,
                parameters="3B",
                context_window=2048,
                devices=["GPU", "CPU"],
                multimodal=True,
                state_complexity="O(N)",
                description="SigLIP-So400m + Gemma 2. Specialized for UI screen grounding, bounding box coordinate detection, OCR, and Computer Use.",
                license="Gemma",
            ),
            GoogleModelSpec(
                huggingface_repo="google/codegemma-2b",
                name="CodeGemma 2B",
                role=ModelRole.CODE_INFILLING,
                parameters="2B",
                context_window=8192,
                devices=["NPU", "GPU", "CPU"],
                multimodal=False,
                state_complexity="O(N)",
                description="Lightweight code completion model trained on Fill-in-the-Middle (FIM) for real-time IDE pair programming and test drafting.",
                license="Gemma",
            ),
            GoogleModelSpec(
                huggingface_repo="google/embeddinggemma-300m",
                name="EmbeddingGemma 300M",
                role=ModelRole.J_SPACE_EMBEDDINGS,
                parameters="308M",
                context_window=8192,
                devices=["NPU", "GPU", "CPU"],
                multimodal=False,
                state_complexity="O(N)",
                description="Lightweight multilingual text-embedding model based on Gemma 3 architecture for dense semantic search and J-Space memory.",
                license="Gemma",
            ),
            GoogleModelSpec(
                huggingface_repo="google/timesfm-2.0-500m-pytorch",
                name="TimesFM 2.0 500M",
                role=ModelRole.TIME_SERIES_FORECASTING,
                parameters="500M",
                context_window=2048,
                devices=["GPU", "CPU"],
                multimodal=False,
                state_complexity="O(N)",
                description="Time-series foundation model with quantile heads for zero-shot forecasting of academic debts, freelance revenues, and bio-metrics.",
                license="Apache-2.0",
            ),
            GoogleModelSpec(
                huggingface_repo="google/shieldgemma-2b",
                name="ShieldGemma 2B",
                role=ModelRole.GUARDRAILS_SYSTEM_ONE,
                parameters="2B",
                context_window=8192,
                devices=["NPU", "GPU", "CPU"],
                multimodal=False,
                state_complexity="O(N)",
                description="Safety and policy evaluation model. Operates as a fast System 1 pre-execution gate for terminal commands and code mods.",
                license="Gemma",
            ),
            GoogleModelSpec(
                huggingface_repo="google/gemma-3-4b-it",
                name="Gemma 3 4B IT",
                role=ModelRole.MULTIMODAL_REASONING,
                parameters="4B",
                context_window=131072,  # 128k context
                devices=["GPU", "CPU"],
                multimodal=True,
                state_complexity="O(N)",
                description="Multimodal 128k context window open model supporting text and images for comprehensive multi-turn analysis.",
                license="Gemma",
            ),
            GoogleModelSpec(
                huggingface_repo="google/timesfm-3.0-pytorch",
                name="TimesFM 3.0 (Multivariate 330M)",
                role=ModelRole.TIME_SERIES_FORECASTING,
                parameters="330M",
                context_window=4096,
                devices=["GPU", "CPU"],
                multimodal=False,
                state_complexity="O(N)",
                description="Google Research's August 2026 native multivariate time-series foundation model with covariate support and cross-series joint prediction.",
                license="TimesFM Non-Commercial v1.0",
            ),
            GoogleModelSpec(
                huggingface_repo="google/paligemma2-10b-mix-448",
                name="PaliGemma 2 10B Mix 448",
                role=ModelRole.COMPUTER_USE_VISION,
                parameters="10B",
                context_window=4096,
                devices=["GPU", "CPU"],
                multimodal=True,
                state_complexity="O(N)",
                description="High-resolution 10B VLM for sub-pixel screen coordinate detection, dense UI elements, and robust accessibility tree parsing.",
                license="Gemma",
            ),
            GoogleModelSpec(
                huggingface_repo="google/gemma-4-12b-it",
                name="Gemma 4 12B IT (Thinking Reasoning)",
                role=ModelRole.MULTIMODAL_REASONING,
                parameters="12B",
                context_window=262144,  # 256k context
                devices=["GPU", "CPU"],
                multimodal=True,
                state_complexity="O(N)",
                description="Google DeepMind's April/June 2026 Apache-2.0 flagship reasoning model with configurable <|think|> tokens and native audio/vision.",
                license="Apache-2.0",
            ),
            GoogleModelSpec(
                huggingface_repo="google/gemma-4-26b-moe",
                name="Gemma 4 26B MoE",
                role=ModelRole.MULTIMODAL_REASONING,
                parameters="26B",
                context_window=262144,  # 256k context
                devices=["GPU"],
                multimodal=True,
                state_complexity="O(N)",
                description="26B Mixture-of-Experts (MoE) with sparse routing for extreme compute efficiency during complex agent workflows.",
                license="Apache-2.0",
            ),
            GoogleModelSpec(
                huggingface_repo="google/gemma-4-31b-it",
                name="Gemma 4 31B IT",
                role=ModelRole.MULTIMODAL_REASONING,
                parameters="31B",
                context_window=262144,  # 256k context
                devices=["GPU"],
                multimodal=True,
                state_complexity="O(N)",
                description="31B Dense model with frontier coding and mathematical reasoning under Apache-2.0 license.",
                license="Apache-2.0",
            ),
            GoogleModelSpec(
                huggingface_repo="google/gemma-4-e2b",
                name="Gemma 4 Edge 2B",
                role=ModelRole.EDGE_NPU_REASONING,
                parameters="2B",
                context_window=131072,  # 128k context
                devices=["NPU", "GPU", "CPU"],
                multimodal=True,
                state_complexity="O(N)",
                description="Apache-2.0 low-power multimodal edge model for instant offline reasoning on Intel NPU/OpenVINO.",
                license="Apache-2.0",
            ),
        ]

        for spec in catalog:
            self._models[spec.huggingface_repo] = spec

    def list_models(self) -> List[GoogleModelSpec]:
        return list(self._models.values())

    def get_model(self, repo_or_name: str) -> Optional[GoogleModelSpec]:
        query = repo_or_name.lower().strip()
        for repo, spec in self._models.items():
            if repo.lower() == query or spec.name.lower() == query or repo.split("/")[-1].lower() == query:
                return spec
        return None

    def get_by_role(self, role: ModelRole) -> Optional[GoogleModelSpec]:
        for spec in self._models.values():
            if spec.role == role:
                return spec
        return None

    def get_models_for_device(self, device: str) -> List[GoogleModelSpec]:
        dev_upper = device.upper().strip()
        return [m for m in self._models.values() if dev_upper in m.devices]

    def get_catalog_summary(self) -> Dict[str, Any]:
        return {
            "total_models": len(self._models),
            "roles": {role.value: [m.name for m in self._models.values() if m.role == role] for role in ModelRole},
            "device_coverage": {
                "NPU": len(self.get_models_for_device("NPU")),
                "GPU": len(self.get_models_for_device("GPU")),
                "CPU": len(self.get_models_for_device("CPU")),
            },
        }
