/*
 * vazus_core/avx512_cosine.c
 * Hardware-Accelerated 768D SIMD Vector Kernel (AVX-512 / AVX2 / Scalar)
 * Compiled with MinGW GCC 14.1.0 on Windows x86_64
 *
 * Dynamic Dispatch & Safety:
 * Functions are decorated with __attribute__((target("..."), noinline)) to prevent
 * GCC from hoisting ZMM/YMM instructions into dispatcher prologues, ensuring 100%
 * crash-free fallback on CPUs without AVX-512.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdint.h>
#include <math.h>
#include <immintrin.h>

#ifdef _WIN32
  #define AVX512_API __declspec(dllexport)
#else
  #define AVX512_API __attribute__((visibility("default")))
#endif

#define ATTR_AVX512 __attribute__((target("avx512f"), noinline))
#define ATTR_AVX2   __attribute__((target("avx2,fma,sse2"), noinline))
#define ATTR_SCALAR __attribute__((target("default"), noinline))

/* ========================================================================= */
/* 1. CPU Hardware Detection                                                 */
/* ========================================================================= */

AVX512_API int avx512_is_hardware_supported(void) {
    #if defined(__GNUC__) || defined(__clang__)
    return __builtin_cpu_supports("avx512f");
    #else
    return 0;
    #endif
}

AVX512_API int avx2_is_hardware_supported(void) {
    #if defined(__GNUC__) || defined(__clang__)
    return __builtin_cpu_supports("avx2") && __builtin_cpu_supports("fma");
    #else
    return 0;
    #endif
}

/* ========================================================================= */
/* 2. AVX-512 SIMD Kernels (512-bit ZMM)                                    */
/* ========================================================================= */

ATTR_AVX512
AVX512_API float avx512_dot_product(const float* a, const float* b, int dim) {
    __m512 sum0 = _mm512_setzero_ps();
    __m512 sum1 = _mm512_setzero_ps();
    __m512 sum2 = _mm512_setzero_ps();

    int i = 0;
    for (; i <= dim - 48; i += 48) {
        __m512 va0 = _mm512_loadu_ps(a + i);
        __m512 vb0 = _mm512_loadu_ps(b + i);
        sum0 = _mm512_fmadd_ps(va0, vb0, sum0);

        __m512 va1 = _mm512_loadu_ps(a + i + 16);
        __m512 vb1 = _mm512_loadu_ps(b + i + 16);
        sum1 = _mm512_fmadd_ps(va1, vb1, sum1);

        __m512 va2 = _mm512_loadu_ps(a + i + 32);
        __m512 vb2 = _mm512_loadu_ps(b + i + 32);
        sum2 = _mm512_fmadd_ps(va2, vb2, sum2);
    }

    for (; i <= dim - 16; i += 16) {
        __m512 va = _mm512_loadu_ps(a + i);
        __m512 vb = _mm512_loadu_ps(b + i);
        sum0 = _mm512_fmadd_ps(va, vb, sum0);
    }

    __m512 sum_all = _mm512_add_ps(sum0, _mm512_add_ps(sum1, sum2));
    float total = _mm512_reduce_add_ps(sum_all);

    for (; i < dim; i++) {
        total += a[i] * b[i];
    }
    return total;
}

ATTR_AVX512
AVX512_API float avx512_vector_norm(const float* a, int dim) {
    float dot = avx512_dot_product(a, a, dim);
    return sqrtf(dot);
}

