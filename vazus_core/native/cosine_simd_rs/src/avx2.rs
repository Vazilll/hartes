#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::*;

#[cfg(target_arch = "x86_64")]
#[inline(always)]
unsafe fn hsum256_ps(v: __m256) -> f32 {
    let hi = _mm256_extractf128_ps(v, 1);
    let lo = _mm256_castps256_ps128(v);
    let sum128 = _mm_add_ps(lo, hi);
    let shuf = _mm_movehdup_ps(sum128);
    let sums = _mm_add_ps(sum128, shuf);
    let hi64 = _mm_movehl_ps(sums, sums);
    let res = _mm_add_ss(sums, hi64);
    _mm_cvtss_f32(res)
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2,fma")]
pub unsafe fn cosine_similarity_768_avx2(a: &[f32; 768], b: &[f32; 768]) -> f32 {
    let mut dot0 = _mm256_setzero_ps();
    let mut dot1 = _mm256_setzero_ps();
    let mut na0 = _mm256_setzero_ps();
    let mut na1 = _mm256_setzero_ps();
    let mut nb0 = _mm256_setzero_ps();
    let mut nb1 = _mm256_setzero_ps();

    let a_ptr = a.as_ptr();
    let b_ptr = b.as_ptr();

    // 768 floats / 16 floats per iteration = 48 iterations (unrolled 2x 256-bit)
    for i in (0..768).step_by(16) {
        let va0 = _mm256_loadu_ps(a_ptr.add(i));
        let vb0 = _mm256_loadu_ps(b_ptr.add(i));
        dot0 = _mm256_fmadd_ps(va0, vb0, dot0);
        na0 = _mm256_fmadd_ps(va0, va0, na0);
        nb0 = _mm256_fmadd_ps(vb0, vb0, nb0);

        let va1 = _mm256_loadu_ps(a_ptr.add(i + 8));
        let vb1 = _mm256_loadu_ps(b_ptr.add(i + 8));
        dot1 = _mm256_fmadd_ps(va1, vb1, dot1);
        na1 = _mm256_fmadd_ps(va1, va1, na1);
        nb1 = _mm256_fmadd_ps(vb1, vb1, nb1);
    }

    let dot_v = _mm256_add_ps(dot0, dot1);
    let na_v = _mm256_add_ps(na0, na1);
    let nb_v = _mm256_add_ps(nb0, nb1);

    let dot = hsum256_ps(dot_v);
    let na = hsum256_ps(na_v);
    let nb = hsum256_ps(nb_v);

    let denom = na.sqrt() * nb.sqrt();
    if denom < 1e-8 {
        return 0.0;
    }
    (dot / denom).clamp(-1.0, 1.0)
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2,fma")]
pub unsafe fn cosine_distance_768_avx2(a: &[f32; 768], b: &[f32; 768]) -> f32 {
    let sim = cosine_similarity_768_avx2(a, b);
    1.0 - sim
}
