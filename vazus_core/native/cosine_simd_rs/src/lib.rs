pub mod avx2;
pub mod scalar;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rayon::prelude::*;

/// Compute cosine similarity between two 768-D vectors with runtime AVX2 dispatch.
pub fn cosine_similarity_768(a: &[f32; 768], b: &[f32; 768]) -> f32 {
    #[cfg(target_arch = "x86_64")]
    {
        if is_x86_feature_detected!("avx2") && is_x86_feature_detected!("fma") {
            return unsafe { avx2::cosine_similarity_768_avx2(a, b) };
        }
    }
    scalar::cosine_similarity_768_scalar(a, b)
}

/// Compute cosine distance (1.0 - similarity) between two 768-D vectors.
pub fn cosine_distance_768(a: &[f32; 768], b: &[f32; 768]) -> f32 {
    let sim = cosine_similarity_768(a, b);
    1.0 - sim
}

/// Compute cosine similarity for arbitrary dimension vectors.
pub fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() || a.is_empty() {
        return 0.0;
    }
    if a.len() == 768 {
        let a_arr: &[f32; 768] = match a.try_into() {
            Ok(arr) => arr,
            Err(_) => return 0.0,
        };
        let b_arr: &[f32; 768] = match b.try_into() {
            Ok(arr) => arr,
            Err(_) => return 0.0,
        };
        return cosine_similarity_768(a_arr, b_arr);
    }
    scalar::cosine_similarity_scalar(a, b)
}

/// Batch compute cosine similarities across a flattened matrix of shape (N, 768) against a 768-D query.
pub fn batch_cosine_similarity_768(matrix: &[f32], query: &[f32; 768]) -> Vec<f32> {
    assert_eq!(matrix.len() % 768, 0, "Matrix length must be multiple of 768");
    matrix
        .par_chunks_exact(768)
        .map(|chunk| {
            let row: &[f32; 768] = chunk.try_into().expect("Chunk size is 768");
            cosine_similarity_768(row, query)
        })
        .collect()
}

/// Batch compute cosine distances across a flattened matrix of shape (N, 768) against a 768-D query.
pub fn batch_cosine_distance_768(matrix: &[f32], query: &[f32; 768]) -> Vec<f32> {
    assert_eq!(matrix.len() % 768, 0, "Matrix length must be multiple of 768");
    matrix
        .par_chunks_exact(768)
        .map(|chunk| {
            let row: &[f32; 768] = chunk.try_into().expect("Chunk size is 768");
            cosine_distance_768(row, query)
        })
        .collect()
}

// -------------------------------------------------------------------------
// PyO3 Python Exports
// -------------------------------------------------------------------------

#[pyfunction]
#[pyo3(name = "cosine_similarity_768")]
fn py_cosine_similarity_768(vec_a: Vec<f32>, vec_b: Vec<f32>) -> PyResult<f32> {
    if vec_a.len() != 768 || vec_b.len() != 768 {
        return Err(PyValueError::new_err(format!(
            "Vectors must both have dimension 768 (got {} and {})",
            vec_a.len(),
            vec_b.len()
        )));
    }
    let a_arr: &[f32; 768] = vec_a.as_slice().try_into().unwrap();
    let b_arr: &[f32; 768] = vec_b.as_slice().try_into().unwrap();
    Ok(cosine_similarity_768(a_arr, b_arr))
}

#[pyfunction]
#[pyo3(name = "cosine_distance_768")]
fn py_cosine_distance_768(vec_a: Vec<f32>, vec_b: Vec<f32>) -> PyResult<f32> {
    if vec_a.len() != 768 || vec_b.len() != 768 {
        return Err(PyValueError::new_err(format!(
            "Vectors must both have dimension 768 (got {} and {})",
            vec_a.len(),
            vec_b.len()
        )));
    }
    let a_arr: &[f32; 768] = vec_a.as_slice().try_into().unwrap();
    let b_arr: &[f32; 768] = vec_b.as_slice().try_into().unwrap();
    Ok(cosine_distance_768(a_arr, b_arr))
}

#[pyfunction]
#[pyo3(name = "batch_cosine_similarity_768")]
fn py_batch_cosine_similarity_768(
    py: Python<'_>,
    query: Vec<f32>,
    matrix: Vec<Vec<f32>>,
) -> PyResult<Vec<f32>> {
    if query.len() != 768 {
        return Err(PyValueError::new_err(format!(
            "Query vector must have dimension 768 (got {})",
            query.len()
        )));
    }
    let q_arr: &[f32; 768] = query.as_slice().try_into().unwrap();

    let results = py.allow_threads(|| {
        matrix
            .into_par_iter()
            .map(|row| {
                if row.len() == 768 {
                    let r_arr: &[f32; 768] = row.as_slice().try_into().unwrap();
                    cosine_similarity_768(r_arr, q_arr)
                } else {
                    cosine_similarity(&row, &query)
                }
            })
            .collect()
    });

    Ok(results)
}

#[pyfunction]
#[pyo3(name = "batch_cosine_distance_768")]
fn py_batch_cosine_distance_768(
    py: Python<'_>,
    query: Vec<f32>,
    matrix: Vec<Vec<f32>>,
) -> PyResult<Vec<f32>> {
    let sims = py_batch_cosine_similarity_768(py, query, matrix)?;
    Ok(sims.into_iter().map(|s| 1.0 - s).collect())
}

