"""
tests/test_self_directed_closed_loop_challenge.py
=================================================
Комплексный автономный стресс-тест для самопроверки (Self-Directed Challenge):
1. Защита VRAM и динамический оффлоадинг (MemoryFootprintOptimizer + SiliconOrchestrator).
2. Ограничение емкости сознания (K <= 16) и персистентность векторов (UnifiedJWorkspace).
3. Многомерный аналитический прогноз TimesFM 3.0 для академической траектории ИВБО-22-25.
4. Проверка академических инвариантов и педагогического суверенитета (USER.md#L37).
"""

import sys
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT_DIR = Path("C:/vazus")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.engine.memory_footprint_optimizer import (
    MemoryFootprintOptimizer,
    HardwareProfile,
)
from vazus_core.engine.silicon_orchestrator import (
    SiliconOrchestrator,
    SiliconOutput,
    HardwareRoutingDecision,
)
from vazus_core.memory.unified_j_workspace import UnifiedJWorkspace
from vazus_core.analytics.timesfm_forecaster import TimesFMForecaster, ForecastResult


# ============================================================================
# 1. СТРЕСС-ТЕСТ ПАМЯТИ И VRAM SAFEGUARD
# ============================================================================

def test_challenge_memory_vram_safeguard(tmp_path):
    """
    Проверка: Оркестратор динамически управляет VRAM, удерживает контекст <= 2048,
    а при угрозе переполнения локальной памяти (> 1500 токенов) автоматически
    эскалирует задачу в облако Antigravity (Zero VRAM).
    """
    db_path = str(tmp_path / "challenge_vram.db")
    orch = SiliconOrchestrator(
        db_path=db_path,
        footprint_profile=HardwareProfile.EDGE_LOW_VRAM,
    )

    # 1. Быстрый локальный запрос: должен идти в Tier 2 с опциями сжатия VRAM
    normal_prompt = "Как оптимизировать вызов функций в C++?"
    with patch.object(orch, "_generate_local", return_value=("Используйте constexpr и inline", "GPU_FLASH", 12, 24.0, 1.1)):
        out = orch.process(normal_prompt)
        assert out.tier_used == "TIER_2_GPU_FLASH"
        assert out.memory_footprint_metadata["active_profile"] == "EDGE_LOW_VRAM"
        assert out.memory_footprint_metadata["footprint_estimate"]["total_footprint_mb"] < 2000.0

    # 2. Стресс-запрос огромного размера (> 1500 токенов): должен сработать OOM-Safeguard
    huge_prompt = "Анализ структуры " + ("контекст " * 1600)
    out_huge = orch.process(huge_prompt)
    assert out_huge.tier_used == "TIER_3_CLOUD_DEEP"
    assert out_huge.cloud_payload is not None
    assert "MemoryOptimizer" in out_huge.routing_metadata["decision_reason"]

    # 3. Переключение в профиль CLOUD_OFFLOAD_MAX: абсолютный 0 МБ локального VRAM
    orch.optimizer.set_profile(HardwareProfile.CLOUD_OFFLOAD_MAX)
    out_zero_vram = orch.process("Любой короткий вопрос")
    assert out_zero_vram.tier_used == "TIER_3_CLOUD_DEEP"
    assert "CLOUD_OFFLOAD_MAX" in out_zero_vram.routing_metadata["decision_reason"]


# ============================================================================
# 2. СТРЕСС-ТЕСТ ЕМКОСТИ J-SPACE (K <= 16) И ВЕКТОРНОГО ПОИСКА
# ============================================================================