ATTR_AVX512
AVX512_API float avx512_cosine_distance(const float* a, const float* b, int dim) {
    __m512 sum_dot0 = _mm512_setzero_ps();
    __m512 sum_na0  = _mm512_setzero_ps();
    __m512 sum_nb0  = _mm512_setzero_ps();

    __m512 sum_dot1 = _mm512_setzero_ps();
    __m512 sum_na1  = _mm512_setzero_ps();
    __m512 sum_nb1  = _mm512_setzero_ps();

    int i = 0;
    for (; i <= dim - 32; i += 32) {
        __m512 va0 = _mm512_loadu_ps(a + i);
        __m512 vb0 = _mm512_loadu_ps(b + i);
        sum_dot0 = _mm512_fmadd_ps(va0, vb0, sum_dot0);
        sum_na0  = _mm512_fmadd_ps(va0, va0, sum_na0);
        sum_nb0  = _mm512_fmadd_ps(vb0, vb0, sum_nb0);

        __m512 va1 = _mm512_loadu_ps(a + i + 16);
        __m512 vb1 = _mm512_loadu_ps(b + i + 16);
        sum_dot1 = _mm512_fmadd_ps(va1, vb1, sum_dot1);
        sum_na1  = _mm512_fmadd_ps(va1, va1, sum_na1);
        sum_nb1  = _mm512_fmadd_ps(vb1, vb1, sum_nb1);
    }

    for (; i <= dim - 16; i += 16) {
        __m512 va = _mm512_loadu_ps(a + i);
        __m512 vb = _mm512_loadu_ps(b + i);
        sum_dot0 = _mm512_fmadd_ps(va, vb, sum_dot0);
        sum_na0  = _mm512_fmadd_ps(va, va, sum_na0);
        sum_nb0  = _mm512_fmadd_ps(vb, vb, sum_nb0);
    }

    float dot = _mm512_reduce_add_ps(_mm512_add_ps(sum_dot0, sum_dot1));
    float na  = _mm512_reduce_add_ps(_mm512_add_ps(sum_na0,  sum_na1));
    float nb  = _mm512_reduce_add_ps(_mm512_add_ps(sum_nb0,  sum_nb1));

    for (; i < dim; i++) {
        dot += a[i] * b[i];
        na  += a[i] * a[i];
        nb  += b[i] * b[i];
    }

    float denom = sqrtf(na) * sqrtf(nb);
    if (denom < 1e-8f) return 1.0f;
    float sim = dot / denom;
    if (sim > 1.0f) sim = 1.0f;
    if (sim < -1.0f) sim = -1.0f;
    return 1.0f - sim;
}

ATTR_AVX512
AVX512_API void avx512_batch_dot_product(const float* matrix, const float* query, float* results, int num_vectors, int dim) {
    #if defined(_OPENMP)
    #pragma omp parallel for schedule(static) if(num_vectors >= 1000)
    #endif
    for (int i = 0; i < num_vectors; i++) {
        const float* vec = matrix + (size_t)i * dim;
        results[i] = avx512_dot_product(vec, query, dim);
    }
}

ATTR_AVX512
AVX512_API void avx512_batch_cosine_distance(const float* matrix, const float* query, float* results, int num_vectors, int dim) {
    #if defined(_OPENMP)
    #pragma omp parallel for schedule(static) if(num_vectors >= 1000)
    #endif
    for (int i = 0; i < num_vectors; i++) {
        const float* vec = matrix + (size_t)i * dim;
        results[i] = avx512_cosine_distance(vec, query, dim);
    }
}

ATTR_AVX512
AVX512_API void avx512_batch_ivf_candidate_scan(const float* matrix, const int32_t* candidate_indices, int num_candidates, const float* query, float* results, int dim) {
    #if defined(_OPENMP)
    #pragma omp parallel for schedule(static) if(num_candidates >= 500)
    #endif
    for (int c = 0; c < num_candidates; c++) {
        int idx = candidate_indices[c];
        results[c] = avx512_dot_product(matrix + (size_t)idx * dim, query, dim);
    }
}

/* ========================================================================= */
/* 3. AVX2 SIMD Kernels (256-bit YMM + FMA)                                  */
/* ========================================================================= */

