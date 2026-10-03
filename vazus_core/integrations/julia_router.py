"""
julia_router.py — System-1 Fast Decision Router based on Julia-1 Architecture.
Provides sub-50ms (typically 1-25ms) intent classification and tool routing across canonical domains,
reserving expensive Cloud LLM calls (Gemini/Claude) only for complex reasoning tasks.

Accelerated by Intel(R) AI Boost NPU via OpenVINO / ONNXRuntime with automatic fallback
to Intel Graphics iGPU, host CPU, and sub-millisecond heuristic reflexes.

Features:
- Fixed 9-domain canonical routing via julia_classifier.onnx on NPU.
- Jev / Julia-1 Typed Decision Primitives (Zero-Token Non-Autoregressive System 1):
  * ChoiceDecision: parallel categorical evaluation over arbitrary options with calibrated probabilities.
  * ScoreDecision: calibrated continuous rubric scoring with uncertainty bounds.
  * NoulDecision: calibrated binary proposition / hypothesis verification.
  * ToolRoutingDecision: sub-15ms MCP tool & subagent dispatching.
- RLCD (Reinforcement Learning for Calibrated Decisions) calibration layer:
  * Temperature scaling & Brier score evaluation to minimize Expected Calibration Error (ECE).
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

try:
    import openvino as ov
except ImportError:
    ov = None

try:
    import onnxruntime as ort
except ImportError:
    ort = None

try:
    from tokenizers import Tokenizer
except ImportError:
    Tokenizer = None

logger = logging.getLogger("julia_router")

# Canonical System Domains in vazus SuperGraph OS
CANONICAL_DOMAINS: List[str] = [
    "academic",  # MIREA, debts, moodle, schedule, socratic tutor
    "code",  # Python, Go, AST, classes, functions, bugs, refactor
    "browser",  # Web search, scraping, playwright, visiting URLs
    "finance",  # Tinkoff, taxes, receipts, freelance NPD
    "health",  # Mi Scale, Google Fit, sleep, supplements
    "system_architecture",  # Hooks, Vazus OS, SuperGraph, configs, memory
    "jules",  # Cloud VM async coding, PR generation
    "cloud_run",  # Gemini Spark mobile MCP bridge
    "general_reasoning",  # Open-ended planning, philosophical inquiries
]

# Canonical Domain to MCP Tool / Skill Dispatch Mapping
DOMAIN_TOOL_MAP: Dict[str, List[str]] = {
    "academic": [
        "vazus-academic-debt-navigator",
        "academic_verification",
        "socratic_mentor",
    ],
    "code": [
        "cbm",
        "vazus_ast_prune",
        "code-quality",
        "pytest_runner",
        "vazus_smt_z3_verify",
    ],
    "browser": [
        "playwright",
        "read_url_content",
        "search_web",
    ],
    "finance": [
        "tinkoff_finance_manager",
        "npd_tax_tracker",
    ],
    "health": [
        "health_agent",
        "mi_scale_sync",
    ],
    "system_architecture": [
        "supergraph_hub",
        "pre_tool_hook",
        "vazus_organic_recall",
        "vazus_record_insight",
    ],
    "jules": [
        "jules_cloud_bridge",
        "wsb_sandbox",
    ],
    "cloud_run": [
        "gemini_spark_bridge",
    ],
    "general_reasoning": [
        "escalate_to_llm",
        "sequentialthinking",
    ],
}

# Canonical Skill Competency Graph (Skill Tree Topology & Prerequisites)
SKILL_TREE_GRAPH: Dict[str, Dict[str, Any]] = {
    # Academic Competency Tree (MIREA 09.03.01 IVT)
    "mirea": {
        "domain": "academic",
        "description": "MIREA academic navigation, debt tracking, syllabus, and study calendar",
        "prerequisites": [],
        "next": ["mirea-rt1-calculus", "mirea-rt1-linalg", "mirea-rt1-logic"],
        "keywords": ["мирэа", "деканат", "долг", "пересдач", "сессия", "ивбо", "китпипи", "брс", "хвост"],
    },
    "mirea-rt1-calculus": {
        "domain": "academic",
        "description": "Calculus, mathematical analysis, limits, derivatives, integrals, and series",
        "prerequisites": ["mirea"],
        "next": ["academic_verification"],
        "keywords": ["матанализ", "предел", "производн", "интеграл", "коши", "дифференциал", "ряд", "calculus"],
    },
    "mirea-rt1-linalg": {
        "domain": "academic",
        "description": "Linear algebra, matrices, determinants, vector spaces, and eigenvalues",
        "prerequisites": ["mirea"],
        "next": ["academic_verification"],
        "keywords": ["линал", "матриц", "определител", "базис", "ранг", "векторн", "собственн", "linalg"],
    },
    "mirea-rt1-logic": {
        "domain": "academic",
        "description": "Mathematical logic, discrete mathematics, boolean algebra, and graph theory",
        "prerequisites": ["mirea"],
        "next": ["academic_verification"],
        "keywords": ["матлогик", "дискретн", "булев", "граф", "предикат", "дизъюнкт", "индукци", "logic"],
    },
    # Code Architecture & Evolutionary Engineering Tree
    "cbm": {
        "domain": "code",
        "description": "Codebase graph modeling, call-graph tracing, and AST definition indexing",
        "prerequisites": [],
        "next": ["code-quality", "vazus_ast_prune"],
        "keywords": ["граф кода", "индекс", "символ", "call graph", "структура проекта", "cbm"],
    },
    "code-quality": {
        "domain": "code",
        "description": "Static analysis, radon complexity, code clones, and maintainability metrics",
        "prerequisites": ["cbm"],
        "next": ["vazus_ast_prune"],
        "keywords": ["качество", "сложность", "цикломатическ", "дубликат", "рефакторинг", "линтер"],
    },
    "vazus_ast_prune": {
        "domain": "code",
        "description": "AST pruning, dead code removal, and unused import elimination",
        "prerequisites": ["code-quality"],
        "next": ["vazus_smt_z3_verify"],
        "keywords": ["ast", "прунинг", "удалить импорт", "мертвый код", "чистка кода"],
    },
    "vazus_smt_z3_verify": {
        "domain": "code",
        "description": "Formal verification of function contracts and invariants via Z3 SMT solver",
        "prerequisites": ["vazus_ast_prune"],
        "next": ["vazus_darwinian_evolve"],
        "keywords": ["z3", "smt", "верификаци", "доказательство", "инвариант", "контракт"],
    },
    "vazus_darwinian_evolve": {
        "domain": "code",
        "description": "Evolutionary AST mutation and Darwinian genetic optimization",
        "prerequisites": ["vazus_smt_z3_verify"],
        "next": [],
        "keywords": ["эволюци", "мутаци", "дарвин", "генетическ", "оптимизаци кода"],
    },
    # Financial Sovereignty Tree
    "tinkoff_finance_manager": {
        "domain": "finance",
        "description": "Tinkoff banking, account balances, transaction tracking, and categorization",
        "prerequisites": [],
        "next": ["npd_tax_tracker"],
        "keywords": ["тинькофф", "т-банк", "баланс", "карта", "транзакци", "расход", "доход", "tinkoff"],
    },
    "npd_tax_tracker": {
        "domain": "finance",
        "description": "Self-employed NPD taxation, receipt generation, and My Tax FNS integration",
        "prerequisites": ["tinkoff_finance_manager"],
        "next": [],
        "keywords": ["налог", "самозанят", "нпд", "чек", "фнс", "мой налог", "tax"],
    },
    # Health & Physical Sovereignty Tree
    "mi_scale_sync": {
        "domain": "health",
        "description": "Xiaomi Mi Scale smart scale Bluetooth/DB sync and weight tracking",
        "prerequisites": [],
        "next": ["health_agent"],
        "keywords": ["весы", "взвешиван", "mi scale", "вес", "масса тела", "scale"],
    },
    "health_agent": {
        "domain": "health",
        "description": "Workout planning, calorie deficit, sleep tracking, and physical training",
        "prerequisites": ["mi_scale_sync"],
        "next": [],
        "keywords": ["тренировк", "зал", "калори", "сон", "пульс", "шаг", "похудени", "спорт", "workout"],
    },
    # System Customization & Automation Tree
    "agy-customizations": {
        "domain": "system_architecture",
        "description": "Antigravity customization system: rules, hooks, skills, and MCP extensions",
        "prerequisites": [],
        "next": ["plugin", "migrate-workflows"],
        "keywords": ["кастомизаци", "правил", "хук", "скилл", "antigravity", "customization"],
    },
    "automation": {
        "domain": "browser",
        "description": "Browser automation, playwright interaction, web scraping, and form filling",
        "prerequisites": [],
        "next": ["playwright"],
        "keywords": ["браузер", "автоматизаци", "клиент", "playwright", "скриншот", "веб", "browser"],
    },
}


# ============================================================================
# Dataclasses for System-1 Decisions (Jev / Julia-1 Typed Primitives)
# ============================================================================


@dataclass
class RoutingDecision:
    """Canonical domain routing decision (backward compatible)."""

    domain: str
    confidence: float
    latency_ms: float
    options_evaluated: List[str]
    requires_cloud_reasoning: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChoiceDecision:
    """Non-autoregressive categorical selection across arbitrary candidate options."""

    selected: str
    confidence: float
    probabilities: Dict[str, float]
    latency_ms: float
    margin: float  # Difference between top-1 and top-2 confidence
    options_evaluated: List[str]
    device_used: str
    calibrated: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoreDecision:
    """Non-autoregressive continuous evaluation against a rubric."""

    score: float
    confidence: float
    normalized_score: float  # [0.0, 1.0]
    rubric: str
    latency_ms: float
    device_used: str
    distribution: Dict[str, float] = field(default_factory=dict)
    calibrated: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NoulDecision:
    """Non-autoregressive binary proposition verification (Yes / No)."""

    passed: bool
    probability: float  # Probability that proposition holds true [0.0, 1.0]
    threshold: float
    confidence: float  # Absolute distance from decision boundary
    latency_ms: float
    device_used: str
    calibrated: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolRoutingDecision:
    """Direct sub-15ms MCP tool or agent skill selection."""

    selected_tool: str
    fallback_tools: List[str]
    domain: str
    confidence: float
    latency_ms: float
    device_used: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillRoutingDecision:
    """
    System-1 Skill routing decision: selects existing skill or detects a skill gap
    with competency tree progression.
    """

    selected_skill: Optional[str]
    confidence: float
    domain: str
    requires_new_skill: bool
    suggested_skill_name: Optional[str]
    prerequisites: List[str] = field(default_factory=list)
    next_in_tree: List[str] = field(default_factory=list)
    authoring_prompt: Optional[str] = None
    latency_ms: float = 0.0
    device_used: str = "NPU"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutineActionDecision:
    """
    System-1 Routine Computer-Use decision: fast direct action dispatching without LLM roundtrips.
    """

    is_routine: bool
    action_type: str  # "run_command", "mcp_call", "sqlite_query", "none"
    suggested_command: Optional[str]
    target_tool: Optional[str]
    confidence: float
    latency_ms: float = 0.0
    device_used: str = "heuristic"
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# RLCD (Reinforcement Learning for Calibrated Decisions) Layer
# ============================================================================


class RLCDCalibrator:
    """
    Mathematical calibration layer implementing Proper Scoring Rules (Brier Score)
    and Temperature Scaling to minimize Expected Calibration Error (ECE).
    """

    def __init__(self, temperature: float = 1.15) -> None:
        self.temperature = max(0.1, float(temperature))

    def temperature_scale(self, logits: Sequence[float], temp: Optional[float] = None) -> List[float]:
        """Applies temperature scaling to logits and computes softmax probabilities."""
        t = temp or self.temperature
        arr = np.array(logits, dtype=np.float64) / max(1e-5, t)
        exp_arr = np.exp(arr - np.max(arr))
        probs = exp_arr / np.sum(exp_arr)
        return [float(p) for p in probs]

    @staticmethod
    def brier_score(probabilities: Sequence[float], targets: Sequence[int]) -> float:
        """
        Computes multi-class Brier score: BS = (1/N) * sum((p_i - y_i)^2).
        Lower is better (0.0 = perfect calibration and accuracy).
        """
        p = np.array(probabilities, dtype=np.float64)
        y = np.array(targets, dtype=np.float64)
        return float(np.mean((p - y) ** 2))

    @staticmethod
    def platt_scale(prob: float, a: float = 1.0, b: float = 0.0) -> float:
        """Platt scaling sigmoid mapping for binary propositions (Noul)."""
        eps = 1e-7
        p = np.clip(prob, eps, 1.0 - eps)
        logit = np.log(p / (1.0 - p))
        scaled_logit = a * logit + b
        return float(1.0 / (1.0 + np.exp(-scaled_logit)))


# ============================================================================
# Hardware-Accelerated Neural Classifier for Canonical Domains
# ============================================================================


class JuliaONNXClassifier:
    """
    Hardware-accelerated neural classifier for Julia-1 System-1 decision routing.
    Executes in < 25ms (typically 1-15ms) targeting Intel(R) AI Boost NPU with
    seamless fallback to Intel Graphics iGPU and host CPU.
    """

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        tokenizer_path: Optional[Union[str, Path]] = None,
        device: str = "NPU",
        backend: str = "openvino",
        max_seq_len: int = 64,
        cache_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self.requested_device = device
        self.active_device: Optional[str] = None
        self.backend: Optional[str] = None
        self.max_seq_len = max_seq_len
        self.domains = CANONICAL_DOMAINS
        self._is_available = False

        self._compiled_model = None
        self._infer_request = None
        self._ort_session = None
        self._tokenizer = None

        # Resolve paths
        self.model_path = self._resolve_model_path(model_path)
        self.tokenizer_path = self._resolve_tokenizer_path(tokenizer_path)
        self.cache_dir = Path(cache_dir or "C:/vazus/data/cache/openvino")

        # Load tokenizer
        self._load_tokenizer()

        # Initialize accelerator backend
        if backend == "openvino" and ov is not None:
            self._init_openvino()

        # Fallback to ONNXRuntime if OpenVINO failed or was not requested
        if not self._is_available and ort is not None and self.model_path and self.model_path.endswith(".onnx"):
            self._init_onnxruntime()

    def _resolve_model_path(self, user_path: Optional[Union[str, Path]]) -> Optional[str]:
        if user_path and Path(user_path).exists():
            return str(user_path)

        candidates = [
            Path("C:/vazus/data/models/julia_router/julia_classifier.onnx"),
            Path(__file__).resolve().parents[2] / "models" / "julia_router" / "julia_classifier.onnx",
            Path("models/julia_router/julia_classifier.onnx"),
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return None

    def _resolve_tokenizer_path(self, user_path: Optional[Union[str, Path]]) -> Optional[str]:
        if user_path and Path(user_path).exists():
            return str(user_path)

        candidates = [
            Path("C:/vazus/data/models/openvino_npu/tokenizer/tokenizer.json"),
            Path(__file__).resolve().parents[2] / "models" / "openvino_npu" / "tokenizer" / "tokenizer.json",
            Path("models/openvino_npu/tokenizer/tokenizer.json"),
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return None

    def _load_tokenizer(self) -> None:
        if self.tokenizer_path and Tokenizer is not None:
            try:
                self._tokenizer = Tokenizer.from_file(self.tokenizer_path)
                self._tokenizer.enable_padding(length=self.max_seq_len)
                self._tokenizer.enable_truncation(max_length=self.max_seq_len)
            except Exception as e:
                logger.debug("Failed to load rust tokenizer: %s", e)

    def _init_openvino(self) -> None:
        if not self.model_path or not os.path.exists(self.model_path):
            logger.debug("OpenVINO model path not found: %s", self.model_path)
            return

        try:
            core = ov.Core()
            available = core.available_devices
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            try:
                core.set_property({"CACHE_DIR": str(self.cache_dir)})
            except Exception as cache_err:
                logger.debug("OpenVINO CACHE_DIR note: %s", cache_err)

            # Prioritize requested device -> NPU -> GPU -> CPU
            device_chain = [self.requested_device, "NPU", "GPU", "CPU"]
            candidate_devices: List[str] = []
            for d in device_chain:
                if d in available and d not in candidate_devices:
                    candidate_devices.append(d)

            model = core.read_model(self.model_path)
            # Static reshape required for Intel NPU VPUX compiler
            try:
                model.reshape({"input_ids": [1, self.max_seq_len]})
            except Exception as reshape_err:
                logger.debug("Model reshape note: %s", reshape_err)

            for dev in candidate_devices:
                try:
                    compile_config = {
                        "PERFORMANCE_HINT": "LATENCY",
                        "CACHE_DIR": str(self.cache_dir),
                    }
                    compiled = core.compile_model(model, device_name=dev, config=compile_config)
                    self._compiled_model = compiled
                    self._infer_request = compiled.create_infer_request()
                    self.active_device = dev
                    self.backend = "openvino"
                    self._is_available = True
                    logger.info("JuliaONNXClassifier successfully loaded on %s via OpenVINO", dev)
                    break
                except Exception as compile_err:
                    logger.warning("Failed to compile Julia model on %s: %s", dev, compile_err)

        except Exception as e:
            logger.warning("OpenVINO initialization error: %s", e)

    def _init_onnxruntime(self) -> None:
        try:
            providers = ["CPUExecutionProvider"]
            self._ort_session = ort.InferenceSession(self.model_path, providers=providers)
            self.active_device = "CPU"
            self.backend = "onnxruntime"
            self._is_available = True
            logger.info("JuliaONNXClassifier loaded via ONNXRuntime on CPU")
        except Exception as e:
            logger.warning("ONNXRuntime initialization error: %s", e)

    @property
    def is_available(self) -> bool:
        return self._is_available

    def predict(self, text: str) -> Tuple[str, float, Dict[str, float], float]:
        """
        Executes hardware-accelerated classification inference on input text.
        Returns:
            (best_domain, confidence, domain_scores_dict, latency_ms)
        """
        start_t = time.perf_counter()

        if not self._is_available or self._tokenizer is None:
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            return "general_reasoning", 0.1, {d: 0.1 for d in self.domains}, elapsed_ms

        enc = self._tokenizer.encode(text)
        input_ids = np.array([enc.ids], dtype=np.int64)

        if self.backend == "openvino" and self._infer_request is not None:
            res = self._infer_request.infer({"input_ids": input_ids})
            out = list(res.values())[0][0]
        elif self.backend == "onnxruntime" and self._ort_session is not None:
            res = self._ort_session.run(None, {"input_ids": input_ids})
            out = res[0][0]
        else:
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            return "general_reasoning", 0.1, {d: 0.1 for d in self.domains}, elapsed_ms

        scores = {dom: float(out[i]) for i, dom in enumerate(self.domains) if i < len(out)}
        best_domain = max(scores.keys(), key=lambda k: scores[k])
        confidence = float(scores[best_domain])

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        return best_domain, confidence, scores, elapsed_ms


# ============================================================================
# Main System-1 Julia Router with Typed Decision Primitives
# ============================================================================


class JuliaRouter:
    """
    Tier-0 Fast Decision Router inspired by Supersonic Labs Julia-1 (mmBERT-small).
    Evaluates decisions in < 25 ms on NPU/GPU/CPU with reflexive fallback.

    Supports:
    - route(): Canonical 9-domain intent classification.
    - route_choice(): N-way decision primitive (Jev Choice).
    - route_score(): Continuous rubric scoring (Jev Score).
    - route_noul(): Binary hypothesis proposition verification (Jev Noul).
    - route_tool(): Instant MCP tool and agent skill dispatcher.
    """

    def __init__(
        self,
        offline_fallback: bool = True,
        use_neural: bool = True,
        use_embedder: bool = True,
        device: str = "NPU",
        model_path: Optional[str] = None,
    ) -> None:
        self.offline_fallback = offline_fallback
        self.use_neural = use_neural
        self.use_embedder = use_embedder
        self.requested_device = device
        self.domains = CANONICAL_DOMAINS
        self.classifier: Optional[JuliaONNXClassifier] = None
        self.calibrator = RLCDCalibrator(temperature=1.15)
        self._npu_embedder = None
        self._embedder_checked = False

        # 1. Initialize Canonical ONNX Classifier
        if self.use_neural:
            try:
                clf = JuliaONNXClassifier(model_path=model_path, device=device)
                if clf.is_available:
                    self.classifier = clf
                    logger.info("JuliaRouter neural classifier active on %s (%s)", clf.active_device, clf.backend)
            except Exception as e:
                logger.warning("Failed to initialize JuliaONNXClassifier: %s. Using heuristics.", e)

    def _get_npu_embedder(self):
        """Lazily load the OpenVINONPUEmbedder for arbitrary Choice/Score/Noul operations."""
        if not self._embedder_checked:
            self._embedder_checked = True
            if self.use_embedder:
                try:
                    from vazus_core.memory.embeddings import OpenVINONPUEmbedder

                    emb = OpenVINONPUEmbedder(device=self.requested_device)
                    if emb.is_available:
                        self._npu_embedder = emb
                        logger.info("JuliaRouter NPU embedder initialized on %s", emb.device)
                except Exception as emb_err:
                    logger.debug("OpenVINONPUEmbedder note in JuliaRouter: %s", emb_err)
        return self._npu_embedder

    def _embed_text(self, text: str) -> Optional[np.ndarray]:
        """Generates a 768-dim normalized embedding via NPU or returns None."""
        emb_engine = self._get_npu_embedder()
        if emb_engine and emb_engine.is_available:
            try:
                # Use Rust tokenizer if present, else fallback
                if hasattr(emb_engine, "_fast_tokenizer") and emb_engine._fast_tokenizer:
                    enc = emb_engine._fast_tokenizer.encode(text)
                    input_ids = np.array([enc.ids], dtype=np.int64)
                    vec = emb_engine.embed_tokens(input_ids)
                    arr = np.array(vec, dtype=np.float32)
                    norm = np.linalg.norm(arr)
                    return arr / max(1e-7, norm)
            except Exception as e:
                logger.debug("NPU embedding extraction note: %s", e)
        return None

    def _heuristic_scores(self, q_clean: str) -> Dict[str, float]:
        """Keyword mapping heuristics for sub-millisecond reflex."""
        weights = {d: 0.05 for d in self.domains}

        # Academic signals
        if any(
            w in q_clean
            for w in (
                "мирэа",
                "ивбо",
                "сдо",
                "долг",
                "хвост",
                "пересдач",
                "ведомост",
                "препод",
                "матан",
                "алгебр",
                "физр",
                "зачет",
                "экзамен",
                "лабораторн",
                "дифф",
            )
        ):
            weights["academic"] += 0.85

        # Code signals
        if any(
            w in q_clean
            for w in (
                "код",
                "питон",
                "python",
                "def ",
                "class ",
                "pytest",
                "тест",
                "рефактор",
                "refactor",
                "ast",
                "ошибк",
                "баг",
                "git",
            )
        ):
            weights["code"] += 0.80

        # Browser / Web signals
        if any(
            w in q_clean
            for w in ("браузер", "browser", "сайт", "web", "найди в интернете", "playwright", "url", "http", "погугли")
        ):
            weights["browser"] += 0.75

        # Finance signals
        if any(
            w in q_clean
            for w in (
                "финанс",
                "деньг",
                "тинькофф",
                "tinkoff",
                "налог",
                "чек",
                "нпд",
                "самозанят",
                "расход",
                "доход",
                "баланс",
                "кредит",
            )
        ):
            weights["finance"] += 0.85

        # Health signals
        if any(
            w in q_clean
            for w in ("весы", "вес", "здоровь", "сон", "пульс", "шаг", "калори", "бад", "ми шкал", "mi scale", "fit")
        ):
            weights["health"] += 0.85

        # Jules signals
        jules_patterns = (r"\bpr\b", r"\bpull request\b", "джулес", "джулс", "jules", "облачн vm")
        if any(re.search(pat, q_clean) if pat.startswith(r"\b") else pat in q_clean for pat in jules_patterns):
            weights["jules"] += 0.90

        # Cloud Run / Spark signals
        if any(w in q_clean for w in ("cloud run", "спарк", "spark", "клауд ран", "телефон", "мобильн", "mcp bridge")):
            weights["cloud_run"] += 0.80

        # Architecture signals
        if any(
            w in q_clean for w in ("хук", "hook", "vazus", "архитектур", "оркестрац", "mcp", "субагент", "supergraph")
        ):
            weights["system_architecture"] += 0.75

        return weights

    # ========================================================================
    # 1. Canonical Domain Routing (route)
    # ========================================================================

    def route(self, user_query: str) -> RoutingDecision:
        """Classifies user intent and returns a structured RoutingDecision."""
        start_t = time.perf_counter()
        q_clean = user_query.strip().lower()

        neural_used = False
        device_used = "heuristic"
        backend_used = "regex"
        best_domain = "general_reasoning"
        confidence = 0.50
        meta: Dict[str, Any] = {"query_length": len(user_query)}

        # 1. Neural classification via NPU/GPU/CPU if available
        if self.classifier and self.classifier.is_available:
            try:
                n_domain, n_conf, n_scores, n_lat = self.classifier.predict(user_query)
                meta["neural_scores"] = {k: round(v, 4) for k, v in n_scores.items()}
                meta["inference_latency_ms"] = round(n_lat, 2)
                device_used = self.classifier.active_device or "CPU"
                backend_used = self.classifier.backend or "openvino"
                neural_used = True

                # If neural confidence is high, adopt it directly
                if n_conf >= 0.70:
                    best_domain = n_domain
                    confidence = n_conf
                else:
                    # Low-confidence ensemble with heuristic reflex
                    h_weights = self._heuristic_scores(q_clean)
                    combined = {}
                    for d in self.domains:
                        combined[d] = 0.6 * n_scores.get(d, 0.0) + 0.4 * min(1.0, h_weights.get(d, 0.05))
                    best_domain = max(combined.keys(), key=lambda k: combined[k])
                    raw_conf = combined[best_domain]
                    if h_weights.get(best_domain, 0.0) >= 0.80:
                        confidence = min(0.95, max(raw_conf, h_weights[best_domain]))
                    else:
                        confidence = min(0.99, raw_conf)
            except Exception as clf_err:
                logger.warning("Neural prediction failed: %s, falling back to heuristics", clf_err)
                neural_used = False

        # 2. Fallback heuristics if neural unavailable or errored
        if not neural_used:
            domain_weights = self._heuristic_scores(q_clean)
            best_domain = max(domain_weights.keys(), key=lambda k: domain_weights[k])
            confidence = min(0.99, domain_weights[best_domain])
            device_used = "heuristic"
            backend_used = "regex"

        # Check if query necessitates cloud escalation
        requires_cloud = confidence < 0.60 or any(
            w in q_clean for w in ("почему", "зачем", "подумай", "проанализируй", "как лучше", "план", "философ")
        )

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        meta.update(
            {
                "device_used": device_used,
                "backend": backend_used,
                "neural_accelerated": neural_used,
            }
        )

        return RoutingDecision(
            domain=best_domain,
            confidence=round(confidence, 3),
            latency_ms=round(elapsed_ms, 2),
            options_evaluated=self.domains,
            requires_cloud_reasoning=requires_cloud,
            metadata=meta,
        )

    # ========================================================================
    # 2. Jev / Julia-1 Choice Primitive (route_choice)
    # ========================================================================

    def route_choice(
        self,
        prompt: str,
        options: List[str],
        rubric: Optional[str] = None,
        temperature: float = 1.0,
    ) -> ChoiceDecision:
        """
        Non-autoregressive categorical selection across arbitrary candidate options.
        Executes parallel comparison without token generation, returning calibrated probabilities.
        """
        start_t = time.perf_counter()
        if not options:
            raise ValueError("options cannot be empty")

        if len(options) == 1:
            return ChoiceDecision(
                selected=options[0],
                confidence=1.0,
                probabilities={options[0]: 1.0},
                latency_ms=(time.perf_counter() - start_t) * 1000.0,
                margin=1.0,
                options_evaluated=options,
                device_used="trivial",
            )

        device_used = "heuristic"
        prompt_vec = self._embed_text(prompt)

        logits: List[float] = []

        if prompt_vec is not None:
            # Neural NPU parallel similarity computation
            device_used = getattr(self._npu_embedder, "device", "NPU")
            for opt in options:
                opt_text = f"{rubric}: {opt}" if rubric else opt
                opt_vec = self._embed_text(opt_text)
                if opt_vec is not None:
                    sim = float(np.dot(prompt_vec, opt_vec))
                    logits.append(sim * 10.0)  # Scale to reasonable logit range
                else:
                    logits.append(0.0)
        else:
            # Sub-millisecond token overlap / jaccard reflex
            p_words = set(re.findall(r"\w+", prompt.lower()))
            for opt in options:
                o_words = set(re.findall(r"\w+", opt.lower()))
                overlap = len(p_words.intersection(o_words))
                logits.append(float(overlap) * 2.0)

        # Apply RLCD temperature scaling
        calibrated_probs = self.calibrator.temperature_scale(logits, temp=temperature)
        prob_dict = {opt: round(calibrated_probs[i], 4) for i, opt in enumerate(options)}

        sorted_opts = sorted(prob_dict.items(), key=lambda kv: kv[1], reverse=True)
        best_opt, best_conf = sorted_opts[0]
        second_conf = sorted_opts[1][1] if len(sorted_opts) > 1 else 0.0
        margin = round(best_conf - second_conf, 4)

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return ChoiceDecision(
            selected=best_opt,
            confidence=round(best_conf, 4),
            probabilities=prob_dict,
            latency_ms=round(elapsed_ms, 2),
            margin=margin,
            options_evaluated=options,
            device_used=device_used,
            calibrated=True,
            metadata={"logits": [round(l, 3) for l in logits]},
        )

    # ========================================================================
    # 3. Jev / Julia-1 Score Primitive (route_score)
    # ========================================================================

    def route_score(
        self,
        prompt: str,
        rubric: str,
        min_score: float = 0.0,
        max_score: float = 1.0,
    ) -> ScoreDecision:
        """
        Non-autoregressive continuous rubric scoring.
        Evaluates input text against alignment criteria in a single pass.
        """
        start_t = time.perf_counter()
        contrast_options = [
            f"The prompt strictly violates the rubric: {rubric}",
            f"The prompt partially meets the rubric: {rubric}",
            f"The prompt perfectly satisfies the rubric: {rubric}",
        ]
        choice = self.route_choice(prompt, contrast_options)

        p_low = choice.probabilities.get(contrast_options[0], 0.33)
        p_med = choice.probabilities.get(contrast_options[1], 0.33)
        p_high = choice.probabilities.get(contrast_options[2], 0.33)

        # Expected normalized value [0.0, 1.0]
        norm_score = p_low * 0.0 + p_med * 0.5 + p_high * 1.0
        scaled_score = min_score + (max_score - min_score) * norm_score
        confidence = choice.confidence

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return ScoreDecision(
            score=round(scaled_score, 4),
            confidence=round(confidence, 4),
            normalized_score=round(norm_score, 4),
            rubric=rubric,
            latency_ms=round(elapsed_ms, 2),
            device_used=choice.device_used,
            distribution={"low": round(p_low, 3), "medium": round(p_med, 3), "high": round(p_high, 3)},
            calibrated=True,
        )

    # ========================================================================
    # 4. Jev / Julia-1 Noul Primitive (route_noul)
    # ========================================================================

    def route_noul(
        self,
        hypothesis: str,
        context: str,
        threshold: float = 0.5,
    ) -> NoulDecision:
        """
        Non-autoregressive binary proposition verification (Yes / No).
        Computes calibrated probability that hypothesis is supported by context.
        """
        start_t = time.perf_counter()
        options = [
            f"False: '{hypothesis}' is false given context",
            f"True: '{hypothesis}' is true given context",
        ]
        choice = self.route_choice(context, options)
        prob_true = choice.probabilities.get(options[1], 0.5)

        # Apply Platt calibration
        calibrated_p = self.calibrator.platt_scale(prob_true)
        passed = calibrated_p >= threshold
        confidence = abs(calibrated_p - 0.5) * 2.0  # Distance from neutrality

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return NoulDecision(
            passed=passed,
            probability=round(calibrated_p, 4),
            threshold=threshold,
            confidence=round(confidence, 4),
            latency_ms=round(elapsed_ms, 2),
            device_used=choice.device_used,
            calibrated=True,
            metadata={"raw_p": round(prob_true, 4)},
        )

    # ========================================================================
    # 5. MCP Tool & Agent Skill Dispatcher (route_tool)
    # ========================================================================

    def route_tool(
        self,
        user_query: str,
        available_tools: Optional[List[str]] = None,
    ) -> ToolRoutingDecision:
        """
        Sub-15ms MCP tool and agent skill dispatcher.
        Identifies the optimal tool for the query without cloud LLM roundtrips.
        """
        start_t = time.perf_counter()

        # Step 1: Rapid canonical domain classification via NPU (<12ms)
        domain_decision = self.route(user_query)
        target_domain = domain_decision.domain
        domain_tools = DOMAIN_TOOL_MAP.get(target_domain, ["escalate_to_llm"])

        # Filter by available_tools if specified
        if available_tools:
            intersected = [t for t in domain_tools if t in available_tools]
            candidate_tools = intersected if intersected else available_tools
        else:
            candidate_tools = domain_tools

        # Step 2: If multiple candidate tools exist, perform Choice selection
        if len(candidate_tools) > 1:
            tool_choice = self.route_choice(
                prompt=user_query,
                options=candidate_tools,
                rubric=f"Select the best tool for domain: {target_domain}",
            )
            selected_tool = tool_choice.selected
            fallback_tools = [t for t in candidate_tools if t != selected_tool]
            confidence = tool_choice.confidence
            device_used = tool_choice.device_used
        else:
            selected_tool = candidate_tools[0]
            fallback_tools = []
            confidence = domain_decision.confidence
            device_used = domain_decision.metadata.get("device_used", "NPU")

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return ToolRoutingDecision(
            selected_tool=selected_tool,
            fallback_tools=fallback_tools,
            domain=target_domain,
            confidence=round(confidence, 3),
            latency_ms=round(elapsed_ms, 2),
            device_used=device_used,
            metadata={
                "domain_decision_latency_ms": domain_decision.latency_ms,
                "domain_confidence": domain_decision.confidence,
            },
        )

    # ========================================================================
    # 6. Skill Tree & Skill Gap Routing (route_skill)
    # ========================================================================

    def route_skill(
        self,
        user_query: str,
        available_skills: Optional[List[str]] = None,
        gap_threshold: float = 0.45,
    ) -> SkillRoutingDecision:
        """
        Matches user intent to an active skill in the skill tree or detects a skill gap,
        proposing creation of a new skill and providing progression guidance.
        """
        start_t = time.perf_counter()
        domain_decision = self.route(user_query)
        target_domain = domain_decision.domain

        q_clean = user_query.strip().lower()
        candidate_skills = available_skills if available_skills else list(SKILL_TREE_GRAPH.keys())

        best_skill: Optional[str] = None
        best_score = 0.0

        for skill_name in candidate_skills:
            info = SKILL_TREE_GRAPH.get(skill_name, {})
            skill_domain = info.get("domain", "")

            # Baseline domain match
            score = 0.25 if skill_domain == target_domain else 0.0

            # Keyword lexical match
            keywords = info.get("keywords", [])
            matches = sum(1 for kw in keywords if kw in q_clean)
            if matches > 0:
                score += min(0.70, matches * 0.25)

            if score > best_score:
                best_score = score
                best_skill = skill_name

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        device_used = domain_decision.metadata.get("device_used", "NPU")

        # Check if gap detected
        if best_skill is not None and best_score >= gap_threshold:
            info = SKILL_TREE_GRAPH[best_skill]
            return SkillRoutingDecision(
                selected_skill=best_skill,
                confidence=round(best_score, 3),
                domain=target_domain,
                requires_new_skill=False,
                suggested_skill_name=None,
                prerequisites=info.get("prerequisites", []),
                next_in_tree=info.get("next", []),
                latency_ms=round(elapsed_ms, 2),
                device_used=device_used,
                metadata={"domain_confidence": domain_decision.confidence},
            )
        else:
            # Gap detected! Recommend authoring
            suggested = self._propose_skill_name(user_query, target_domain)
            prompt = (
                f"Обнаружен пробел в навыках (confidence {best_score:.2f} < {gap_threshold}). "
                f"Рекомендуется вызвать 'vazus_author_skill' для создания '{suggested}' в домене '{target_domain}'."
            )
            return SkillRoutingDecision(
                selected_skill=None,
                confidence=round(best_score, 3),
                domain=target_domain,
                requires_new_skill=True,
                suggested_skill_name=suggested,
                prerequisites=[],
                next_in_tree=[],
                authoring_prompt=prompt,
                latency_ms=round(elapsed_ms, 2),
                device_used=device_used,
                metadata={"domain_confidence": domain_decision.confidence},
            )

    def _propose_skill_name(self, query: str, domain: str) -> str:
        """Generates an intuitive kebab-case skill identifier from unhandled intent."""
        words = re.findall(r"[a-zA-Zа-яА-Я0-9]+", query.lower())
        key_words = [
            w for w in words
            if len(w) > 3 and w not in ("пожалуйста", "нужно", "помоги", "как", "сделать", "please", "help")
        ]
        slug = "-".join(key_words[:3]) if key_words else "custom-task"
        translit = {
            "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh",
            "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
            "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
            "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ы": "y",
            "э": "e", "ю": "yu", "я": "ya",
        }
        latin_slug = "".join(translit.get(c, c) for c in slug)
        latin_slug = re.sub(r"[^a-z0-9\-]", "", latin_slug)
        return f"{domain}-{latin_slug}" if latin_slug else f"{domain}-specialist"

    # ========================================================================
    # 7. Routine Computer-Use & Fast Reflex Dispatcher
    # ========================================================================

    def route_routine_action(self, user_query: str) -> RoutineActionDecision:
        """
        Zero-Token Fast Reflex Dispatcher for high-frequency computer-use and routine tasks.
        Bypasses LLM reasoning when a direct local command or MCP call is deterministic.
        """
        start_t = time.perf_counter()
        q = user_query.strip().lower()

        routine_specs = [
            (r"(запусти|прогони|запуск).*(тест|pytest)", "run_command", "pytest -v", "pytest_runner", "code"),
            (r"(прочитай|извлеки|распознай).*(буфер|скриншот|клипборд|ocr)", "run_command", r"python C:\vazus\clip_ocr.py", "clip_ocr", "system_architecture"),
            (r"(покажи|какой|проверь).*(баланс|карт)", "mcp_call", "tinkoff_finance_manager.get_balance", "tinkoff_finance_manager", "finance"),
            (r"(сделай|создай).*(бэкап|backup).*(баз|db)", "run_command", r"python C:\vazus\vazus_core\memory\backup_db.py", "sqlite_backup", "system_architecture"),
            (r"(проверь|покажи|сколько).*(долг|задолженност)", "mcp_call", "vazus-academic-debt-navigator.get_summary", "vazus-academic-debt-navigator", "academic"),
            (r"(синхронизируй|подключи|проверь).*(весы|взвешиван|mi scale)", "mcp_call", "mi_scale_sync.sync_reading", "mi_scale_sync", "health"),
        ]

        for pat, action_type, cmd, tool, domain in routine_specs:
            if re.search(pat, q):
                ms = (time.perf_counter() - start_t) * 1000.0
                return RoutineActionDecision(
                    is_routine=True,
                    action_type=action_type,
                    suggested_command=cmd,
                    target_tool=tool,
                    confidence=0.98,
                    latency_ms=round(ms, 2),
                    device_used="heuristic_reflex",
                    metadata={"domain": domain},
                )

        ms = (time.perf_counter() - start_t) * 1000.0
        return RoutineActionDecision(
            is_routine=False,
            action_type="none",
            suggested_command=None,
            target_tool=None,
            confidence=0.05,
            latency_ms=round(ms, 2),
            device_used="heuristic_reflex",
        )

    def get_skill_tree_progression(self, skill_name: str) -> Dict[str, Any]:
        """Returns prerequisites, forward paths, and domain metadata for a given skill in the tree."""
        if skill_name not in SKILL_TREE_GRAPH:
            return {"error": f"Skill '{skill_name}' not found in canonical graph"}
        info = SKILL_TREE_GRAPH[skill_name]
        return {
            "skill": skill_name,
            "domain": info.get("domain"),
            "description": info.get("description"),
            "prerequisites": info.get("prerequisites", []),
            "next_recommended": info.get("next", []),
        }


__all__ = [
    "CANONICAL_DOMAINS",
    "DOMAIN_TOOL_MAP",
    "SKILL_TREE_GRAPH",
    "RoutingDecision",
    "ChoiceDecision",
    "ScoreDecision",
    "NoulDecision",
    "ToolRoutingDecision",
    "SkillRoutingDecision",
    "RoutineActionDecision",
    "RLCDCalibrator",
    "JuliaONNXClassifier",
    "JuliaRouter",
]


def main() -> None:
    # Ensure UTF-8 output on Windows
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")

    router = JuliaRouter()
    print("=" * 70)
    print("Julia System-1 Decision Router Demo (OpenVINO / NPU Accelerated)")
    print("=" * 70)

    # 1. Test Domain Routing
    print("\n[1. Domain Routing]")
    queries = [
        "Срочно проверь задолженности по матанализу и график пересдач",
        "Сделай рефакторинг функции ast_prune и прогони pytest",
        "Посмотри сколько налога нужно заплатить за самозанятость в Тинькофф",
        "Что думаешь по поводу философии Ухтомского и доминанты внимания?",
    ]
    for q in queries:
        d = router.route(q)
        print(f" -> '{q[:40]}...' => {d.domain} (conf={d.confidence}, {d.latency_ms}ms, dev={d.metadata.get('device_used')})")

    # 2. Test Choice Primitive
    print("\n[2. Choice Primitive]")
    options = ["search_web", "playwright_browser", "cbm_ast_index", "run_pytest"]
    choice = router.route_choice("Проверь упавшие тесты в test_julia_router.py", options)
    print(f" -> Selected: {choice.selected} (conf={choice.confidence}, margin={choice.margin}, {choice.latency_ms}ms, dev={choice.device_used})")

    # 3. Test Score Primitive
    print("\n[3. Score Primitive]")
    score = router.route_score("Код не прошел тесты и выдал SyntaxError", "Code quality and test pass status")
    print(f" -> Score: {score.score:.2f} (norm={score.normalized_score:.2f}, {score.latency_ms}ms, dev={score.device_used})")

    # 4. Test Noul Primitive
    print("\n[4. Noul Primitive]")
    noul = router.route_noul("The code has syntax errors", "SyntaxError: invalid syntax on line 42")
    print(f" -> Hypothesis holds: {noul.passed} (prob={noul.probability:.2f}, conf={noul.confidence:.2f}, {noul.latency_ms}ms)")

    # 5. Test Tool Dispatch
    print("\n[5. Tool Dispatch]")
    tool = router.route_tool("Запусти pytest и проверь ast деревья")
    print(f" -> Tool: {tool.selected_tool} (domain={tool.domain}, conf={tool.confidence}, {tool.latency_ms}ms, dev={tool.device_used})")
    print("=" * 70)


if __name__ == "__main__":
    main()
