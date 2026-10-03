"""
tests/test_timesfm_forecaster.py
=================================
Test suite for TimesFM Time-Series Forecaster:
- Zero-shot forecasting adapter for tabular/metric data in vazus.db
- Analytical / lightweight fallback engine without downloading heavy weights
- Predicts future horizon with mean and confidence intervals (upper/lower bounds)
"""

import pytest
from vazus_core.analytics.timesfm_forecaster import TimesFMForecaster, ForecastResult


def test_forecaster_initialization():
    forecaster = TimesFMForecaster()
    assert forecaster is not None


def test_zero_shot_forecast_shape_and_bounds():
    forecaster = TimesFMForecaster()
    history = [85.5, 85.2, 84.9, 85.0, 84.6, 84.4, 84.1]
    res = forecaster.forecast(history, horizon=5)

    assert isinstance(res, ForecastResult)
    assert len(res.mean) == 5
    assert len(res.lower_bound) == 5
    assert len(res.upper_bound) == 5

    # Check that bounds make sense: lower <= mean <= upper
    for l, m, u in zip(res.lower_bound, res.mean, res.upper_bound):
        assert l <= m <= u


def test_academic_debt_liquidation_trajectory():
    forecaster = TimesFMForecaster()
    # 18 debts decreasing over past 4 weeks: 18 -> 17 -> 16 -> 15
    debts = [18.0, 17.0, 16.0, 15.0]
    res = forecaster.forecast(debts, horizon=4)
    
    # Downward trend expected
    assert res.mean[-1] < debts[-1]
    assert all(d >= 0.0 for d in res.mean)  # debts cannot be negative


def test_empty_or_single_point_history():
    forecaster = TimesFMForecaster()
    res = forecaster.forecast([10.0], horizon=3)
    assert len(res.mean) == 3
    assert res.mean == [10.0, 10.0, 10.0]


def test_multivariate_timesfm_3_forecast():
    forecaster = TimesFMForecaster(model_path="google/timesfm-3.0-pytorch")
    multivar = {
        "academic_debts": [18.0, 17.0, 16.0, 15.0],
        "completed_labs": [2.0, 4.0, 6.0, 8.0],
        "study_hours_weekly": [10.0, 12.0, 14.0, 15.0]
    }
    res = forecaster.forecast_multivariate(multivar, horizon=3)
    assert "academic_debts" in res
    assert "completed_labs" in res
    assert "study_hours_weekly" in res
    assert len(res["academic_debts"].mean) == 3
    assert res["academic_debts"].backend == "timesfm_3.0_multivariate_engine"


def test_long_horizon_monotonic_trend():
    """Validates that a steady downward trend does not reverse or bounce back over a 20-step horizon."""
    forecaster = TimesFMForecaster()
    history = [100.0, 95.0, 90.0, 85.0, 80.0]
    res = forecaster.forecast(history, horizon=20)
    # The trajectory should be non-increasing throughout the entire horizon
    for i in range(len(res.mean) - 1):
        assert res.mean[i] >= res.mean[i + 1], f"Trend reversed at step {i}: {res.mean[i]} < {res.mean[i+1]}"

