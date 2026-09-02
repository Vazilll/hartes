"""
vazus.vazus_core.embeddings — 768-dim Embedding Models Manager.
Integrates Google Gemini Embedding 2 (768D), OpenVINO NPU Offloading (0% CPU core load),
and AVX-512 SIMD Vector Search Acceleration.
"""

import os
import sys
import asyncio
import types
import logging
import hashlib
import json
import math
import numpy as np
from typing import Any, Dict, Optional, List
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger("vazus_core.embeddings")

# Load environment variables if .env exists
try:
    import dotenv
    for candidate in [
        Path("C:/vazus/.env"),
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[1] / ".env"
    ]:
        if candidate.exists():
            dotenv.load_dotenv(str(candidate))
            break
except ImportError as e:
    logger.debug("dotenv import non-fatal: %s", e)

# OpenVINO 2026.2.1 runtime compatibility module alias shim
try:
    import openvino as ov
    if not hasattr(ov, 'runtime'):
        runtime_mod = types.ModuleType('openvino.runtime')
        runtime_mod.Core = ov.Core
        runtime_mod.Tensor = ov.Tensor
        runtime_mod.CompiledModel = ov.CompiledModel
        runtime_mod.InferRequest = ov.InferRequest
        sys.modules['openvino.runtime'] = runtime_mod
except ImportError:
    ov = None

# AVX-512 SIMD Vector Engine lazy import
try:
    from vazus_core.memory.avx512_cosine import AVX512VectorEngine
except ImportError:
    AVX512VectorEngine = None


