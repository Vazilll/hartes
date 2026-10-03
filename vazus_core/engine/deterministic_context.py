"""
Deterministic Session Context & Virtual Clock for Vazus OS.
Provides time virtualization, PRNG synchronization, and reproducible agent trajectory replay.
"""

import logging
import os
import random
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VirtualClock:
    """
    Simulated discrete-event virtual clock.
    Increments strictly on logical events, ensuring identical timestamps across replays.
    """

    def __init__(self, epoch_start: float = 1771500000.0, step_delta: float = 0.1):
        self.current_time = epoch_start
        self.step_delta = step_delta
        self.step_count = 0

    def tick(self, delta: Optional[float] = None) -> float:
        """Advances logical time."""
        self.step_count += 1
        self.current_time += delta if delta is not None else self.step_delta
        return self.current_time

    def now(self) -> float:
        """Returns the current virtual timestamp."""
        return self.current_time


class DeterministicSessionContext:
    """
    Context manager establishing deterministic runtime conditions:
    - Fixed PRNG seeds (random, numpy, torch if present)
    - Virtualized logical clock
    - Fixed PYTHONHASHSEED
    """

    def __init__(self, session_seed: int = 42, epoch_start: float = 1771500000.0, session_id: Optional[str] = None):
        self.seed = session_seed
        self.session_id = session_id or f"session_{session_seed}_{int(epoch_start)}"
        self.clock = VirtualClock(epoch_start=epoch_start)
        self.event_log: List[Dict[str, Any]] = []

    def __enter__(self):
        os.environ["PYTHONHASHSEED"] = str(self.seed)
        random.seed(self.seed)

        # Optional: Seed numpy & PyTorch if imported
        try:
            import numpy as np

            np.random.seed(self.seed)
        except ImportError as exc:
            logger.debug("Optional module numpy unavailable for seeding: %s", exc)

        try:
            import torch

            torch.manual_seed(self.seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(self.seed)
        except ImportError as exc:
            logger.debug("Optional module torch unavailable for seeding: %s", exc)

        return self

    def log_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Records a timestamped event in the deterministic replay journal."""
        entry = {
            "step": self.clock.step_count,
            "virtual_timestamp": self.clock.tick(),
            "event_type": event_type,
            "payload": payload,
        }
        self.event_log.append(entry)
        return entry

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Finalizes deterministic session context, logs exit status, and handles seed cleanup."""
        status = "error" if exc_type else "success"
        exit_event = {
            "event": "session_exit",
            "session_id": self.session_id,
            "status": status,
            "error": str(exc_val) if exc_val else None,
            "event_count": len(self.event_log),
        }
        self.event_log.append(exit_event)
        logger.debug("DeterministicSessionContext finalized: %s", exit_event)
        return False  # Propagate exceptions cleanly
