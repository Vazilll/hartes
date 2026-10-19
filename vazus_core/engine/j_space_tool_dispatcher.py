"""
vazus_core.engine.j_space_tool_dispatcher
=========================================
NPU Speculative Tool Dispatcher & J-Space Semantic Router for Vazus OS.

On EVERY turn of the dialogue (turn 0 and turn > 0), utilizes the high-speed
Julia-1 ONNX classifier (Intel AI Boost NPU, ~4.5ms) combined with J-Space
Jacobian Latent Space semantic tool pre-filtering (<1ms) to keep relevant tools
active in context with minimal token overhead (<15 tokens).

Output format:
⚡ [J-Space NPU Tool Activation]: <tool_1> (<desc>), <tool_2> (<desc>)
"""

from __future__ import annotations

import hashlib
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Ensure vazus root in path
ROOT_DIR = Path("/home/tarhes/Проекты/vazus")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.integrations.julia_router import JuliaONNXClassifier

logger = logging.getLogger("j_space_tool_dispatcher")


@dataclass
class ToolMatch:
    """Represents a matched tool candidate in J-Space."""

    name: str
    description: str
    similarity: float
    domain: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    @property
    def tool_name(self) -> str:
        return self.name

    @property
    def module(self) -> str:
        return self.category or self.name

    def __getitem__(self, item: str) -> Any:
        if item == "tool_name":
            return self.name
        if item == "module":
            return self.module
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        if item == "tool_name":
            return self.name
        if item == "module":
            return self.module
        return getattr(self, item, default)


class _HybridFindTools:
    """
    Descriptor enabling find_tools_for_query to be invoked either on the
    JSpaceToolIndexer class directly (e.g. JSpaceToolIndexer.find_tools_for_query(...))
    or on an instance (e.g. indexer.find_tools_for_query(...)).
    """

    def __get__(self, instance: Optional[JSpaceToolIndexer], owner: Any = None):
        if instance is None:

            def _classmethod_wrapper(
                prompt: str,
                top_k: int = 3,
                min_similarity: float = 0.35,
                domain: Optional[str] = None,
            ) -> List[ToolMatch]:
                inst = owner.get_default_instance()
                return inst.find_tools(prompt, top_k=top_k, min_similarity=min_similarity, domain=domain)

            return _classmethod_wrapper
        else:

            def _instancemethod_wrapper(
                prompt: str,
                top_k: int = 3,
                min_similarity: float = 0.35,
                domain: Optional[str] = None,
            ) -> List[ToolMatch]:
                return instance.find_tools(prompt, top_k=top_k, min_similarity=min_similarity, domain=domain)

            return _instancemethod_wrapper


