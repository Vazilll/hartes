"""
═══════════════════════════════════════════════════════════════
  SpikeBus — SNN-style Inter-Component Signal Bus
═══════════════════════════════════════════════════════════════

Межкомпонентная шина спайковых сигналов для TARS.
Основана на принципах SI-LIF из brain/spiking/spiking_synapse.py.

Два уровня передачи:
  1. Spike {-1, 0, +1} — быстрый бинарный/тернарный сигнал
  2. INT8 payload — точные данные (опционально)

Типы сигналов:
  - WAKE:        VAD обнаружил речь или нажатие клавиши
  - INTENT:      ReflexClassifier определил намерение
  - URGENCY:     Уровень срочности (emotion/voice analysis)
  - MODEL_READY: Основная модель загружена / prefetch done
  - SLEEP:       Переход в режим сна

Usage:
    from core.runtime.spike_bus import get_spike_bus, SpikeSignal

    bus = get_spike_bus()
    
    # Producer
    bus.emit("WAKE", spike=1)
    bus.emit("INTENT", spike=1, payload=b'\\x03')  # intent_code=3
    
    # Consumer (callback)
    bus.subscribe("WAKE", lambda sig: wake_up_brain())
    
    # Consumer (polling)
    signal = bus.poll("WAKE")
    if signal and signal.spike > 0:
        prefetch_model()
"""

import time
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, List, Any

logger = logging.getLogger("Tars.SpikeBus")


# ═══════════════════════════════════════════
# Signal Types
# ═══════════════════════════════════════════

SIGNAL_TYPES = {
    "WAKE",           # VAD или keyboard → пробуждение
    "INTENT",         # ReflexClassifier → код намерения
    "URGENCY",        # EmotionSensor → уровень срочности
    "MODEL_READY",    # Prefetch модели завершён
    "SLEEP",          # Переход в sleep mode
    "VOICE_ACTIVE",   # VAD: речь продолжается
    "SUPPLEMENT",     # Пользователь дополняет запрос
}


@dataclass
class SpikeSignal:
    """
    Единица данных на спайковой шине.
    
    Attributes:
        signal_type: Тип сигнала (WAKE, INTENT, etc.)
        spike: Тернарный спайк {-1, 0, +1}
               +1 = активация, -1 = деактивация, 0 = нет события
        payload: INT8 данные (опционально). Точные параметры.
                 Например: intent_code, urgency_level, device_id
        timestamp_ms: Время создания сигнала (monotonic clock, ms)
        source: Имя компонента-источника
    """
    signal_type: str
    spike: int                          # {-1, 0, +1}
    payload: Optional[bytes] = None     # INT8 encoded data
    timestamp_ms: float = 0.0
    source: str = ""
    
    def __post_init__(self):
        if self.timestamp_ms == 0.0:
            self.timestamp_ms = time.monotonic() * 1000
        # Clamp spike to ternary
        self.spike = max(-1, min(1, self.spike))
    
    @property
    def payload_int(self) -> int:
        """Decode single-byte payload as signed int8."""
        if self.payload and len(self.payload) >= 1:
            val = self.payload[0]
            return val if val < 128 else val - 256
        return 0
    
    @property
    def age_ms(self) -> float:
        """Age of this signal in milliseconds."""
        return time.monotonic() * 1000 - self.timestamp_ms
    
    def __repr__(self):
        payload_str = f", payload={self.payload_int}" if self.payload else ""
        return f"Spike({self.signal_type}={self.spike:+d}{payload_str}, age={self.age_ms:.0f}ms)"