ATTR_AVX2
AVX512_API float avx2_dot_product(const float* a, const float* b, int dim) {
    __m256 sum0 = _mm256_setzero_ps();
    __m256 sum1 = _mm256_setzero_ps();
    __m256 sum2 = _mm256_setzero_ps();
    __m256 sum3 = _mm256_setzero_ps();

    int i = 0;
    for (; i <= dim - 32; i += 32) {
        __m256 va0 = _mm256_loadu_ps(a + i);
        __m256 vb0 = _mm256_loadu_ps(b + i);
        sum0 = _mm256_fmadd_ps(va0, vb0, sum0);

        __m256 va1 = _mm256_loadu_ps(a + i + 8);
        __m256 vb1 = _mm256_loadu_ps(b + i + 8);
        sum1 = _mm256_fmadd_ps(va1, vb1, sum1);

        __m256 va2 = _mm256_loadu_ps(a + i + 16);
        __m256 vb2 = _mm256_loadu_ps(b + i + 16);
        sum2 = _mm256_fmadd_ps(va2, vb2, sum2);

        __m256 va3 = _mm256_loadu_ps(a + i + 24);
        __m256 vb3 = _mm256_loadu_ps(b + i + 24);
        sum3 = _mm256_fmadd_ps(va3, vb3, sum3);
    }

    for (; i <= dim - 8; i += 8) {
        __m256 va = _mm256_loadu_ps(a + i);
        __m256 vb = _mm256_loadu_ps(b + i);
        sum0 = _mm256_fmadd_ps(va, vb, sum0);
    }

    __m256 sum_all = _mm256_add_ps(_mm256_add_ps(sum0, sum1), _mm256_add_ps(sum2, sum3));
    __m128 vlow  = _mm256_castps256_ps128(sum_all);
    __m128 vhigh = _mm256_extractf128_ps(sum_all, 1);
    __m128 vsum  = _mm_add_ps(vlow, vhigh);
    vsum = _mm_add_ps(vsum, _mm_movehl_ps(vsum, vsum));
    vsum = _mm_add_ss(vsum, _mm_shuffle_ps(vsum, vsum, 0x55));
    float total = _mm_cvtss_f32(vsum);

    for (; i < dim; i++) {
        total += a[i] * b[i];
    }
    return total;
}

ATTR_AVX2
AVX512_API float avx2_vector_norm(const float* a, int dim) {
    float dot = avx2_dot_product(a, a, dim);
    return sqrtf(dot);
}

ATTR_AVX2
AVX512_API float avx2_cosine_distance(const float* a, const float* b, int dim) {
    __m256 sum_dot0 = _mm256_setzero_ps();
    __m256 sum_na0  = _mm256_setzero_ps();
    __m256 sum_nb0  = _mm256_setzero_ps();

    int i = 0;
    for (; i <= dim - 8; i += 8) {
        __m256 va0 = _mm256_loadu_ps(a + i);
        __m256 vb0 = _mm256_loadu_ps(b + i);
        sum_dot0 = _mm256_fmadd_ps(va0, vb0, sum_dot0);
        sum_na0  = _mm256_fmadd_ps(va0, va0, sum_na0);
        sum_nb0  = _mm256_fmadd_ps(vb0, vb0, sum_nb0);
    }

    __m128 vlow_dot = _mm256_castps256_ps128(sum_dot0);
    __m128 vhigh_dot = _mm256_extractf128_ps(sum_dot0, 1);
    __m128 vsum_dot = _mm_add_ps(vlow_dot, vhigh_dot);
    vsum_dot = _mm_add_ps(vsum_dot, _mm_movehl_ps(vsum_dot, vsum_dot));
    vsum_dot = _mm_add_ss(vsum_dot, _mm_shuffle_ps(vsum_dot, vsum_dot, 0x55));
    float dot = _mm_cvtss_f32(vsum_dot);

    __m128 vlow_na = _mm256_castps256_ps128(sum_na0);
    __m128 vhigh_na = _mm256_extractf128_ps(sum_na0, 1);
    __m128 vsum_na = _mm_add_ps(vlow_na, vhigh_na);
    vsum_na = _mm_add_ps(vsum_na, _mm_movehl_ps(vsum_na, vsum_na));
    vsum_na = _mm_add_ss(vsum_na, _mm_shuffle_ps(vsum_na, vsum_na, 0x55));
    float na = _mm_cvtss_f32(vsum_na);

    __m128 vlow_nb = _mm256_castps256_ps128(sum_nb0);
    __m128 vhigh_nb = _mm256_extractf128_ps(sum_nb0, 1);
    __m128 vsum_nb = _mm_add_ps(vlow_nb, vhigh_nb);
    vsum_nb = _mm_add_ps(vsum_nb, _mm_movehl_ps(vsum_nb, vsum_nb));
    vsum_nb = _mm_add_ss(vsum_nb, _mm_shuffle_ps(vsum_nb, vsum_nb, 0x55));
    float nb = _mm_cvtss_f32(vsum_nb);

    for (; i < dim; i++) {
        dot += a[i] * b[i];
        na  += a[i] * a[i];
        nb  += b[i] * b[i];
    }

    float denom = sqrtf(na) * sqrtf(nb);
    if (denom < 1e-8f) return 1.0f;
    float sim = dot / denom;
    if (sim > 1.0f) sim = 1.0f;
    if (sim < -1.0f) sim = -1.0f;
    return 1.0f - sim;
}