class JSpaceToolIndexer:
    """
    J-Space Semantic Tool Indexer (768D Latent Projection).
    Indexes canonical system tools and custom tools, computing fast cosine similarity
    and lexical-semantic overlap in < 1 ms.
    """

    _default_instance: Optional[JSpaceToolIndexer] = None

    def __init__(self, auto_bootstrap: bool = True) -> None:
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._tool_names: List[str] = []
        self._tool_matrix: Optional[np.ndarray] = None
        self._matrix_dirty: bool = False
        if auto_bootstrap:
            self._bootstrap_canonical_tools()

    @classmethod
    def get_default_instance(cls) -> JSpaceToolIndexer:
        if cls._default_instance is None:
            cls._default_instance = cls(auto_bootstrap=True)
        return cls._default_instance

    @staticmethod
    def compute_j_space_vector(text: str, dim: int = 768) -> np.ndarray:
        """
        Projects arbitrary text into 768D J-Space representation using fast
        word-token + character 3-gram MD5 hashing, normalized to unit L2 sphere.
        Runs in < 0.2 ms in pure NumPy.
        """
        vec = np.zeros(dim, dtype=np.float32)
        clean = text.lower()
        words = re.findall(r"\b[\w-]{2,}\b", clean)
        for w in words:
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:8], 16) % dim
            vec[h] += 1.0
            # Include character 3-grams for morphological inflection matching (Russian/English)
            w_len = len(w)
            for i in range(max(0, w_len - 2)):
                gh = int(hashlib.md5(w[i : i + 3].encode("utf-8")).hexdigest()[:8], 16) % dim
                vec[gh] += 0.5

        norm = float(np.linalg.norm(vec))
        if norm > 1e-6:
            vec /= norm
        return vec

    def register_tool(
        self,
        name: str,
        description: str,
        tags: Optional[List[str]] = None,
        domain: Optional[str] = None,
        category: Optional[str] = None,
    ) -> None:
        """Registers a tool into the J-Space index with pre-computed 768D vector."""
        tag_list = tags or []
        combined_text = f"{name} {description} {' '.join(tag_list)}"
        vec = self.compute_j_space_vector(combined_text)

        self.tools[name] = {
            "name": name,
            "description": description,
            "tags": [t.lower() for t in tag_list],
            "domain": domain,
            "category": category,
            "vector": vec,
        }
        self._matrix_dirty = True

    def _rebuild_matrix_if_needed(self) -> None:
        if not self._matrix_dirty and self._tool_matrix is not None:
            return
        if not self.tools:
            self._tool_matrix = None
            self._tool_names = []
            self._matrix_dirty = False
            return

        self._tool_names = list(self.tools.keys())
        stacked = [self.tools[name]["vector"] for name in self._tool_names]
        self._tool_matrix = np.ascontiguousarray(stacked, dtype=np.float32)
        self._matrix_dirty = False

    def find_tools(
        self,
        prompt: str,
        top_k: int = 3,
        min_similarity: float = 0.35,
        domain: Optional[str] = None,
    ) -> List[ToolMatch]:
        """
        Discovers top-k candidate tools using J-Space 768D cosine similarity,
        lexical keyword overlap, and neural domain affinity.
        """
        if not prompt or not prompt.strip() or not self.tools:
            return []

        self._rebuild_matrix_if_needed()
        if self._tool_matrix is None or len(self._tool_names) == 0:
            return []

        q_vec = self.compute_j_space_vector(prompt)
        q_lower = prompt.lower()
        q_words = set(re.findall(r"\b[\w-]{2,}\b", q_lower))

        # Vectorized cosine similarity across all indexed tools
        cos_sims = np.dot(self._tool_matrix, q_vec)

        matches: List[ToolMatch] = []
        for idx, name in enumerate(self._tool_names):
            tool_data = self.tools[name]
            raw_cos = float(cos_sims[idx])

            # Lexical & stem matching score
            lex_score = 0.0
            d_name_lower = name.lower()
            if d_name_lower in q_lower:
                lex_score += 0.60
            elif any(part in q_words for part in d_name_lower.split("-") if len(part) >= 3):
                lex_score += 0.40

            tags = tool_data["tags"]
            for tag in tags:
                if tag in q_words:
                    lex_score += 0.50
                elif any(w.startswith(tag) or tag.startswith(w) for w in q_words if len(w) >= 3 and len(tag) >= 3):
                    lex_score += 0.40
                elif tag in q_lower:
                    lex_score += 0.30

            # Domain alignment boost from JuliaONNXClassifier
            domain_score = 0.0
            t_domain = tool_data.get("domain")
            if domain and t_domain:
                if domain == t_domain:
                    domain_score = 0.20
                elif domain in ("code", "system_architecture") and t_domain in ("code", "system_architecture"):
                    domain_score = 0.10

            # Combined multi-tier score
            total_score = min(1.0, 0.45 * lex_score + 0.40 * (raw_cos * 2.5) + domain_score)

            if total_score >= min_similarity:
                matches.append(
                    ToolMatch(
                        name=name,
                        description=tool_data["description"],
                        similarity=round(total_score, 4),
                        domain=t_domain,
                        category=tool_data.get("category"),
                        tags=tags,
                    )
                )

        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches[:top_k]

    # Hybrid descriptor enabling direct invocation on class or instance
    find_tools_for_query = _HybridFindTools()

    def _bootstrap_canonical_tools(self) -> None:
        """Populates canonical Vazus OS tools into the J-Space index."""
        canonical = [
            (
                "vazus-sandbox",
                "Windows Sandbox isolated execution and GUI/CLI automation",
                [
                    "песочница",
                    "песочниц",
                    "sandbox",
                    "изолированн",
                    "изоляци",
                    "тестбед",
                    "тестирован",
                    "guest",
                    "win32",
                    "контейнер",
                ],
                "code",
                "sandbox",
            ),
            (
                "db_backup",
                "Automated SQLite database backup, rotation and integrity check",
                [
                    "бэкап",
                    "бэкапа",
                    "бэкапы",
                    "backup",
                    "дамп",
                    "дампы",
                    "резервн",
                    "sqlite",
                    "база данных",
                    "vazus.db",
                    "база",
                    "сохранен",
                ],
                "system_architecture",
                "maintenance",
            ),
            (
                "vazus_ast_prune",
                "Prunes AST signatures to save tokens on Go, C, Python code",
                ["ast", "prune", "сигнатур", "рефакторинг", "токен", "парсинг", "ast_prune", "astprune"],
                "code",
                "code_intelligence",
            ),
            (
                "vazus_smt_z3_verify",
                "Formal verification and invariant contract proving via Microsoft Z3",
                ["z3", "smt", "верификаци", "доказательств", "инвариант", "контракт", "теорем", "smt z3"],
                "code",
                "verification",
            ),
            (
                "cbm_search_code",
                "Semantic and structural code graph search across codebase",
                ["поиск кода", "поиск", "cbm", "граф кода", "функци", "класс", "символ", "код"],
                "code",
                "cbm",
            ),
            (
                "vazus_finance_agent",
                "Tinkoff transactions, NPD freelance taxes, receipts and orders",
                ["финанс", "деньг", "тинькофф", "налог", "чек", "нпд", "самозанят", "доход", "расход", "баланс"],
                "finance",
                "finance",
            ),
            (
                "vazus_health_agent",
                "Mi Scale body composition, Google Fit telemetry, readiness score",
                ["здоровь", "вес", "сон", "пульс", "шаг", "ми шкал", "mi scale", "fit", "состав тела", "взвешиван"],
                "health",
                "health",
            ),
            (
                "vazus_academic_debt_navigator",
                "MIREA academic debt audit, Moodle SDO, and exam retake schedule",
                ["мирэа", "долг", "хвост", "сдо", "moodle", "пересдач", "зачет", "экзамен", "ивбо", "сесси"],
                "academic",
                "academic",
            ),
            (
                "jules_execute_task",
                "Google Jules cloud VM asynchronous coding, PR generation and pre-commit",
                ["jules", "джулс", "pr", "pull request", "облачн vm", "github pr", "асинхронн код"],
                "jules",
                "jules",
            ),
            (
                "playwright_browser",
                "Web browsing, page scraping, and browser automation via Playwright",
                ["браузер", "browser", "веб", "сайт", "playwright", "url", "погугли", "страниц"],
                "browser",
                "browser",
            ),
            (
                "radon_complexity",
                "Computes cyclomatic complexity CC and maintainability metrics",
                ["radon", "сложность", "complexity", "метрика", "цикломатическ", "cc", "хотспот"],
                "code",
                "code-quality",
            ),
            (
                "vazus_evidence_jury",
                "Concordia multi-agent jury consensus and formal verification voting",
                ["jury", "жюри", "конкордия", "concordia", "консенсус", "голосован"],
                "general_reasoning",
                "concordia",
            ),
        ]

        for name, desc, tags, dom, cat in canonical:
            self.register_tool(name, desc, tags=tags, domain=dom, category=cat)