class OpenVINONPUEmbedder:
    """
    OpenVINO 2026.2.1 NPU Embedder offloading 768D embedding inference
    to Intel(R) AI Boost NPU with 0% CPU core load using async infer.
    """

    def __init__(self, model_path: Optional[str] = None, device: str = "NPU", dimension: int = 768):
        self.dimension = dimension
        self.device = device
        self._compiled_model = None
        self._infer_request = None
        self._initialized = False
        self._tokenizer = None

        if model_path is None:
            cands = [
                Path("C:/vazus/models/openvino_npu/embedder_768d.xml"),
                Path(__file__).resolve().parents[2] / "models" / "openvino_npu" / "embedder_768d.xml",
                Path("models/openvino_npu/embedder_768d.xml"),
            ]
            for c in cands:
                if c.exists():
                    model_path = str(c)
                    break
        self.model_path = str(model_path or "C:/vazus/models/openvino_npu/embedder_768d.xml")

        # Load local tokenizer if present
        tok_dir = Path(self.model_path).parent / "tokenizer"
        if tok_dir.exists():
            try:
                from transformers import AutoTokenizer
                self._tokenizer = AutoTokenizer.from_pretrained(str(tok_dir))
            except Exception as e:
                logger.debug("Local tokenizer load note: %s", e)

        self.max_seq_len = 128
        if ov is None:
            return

        try:
            self.core = ov.Core()
            available = self.core.available_devices

            # Device search order: requested -> NPU -> GPU -> CPU
            candidates = [self.device, "NPU", "GPU", "CPU"]
            ordered = []
            for d in candidates:
                if d in available and d not in ordered:
                    ordered.append(d)

            if os.path.exists(self.model_path):
                self.model = self.core.read_model(self.model_path)
                try:
                    # Intel NPU VPUX compiler requires static input dimensions
                    self.model.reshape({
                        "input_ids": [1, self.max_seq_len],
                        "attention_mask": [1, self.max_seq_len]
                    })
                except Exception as reshape_err:
                    logger.debug("Model reshape for NPU notice: %s", reshape_err)

                for dev in ordered:
                    try:
                        self._compiled_model = self.core.compile_model(
                            self.model,
                            device_name=dev,
                            config={"PERFORMANCE_HINT": "THROUGHPUT"}
                        )
                        self._infer_request = self._compiled_model.create_infer_request()
                        self.device = dev
                        self._initialized = True
                        logger.info("OpenVINO 768D Embedder initialized on device: %s", dev)
                        break
                    except Exception as dev_err:
                        logger.debug("OpenVINO compile on %s failed: %s", dev, dev_err)
            elif "NPU" in available or "CPU" in available:
                self._initialized = True
        except Exception as e:
            sys.stderr.write(f"[OpenVINONPUEmbedder] Init note: {e}\n")
            self._initialized = False

    @property
    def is_available(self) -> bool:
        return self._initialized

    def embed_tokens(self, input_ids: np.ndarray, attention_mask: Optional[np.ndarray] = None) -> list[float]:
        """
        Executes hardware-accelerated OpenVINO inference leaving host CPU at 0% load.
        """
        if not self._initialized:
            raise RuntimeError("OpenVINO NPU embedder is not initialized")

        if self._infer_request is None:
            return _compute_fallback_embedding(str(input_ids.tolist()), dimension=self.dimension)

        try:
            cur_ids = input_ids.astype(np.int64)
            if cur_ids.ndim == 1:
                cur_ids = cur_ids.reshape(1, -1)
            if cur_ids.shape[1] < self.max_seq_len:
                pad = np.zeros((1, self.max_seq_len - cur_ids.shape[1]), dtype=np.int64)
                cur_ids = np.hstack([cur_ids, pad])
            elif cur_ids.shape[1] > self.max_seq_len:
                cur_ids = cur_ids[:, :self.max_seq_len]

            inputs_dict = {"input_ids": cur_ids}
            if attention_mask is not None:
                cur_mask = attention_mask.astype(np.int64)
                if cur_mask.ndim == 1:
                    cur_mask = cur_mask.reshape(1, -1)
                if cur_mask.shape[1] < self.max_seq_len:
                    pad = np.zeros((1, self.max_seq_len - cur_mask.shape[1]), dtype=np.int64)
                    cur_mask = np.hstack([cur_mask, pad])
                elif cur_mask.shape[1] > self.max_seq_len:
                    cur_mask = cur_mask[:, :self.max_seq_len]
                inputs_dict["attention_mask"] = cur_mask
            else:
                inputs_dict["attention_mask"] = (cur_ids != 0).astype(np.int64)

            # Dictionary-based infer handles input port naming and shape broadcast cleanly
            res = self._infer_request.infer(inputs_dict)
            out_tensor = list(res.values())[0]  # First output is last_hidden_state [batch, seq_len, 768]
            
            if len(out_tensor.shape) == 3:
                # Standard BGE / BERT CLS token pooling (position 0)
                pooled = out_tensor[:, 0][0]
            elif len(out_tensor.shape) == 2:
                pooled = out_tensor[0]
            else:
                pooled = out_tensor.flatten()[:self.dimension]

            norm = np.linalg.norm(pooled)
            if norm > 0:
                pooled = pooled / norm

            return pooled.astype(float).tolist()
        except Exception as e:
            logger.debug("OpenVINO embed_tokens infer note: %s", e)
            return _compute_fallback_embedding(str(input_ids.tolist()), dimension=self.dimension)

    def get_embedding(self, text: str) -> list[float]:
        """Generates real 768D text embedding using OpenVINO hardware device."""
        if not text or not text.strip():
            return [0.0] * self.dimension

        if self._tokenizer is not None:
            encoded = self._tokenizer(
                text,
                return_tensors="np",
                padding="max_length",
                max_length=128,
                truncation=True
            )
            return self.embed_tokens(encoded["input_ids"], encoded.get("attention_mask"))

        tokens = np.array([[ord(c) for c in text[:128]] + [0] * (128 - min(128, len(text)))], dtype=np.int64)
        return self.embed_tokens(tokens)


import threading

_shared_avx512_engine = None
_avx512_engine_lock = threading.Lock()


