"""
vazus_core.engine.speculative_tool_predictor
=============================================
Speculative Tool Prediction Contour for Vazus OS.

Predicts which MCP tools/servers the agent will need NEXT based on:
  - Historical tool activation sequences from vazus.db
  - TimesFM 3.0 time-series forecasting of tool-index trajectories
  - Julia ONNX NPU domain classifier (optional, graceful fallback)
  - Frequency-based fallback when TimesFM unavailable

Architecture:
  ToolActivationHistory  → numeric time-series of tool indices
  TimesFMPredictor       → forecast next-H tool indices + quantile probs
  JuliaDomainClassifier  → query domain classification via NPU ONNX
  SpeculativeToolPredictor → orchestrates all components, returns SpeculativePrediction

Latency target: < 500 ms total (TimesFM on CPU, Julia NPU optional).

Usage::

    predictor = SpeculativeToolPredictor()
    result = predictor.predict_for_query("Сколько у меня долгов в МИРЭА?")
    print(result)
"""

from __future__ import annotations

import logging
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger("vazus_core.engine.speculative_tool_predictor")

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
_DB_PATH = Path("C:/vazus/services/memory/vazus.db")
_TIMESFM_LOCAL = "C:/vazus/models/timesfm3"
_JULIA_ONNX_PATH = "C:/vazus/models/julia_router/julia_classifier.onnx"
_JULIA_CONFIG_PATH = "C:/vazus/models/julia_router/config.json"
_JULIA_TOKENIZER_PATH = "C:/vazus/models/openvino_npu/tokenizer/tokenizer.json"

_WINDOW_SIZE = 128      # sliding window of last N activations
_HORIZON = 8            # forecast this many steps ahead
# Quantile indices are resolved dynamically at decode time to handle
# models that return fewer quantile bands (e.g. 8 instead of 9).

# Housekeeping/background tools that should never appear in predictions
# (they are called internally, not in response to user queries)
_TOOL_BLACKLIST: frozenset[str] = frozenset({
    "vazus-sandbox",
    "db_backup",
    "delete_cell",
    "interact_with_process",
})


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SpeculativePrediction:
    """Result of a speculative tool prediction for a query."""
    predicted_tools: List[str] = field(default_factory=list)
    """Tool names predicted to be needed next (ranked by probability)."""

    domain: str = "general_reasoning"
    """Domain classified by Julia NPU (or fallback)."""

    confidence: float = 0.0
    """Confidence score in [0, 1] derived from TimesFM quantile spread."""

    reasoning: str = ""
    """Human-readable explanation of the prediction."""

    prefetch_schemas: List[str] = field(default_factory=list)
    """MCP server names whose schemas should be pre-loaded."""

    latency_ms: float = 0.0
    """Total prediction latency in milliseconds."""


# ---------------------------------------------------------------------------
# ToolActivationHistory
# ---------------------------------------------------------------------------