#[pyfunction]
#[pyo3(name = "cosine_similarity")]
fn py_cosine_similarity(a: Vec<f32>, b: Vec<f32>) -> PyResult<f32> {
    if a.len() != b.len() {
        return Err(PyValueError::new_err(format!(
            "Vector dimensions must match (got {} and {})",
            a.len(),
            b.len()
        )));
    }
    Ok(cosine_similarity(&a, &b))
}

#[pyfunction]
#[pyo3(name = "batch_top_k")]
fn py_batch_top_k(
    py: Python<'_>,
    query: Vec<f32>,
    corpus: Vec<Vec<f32>>,
    k: usize,
) -> PyResult<Vec<(usize, f32)>> {
    let sims = py_batch_cosine_similarity_768(py, query, corpus)?;
    let mut indexed: Vec<(usize, f32)> = sims.into_iter().enumerate().collect();
    indexed.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    indexed.truncate(k);
    Ok(indexed)
}

#[pymodule]
fn cosine_simd_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_cosine_similarity_768, m)?)?;
    m.add_function(wrap_pyfunction!(py_cosine_distance_768, m)?)?;
    m.add_function(wrap_pyfunction!(py_batch_cosine_similarity_768, m)?)?;
    m.add_function(wrap_pyfunction!(py_batch_cosine_distance_768, m)?)?;
    m.add_function(wrap_pyfunction!(py_cosine_similarity, m)?)?;
    m.add_function(wrap_pyfunction!(py_batch_top_k, m)?)?;
    Ok(())
}

// -------------------------------------------------------------------------
// Unit Tests
// -------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_identical_vectors() {
        let mut a = [0.0f32; 768];
        for i in 0..768 {
            a[i] = (i as f32) * 0.01;
        }
        let sim = cosine_similarity_768(&a, &a);
        assert!((sim - 1.0).abs() < 1e-5, "Expected 1.0, got {}", sim);
        let dist = cosine_distance_768(&a, &a);
        assert!(dist.abs() < 1e-5, "Expected 0.0 distance, got {}", dist);
    }

    #[test]
    fn test_orthogonal_vectors() {
        let mut a = [0.0f32; 768];
        let mut b = [0.0f32; 768];
        for i in 0..384 {
            a[i] = 1.0;
        }
        for i in 384..768 {
            b[i] = 1.0;
        }
        let sim = cosine_similarity_768(&a, &b);
        assert!(sim.abs() < 1e-5, "Expected 0.0, got {}", sim);
        let dist = cosine_distance_768(&a, &b);
        assert!((dist - 1.0).abs() < 1e-5, "Expected 1.0 distance, got {}", dist);
    }

    #[test]
    fn test_opposite_vectors() {
        let mut a = [0.0f32; 768];
        let mut b = [0.0f32; 768];
        for i in 0..768 {
            a[i] = 1.0;
            b[i] = -1.0;
        }
        let sim = cosine_similarity_768(&a, &b);
        assert!((sim - (-1.0)).abs() < 1e-5, "Expected -1.0, got {}", sim);
        let dist = cosine_distance_768(&a, &b);
        assert!((dist - 2.0).abs() < 1e-5, "Expected 2.0 distance, got {}", dist);
    }

    #[test]
    fn test_avx2_vs_scalar_match() {
        let mut a = [0.0f32; 768];
        let mut b = [0.0f32; 768];
        for i in 0..768 {
            a[i] = ((i * 17) % 100) as f32 / 100.0;
            b[i] = ((i * 31) % 100) as f32 / 100.0;
        }
        let sim_scalar = scalar::cosine_similarity_768_scalar(&a, &b);
        let sim_dispatch = cosine_similarity_768(&a, &b);
        assert!(
            (sim_scalar - sim_dispatch).abs() < 1e-5,
            "Scalar ({}) and dispatch ({}) must match",
            sim_scalar,
            sim_dispatch
        );
    }

    #[test]
    fn test_batch_similarity() {
        let mut q = [0.0f32; 768];
        for i in 0..768 {
            q[i] = 1.0;
        }
        let mut mat = Vec::with_capacity(768 * 3);
        // row 0: identical to q
        mat.extend_from_slice(&q);
        // row 1: zeros
        mat.extend_from_slice(&[0.0f32; 768]);
        // row 2: opposite of q
        let opp = [-1.0f32; 768];
        mat.extend_from_slice(&opp);

        let sims = batch_cosine_similarity_768(&mat, &q);
        assert_eq!(sims.len(), 3);
        assert!((sims[0] - 1.0).abs() < 1e-5);
        assert!(sims[1].abs() < 1e-5);
        assert!((sims[2] - (-1.0)).abs() < 1e-5);
    }

    #[test]
    fn test_large_magnitude_vectors() {
        let mut a = [0.0f32; 768];
        for i in 0..768 {
            a[i] = if i % 2 == 0 { 1e15 } else { 1e-15 };
        }
        let sim = cosine_similarity_768(&a, &a);
        assert!((sim - 1.0).abs() < 1e-4, "Expected 1.0 for extreme floats, got {}", sim);
    }
}