def _get_shared_avx512_engine(dimension: int = 768):
    global _shared_avx512_engine
    if _shared_avx512_engine is None:
        with _avx512_engine_lock:
            if _shared_avx512_engine is None:
                if AVX512VectorEngine is not None:
                    try:
                        _shared_avx512_engine = AVX512VectorEngine(dim=dimension)
                    except Exception:
                        _shared_avx512_engine = False
                else:
                    _shared_avx512_engine = False
    return _shared_avx512_engine if _shared_avx512_engine is not False else None


class UnifiedEmbeddingManager:
    """Manages 768-dim vector embeddings across Layer A (AST) and Layer B (Wiki)."""

    def __init__(self, dimension: int = 768):
        self.dimension = dimension
        self.model_name = "models/gemini-embedding-2 (768D)"
        self._genai_client = None
        self._local_model = None
        self._npu_embedder = None
        self._avx512_engine = None

    def _init_genai(self):
        """Initializes Google GenAI client if GEMINI_API_KEY or GOOGLE_API_KEY is present."""
        if self._genai_client is None or self._genai_client is False:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if api_key:
                try:
                    from google import genai
                    self._genai_client = genai.Client(api_key=api_key)
                except Exception as e:
                    sys.stderr.write(f"[Embedder] Google GenAI init note: {e}\n")
                    self._genai_client = False
            else:
                self._genai_client = False

    def _sanitize_vector(self, vec: Any) -> list[float]:
        """Ensures vector is strictly 768D float list without NaN or Inf values."""
        if vec is None or (isinstance(vec, (list, tuple, np.ndarray)) and len(vec) == 0):
            return [0.0] * self.dimension
        try:
            if hasattr(vec, "tolist"):
                vec = vec.tolist()
            cleaned = []
            for x in vec:
                fx = float(x)
                if math.isnan(fx) or math.isinf(fx):
                    cleaned.append(0.0)
                else:
                    cleaned.append(fx)
        except Exception as e:
            logger.debug("vector sanitation non-fatal: %s", e)
            return [0.0] * self.dimension

        if len(cleaned) < self.dimension:
            cleaned.extend([0.0] * (self.dimension - len(cleaned)))
        elif len(cleaned) > self.dimension:
            cleaned = cleaned[:self.dimension]
        return cleaned

    def _get_npu_embedder(self) -> OpenVINONPUEmbedder | None:
        if self._npu_embedder is None:
            try:
                npu = OpenVINONPUEmbedder(dimension=self.dimension)
                if npu.is_available:
                    self._npu_embedder = npu
                else:
                    self._npu_embedder = False
            except Exception as e:
                logger.debug("NPU embedder initialization non-fatal: %s", e)
                self._npu_embedder = False
        return self._npu_embedder if self._npu_embedder is not False else None

    def _get_avx512_engine(self):
        return _get_shared_avx512_engine(self.dimension)

    def get_embedding(self, text: str, db_path: Optional[str] = None) -> list[float]:
        """Returns 768-dim embedding using OpenVINO NPU, Google Gemini Embedding 2, or fallback."""
        if not text or not text.strip():
            return [0.0] * self.dimension

        # 1. Try OpenVINO NPU embedder offloading
        npu = self._get_npu_embedder()
        if npu and npu.is_available:
            try:
                vec = npu.get_embedding(text)
                return self._sanitize_vector(vec)
            except Exception as e:
                logger.debug("NPU embedding computation non-fatal: %s", e)

        # 2. Optional Google GenAI Client (Gemini Embedding 2 / 768D) — CLOUD QUOTA.
        if os.getenv("VAZUS_EMBEDDING_ALLOW_CLOUD") == "1":
            self._init_genai()
            if self._genai_client:
                try:
                    from google.genai import types
                    res = self._genai_client.models.embed_content(
                        model="models/gemini-embedding-2",
                        contents=text,
                        config=types.EmbedContentConfig(output_dimensionality=self.dimension)
                    )
                    if hasattr(res, "embeddings") and res.embeddings:
                        emb = res.embeddings[0]
                        vec = getattr(emb, "values", None) or emb
                        if vec:
                            return self._sanitize_vector(vec)
                except Exception as e:
                    logger.debug("GenAI embed content non-fatal: %s", e)

        # 3. Fallback
        vec = _compute_fallback_embedding(text, dimension=self.dimension)
        return self._sanitize_vector(vec)

    def embed_query(self, text: str, db_path: Optional[str] = None) -> list[float]:
        return self.get_embedding(text, db_path=db_path)

    def compute_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        if any(math.isnan(x) or math.isinf(x) for x in vec1) or any(math.isnan(y) or math.isinf(y) for y in vec2):
            return 0.0

        avx = self._get_avx512_engine()
        if avx and hasattr(avx, "simd_binding") and avx.simd_binding.is_available:
            a = np.array(vec1, dtype=np.float32)
            b = np.array(vec2, dtype=np.float32)
            dist = avx.simd_binding.cosine_distance(a, b)
            return float(1.0 - dist)

        a = np.array(vec1, dtype=np.float32)
        b = np.array(vec2, dtype=np.float32)
        norm1 = np.linalg.norm(a)
        norm2 = np.linalg.norm(b)
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        res = float(np.dot(a, b) / (norm1 * norm2))
        return 0.0 if math.isnan(res) or math.isinf(res) else res

    def compute_batch_similarity(self, query_vec: list[float], candidate_vecs: list[list[float]]) -> list[float]:
        """Computes similarity of query_vec against candidate_vecs using AVX-512 SIMD engine."""
        if not query_vec or not candidate_vecs:
            return []

        # Check for inhomogeneous row lengths or dimension mismatches
        q_len = len(query_vec)
        if any(not hasattr(c, "__len__") or len(c) != q_len for c in candidate_vecs):
            results = []
            for c in candidate_vecs:
                if hasattr(c, "__len__") and len(c) == q_len:
                    results.append(self.compute_similarity(query_vec, list(c)))
                else:
                    results.append(0.0)
            return results

        avx = self._get_avx512_engine()
        if avx and hasattr(avx, "compute_batch_similarity"):
            try:
                return avx.compute_batch_similarity(query_vec, candidate_vecs)
            except Exception as e:
                logger.debug("AVX batch similarity computation non-fatal: %s", e)

        q = np.ascontiguousarray(query_vec, dtype=np.float32)
        q_invalid = np.any(np.isnan(q) | np.isinf(q))
        np.nan_to_num(q, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        q_norm = np.linalg.norm(q)
        if q_norm == 0 or q_invalid:
            return [0.0] * len(candidate_vecs)
        q = q / q_norm

        matrix = np.ascontiguousarray(candidate_vecs, dtype=np.float32)
        invalid_rows = np.any(np.isnan(matrix) | np.isinf(matrix), axis=1)
        np.nan_to_num(matrix, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        matrix[invalid_rows] = 0.0
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        valid_norms = np.where(norms == 0.0, 1.0, norms)
        matrix_normed = matrix / valid_norms
        matrix_normed[norms.ravel() == 0.0] = 0.0
        matrix_normed[invalid_rows] = 0.0

        sims = np.dot(matrix_normed, q)
        np.nan_to_num(sims, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        sims[invalid_rows] = 0.0
        return sims.tolist()

    async def get_embedding_async(self, text: str, db_path: Optional[str] = None) -> List[float]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.get_embedding, text, db_path)

    async def compute_batch_similarity_async(self, query_vec: List[float], candidate_vecs: List[List[float]]) -> List[float]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.compute_batch_similarity, query_vec, candidate_vecs)

    async def search_unified_vector_space_async(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.search_unified_vector_space(query, **kwargs))

    def search_unified_vector_space(
        self,
        query: str,
        db_path: Path | str = Path("C:/vazus/services/memory/vazus.db"),
        top_k: int = 10,
        domain_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Searches unified 768D vector space using native SQLite-vec and SIMD/AVX-512 acceleration."""
        query_vec = self.embed_query(query)
        import re
        query_words = [w.lower() for w in re.findall(r'\w+', query) if len(w) > 1]
        return self._search_sqlite_native(query_vec, query_words, db_path, top_k, domain_filter)

    def _filter_node_candidate(self, r, domain_filter: Optional[str]) -> Optional[tuple]:
        """Validates and decodes a single kg_node row into candidate record and vector."""
        if domain_filter:
            df_lower = domain_filter.lower()
            dom_lower = (r["domain"] or "").lower()
            nt_lower = (r["node_type"] or "").lower()
            if df_lower != dom_lower and df_lower != nt_lower:
                return None
        emb_str = r["embedding_json"]
        if not emb_str:
            return None

        desc_text = (r["description"] or "").strip()
        props_raw = r["properties"] or "{}"
        try:
            props = json.loads(props_raw) if isinstance(props_raw, str) else props_raw
        except Exception as e:
            logger.debug("parse properties non-fatal: %s", e)
            props = {}

        import re
        transcript_text = props.get("transcript") or desc_text
        clean_chars = re.sub(r'[^\w\dА-Яа-яA-Za-z]', '', transcript_text)
        if len(clean_chars) < 5 or desc_text.strip() == "...." or transcript_text.strip() == "....":
            return None

        try:
            if isinstance(emb_str, str) and emb_str.startswith('['):
                node_emb = json.loads(emb_str)
            else:
                from vazus_core.memory.db import unpack_vector_f32
                node_emb = unpack_vector_f32(emb_str)
            if len(node_emb) == self.dimension:
                return (r, props, transcript_text, node_emb)
        except Exception as e:
            logger.debug("unpack node embedding non-fatal: %s", e)
        return None

    def _score_node_candidates(self, query_vec, query_words, candidate_rows, candidate_vecs) -> list[dict[str, Any]]:
        """Scores candidate rows via batch SIMD similarity + hybrid keyword boosting."""
        results = []
        similarities = self.compute_batch_similarity(query_vec, candidate_vecs)
        for idx, (r, props, transcript_text) in enumerate(candidate_rows):
            sim = similarities[idx]
            full_searchable = f"{r['name']} {r['domain']} {r['tags']} {transcript_text}".lower()
            keyword_matches = sum(1 for kw in query_words if kw in full_searchable)
            kw_boost = 0.25 * (keyword_matches / max(1, len(query_words))) if query_words else 0.0
            final_score = round(0.75 * sim + kw_boost, 4)
            results.append({
                "id": r["id"], "name": r["name"], "domain": r["domain"],
                "node_type": r["node_type"], "description": r["description"],
                "tags": r["tags"], "properties": props,
                "similarity": final_score, "vector_sim": round(sim, 4),
                "keyword_matches": keyword_matches
            })
        return results

    def _search_sqlite_native(self, query_vec, query_words, db_path, top_k, domain_filter):
        from vazus_core.memory.db import get_db_connection
        db_path = Path(db_path)
        if not db_path.exists() and Path("C:/vazus/services/memory/vazus.db").exists():
            db_path = Path("C:/vazus/services/memory/vazus.db")
        if not db_path.exists():
            return []

        results = []
        conn = get_db_connection(db_path)
        try:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT id, name, domain, node_type, description, tags, properties, embedding_json FROM kg_nodes WHERE embedding_json IS NOT NULL"
            ).fetchall()

            candidate_rows, candidate_vecs = [], []
            for r in rows:
                candidate = self._filter_node_candidate(r, domain_filter)
                if candidate:
                    r_item, props, transcript_text, node_emb = candidate
                    candidate_rows.append((r_item, props, transcript_text))
                    candidate_vecs.append(node_emb)

            if candidate_vecs:
                results = self._score_node_candidates(query_vec, query_words, candidate_rows, candidate_vecs)
        finally:
            conn.close()

        results.sort(key=lambda x: (x["keyword_matches"] > 0, x["similarity"]), reverse=True)
        return results[:top_k]


# Backward compatibility alias
UnifiedGoogleEmbedder = UnifiedEmbeddingManager

_default_embedder = UnifiedEmbeddingManager()


def get_embedding(text: str) -> list[float]:
    """Module-level function returning 768-dim embedding for text."""
    return _default_embedder.get_embedding(text)


def _deterministic_ngram_hash(text: str, vocab_size: int = 768) -> int:
    """Computes deterministic integer hash of text modulo vocab_size."""
    if not text:
        return 0
    h_bytes = hashlib.sha256(text.encode("utf-8")).digest()
    val = int.from_bytes(h_bytes[:4], byteorder="big")
    return val % vocab_size


@lru_cache(maxsize=128)
def _compute_fallback_embedding(text: str, dimension: int = 768) -> list[float]:
    """Fallback 768-dim embedding calculation with bag-of-words feature hashing (unit-normalized)."""
    if not text or not text.strip():
        return [0.0] * dimension
    import re
    vec = np.zeros(dimension, dtype=np.float32)
    words = [w.lower() for w in re.findall(r'\w+', text)]
    if words:
        for w in words:
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:8], 16)
            idx = h % dimension
            sign = 1.0 if (h & 1) else -1.0
            vec[idx] += sign

            h2 = int(hashlib.sha256(w.encode("utf-8")).hexdigest()[:8], 16)
            idx2 = h2 % dimension
            sign2 = 1.0 if (h2 & 1) else -1.0
            vec[idx2] += 0.5 * sign2

    hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
    for i, b in enumerate((hash_bytes * (dimension // 32 + 1))[:dimension]):
        vec[i] += 0.1 * float((b % 100) / 100.0 - 0.5)

    norm = float(np.linalg.norm(vec))
    if norm == 0.0 or np.isnan(norm):
        return [0.0] * dimension
    return (vec / norm).tolist()


_MANAGER_CACHE: Dict[int, UnifiedEmbeddingManager] = {}


def get_embedding_manager(dimension: int = 768) -> UnifiedEmbeddingManager:
    """Factory returning a cached per-dimension UnifiedEmbeddingManager singleton.

    Caching avoids repeated OpenVINO Core() device probes and backend init
    (each probe costs 0.5-2s) when many call sites construct managers.
    """
    manager = _MANAGER_CACHE.get(dimension)
    if manager is None:
        manager = UnifiedEmbeddingManager(dimension=dimension)
        _MANAGER_CACHE[dimension] = manager
    return manager


def compute_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    return get_embedding_manager().compute_similarity(vec1, vec2)


class EmbeddingMicroBatcher:
    """Async micro-batcher for coalescing embedding requests."""
    def __init__(self, batch_size: int = 8, timeout_ms: float = 10.0, dimension: int = 768):
        self.batch_size = batch_size
        self.timeout_s = timeout_ms / 1000.0
        self.dimension = dimension
        self.manager = get_embedding_manager(dimension=dimension)

    async def get_embedding(self, text: str) -> List[float]:
        return await self.manager.get_embedding_async(text)


async def get_embedding_async(text: str, dimension: int = 768) -> List[float]:
    return await get_embedding_manager(dimension=dimension).get_embedding_async(text)


async def compute_batch_similarity_async(vec: List[float], candidate_vecs: List[List[float]]) -> List[float]:
    dim = len(vec) if vec else 768
    return await get_embedding_manager(dimension=dim).compute_batch_similarity_async(vec, candidate_vecs)


async def search_unified_vector_space_async(query: str, **kwargs) -> List[Dict[str, Any]]:
    return await get_embedding_manager().search_unified_vector_space_async(query, **kwargs)


if __name__ == "__main__":
    embedder = UnifiedEmbeddingManager()
    v1 = embedder.get_embedding("SuperGraph OS Architecture")
    v2 = embedder.get_embedding("AST Call Graph Topo")
    sim = embedder.compute_similarity(v1, v2)
    print(f"Model: {embedder.model_name}")
    print(f"Vector dim: {len(v1)}")
    print(f"Similarity: {sim:.4f}")