ATTR_AVX2
AVX512_API void avx2_batch_dot_product(const float* matrix, const float* query, float* results, int num_vectors, int dim) {
    #if defined(_OPENMP)
    #pragma omp parallel for schedule(static) if(num_vectors >= 1000)
    #endif
    for (int i = 0; i < num_vectors; i++) {
        const float* vec = matrix + (size_t)i * dim;
        results[i] = avx2_dot_product(vec, query, dim);
    }
}

ATTR_AVX2
AVX512_API void avx2_batch_cosine_distance(const float* matrix, const float* query, float* results, int num_vectors, int dim) {
    #if defined(_OPENMP)
    #pragma omp parallel for schedule(static) if(num_vectors >= 1000)
    #endif
    for (int i = 0; i < num_vectors; i++) {
        const float* vec = matrix + (size_t)i * dim;
        results[i] = avx2_cosine_distance(vec, query, dim);
    }
}

ATTR_AVX2
AVX512_API void avx2_batch_ivf_candidate_scan(const float* matrix, const int32_t* candidate_indices, int num_candidates, const float* query, float* results, int dim) {
    #if defined(_OPENMP)
    #pragma omp parallel for schedule(static) if(num_candidates >= 500)
    #endif
    for (int c = 0; c < num_candidates; c++) {
        int idx = candidate_indices[c];
        results[c] = avx2_dot_product(matrix + (size_t)idx * dim, query, dim);
    }
}

/* ========================================================================= */
/* 4. Scalar Fallback Kernels                                                */
/* ========================================================================= */

ATTR_SCALAR
AVX512_API float scalar_dot_product(const float* a, const float* b, int dim) {
    float sum = 0.0f;
    for (int i = 0; i < dim; i++) sum += a[i] * b[i];
    return sum;
}

ATTR_SCALAR
AVX512_API float scalar_vector_norm(const float* a, int dim) {
    return sqrtf(scalar_dot_product(a, a, dim));
}

ATTR_SCALAR
AVX512_API float scalar_cosine_distance(const float* a, const float* b, int dim) {
    float dot = scalar_dot_product(a, b, dim);
    float na = scalar_dot_product(a, a, dim);
    float nb = scalar_dot_product(b, b, dim);
    float denom = sqrtf(na) * sqrtf(nb);
    if (denom < 1e-8f) return 1.0f;
    float sim = dot / denom;
    if (sim > 1.0f) sim = 1.0f;
    if (sim < -1.0f) sim = -1.0f;
    return 1.0f - sim;
}

ATTR_SCALAR
AVX512_API void scalar_batch_dot_product(const float* matrix, const float* query, float* results, int num_vectors, int dim) {
    for (int i = 0; i < num_vectors; i++) {
        const float* vec = matrix + (size_t)i * dim;
        results[i] = scalar_dot_product(vec, query, dim);
    }
}

