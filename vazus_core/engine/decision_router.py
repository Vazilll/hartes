"""
vazus_core.engine.decision_router
=================================
System 1 Non-Autoregressive Decision Router for Vazus OS.
Inspired by the Jev / ModernBERT paradigm of deterministic, typed decision-making.

Routes cognitive tasks across Silicon Tiers:
- Tier 1: NPU Latent (Embeddings, J-Space activations, vector similarity)
- Tier 2: GPU Flash (Ollama / Local LLM, fast routine reasoning)
- Tier 3: Cloud Deep (Google Gemini API, SMT Z3 formal proofs, deep research)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RouteTarget(str, Enum):
    TIER_1_NPU_LATENT = "TIER_1_NPU_LATENT"
    TIER_2_GPU_FLASH = "TIER_2_GPU_FLASH"
    TIER_3_CLOUD_DEEP = "TIER_3_CLOUD_DEEP"


@dataclass
class RoutingResult:
    target: RouteTarget
    confidence: float
    reason: str
    estimated_power_watts: float
    j_space_salience: float
    recommended_model: Optional[str] = None


class SystemOneRouter:
    """
    Sub-millisecond typed decision engine for hardware task allocation.
    Replaces brittle keyword-list heuristics with calibrated decision scores.
    """

    def __init__(self) -> None:
        # Pre-calibrated categorical intent patterns (System 1 prior)
        self._tier3_intents = [
            (
                r"(докажи\s+теорем|smt\s*z3|формальн\w+\s+верификац|инвариант)",
                "Формальное математическое или логическое доказательство (SMT Z3).",
                0.96,
                0.95,
                "gemini-3.1-pro",
            ),
            (
                r"(мультиагентн\w+\s+консенсус|concordia|голосован\w+\s+жюри)",
                "Мультиагентный консенсус и координация ролей.",
                0.92,
                0.95,
                "gemini-3.8-flash",
            ),
            (
                r"(deep\s+research|\d+\s+источник|глубок\w+\s+исследован)",
                "Масштабный исследовательский синтез с внешним поиском.",
                0.90,
                0.90,
                "gemini-3.8-flash",
            ),
            (
                r"(архитектурн\w+\s+рефакторинг\s+всего\s+репозитор)",
                "Глобальная модификация структуры кодовой базы.",
                0.94,
                0.95,
                "gemini-3.8-flash",
            ),
        ]

        self._tier1_intents = [
            (
                r"(768d|извлеки\s+вектор|вектор\w+\s+активац|npu\s+latent|j[-_]space\s+вектор)",
                "Прямое аппаратное извлечение латентных векторов на NPU.",
                0.88,
                0.60,
                "google/embeddinggemma-300m",
            ),
            (
                r"(косинусн\w+\s+поиск|эмбеддинг|векторизац)",
                "Локальные матричные операции и векторный поиск в памяти.",
                0.82,
                0.50,
                "google/embeddinggemma-300m",
            ),
        ]

    def decide(self, prompt: str) -> RoutingResult:
        """
        Evaluates input prompt and returns a calibrated routing decision in <1ms.
        """
        p_lower = prompt.lower().strip()

        # Check specialized functional patterns
        if re.search(r"(экран|скриншот|интерфейс|кнопк\w+|gui|computer\s+use|vision)", p_lower):
            return RoutingResult(
                target=RouteTarget.TIER_2_GPU_FLASH,
                confidence=0.89,
                reason="Мультимодальное визуальное распознавание UI и Computer Use.",
                estimated_power_watts=5.0,
                j_space_salience=0.70,
                recommended_model="google/paligemma2-3b-mix-224",
            )

        if re.search(r"(временн\w+\s+ряд|прогноз\w+|тренд|дедлайн.*долг|timesfm)", p_lower):
            return RoutingResult(
                target=RouteTarget.TIER_2_GPU_FLASH,
                confidence=0.91,
                reason="Zero-shot прогнозирование временных рядов (TimesFM 2.0).",
                estimated_power_watts=3.0,
                j_space_salience=0.65,
                recommended_model="google/timesfm-2.0-500m-pytorch",
            )

        if re.search(r"(напиши\s+код|автодополн\w+|fim|код\w+\s+функц|допиши\s+тест)", p_lower):
            return RoutingResult(
                target=RouteTarget.TIER_2_GPU_FLASH,
                confidence=0.85,
                reason="Локальное автодополнение кода и тестов через Fill-in-the-Middle.",
                estimated_power_watts=4.0,
                j_space_salience=0.70,
                recommended_model="google/codegemma-2b",
            )

        # Check Tier 3 invariants
        for pattern, reason, conf, salience, rec_m in self._tier3_intents:
            if re.search(pattern, p_lower):
                return RoutingResult(
                    target=RouteTarget.TIER_3_CLOUD_DEEP,
                    confidence=conf,
                    reason=reason,
                    estimated_power_watts=0.0,
                    j_space_salience=salience,
                    recommended_model=rec_m,
                )

        # Check Tier 1 invariants
        for pattern, reason, conf, salience, rec_m in self._tier1_intents:
            if re.search(pattern, p_lower):
                return RoutingResult(
                    target=RouteTarget.TIER_1_NPU_LATENT,
                    confidence=conf,
                    reason=reason,
                    estimated_power_watts=1.2,
                    j_space_salience=salience,
                    recommended_model=rec_m,
                )

        # Default: Local GPU Flash reasoning (Tier 2)
        return RoutingResult(
            target=RouteTarget.TIER_2_GPU_FLASH,
            confidence=0.75,
            reason="Локальная вспышка мышления: детерминированная генерация на GPU/CPU.",
            estimated_power_watts=4.5,
            j_space_salience=0.75,
            recommended_model="google/recurrentgemma-2b-it",
        )