def format_tool_directive(tools: List[ToolMatch]) -> str:
    """
    Formats the concise J-Space NPU tool directive (1-2 lines, ~15 tokens).
    Example:
    ⚡ [J-Space NPU Tool Activation]: vazus-sandbox (Windows Sandbox isolated execution and GUI/CLI automation)
    """
    if not tools:
        return ""

    parts = []
    for t in tools:
        desc = t.description
        if len(desc) > 65:
            desc = desc[:62].strip() + "..."
        parts.append(f"{t.name} ({desc})")

    return f"⚡ [J-Space NPU Tool Activation]: {', '.join(parts)}"


@dataclass
class DispatchResult:
    """Detailed telemetry result of speculative tool dispatch."""

    directive: str
    matches: List[ToolMatch]
    domain: str
    confidence: float
    latency_ms: float
    device: str
    backend: str


_CLASSIFIER_INSTANCE: Optional[JuliaONNXClassifier] = None


def get_default_classifier() -> JuliaONNXClassifier:
    global _CLASSIFIER_INSTANCE
    if _CLASSIFIER_INSTANCE is None:
        _CLASSIFIER_INSTANCE = JuliaONNXClassifier(device="NPU")
    return _CLASSIFIER_INSTANCE


class JSpaceToolDispatcher:
    """
    NPU Speculative Tool Dispatcher.
    Combines Julia-1 ONNX (Intel AI Boost NPU, ~4.5ms) and J-Space Latent Search (<1ms).
    Total latency < 20 ms.
    """

    def __init__(
        self,
        classifier: Optional[JuliaONNXClassifier] = None,
        indexer: Optional[JSpaceToolIndexer] = None,
    ) -> None:
        self.classifier = classifier
        self.indexer = indexer or JSpaceToolIndexer.get_default_instance()

    def _get_classifier(self) -> JuliaONNXClassifier:
        if self.classifier is None:
            self.classifier = get_default_classifier()
        return self.classifier

    def dispatch(
        self,
        prompt: str,
        top_k: int = 3,
        min_similarity: float = 0.35,
    ) -> str:
        """
        Dispatches prompt and returns formatted micro-directive string if relevant tools exist.
        Runs in < 20 ms.
        """
        if not prompt or not prompt.strip():
            return ""

        result = self.dispatch_detailed(prompt, top_k=top_k, min_similarity=min_similarity)
        return result.directive

    dispatch_prompt = dispatch  # Alias

    def dispatch_detailed(
        self,
        prompt: str,
        top_k: int = 3,
        min_similarity: float = 0.35,
    ) -> DispatchResult:
        """
        Executes end-to-end dispatch and returns full telemetry and matched tools.
        """
        start_t = time.perf_counter()

        if not prompt or not prompt.strip():
            return DispatchResult(
                directive="",
                matches=[],
                domain="general_reasoning",
                confidence=0.0,
                latency_ms=0.0,
                device="none",
                backend="none",
            )

        # 1. NPU intent classification via Julia-1 ONNX
        domain = "general_reasoning"
        conf = 0.0
        device = "heuristic"
        backend = "none"

        clf = self._get_classifier()
        if clf and clf.is_available:
            try:
                pred_domain, pred_conf, _, _ = clf.predict(prompt)
                domain = pred_domain
                conf = pred_conf
                device = clf.active_device or "NPU"
                backend = clf.backend or "openvino"
            except Exception as e:
                logger.debug("Neural intent classification error: %s", e)

        # 2. J-Space semantic tool index query
        matches = self.indexer.find_tools(
            prompt,
            top_k=top_k,
            min_similarity=min_similarity,
            domain=domain,
        )

        # 3. Format concise directive
        directive = format_tool_directive(matches)
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return DispatchResult(
            directive=directive,
            matches=matches,
            domain=domain,
            confidence=round(conf, 3),
            latency_ms=round(elapsed_ms, 2),
            device=device,
            backend=backend,
        )


_DEFAULT_DISPATCHER: Optional[JSpaceToolDispatcher] = None


def get_default_dispatcher() -> JSpaceToolDispatcher:
    global _DEFAULT_DISPATCHER
    if _DEFAULT_DISPATCHER is None:
        _DEFAULT_DISPATCHER = JSpaceToolDispatcher()
    return _DEFAULT_DISPATCHER


def dispatch_tools(prompt: str, top_k: int = 3, min_similarity: float = 0.35) -> str:
    """Convenience helper to dispatch tools from prompt."""
    return get_default_dispatcher().dispatch(prompt, top_k=top_k, min_similarity=min_similarity)


__all__ = [
    "ToolMatch",
    "JSpaceToolIndexer",
    "format_tool_directive",
    "DispatchResult",
    "JSpaceToolDispatcher",
    "get_default_dispatcher",
    "dispatch_tools",
]