ATTR_SCALAR
AVX512_API void scalar_batch_cosine_distance(const float* matrix, const float* query, float* results, int num_vectors, int dim) {
    for (int i = 0; i < num_vectors; i++) {
        const float* vec = matrix + (size_t)i * dim;
        results[i] = scalar_cosine_distance(vec, query, dim);
    }
}

ATTR_SCALAR
AVX512_API void scalar_batch_ivf_candidate_scan(const float* matrix, const int32_t* candidate_indices, int num_candidates, const float* query, float* results, int dim) {
    for (int c = 0; c < num_candidates; c++) {
        int idx = candidate_indices[c];
        const float* vec = matrix + (size_t)idx * dim;
        results[c] = scalar_dot_product(vec, query, dim);
    }
}

/* ========================================================================= */
/* 5. Dynamic Dispatch Unified APIs                                          */
/* ========================================================================= */

ATTR_SCALAR
AVX512_API float vazus_dot_product(const float* a, const float* b, int dim) {
    if (avx512_is_hardware_supported()) return avx512_dot_product(a, b, dim);
    if (avx2_is_hardware_supported()) return avx2_dot_product(a, b, dim);
    return scalar_dot_product(a, b, dim);
}

ATTR_SCALAR
AVX512_API float vazus_vector_norm(const float* a, int dim) {
    if (avx512_is_hardware_supported()) return avx512_vector_norm(a, dim);
    if (avx2_is_hardware_supported()) return avx2_vector_norm(a, dim);
    return scalar_vector_norm(a, dim);
}

ATTR_SCALAR
AVX512_API float vazus_cosine_distance(const float* a, const float* b, int dim) {
    if (avx512_is_hardware_supported()) return avx512_cosine_distance(a, b, dim);
    if (avx2_is_hardware_supported()) return avx2_cosine_distance(a, b, dim);
    return scalar_cosine_distance(a, b, dim);
}

ATTR_SCALAR
AVX512_API void vazus_batch_dot_product(const float* matrix, const float* query, float* results, int num_vectors, int dim) {
    if (avx512_is_hardware_supported()) {
        avx512_batch_dot_product(matrix, query, results, num_vectors, dim);
    } else if (avx2_is_hardware_supported()) {
        avx2_batch_dot_product(matrix, query, results, num_vectors, dim);
    } else {
        scalar_batch_dot_product(matrix, query, results, num_vectors, dim);
    }
}

ATTR_SCALAR
AVX512_API void vazus_batch_cosine_distance(const float* matrix, const float* query, float* results, int num_vectors, int dim) {
    if (avx512_is_hardware_supported()) {
        avx512_batch_cosine_distance(matrix, query, results, num_vectors, dim);
    } else if (avx2_is_hardware_supported()) {
        avx2_batch_cosine_distance(matrix, query, results, num_vectors, dim);
    } else {
        scalar_batch_cosine_distance(matrix, query, results, num_vectors, dim);
    }
}

ATTR_SCALAR
AVX512_API void vazus_batch_ivf_candidate_scan(const float* matrix, const int32_t* candidate_indices, int num_candidates, const float* query, float* results, int dim) {
    if (avx512_is_hardware_supported()) {
        avx512_batch_ivf_candidate_scan(matrix, candidate_indices, num_candidates, query, results, dim);
    } else if (avx2_is_hardware_supported()) {
        avx2_batch_ivf_candidate_scan(matrix, candidate_indices, num_candidates, query, results, dim);
    } else {
        scalar_batch_ivf_candidate_scan(matrix, candidate_indices, num_candidates, query, results, dim);
    }
}

/* Aliases for Go MCP / alternate bindings */

ATTR_SCALAR
AVX512_API float avx512_cosine_similarity(const float* a, const float* b, int dim) {
    float dist = vazus_cosine_distance(a, b, dim);
    return 1.0f - dist;
}

ATTR_SCALAR
AVX512_API void avx512_batch_cosine(const float* query, const float* matrix, float* scores, int num_vectors, int dim) {
    vazus_batch_dot_product(matrix, query, scores, num_vectors, dim);
}
