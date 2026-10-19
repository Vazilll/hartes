"""
tests/test_avx512_cosine.py — Unit Tests & Benchmarks for AVX-512 SIMD Vector Engine.
"""

import sys
import os
import time
import ctypes
import numpy as np
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vazus_core.memory.avx512_cosine import (
    AVX512CtypesBinding,
    AVX512VectorEngine
)


def test_dll_hardware_detection():
    """Verifies that the compiled C shared library loads and reports hardware capability without crashing."""
    dll_path = Path("/home/tarhes/Проекты/vazus/vazus_core/libavx512_cosine.so")
    assert dll_path.exists(), "Shared library vazus_core/libavx512_cosine.so must exist"

    binding = AVX512CtypesBinding(dll_path=str(dll_path))
    assert binding.is_available is True, "AVX512CtypesBinding should load the shared library successfully"

    # Call hardware detection C functions
    dll = binding.dll
    avx512_sup = bool(dll.avx512_is_hardware_supported())
    avx2_sup = bool(dll.avx2_is_hardware_supported())

    # Host CPU (Intel Ultra 5 125U) supports AVX2
    assert isinstance(avx512_sup, bool)
    assert isinstance(avx2_sup, bool)
    assert avx2_sup is True, "AVX2 should be supported on host CPU"


def test_simd_numerical_accuracy():
    """Verifies C SIMD cosine distance and dot products against NumPy reference calculations."""
    binding = AVX512CtypesBinding()
    assert binding.is_available is True

    np.random.seed(42)
    a = np.random.randn(768).astype(np.float32)
    b = np.random.randn(768).astype(np.float32)
    a /= np.linalg.norm(a)
    b /= np.linalg.norm(b)

    # 1. Cosine Distance
    expected_dist = 1.0 - float(np.dot(a, b))
    actual_dist = binding.cosine_distance(a, b)
    assert abs(actual_dist - expected_dist) < 1e-4

    # 2. Batch Dot Product
    matrix = np.random.randn(100, 768).astype(np.float32)
    expected_dots = np.dot(matrix, a)
    actual_dots = binding.batch_dot_product(matrix, a)
    max_err = np.max(np.abs(actual_dots - expected_dots))
    assert max_err < 1e-4


def test_ctypes_fallback_handling():
    """Verifies graceful fallback to NumPy when DLL path is non-existent."""
    fallback_binding = AVX512CtypesBinding(dll_path="non_existent_path.dll")
    assert fallback_binding.is_available is False

    a = np.random.randn(768).astype(np.float32)
    matrix = np.random.randn(10, 768).astype(np.float32)
    res = fallback_binding.batch_dot_product(matrix, a)
    assert len(res) == 10


def test_ivf256_vector_engine_index_and_search():
    """Tests building index and searching top-k vectors with AVX512VectorEngine."""
    np.random.seed(42)
    num_vectors = 10000
    dim = 768

    engine = AVX512VectorEngine(num_centroids=256, nprobe=8, dim=dim)
    vectors = np.random.uniform(-1.0, 1.0, size=(num_vectors, dim)).astype(np.float32)

    # Insert known identical target vector at index 1234
    query = np.random.uniform(-1.0, 1.0, size=dim).astype(np.float32)
    query /= np.linalg.norm(query)
    vectors[1234] = query.copy()

    engine.build_index(vectors)
    assert engine.is_indexed is True

    results = engine.search_top_k(query, top_k=5)
    assert len(results) == 5

    top_idx, top_score = results[0]
    assert top_idx == 1234, f"Top match should be inserted vector 1234, got {top_idx}"
    assert top_score > 0.99, f"Top similarity score should be ~1.0, got {top_score}"


def test_ivf256_batch_search():
    """Tests batch_search interface on multiple query vectors."""
    np.random.seed(42)
    engine = AVX512VectorEngine(num_centroids=32, nprobe=4, dim=768)
    vectors = np.random.randn(2000, 768).astype(np.float32)
    engine.build_index(vectors)

    queries = np.random.randn(5, 768).astype(np.float32)
    batch_results = engine.batch_search(queries, top_k=3)

    assert len(batch_results) == 5
    for res in batch_results:
        assert len(res) == 3


def test_100k_vector_query_latency_benchmark():
    """
    Latency Benchmark Gate:
    Verifies that query search over 100,000 768D float32 vectors completes in < 5.0 ms.
    """
    np.random.seed(42)
    num_vectors = 100000
    dim = 768

    engine = AVX512VectorEngine(num_centroids=256, nprobe=8, dim=dim)
    vectors = np.random.uniform(-1.0, 1.0, size=(num_vectors, dim)).astype(np.float32)
    engine.build_index(vectors)

    # Warmup queries
    for _ in range(5):
        q = np.random.uniform(-1.0, 1.0, size=dim).astype(np.float32)
        engine.search_top_k(q, top_k=10)

    # Measure average latency over 50 search runs
    num_runs = 50
    start_time = time.perf_counter()
    for _ in range(num_runs):
        q = np.random.uniform(-1.0, 1.0, size=dim).astype(np.float32)
        engine.search_top_k(q, top_k=10)
    end_time = time.perf_counter()

    avg_latency_sec = (end_time - start_time) / num_runs
    avg_latency_ms = avg_latency_sec * 1000.0
    avg_latency_us = avg_latency_sec * 1000000.0

    print(f"\n[BENCHMARK RESULT] 100k 768D Vector IVF-256 Latency: {avg_latency_ms:.4f} ms ({avg_latency_us:.1f} µs)")
    assert avg_latency_ms < 5.0, f"Average query latency must be < 5.0 ms, got {avg_latency_ms:.4f} ms"
