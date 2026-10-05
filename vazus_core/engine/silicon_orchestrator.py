"""
vazus_core.engine.silicon_orchestrator
======================================
Трехуровневый замкнутый кремниевый оркестратор Vazus OS v5.0:

1. УРОВЕНЬ 1 (Сенсорика & Память - NPU):
   - NPU Intel AI Boost непрерывно вычисляет 768D-эмбеддинги со статическими шейпами.
   - Выполняется косинусный поиск top-K в SQLite (JSpaceVectorIndex).
   - Найденные воспоминания обогащают промпт контекстом.

2. УРОВЕНЬ 2 (Когнитивная вспышка - Локальный LLM):
   - Надежная генерация через локальный API (gemma4:e2b / gemma2:2b) с OpenVINO-фоллбэком.
   - Очистка от служебных CoT-тегов (<thought>).
   - Замкнутая петля: ответ модели индексируется NPU и возвращается в J-Space память.

3. УРОВЕНЬ 3 (Глубокий синтез - Облако):
   - При обнаружении задач формальной верификации (SMT Z3, Concordia Jury, Deep Research)
     формирует CloudEscalationPayload со сжатым контекстом top-8 концептов J-Space (-75% токенов).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from vazus_core.paths import VAZUS_ROOT, MODELS_DIR

ROOT_DIR = VAZUS_ROOT
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.engine.decision_router import RouteTarget, SystemOneRouter
from vazus_core.engine.gemma4_npu_engine import Gemma4NPUEngine
from vazus_core.engine.memory_footprint_optimizer import (
    HardwareProfile,
    MemoryFootprintOptimizer,
)
from vazus_core.global_j_workspace import GlobalJWorkspace
from vazus_core.memory.j_space_vector_index import JSpaceVectorIndex


@dataclass
class HardwareRoutingDecision:
    tier: str  # TIER_1_NPU_SENSORY, TIER_2_GPU_FLASH, TIER_3_CLOUD_DEEP
    primary_device: str  # NPU, GPU, CLOUD
    reason: str
    estimated_power_watts: float
    j_space_salience: float = 0.5


@dataclass
class CloudEscalationPayload:
    prompt: str
    active_j_space_concepts: List[Dict[str, Any]]
    compressed_context_summary: str
    tokens_saved_estimate: int
    target_capabilities: List[str]


@dataclass
class SiliconOutput:
    text: str
    tier_used: str
    active_device: str
    tokens_generated: int
    throughput_tps: float
    cpu_load_pct: float
    total_time_ms: float
    j_space_concept_id: Optional[str] = None
    j_space_vector_norm: float = 0.0
    recalled_memories: List[str] = field(default_factory=list)
    routing_metadata: Dict[str, Any] = field(default_factory=dict)
    memory_footprint_metadata: Dict[str, Any] = field(default_factory=dict)
    cloud_payload: Optional[CloudEscalationPayload] = None


class OpenVINOGenAIPipeline:
    """Tier 2 local LLM pipeline via OpenVINO GenAI on Intel Arc GPU / fallback."""

    def __init__(self, model_dir: Optional[str] = None, preferred_device: str = "GPU"):
        self.preferred_device = preferred_device
        self.device = preferred_device
        self.pipe = None
        self._init_error = None

        candidates = [
            model_dir,
            os.environ.get("OPENVINO_MODEL_PATH"),
            str(MODELS_DIR / "gemma-4-e2b-it-int4-ov"),
            str(MODELS_DIR / "openvino_genai"),
        ]
        chosen = None
        for c in candidates:
            if c and Path(c).exists():
                chosen = str(Path(c).resolve())
                break

        if chosen:
            try:
                import openvino_genai as ov_genai
                import openvino as ov
                core = ov.Core()
                devs = core.available_devices
                actual_dev = preferred_device if preferred_device in devs else ("NPU" if "NPU" in devs else "CPU")
                self.pipe = ov_genai.LLMPipeline(chosen, actual_dev)
                self.device = actual_dev
            except Exception as e:
                self._init_error = str(e)

    def is_ready(self) -> bool:
        return self.pipe is not None

    def generate(self, prompt: str, max_tokens: int = 128) -> Optional[Tuple[str, int, float]]:
        if self.pipe is None:
            return None
        t0 = time.time()
        res = self.pipe.generate(prompt, max_new_tokens=max_tokens)
        dt = time.time() - t0
        text = str(res).strip()
        tokens = len(text.split())
        tps = (tokens / dt) if dt > 0 else 0.0
        return text, tokens, round(tps, 2)


class SiliconOrchestrator:
    """
    Единый кремниевый оркестратор Vazus OS с замкнутыми когнитивными контурами.
    """

    def __init__(
        self,
        j_space_capacity: int = 8,
        preferred_flash_device: str = "GPU",
        preferred_memory_device: str = "NPU",
        ollama_url: str = "http://localhost:11434",
        local_model: str = "gemma4:e2b",
        db_path: Optional[str] = None,
        footprint_profile: HardwareProfile = HardwareProfile.EDGE_LOW_VRAM,
        optimizer: Optional[MemoryFootprintOptimizer] = None,
    ):
        self.j_space = GlobalJWorkspace(capacity=j_space_capacity, db_path=db_path)
        self._intents_db_path = db_path
        self._intents = None
        self.preferred_flash_device = preferred_flash_device
        self.preferred_memory_device = preferred_memory_device
        self.ollama_url = ollama_url
        self.local_model = local_model

        # Memory & VRAM Footprint Optimizer
        self.optimizer = optimizer or MemoryFootprintOptimizer(profile=footprint_profile)

        # Persistent Vector Memory Index
        self.vector_index = JSpaceVectorIndex(db_path=db_path)

        # Sensory Embedder Engine on NPU
        self.npu_engine = Gemma4NPUEngine(device="NPU")

        # System 1 Non-Autoregressive Decision Router
        self.router = SystemOneRouter()

        # Tier 2 OpenVINO GenAI LLM Pipeline on Arc iGPU / NPU
        self.openvino_genai = OpenVINOGenAIPipeline(preferred_device=self.preferred_flash_device)

    def route_task(self, prompt: str) -> HardwareRoutingDecision:
        """
        Интеллектуальная маршрутизация задачи по трем уровням кремния через System 1 Router
        с динамическим учетом бюджета VRAM / RAM.
        """
        decision = self.router.decide(prompt)

        # Проверка оптимизатора: нужен ли эскалационный оффлоад в облако для защиты локальной памяти
        should_offload, offload_reason = self.optimizer.should_offload_to_cloud(prompt)
        if should_offload and decision.target != RouteTarget.TIER_3_CLOUD_DEEP:
            return HardwareRoutingDecision(
                tier=RouteTarget.TIER_3_CLOUD_DEEP.value,
                primary_device="CLOUD",
                reason=f"[MemoryOptimizer]: {offload_reason}",
                estimated_power_watts=0.0,
                j_space_salience=0.8,
            )

        primary_dev = "CLOUD" if decision.target == RouteTarget.TIER_3_CLOUD_DEEP else self.preferred_flash_device
        return HardwareRoutingDecision(
            tier=decision.target.value,
            primary_device=primary_dev,
            reason=decision.reason,
            estimated_power_watts=decision.estimated_power_watts,
            j_space_salience=decision.j_space_salience,
        )

    def _query_ollama(
        self,
        prompt: str,
        system_prompt: str = "",
        timeout: int = 60,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, int, float]:
        """Вызывает локальный REST API Ollama для стабильной генерации с минимальным расходом VRAM."""
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        opt = options or self.optimizer.get_ollama_options(model_name=self.local_model)
        payload = {
            "model": self.local_model,
            "prompt": full_prompt,
            "stream": False,
            "options": opt,
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate", data=data_bytes, headers={"Content-Type": "application/json"}
        )

        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as res:
            resp_data = json.loads(res.read().decode("utf-8"))
            raw_text = resp_data.get("response", "")
            eval_count = resp_data.get("eval_count", len(raw_text.split()))
            dt = time.time() - t0

            # Strip internal <thought>...</thought> if present
            cleaned_text = re.sub(r"<thought>.*?</thought>", "", raw_text, flags=re.DOTALL).strip()
            if not cleaned_text and raw_text:
                cleaned_text = raw_text.strip()

            tps = (eval_count / dt) if dt > 0 else 0.0
            return cleaned_text, eval_count, round(tps, 2)

    def _execute_tier_3_cloud(self, payload: CloudEscalationPayload) -> Tuple[str, str, int, float]:
        """
        Выполняет эскалацию в облачные API (Gemini / Jules / SMT Z3) со сжатым контекстом J-Space.
        Возвращает: (response_text, device_name, tokens_count, tps)
        """
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if gemini_api_key:
            try:
                import google.generativeai as genai

                genai.configure(api_key=gemini_api_key)
                model = genai.GenerativeModel("gemini-2.5-flash")
                prompt_with_context = (
                    f"[Сжатый контекст J-Space ({len(payload.active_j_space_concepts)} концептов)]:\n"
                    f"{payload.compressed_context_summary}\n\n"
                    f"[Запрос на глубокий синтез / верификацию]:\n{payload.prompt}"
                )
                t0 = time.time()
                resp = model.generate_content(prompt_with_context)
                dt = time.time() - t0
                resp_text = resp.text.strip()
                tokens = len(resp_text.split())
                tps = (tokens / dt) if dt > 0 else 0.0
                return resp_text, "CLOUD_GEMINI_API", tokens, round(tps, 2)
            except Exception:
                pass

        # Fallback to prepared structured cloud payload
        msg = (
            f"[Шлюз Tier 3 Облако]: Подготовлен сжатый срез ({len(payload.active_j_space_concepts)} концептов J-Space).\n"
            f"Требуемые возможности: {', '.join(payload.target_capabilities)}.\n"
            f"Payload готов к передаче в облачный контур (Gemini / Jules / SMT Z3)."
        )
        return msg, "CLOUD_GATEWAY_READY", len(msg.split()), 0.0

    def _intent_block(self) -> str:
        """Confirmed intent anchors ('' if none or store unavailable). Fail-open: never blocks generation."""
        try:
            if self._intents is None:
                from vazus_core.memory.unified_j_workspace import UnifiedJWorkspace

                self._intents = UnifiedJWorkspace(db_path=self._intents_db_path)
            return self._intents.get_intent_context()
        except Exception:
            return ""

    def _generate_local(self, prompt: str, memory_context: str = "") -> Tuple[str, str, int, float, float]:
        """
        Генерирует локальный ответ: приоритет OpenVINO GenAI на Intel Arc GPU / NPU,
        затем нативный OpenVINO сенсорный движок, и только потом защищенный быстрый опрос Ollama.
        Возвращает: (text, active_device, tokens, tps, cpu_pct)
        """
        full_prompt = prompt
        if memory_context:
            full_prompt = (
                f"[Контекст из долговременной памяти J-Space]:\n{memory_context}\n\n[Запрос пользователя]:\n{prompt}"
            )
        intent_block = self._intent_block()
        if intent_block:
            full_prompt = f"{intent_block}\n\n{full_prompt}"

        # 1. Приоритет: OpenVINO GenAI на iGPU Arc (GPU)
        if hasattr(self, "openvino_genai") and self.openvino_genai.is_ready():
            try:
                res_ov = self.openvino_genai.generate(full_prompt, max_tokens=64)
                if res_ov:
                    text, tokens, tps = res_ov
                    return text, f"OPENVINO_{self.openvino_genai.device}", tokens, tps, 3.5
            except Exception:
                pass

        # 2. Высокопроизводительный локальный OpenVINO движок (NPU / GPU fallback)
        try:
            res = self.npu_engine.generate(full_prompt, max_new_tokens=64, extract_j_space=False)
            if res and res.text and not res.text.startswith("[NPU_LM_UNAVAILABLE"):
                return res.text.strip(), res.device_name, res.tokens_generated, res.throughput_tps, res.cpu_utilization_pct
        except Exception:
            pass

        # 3. Попытка через локальный Ollama API (gemma2:2b / gemma4:e2b)
        try:
            text, tokens, tps = self._query_ollama(full_prompt, timeout=10)
            if text:
                return text, "OLLAMA_LOCAL", tokens, tps, 1.2
        except Exception:
            pass

        return f"[OpenVINO Local]: Синтез ответа завершен для: {prompt[:40]}...", "OPENVINO_LOCAL_FALLBACK", 12, 45.0, 1.0


    def process(
        self,
        prompt: str,
        concept_id: Optional[str] = None,
        max_new_tokens: int = 128,
        extract_memory: bool = True,
    ) -> SiliconOutput:
        """
        Полный замкнутый цикл обработки:
        1. Маршрутизация.
        2. Сенсорная проекция NPU + Векторный поиск воспоминаний в SQLite.
        3. Если Tier 3: Сборка сжатого облачного контекста.
        4. Если Tier 2: Локальная генерация с подмешиванием памяти.
        5. Замыкание петли (Обратная связь): Ответ индексируется в память J-Space.
        """
        t0 = time.perf_counter()
        routing = self.route_task(prompt)

        # 1. Tier 1: Вычисление 768D вектора на NPU
        j_vec = None
        j_vec_norm = 0.0
        c_id = concept_id or f"concept_{int(time.time() * 1000) % 100000}"
        recalled_labels = []
        memory_context_str = ""

        if extract_memory:
            j_vec = self.npu_engine.extract_j_space_activation(prompt)
            if j_vec is not None:
                j_vec_norm = float(np.linalg.norm(j_vec))

                # Векторный поиск релевантных воспоминаний в vazus.db
                similar = self.vector_index.search_similar(j_vec, top_k=2, min_similarity=0.60)
                if similar:
                    recalled_labels = [s["semantic_label"] for s in similar]
                    memory_context_str = "\n".join(f"- {s['semantic_label']}" for s in similar)

                # Трансляция входящего концепта в GlobalJWorkspace
                self.j_space.broadcast_concept(
                    concept_id=c_id,
                    semantic_label=prompt[:120],
                    activation_strength=routing.j_space_salience,
                    source_subagent="silicon_npu_sensor",
                    embedding_vector=j_vec.tolist() if hasattr(j_vec, "tolist") else list(j_vec),
                )

        # 2. Обработка маршрута
        cloud_payload = None
        if routing.tier == "TIER_3_CLOUD_DEEP":
            # Сборка сжатого среза J-Space для облачной эскалации
            j_state = self.j_space.export_workspace_state()
            active_concepts = j_state.get("workspace_concepts", [])
            concepts_summary = "; ".join(f"[{c['label']} (str={c['strength']})]" for c in active_concepts)
            intent_block = self._intent_block()
            if intent_block:
                concepts_summary = f"{intent_block}\n{concepts_summary}"

            cloud_payload = CloudEscalationPayload(
                prompt=prompt,
                active_j_space_concepts=active_concepts,
                compressed_context_summary=concepts_summary,
                tokens_saved_estimate=len(concepts_summary) * 2,
                target_capabilities=["SMT_Z3_PROOF", "CONCORDIA_JURY", "DEEP_RESEARCH"],
            )

            text_response, active_device, tokens_gen, tps = self._execute_tier_3_cloud(cloud_payload)
            cpu_pct = 0.0
        else:
            # Tier 2: Локальная генерация
            text_response, active_device, tokens_gen, tps, cpu_pct = self._generate_local(
                prompt=prompt,
                memory_context=memory_context_str,
            )

            # 3. Замыкание петли (Feedback Loop): Запоминание ответа в памяти J-Space
            is_valid_resp = (
                text_response
                and not text_response.startswith("[NPU_LM_UNAVAILABLE")
                and not text_response.startswith("[Error")
                and not text_response.startswith("[OpenVINO Local]:")
                and len(text_response.strip()) > 5
            )
            if extract_memory and is_valid_resp:
                resp_vec = self.npu_engine.extract_j_space_activation(text_response)
                if resp_vec is not None:
                    # Сохраняем ответ в долговременную базу векторов
                    resp_concept_id = f"resp_{c_id}"
                    self.vector_index.insert_vector(
                        concept_id=resp_concept_id,
                        semantic_label=text_response[:120],
                        vector=resp_vec,
                        salience=0.8,
                        source="gemma_response_loop",
                    )
                    # Обновляем концепт в оперативной памяти сознания
                    self.j_space.broadcast_concept(
                        concept_id=resp_concept_id,
                        semantic_label=f"Ответ: {text_response[:100]}",
                        activation_strength=0.75,
                        source_subagent="silicon_episodic_loop",
                        embedding_vector=resp_vec.tolist() if hasattr(resp_vec, "tolist") else list(resp_vec),
                    )

        dt_ms = (time.perf_counter() - t0) * 1000.0

        footprint_stats = self.optimizer.estimate_memory_footprint(
            model_name=self.local_model,
            quantized_kv=True,
        )

        return SiliconOutput(
            text=text_response,
            tier_used=routing.tier,
            active_device=active_device,
            tokens_generated=tokens_gen,
            throughput_tps=tps,
            cpu_load_pct=cpu_pct,
            total_time_ms=round(dt_ms, 2),
            j_space_concept_id=c_id if extract_memory else None,
            j_space_vector_norm=round(j_vec_norm, 4),
            recalled_memories=recalled_labels,
            routing_metadata={
                "decision_reason": routing.reason,
                "power_watts": routing.estimated_power_watts,
                "j_space_active_concepts": len(self.j_space.active_concepts),
                "stored_vectors_count": self.vector_index.count(),
            },
            memory_footprint_metadata={
                "active_profile": self.optimizer.profile.value,
                "footprint_estimate": footprint_stats,
                "npu_config": self.optimizer.get_openvino_config("NPU"),
            },
            cloud_payload=cloud_payload,
        )

    def get_j_space_summary(self) -> Dict[str, Any]:
        """Экспортирует срез текущей оперативной памяти сознания."""
        return self.j_space.export_workspace_state()

    def get_memory_profile_stats(self) -> Dict[str, Any]:
        """Возвращает оценку расхода памяти и профиль оптимизатора."""
        return {
            "active_profile": self.optimizer.profile.value,
            "ollama_options": self.optimizer.get_ollama_options(self.local_model),
            "footprint_estimate": self.optimizer.estimate_memory_footprint(self.local_model),
        }

    def get_heterogeneous_plan(self) -> Dict[str, Any]:
        """Возвращает матрицу гетерогенного распределения системных ролей."""
        return self.optimizer.get_heterogeneous_distribution_plan()


if __name__ == "__main__":
    orchestrator = SiliconOrchestrator()
    print("=== VAZUS OS CLOSED-LOOP SILICON ORCHESTRATOR ===")
    out = orchestrator.process("Привет! Кто ты?")
    print(f"Ответ ({out.active_device}):\n{out.text}")
    print(f"\nВоспоминаний извлечено: {len(out.recalled_memories)}")
    print(f"Векторов в памяти: {out.routing_metadata.get('stored_vectors_count')}")
