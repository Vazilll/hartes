"""
labs/mission_aegis_omni/aegis_pipeline.py — Python Telemetry Pipeline.
"""

from typing import List, Dict, Any, Optional


class AegisPipeline:
    """Processes sensor data and calculates anomaly confidence."""

    def __init__(self, window_size: int = 10, threshold: float = 2.5):
        self.window_size = window_size
        self.threshold = threshold
        self.history: List[float] = []

    def ingest_metric(self, value: float) -> Dict[str, Any]:
        """Ingests a metric and evaluates anomaly threshold."""
        self.history.append(value)
        if len(self.history) > self.window_size:
            self.history.pop(0)

        mean = sum(self.history) / max(1, len(self.history))
        variance = sum((x - mean) ** 2 for x in self.history) / max(1, len(self.history))
        std_dev = variance ** 0.5

        is_anomaly = abs(value - mean) > (self.threshold * std_dev) if std_dev > 0.0 else False

        return {
            "value": value,
            "window_mean": round(mean, 4),
            "std_dev": round(std_dev, 4),
            "is_anomaly": is_anomaly,
        }

    def clear(self) -> None:
        self.history.clear()