class SpikeBus:
    """
    Lock-free inter-component signal bus.
    
    Uses collections.deque (thread-safe for single-producer/single-consumer)
    and threading.Lock for subscriber management.
    
    Design principles:
      - Signals are ephemeral — old signals are auto-pruned
      - INT8 payloads for precise data (no text, no tokenization)
      - Ternary spikes for quick boolean signals
      - Subscribers receive signals asynchronously via callbacks
    """
    
    def __init__(self, max_queue_size: int = 64, signal_ttl_ms: float = 5000):
        """
        Args:
            max_queue_size: Maximum signals per type in queue
            signal_ttl_ms: Time-to-live for signals (ms). Old ones are pruned.
        """
        self._queues: Dict[str, deque] = {}
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
        self._max_queue = max_queue_size
        self._ttl_ms = signal_ttl_ms
        
        # Stats
        self._emit_count = 0
        self._poll_count = 0
        
        # Initialize queues for all known signal types
        for sig_type in SIGNAL_TYPES:
            self._queues[sig_type] = deque(maxlen=max_queue_size)
            self._subscribers[sig_type] = []
        
        logger.debug(f"SpikeBus initialized: {len(SIGNAL_TYPES)} signal types")
    
    def emit(
        self,
        signal_type: str,
        spike: int = 1,
        payload: Optional[bytes] = None,
        source: str = "",
    ) -> SpikeSignal:
        """
        Emit a spike signal on the bus.
        
        Args:
            signal_type: Type of signal (WAKE, INTENT, etc.)
            spike: Ternary value {-1, 0, +1}
            payload: Optional INT8 data bytes
            source: Name of emitting component
        
        Returns:
            The emitted SpikeSignal
        """
        signal = SpikeSignal(
            signal_type=signal_type,
            spike=spike,
            payload=payload,
            source=source,
        )
        
        # Add to queue
        if signal_type not in self._queues:
            self._queues[signal_type] = deque(maxlen=self._max_queue)
            self._subscribers[signal_type] = []
        
        self._queues[signal_type].append(signal)
        self._emit_count += 1
        
        # Notify subscribers (non-blocking)
        subscribers = self._subscribers.get(signal_type, [])
        for callback in subscribers:
            try:
                callback(signal)
            except Exception as e:
                logger.debug(f"SpikeBus subscriber error: {e}")
        
        logger.debug(f"SpikeBus.emit: {signal}")
        return signal
    
    def poll(self, signal_type: str) -> Optional[SpikeSignal]:
        """
        Poll for latest signal of given type.
        Consumes the signal (removes from queue).
        
        Returns:
            Latest SpikeSignal or None if queue empty.
        """
        self._poll_count += 1
        queue = self._queues.get(signal_type)
        if not queue:
            return None
        
        # Prune old signals
        now_ms = time.monotonic() * 1000
        while queue and (now_ms - queue[0].timestamp_ms) > self._ttl_ms:
            queue.popleft()
        
        if queue:
            return queue.popleft()
        return None
    
    def peek(self, signal_type: str) -> Optional[SpikeSignal]:
        """
        Peek at latest signal without consuming it.
        """
        queue = self._queues.get(signal_type)
        if not queue:
            return None
        
        # Prune old
        now_ms = time.monotonic() * 1000
        while queue and (now_ms - queue[0].timestamp_ms) > self._ttl_ms:
            queue.popleft()
        
        return queue[-1] if queue else None
    
    def subscribe(self, signal_type: str, callback: Callable[[SpikeSignal], Any]):
        """
        Subscribe to signals of given type.
        Callback is invoked synchronously in emitter's thread.
        
        Args:
            signal_type: Signal type to subscribe to
            callback: Function(SpikeSignal) called on each emission
        """
        with self._lock:
            if signal_type not in self._subscribers:
                self._subscribers[signal_type] = []
                self._queues[signal_type] = deque(maxlen=self._max_queue)
            self._subscribers[signal_type].append(callback)
            logger.debug(f"SpikeBus: subscribed to {signal_type}")
    
    def unsubscribe(self, signal_type: str, callback: Callable):
        """Remove a subscriber."""
        with self._lock:
            subs = self._subscribers.get(signal_type, [])
            if callback in subs:
                subs.remove(callback)
    
    def clear(self, signal_type: Optional[str] = None):
        """Clear all signals (or just one type)."""
        if signal_type:
            queue = self._queues.get(signal_type)
            if queue:
                queue.clear()
        else:
            for queue in self._queues.values():
                queue.clear()
    
    def stats(self) -> dict:
        """Bus statistics."""
        return {
            "total_emits": self._emit_count,
            "total_polls": self._poll_count,
            "queue_sizes": {
                k: len(v) for k, v in self._queues.items() if len(v) > 0
            },
            "subscriber_counts": {
                k: len(v) for k, v in self._subscribers.items() if len(v) > 0
            },
        }
    
    def __repr__(self):
        active = sum(1 for q in self._queues.values() if len(q) > 0)
        return f"SpikeBus(emits={self._emit_count}, active_queues={active})"


# ═══════════════════════════════════════════
# INT8 Payload Helpers
# ═══════════════════════════════════════════

def int8_encode(value: int) -> bytes:
    """Encode integer as single INT8 byte. Clamps to [-128, 127]."""
    value = max(-128, min(127, value))
    return bytes([(value + 256) % 256])


def int8_decode(data: bytes) -> int:
    """Decode single INT8 byte to integer."""
    if not data:
        return 0
    val = data[0]
    return val if val < 128 else val - 256


def int8_array_encode(values: list) -> bytes:
    """Encode list of integers as INT8 byte array."""
    return bytes([(max(-128, min(127, v)) + 256) % 256 for v in values])


def int8_array_decode(data: bytes) -> list:
    """Decode INT8 byte array to list of integers."""
    return [v if v < 128 else v - 256 for v in data]


# ═══════════════════════════════════════════
# Global singleton
# ═══════════════════════════════════════════
_global_bus: Optional[SpikeBus] = None


def get_spike_bus() -> SpikeBus:
    """Get or create global SpikeBus singleton."""
    global _global_bus
    if _global_bus is None:
        _global_bus = SpikeBus()
    return _global_bus