class ToolActivationHistory:
    """
    Reads and caches the tool activation history from vazus.db.

    Builds a canonical sorted list of all unique tool names with stable
    integer indices and converts the activation log into a numeric time series.
    """

    def __init__(self, db_path: str | Path = _DB_PATH) -> None:
        self._db_path = str(db_path)
        self._tool_index: Dict[str, int] = {}      # tool_name → int index
        self._index_tool: Dict[int, str] = {}      # int index → tool_name
        self._series: List[int] = []               # chronological tool indices
        self._module_map: Dict[str, str] = {}      # tool_name → mcp server module
        self._loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load activation history and metadata from DB (idempotent)."""
        if self._loaded:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                self._load_tool_index(conn)
                self._load_series(conn)
                self._load_module_map(conn)
            self._loaded = True
            logger.info(
                "ToolActivationHistory loaded: %d unique tools, %d activations",
                len(self._tool_index),
                len(self._series),
            )
        except Exception as exc:
            logger.warning("Failed to load activation history: %s", exc)

    @property
    def tool_names(self) -> List[str]:
        """Sorted canonical list of all unique tool names."""
        self.load()
        return list(self._tool_index.keys())

    @property
    def n_tools(self) -> int:
        self.load()
        return len(self._tool_index)

    def tool_to_index(self, name: str) -> int:
        """Return integer index for a tool name (−1 if unknown)."""
        self.load()
        return self._tool_index.get(name, -1)

    def index_to_tool(self, idx: int) -> str:
        """Return tool name for an integer index (empty string if unknown)."""
        self.load()
        return self._index_tool.get(int(round(idx)), "")

    def get_window(self, n: int = _WINDOW_SIZE, domain_prefix: str = "") -> List[int]:
        """
        Return the last *n* tool-index values from the activation log.

        Parameters
        ----------
        n:
            Window size (number of most-recent activations to return).
        domain_prefix:
            If non-empty, filter the series to only include tools whose
            names start with this prefix before slicing the window.
        """
        self.load()
        series = self._series
        if domain_prefix:
            prefix_indices = {
                idx for name, idx in self._tool_index.items()
                if name.startswith(domain_prefix)
            }
            series = [s for s in series if s in prefix_indices]
        return series[-n:]

    def frequency_top_k(
        self,
        k: int = 5,
        domain_filter: str = "",
    ) -> List[Tuple[str, float]]:
        """
        Return top-*k* tools by raw activation frequency.

        Returns a list of (tool_name, normalized_frequency) tuples.
        """
        self.load()
        series = self._series
        if domain_filter:
            domain_indices = {
                idx for name, idx in self._tool_index.items()
                if name.startswith(domain_filter)
            }
            series = [s for s in series if s in domain_indices]
        if not series:
            series = self._series  # fallback to full history

        counts = Counter(series)
        total = sum(counts.values()) or 1
        top = counts.most_common(k)
        return [(self._index_tool.get(idx, ""), cnt / total) for idx, cnt in top]

    def module_for_tool(self, tool_name: str) -> str:
        """Return the MCP server module name for a given tool (empty if unknown)."""
        self.load()
        return self._module_map.get(tool_name, "")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_tool_index(self, conn: sqlite3.Connection) -> None:
        """Build canonical sorted tool index from both activations and metadata."""
        names: set[str] = set()
        try:
            for row in conn.execute(
                "SELECT DISTINCT tool_name FROM j_space_tool_activations"
            ):
                if row[0] and row[0] not in _TOOL_BLACKLIST:
                    names.add(row[0])
        except sqlite3.OperationalError:
            pass
        try:
            for row in conn.execute(
                "SELECT DISTINCT tool_name FROM j_space_tool_metadata"
            ):
                if row[0] and row[0] not in _TOOL_BLACKLIST:
                    names.add(row[0])
        except sqlite3.OperationalError:
            pass

        sorted_names = sorted(names)
        self._tool_index = {name: i for i, name in enumerate(sorted_names)}
        self._index_tool = {i: name for i, name in enumerate(sorted_names)}

    def _load_series(self, conn: sqlite3.Connection) -> None:
        """Convert activation log to a numeric time series of tool indices."""
        try:
            rows = conn.execute(
                """
                SELECT tool_name, timestamp
                FROM j_space_tool_activations
                ORDER BY timestamp ASC
                """
            ).fetchall()
            self._series = [
                self._tool_index[r[0]]
                for r in rows
                if r[0] and r[0] in self._tool_index  # blacklisted tools absent from index
            ]
        except sqlite3.OperationalError as exc:
            logger.warning("Cannot load activation series: %s", exc)
            self._series = []

    def _load_module_map(self, conn: sqlite3.Connection) -> None:
        """Build tool_name → module mapping from j_space_tool_metadata."""
        try:
            rows = conn.execute(
                "SELECT tool_name, module FROM j_space_tool_metadata"
            ).fetchall()
            self._module_map = {r[0]: r[1] for r in rows if r[0] and r[1]}
        except sqlite3.OperationalError:
            self._module_map = {}


# ---------------------------------------------------------------------------
# TimesFMPredictor
# ---------------------------------------------------------------------------

class TimesFMPredictor:
    """
    Wraps TimesFM 3.0 (PyTorch) for tool-sequence forecasting.

    Loads the model lazily from a local checkpoint directory.
    Falls back gracefully to frequency-based prediction on any failure.
    """

    def __init__(
        self,
        checkpoint_path: str = _TIMESFM_LOCAL,
        device: str = "cpu",
    ) -> None:
        self._checkpoint_path = checkpoint_path
        self._device = device
        self._model: Any = None          # timesfm.TimesFM3Forecaster
        self._load_attempted = False
        self._available = False

    # ------------------------------------------------------------------
    # Lazy load
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> bool:
        """Attempt to load TimesFM model if not done yet. Returns availability."""
        if self._load_attempted:
            return self._available
        self._load_attempted = True
        try:
            import timesfm  # noqa: PLC0415 – lazy import intentional
            logger.info("Loading TimesFM 3.0 from %s …", self._checkpoint_path)
            import contextlib
            t0 = time.perf_counter()
            with contextlib.redirect_stdout(sys.stderr):
                self._model = timesfm.TimesFM3Forecaster.from_pretrained(
                    pretrained_model_name_or_path=self._checkpoint_path,
                    device=self._device,
                    local_files_only=True,
                )
            dt = (time.perf_counter() - t0) * 1000
            logger.info("TimesFM 3.0 loaded in %.0f ms", dt)
            self._available = True
        except Exception as exc:
            logger.warning("TimesFM load failed (%s); will use fallback", exc)
            self._available = False
        return self._available

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """True if TimesFM model was loaded successfully."""
        return self._ensure_loaded()

    def predict_next_tools(
        self,
        history: List[int],
        horizon: int = _HORIZON,
        n_tools: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Forecast the next *horizon* tool indices from a numeric history.

        Parameters
        ----------
        history:
            List of integer tool indices (chronological order).
        horizon:
            Number of future steps to forecast.
        n_tools:
            Total number of distinct tools in the vocabulary (used to
            clamp predicted indices to valid range).

        Returns
        -------
        List of dicts with keys ``tool_index``, ``probability``, ``rank``,
        ``quantile_spread``, sorted by descending probability.
        """
        if not self._ensure_loaded() or not history:
            return []
        try:
            import numpy as np  # noqa: PLC0415

            ctx = np.array(history, dtype=np.float32)
            result = self._model.predict(
                context=ctx,
                horizon=horizon,
                return_quantiles=True,
                make_positive=True,
                sort_quantiles=True,
            )
            # result.forecast shape: [1, horizon] (mean / median forecast)
            # result.quantiles shape: [9, horizon] (quantile forecasts)
            forecast_vals = np.asarray(result.forecast).flatten()   # (horizon,)
            quantile_vals = (
                np.asarray(result.quantiles)  # may be (9, horizon) or (1, 9, horizon)
                if result.quantiles is not None
                else None
            )
            if quantile_vals is not None and quantile_vals.ndim == 3:
                quantile_vals = quantile_vals[0]  # → (9, horizon)

            return self._decode_forecast(
                forecast_vals, quantile_vals, horizon, n_tools
            )
        except Exception as exc:
            logger.warning("TimesFM inference failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_forecast(
        forecast: "np.ndarray",   # (horizon,) median predictions
        quantiles: "np.ndarray | None",  # (9, horizon) or None
        horizon: int,
        n_tools: int,
    ) -> List[Dict[str, Any]]:
        """
        Convert raw float forecasts into ranked tool predictions.

        Strategy:
          - Round each forecast value to nearest integer → candidate tool idx.
          - Build a vote-weight map across the horizon (position-decayed).
          - If quantiles available, compute spread confidence per step.
        """

        vote_weights: Dict[int, float] = defaultdict(float)
        spread_map: Dict[int, float] = defaultdict(float)

        # Resolve quantile band indices from actual model output size
        n_quantiles = quantiles.shape[0] if quantiles is not None else 0
        q_idx_low = 0
        q_idx_high = max(0, n_quantiles - 1)  # last band (≈ 0.9)

        for step, raw_val in enumerate(forecast[:horizon]):
            decay = 1.0 / (step + 1)  # earlier predictions are more relevant
            candidate = int(round(float(raw_val)))
            if n_tools > 0:
                candidate = max(0, min(candidate, n_tools - 1))
            vote_weights[candidate] += decay

            if quantiles is not None and n_quantiles > 0 and quantiles.shape[-1] > step:
                q10 = float(quantiles[q_idx_low, step])
                q90 = float(quantiles[q_idx_high, step])
                spread = abs(q90 - q10)
                spread_map[candidate] += spread * decay

        if not vote_weights:
            return []

        total_weight = sum(vote_weights.values())
        results = []
        for rank, (tidx, weight) in enumerate(
            sorted(vote_weights.items(), key=lambda kv: -kv[1])
        ):
            spread = spread_map.get(tidx, 0.0)
            # Confidence: high when spread is small relative to tool vocab
            confidence = weight / total_weight if total_weight > 0 else 0.0
            results.append(
                {
                    "tool_index": tidx,
                    "probability": round(confidence, 4),
                    "rank": rank,
                    "quantile_spread": round(spread, 4),
                }
            )
        return results