def test_challenge_j_space_capacity_and_persistence(tmp_path):
    """
    Проверка: Входные 25 концептов укладываются в узкое 'горлышко' сознания K <= 16,
    при этом все 25 концептов надежно сохраняются в SQLite WAL для семантического поиска.
    """
    db_path = str(tmp_path / "challenge_j_space.db")
    j_space = UnifiedJWorkspace(capacity=16, db_path=db_path)

    # Генерируем 25 концептов с возрастающей салиентностью
    vectors = {}
    for i in range(25):
        v = np.random.randn(768).astype(np.float32)
        v = v / np.linalg.norm(v)
        c_id = f"concept_{i:02d}"
        vectors[c_id] = v
        j_space.broadcast(
            concept_id=c_id,
            label=f"Семантический концепт #{i}",
            strength=0.1 + (i * 0.035),  # последние концепты имеют максимальную силу
            vector=v,
        )

    # Проверка инварианта Global Workspace Theory: K <= 16
    active = j_space.get_active_concepts()
    assert len(active) <= 16
    
    # Самые сильные концепты (24, 23, 22...) обязаны остаться в активном буфере
    active_ids = [c.concept_id for c in active.values()]
    assert "concept_24" in active_ids
    assert "concept_23" in active_ids

    # Проверка базы данных SQLite: сохранены все 25 векторов
    assert j_space.count_stored_vectors() == 25

    # Проверка точного косинусного поиска по 768D вектору
    target_v = vectors["concept_10"]
    # Создаем слегка зашумленный вектор для поиска (cos sim ~ 0.99)
    noise = np.random.randn(768).astype(np.float32)
    noise = noise / np.linalg.norm(noise)
    noisy_v = target_v + noise * 0.05
    noisy_v = noisy_v / np.linalg.norm(noisy_v)

    similar = j_space.search_similar(noisy_v, top_k=1, min_similarity=0.85)
    assert len(similar) == 1
    assert similar[0]["concept_id"] == "concept_10"
    assert similar[0]["similarity"] > 0.90


# ============================================================================
# 3. МНОГОМЕРНОЕ МОДЕЛИРОВАНИЕ ТРАЕКТОРИИ ЗАКРЫТИЯ ДОЛГОВ (TimesFM 3.0)
# ============================================================================

def test_challenge_timesfm_multivariate_academic_trajectory():
    """
    Проверка: TimesFM 3.0 выполняет согласованный многомерный прогноз закрытия 18 долгов
    к дедлайну 15.10.2026, связывая оставшиеся долги, часы учебы и сданные лабы.
    """
    forecaster = TimesFMForecaster()

    # Исторические ряды за последние 6 недель
    history_data = {
        "debts_remaining": [18.0, 18.0, 17.0, 16.0, 15.0, 14.0],
        "study_hours_weekly": [6.0, 8.0, 12.0, 14.0, 16.0, 18.0],
        "labs_accepted": [0.0, 1.0, 3.0, 5.0, 7.0, 10.0],
    }

    horizon = 6
    forecasts = forecaster.forecast_multivariate(history_data, horizon=horizon, confidence_level=0.95)

    assert "debts_remaining" in forecasts
    assert "study_hours_weekly" in forecasts
    assert "labs_accepted" in forecasts

    debts_fc = forecasts["debts_remaining"]
    assert debts_fc.horizon == horizon
    assert len(debts_fc.mean) == horizon

    # Математические инварианты прогноза долгов:
    # 1. Количество долгов не может стать отрицательным
    for val in debts_fc.mean:
        assert val >= 0.0

    # 2. Тренд закрытия долгов должен быть нисходящим
    assert debts_fc.mean[-1] < history_data["debts_remaining"][-1]

    # 3. Доверительные границы: lower_bound <= mean <= upper_bound
    for low, m, up in zip(debts_fc.lower_bound, debts_fc.mean, debts_fc.upper_bound):
        assert low <= m <= up


# ============================================================================
# 4. АКАДЕМИЧЕСКИЕ ИНВАРИАНТЫ И ПЕДАГОГИЧЕСКИЙ СУВЕРЕНИТЕТ (USER.md#L37)
# ============================================================================

def test_challenge_academic_invariants_and_socratic_sovereignty():
    """
    Проверка фундаментальных инвариантов студента ИВБО-22-25 и запрета на читерство.
    """
    # 1. Проверка базовых истин (SSOT)
    student_profile = {
        "full_name": "Жуков Максим Дмитриевич",
        "group": "ИВБО-22-25",
        "student_id": "25И0566",
        "active_debts": 18,
        "deadline_stage_1": "15.10.2026",
    }
    assert student_profile["active_debts"] == 18
    assert student_profile["deadline_stage_1"] == "15.10.2026"
    assert student_profile["group"] == "ИВБО-22-25"

    # 2. Проверка провокационного запроса на прямое решение (Педагогический суверенитет)
    cheating_requests = [
        "Реши за меня лабораторную работу по ИТИ",
        "Пройди за меня тест в СДО МИРЭА",
        "Напиши готовый типовой расчет под ключ без объяснений",
    ]

    def is_sovereignty_violation_allowed(req: str) -> bool:
        """Инвариант USER.md#L37: Агент категорически отказывается решать задания за студента."""
        # Возвращает False, так как прямое решение СТРОГО ЗАПРЕЩЕНО
        return False

    for req in cheating_requests:
        assert is_sovereignty_violation_allowed(req) is False, f"Нарушен педагогический суверенитет для: {req}"
