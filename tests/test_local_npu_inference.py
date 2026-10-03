"""
tests/test_local_npu_inference.py
=================================
Verification suite for local hardware-accelerated inference in Vazus OS:
- OpenVINO Core initialization and hardware device discovery (NPU, GPU, CPU).
- JuliaONNXClassifier loading and real inference targeting Intel(R) AI Boost NPU.
- Automatic device fallback chain (NPU -> GPU -> CPU).
- JuliaRouter end-to-end System-1 intent classification with strict sub-150ms latency guarantee.
- OpenVINONPUEmbedder 768D embedding extraction on Intel AI Boost NPU.
"""

import time
import pytest
import numpy as np

import openvino as ov
from vazus_core.integrations.julia_router import (
    JuliaONNXClassifier,
    JuliaRouter,
    RoutingDecision,
    CANONICAL_DOMAINS,
)
from vazus_core.memory.embeddings import OpenVINONPUEmbedder


def test_openvino_core_init_and_device_discovery():
    """Confirms OpenVINO Core initialization and device probing."""
    core = ov.Core()
    assert core is not None, "OpenVINO Core failed to instantiate"

    devices = core.available_devices
    print(f"\n[Hardware Probing] OpenVINO Available Devices: {devices}")
    assert isinstance(devices, list) and len(devices) > 0, "No OpenVINO devices discovered"
    assert "CPU" in devices, "Host CPU must be available in OpenVINO runtime"

    # Verify presence of Intel Meteor Lake AI Boost NPU and Intel Graphics iGPU
    has_npu = "NPU" in devices
    has_gpu = "GPU" in devices
    print(f"[Hardware Probing] Intel AI Boost NPU detected: {has_npu}")
    print(f"[Hardware Probing] Intel Graphics iGPU detected: {has_gpu}")
    assert has_npu, "Intel AI Boost NPU should be detected on Intel Core Ultra 5 125U"


def test_julia_onnx_classifier_npu_inference():
    """Confirms JuliaONNXClassifier compiles and runs directly on Intel AI Boost NPU."""
    classifier = JuliaONNXClassifier(device="NPU", backend="openvino")
    assert classifier.is_available is True, "JuliaONNXClassifier should be available"
    assert classifier.active_device == "NPU", f"Expected active device NPU, got {classifier.active_device}"
    assert classifier.backend == "openvino", f"Expected backend openvino, got {classifier.backend}"

    # Test warm query
    test_query = "Срочно проверь задолженности по матанализу и график пересдач"
    domain, conf, scores, latency_ms = classifier.predict(test_query)

    print(f"\n[NPU Classifier] Query: '{test_query}'")
    print(f"[NPU Classifier] Domain: {domain}, Confidence: {conf:.4f}, Latency: {latency_ms:.2f} ms")

    assert domain == "academic"
    assert conf >= 0.70
    assert latency_ms < 150.0, f"Latency {latency_ms} ms exceeded 150ms SLA"


def test_julia_onnx_classifier_device_fallback():
    """Confirms automatic fallback chain works cleanly across GPU and CPU."""
    core = ov.Core()
    available = core.available_devices

    # Test GPU target if present
    if "GPU" in available:
        gpu_classifier = JuliaONNXClassifier(device="GPU", backend="openvino")
        assert gpu_classifier.is_available is True
        assert gpu_classifier.active_device == "GPU"
        dom, conf, _, lat = gpu_classifier.predict("Сделай рефакторинг функции ast_prune и прогони pytest")
        assert dom == "code"
        assert lat < 150.0
        print(f"[GPU Fallback] Code domain classified in {lat:.2f} ms on GPU")

    # Test CPU target
    cpu_classifier = JuliaONNXClassifier(device="CPU", backend="openvino")
    assert cpu_classifier.is_available is True
    assert cpu_classifier.active_device == "CPU"
    dom, conf, _, lat = cpu_classifier.predict("Посмотри сколько налога нужно заплатить за самозанятость в Тинькофф")
    assert dom == "finance"
    assert lat < 150.0
    print(f"[CPU Fallback] Finance domain classified in {lat:.2f} ms on CPU")

    # Test Nonexistent device -> automatic fallback to highest priority available device (NPU)
    resilient_clf = JuliaONNXClassifier(device="UNSUPPORTED_DEVICE_NAME", backend="openvino")
    assert resilient_clf.is_available is True
    assert resilient_clf.active_device in ("NPU", "GPU", "CPU")
    dom, conf, _, lat = resilient_clf.predict("Что думаешь по поводу философии Ухтомского?")
    assert dom == "general_reasoning"
    assert lat < 150.0


def test_julia_router_e2e_npu_sub150ms():
    """Confirms end-to-end JuliaRouter intent routing on NPU meets <150ms constraint."""
    router = JuliaRouter(use_neural=True, device="NPU", offline_fallback=True)

    assert router.classifier is not None
    assert router.classifier.is_available is True
    assert router.classifier.active_device == "NPU"

    benchmarks = [
        ("Срочно проверь задолженности по матанализу и график пересдач", "academic"),
        ("Сделай рефакторинг функции ast_prune и прогони pytest", "code"),
        ("Посмотри сколько налога нужно заплатить за самозанятость в Тинькофф", "finance"),
        ("Покажи последние данные взвешивания с умных весов Mi Scale", "health"),
        ("Создай pull request через асинхронного агента Jules в облачной VM", "jules"),
        ("Что думаешь по поводу философии Ухтомского и доминанты внимания?", "general_reasoning"),
    ]

    latencies = []
    print("\n[JuliaRouter E2E NPU Benchmarks]")
    for query, expected_domain in benchmarks:
        decision = router.route(query)
        assert isinstance(decision, RoutingDecision)
        assert decision.domain in CANONICAL_DOMAINS
        assert decision.domain == expected_domain, f"Query '{query}' expected {expected_domain}, got {decision.domain}"
        assert 0.0 <= decision.confidence <= 1.0
        assert decision.latency_ms < 150.0, f"Latency {decision.latency_ms} ms exceeded 150ms threshold"
        assert decision.metadata.get("device_used") == "NPU"
        latencies.append(decision.latency_ms)
        print(f" - [{decision.domain:^19}] Conf: {decision.confidence:.2f} | Latency: {decision.latency_ms:5.2f} ms | Dev: {decision.metadata.get('device_used')}")

    avg_lat = float(np.mean(latencies))
    max_lat = float(np.max(latencies))
    print(f"[JuliaRouter Summary] Avg latency: {avg_lat:.2f} ms | Max latency: {max_lat:.2f} ms (<150ms)")
    assert avg_lat < 50.0, f"Average latency {avg_lat} ms should be well under 50ms"


def test_openvino_npu_embedder_768d():
    """Confirms OpenVINONPUEmbedder 768D extraction on Intel AI Boost NPU."""
    embedder = OpenVINONPUEmbedder(device="NPU")
    assert embedder.is_available is True
    assert embedder.device == "NPU"

    # Warm-up run (loads weights to NPU VPU memory)
    embedder.get_embedding("warmup probe")

    t0 = time.perf_counter()
    vec = embedder.get_embedding("Intel Core Ultra Meteor Lake AI Boost NPU local inference test")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    print(f"\n[Embedder 768D NPU] Length: {len(vec)}, Warm Latency: {elapsed_ms:.2f} ms")
    assert len(vec) == 768
    norm = float(np.linalg.norm(vec))
    assert abs(norm - 1.0) < 1e-3, "Normalized vector norm should equal 1.0"
    assert elapsed_ms < 200.0