# ---------------------------------------------------------------------------
# JuliaDomainClassifier
# ---------------------------------------------------------------------------

class JuliaDomainClassifier:
    """
    Optional domain classifier using the Julia ONNX model on NPU/CPU.

    Input:  tokenized query → int64[1, 64]
    Output: probability logits over 9 domain classes → float[1, 9]

    Gracefully disabled when ONNX runtime or tokenizer is unavailable.
    """

    DOMAINS = [
        "academic", "code", "browser", "finance", "health",
        "system_architecture", "jules", "cloud_run", "general_reasoning",
    ]

    # Map domain → likely MCP server prefixes for domain-filtering
    DOMAIN_TOOL_PREFIXES: Dict[str, List[str]] = {
        "academic":            ["vazus_academic", "mirea", "study"],
        "code":                ["cbm", "ckb", "code-quality", "github"],
        "browser":             ["playwright", "computer-use"],
        "finance":             ["vazus_finance", "finance"],
        "health":              ["vazus_health", "mi_scale"],
        "system_architecture": ["cbm", "ckb", "code-quality"],
        "jules":               ["jules", "vazus-sandbox"],
        "cloud_run":           ["colab", "gemini-notebook", "notebooks"],
        "general_reasoning":   ["sequential-thinking", "vazus-organic"],
    }

    def __init__(
        self,
        onnx_path: str = _JULIA_ONNX_PATH,
        config_path: str = _JULIA_CONFIG_PATH,
        tokenizer_path: str = _JULIA_TOKENIZER_PATH,
    ) -> None:
        self._onnx_path = onnx_path
        self._config_path = config_path
        self._tokenizer_path = tokenizer_path
        self._session: Any = None
        self._tokenizer: Any = None
        self._load_attempted = False
        self._available = False

    def _ensure_loaded(self) -> bool:
        if self._load_attempted:
            return self._available
        self._load_attempted = True
        try:
            import onnxruntime as ort  # noqa: PLC0415

            providers = self._select_providers()
            self._session = ort.InferenceSession(
                self._onnx_path, providers=providers
            )
            self._tokenizer = self._load_tokenizer()
            self._available = True
            logger.info("Julia ONNX classifier loaded (providers=%s)", providers)
        except Exception as exc:
            logger.info("Julia classifier unavailable (%s); domain filter skipped", exc)
            self._available = False
        return self._available

    @staticmethod
    def _select_providers() -> List[str]:
        """Prefer NPU / OpenVINO, fall back through GPU to CPU."""
        try:
            import onnxruntime as ort  # noqa: PLC0415
            avail = ort.get_available_providers()
            for pref in [
                "OpenVINOExecutionProvider",
                "DmlExecutionProvider",
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            ]:
                if pref in avail:
                    providers = [pref]
                    # Always add CPUExecutionProvider as fallback (only if different)
                    if pref != "CPUExecutionProvider":
                        providers.append("CPUExecutionProvider")
                    return providers
        except Exception:
            pass
        return ["CPUExecutionProvider"]

    def _load_tokenizer(self) -> Any:
        """Load a HuggingFace-compatible tokenizer from JSON."""
        try:
            from tokenizers import Tokenizer  # noqa: PLC0415
            return Tokenizer.from_file(self._tokenizer_path)
        except Exception:
            return None

    @property
    def available(self) -> bool:
        return self._ensure_loaded()

    def classify(self, query: str) -> Tuple[str, float]:
        """
        Classify *query* into one of the 9 domain labels.

        Returns
        -------
        (domain_name, confidence) — or ("general_reasoning", 0.0) on failure.
        """
        if not self._ensure_loaded():
            return "general_reasoning", 0.0
        try:
            import numpy as np  # noqa: PLC0415

            input_ids = self._tokenize(query)
            outputs = self._session.run(
                ["probabilities"],
                {"input_ids": input_ids},
            )
            probs = np.asarray(outputs[0]).flatten()  # (9,)
            best_idx = int(np.argmax(probs))
            domain = self.DOMAINS[best_idx] if best_idx < len(self.DOMAINS) else "general_reasoning"
            confidence = float(probs[best_idx])
            return domain, confidence
        except Exception as exc:
            logger.warning("Julia classify failed: %s", exc)
            return "general_reasoning", 0.0

    def _tokenize(self, text: str) -> "np.ndarray":
        """Tokenize text to int64[1, 64] (truncate / pad to 64 tokens)."""
        import numpy as np  # noqa: PLC0415

        max_len = 64
        if self._tokenizer is not None:
            try:
                enc = self._tokenizer.encode(text)
                ids = enc.ids[:max_len]
                padded = ids + [0] * (max_len - len(ids))
                return np.array([padded], dtype=np.int64)
            except Exception:
                pass
        # Fallback: crude character-based encoding
        ids = [ord(c) % 50000 for c in text[:max_len]]
        ids += [0] * (max_len - len(ids))
        return np.array([ids], dtype=np.int64)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class SpeculativeToolPredictor:
    """
    Orchestrates TimesFM + Julia ONNX to predict MCP tools needed for a query.

    Prediction pipeline:
      1. Load tool activation history from DB.
      2. Classify query domain via Julia NPU (optional).
      3. Extract sliding-window history (optionally domain-filtered).
      4. Feed window into TimesFM 3.0 → ranked tool-index forecast.
      5. Resolve tool names from indices and build SpeculativePrediction.
      6. Fall back to frequency-based ranking if TimesFM unavailable.
    """

    def __init__(
        self,
        db_path: str | Path = _DB_PATH,
        timesfm_checkpoint: str = _TIMESFM_LOCAL,
        device: str = "cpu",
    ) -> None:
        self._history = ToolActivationHistory(db_path=db_path)
        self._tfm = TimesFMPredictor(
            checkpoint_path=timesfm_checkpoint, device=device
        )
        self._julia = JuliaDomainClassifier()
        # Lazily trigger history load (fast DB read; non-blocking for model loads)
        self._history.load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict_for_query(
        self,
        query: str,
        top_k: int = 3,
        horizon: int = _HORIZON,
        window: int = _WINDOW_SIZE,
    ) -> SpeculativePrediction:
        """
        Predict which MCP tools are most likely needed for the given query.

        Parameters
        ----------
        query:
            The user's natural-language query text.
        top_k:
            Number of top predicted tools to return.
        horizon:
            TimesFM forecast horizon (number of future steps).
        window:
            Sliding-window size for recent history.

        Returns
        -------
        SpeculativePrediction dataclass with ranked tool names, domain, and
        prefetch hints.
        """
        t_start = time.perf_counter()

        # Step 1: domain classification (optional)
        domain, domain_conf = self._julia.classify(query)
        logger.debug("Domain: %s (conf=%.3f)", domain, domain_conf)

        # Step 2: get activation window (may domain-filter)
        domain_prefixes = JuliaDomainClassifier.DOMAIN_TOOL_PREFIXES.get(domain, [])
        history_window = self._history.get_window(n=window)
        history_window_filtered: List[int] = []
        for pfx in domain_prefixes:
            partial = self._history.get_window(n=window, domain_prefix=pfx)
            history_window_filtered.extend(partial)
        # Use domain-filtered window if non-empty and Julia was available
        if history_window_filtered and self._julia.available:
            active_window = history_window_filtered[-window:]
        else:
            active_window = history_window

        # Step 3: TimesFM prediction
        tfm_preds = self._tfm.predict_next_tools(
            history=active_window,
            horizon=horizon,
            n_tools=self._history.n_tools,
        )

        # Step 4: resolve tool names from predicted indices
        use_timesfm = bool(tfm_preds)
        if use_timesfm:
            predicted_tools, confidence, reasoning = self._resolve_timesfm(
                tfm_preds, top_k, domain, horizon
            )
        else:
            predicted_tools, confidence, reasoning = self._resolve_frequency(
                top_k, domain
            )

        # Step 5: determine MCP servers to prefetch
        prefetch_servers = self._prefetch_servers(predicted_tools)

        latency_ms = (time.perf_counter() - t_start) * 1000
        logger.info(
            "SpeculativeToolPredictor: domain=%s, tools=%s, latency=%.1f ms",
            domain, predicted_tools, latency_ms,
        )

        return SpeculativePrediction(
            predicted_tools=predicted_tools,
            domain=domain,
            confidence=confidence,
            reasoning=reasoning,
            prefetch_schemas=prefetch_servers,
            latency_ms=round(latency_ms, 2),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_timesfm(
        self,
        tfm_preds: List[Dict[str, Any]],
        top_k: int,
        domain: str,
        horizon: int,
    ) -> Tuple[List[str], float, str]:
        """Convert TimesFM integer predictions to tool names."""
        seen: Dict[str, float] = {}
        for p in tfm_preds:
            name = self._history.index_to_tool(p["tool_index"])
            if name and name not in seen:
                seen[name] = p["probability"]
            if len(seen) >= top_k * 2:
                break

        # Sort by probability and take top_k
        ranked = sorted(seen.items(), key=lambda kv: -kv[1])[:top_k]
        tool_names = [t for t, _ in ranked]
        probs = [p for _, p in ranked]
        confidence = probs[0] if probs else 0.0

        reason_parts = [
            f"TimesFM 3.0 forecast over {horizon} steps (domain={domain}):"
        ]
        for i, (name, prob) in enumerate(ranked):
            reason_parts.append(f"  #{i+1} '{name}' → p={prob:.3f}")
        reasoning = "\n".join(reason_parts)

        return tool_names, confidence, reasoning

    def _resolve_frequency(
        self,
        top_k: int,
        domain: str,
    ) -> Tuple[List[str], float, str]:
        """Fallback: frequency-based tool ranking."""
        domain_prefixes = JuliaDomainClassifier.DOMAIN_TOOL_PREFIXES.get(domain, [])
        results: List[Tuple[str, float]] = []
        for pfx in domain_prefixes:
            results.extend(self._history.frequency_top_k(k=top_k, domain_filter=pfx))
        if not results:
            results = self._history.frequency_top_k(k=top_k)

        # Deduplicate and take top_k
        seen: Dict[str, float] = {}
        for name, freq in results:
            if name and name not in seen:
                seen[name] = freq
            if len(seen) >= top_k:
                break
        ranked = sorted(seen.items(), key=lambda kv: -kv[1])[:top_k]
        tool_names = [t for t, _ in ranked]
        probs = [p for _, p in ranked]
        confidence = probs[0] if probs else 0.0

        reason_parts = [
            f"[Fallback] Frequency-based ranking (TimesFM unavailable, domain={domain}):"
        ]
        for i, (name, prob) in enumerate(ranked):
            reason_parts.append(f"  #{i+1} '{name}' → freq={prob:.3f}")
        reasoning = "\n".join(reason_parts)

        return tool_names, confidence, reasoning

    def _prefetch_servers(self, tool_names: List[str]) -> List[str]:
        """Derive unique MCP server names from predicted tool names."""
        servers: list[str] = []
        seen: set[str] = set()
        for name in tool_names:
            mod = self._history.module_for_tool(name)
            if mod and mod not in seen:
                servers.append(mod)
                seen.add(mod)
        return servers


# ---------------------------------------------------------------------------
# record_tool_used
# ---------------------------------------------------------------------------

def record_tool_used(
    tool_name: str,
    prompt: str,
    invocation_num: int = 0,
    db_path: str | Path = _DB_PATH,
) -> None:
    """
    Record a confirmed tool usage into j_space_tool_activations.

    Call this from pre/post-tool hooks when a tool is actually invoked.

    Parameters
    ----------
    tool_name:
        MCP tool name that was used (e.g. ``"search_graph"``).
    prompt:
        The user prompt that triggered the tool invocation.
    invocation_num:
        Optional sequential invocation number within the current session.
    db_path:
        Path to vazus.db (default: canonical path).
    """
    try:
        ts = time.time()
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """
                INSERT INTO j_space_tool_activations
                    (tool_name, prompt, invocation_num, timestamp, was_used)
                VALUES (?, ?, ?, ?, 1)
                """,
                (tool_name, prompt, invocation_num, ts),
            )
            conn.commit()
        logger.debug("Recorded tool usage: %s @ %.3f", tool_name, ts)
    except Exception as exc:
        logger.warning("record_tool_used failed: %s", exc)


# ---------------------------------------------------------------------------
# Demo / self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # Force UTF-8 output
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    print("=" * 70)
    print("Speculative Tool Predictor – self-test")
    print("=" * 70)

    predictor = SpeculativeToolPredictor()

    queries = [
        "Сколько у меня долгов в МИРЭА?",
        "Run a git diff on the vazus_core package",
        "Search github for TimesFM issues",
        "How much money do I have left this month?",
    ]

    for q in queries:
        print(f"\nQuery: {q!r}")
        result = predictor.predict_for_query(q, top_k=3)
        print(f"  domain          : {result.domain}")
        print(f"  predicted_tools : {result.predicted_tools}")
        print(f"  prefetch_schemas: {result.prefetch_schemas}")
        print(f"  confidence      : {result.confidence:.4f}")
        print(f"  latency_ms      : {result.latency_ms:.1f}")
        print(f"  reasoning       :\n{result.reasoning}")
        print("-" * 60)
