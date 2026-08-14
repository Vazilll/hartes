use pyo3::prelude::*;
use rayon::prelude::*;

/// Normalise a raw f32 slice into a unit vector in-place.
#[inline]
fn l2_normalize(v: &mut [f32]) {
    let norm: f32 = v.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm > 1e-10 {
        v.iter_mut().for_each(|x| *x /= norm);
    }
}

/// Cosine similarity between two equal-length slices.
#[inline]
fn cosine(a: &[f32], b: &[f32]) -> f32 {
    a.iter().zip(b.iter()).map(|(x, y)| x * y).sum()
}

// ---------------------------------------------------------------------------
// PyO3 exported functions
// ---------------------------------------------------------------------------

/// Embed a batch of texts into 768-dim float32 vectors.
///
/// **NOTE**: This function currently returns deterministic hash-based pseudo-
/// embeddings so the extension compiles and runs without a downloaded model.
/// Replace the body with a real Candle / tokenizer pipeline once model weights
/// are available (see build.ps1 for download instructions).
///
/// The GIL is released for the entire computation via `py.allow_threads`.
#[pyfunction]
fn embed_texts(py: Python, texts: Vec<String>) -> PyResult<Vec<Vec<f32>>> {
    py.allow_threads(|| {
        let embeddings: Vec<Vec<f32>> = texts
            .par_iter()
            .map(|text| {
                // Deterministic pseudo-embedding: hash each character position.
                // Swap this section for candle inference once weights are ready.
                let mut vec = vec![0.0f32; 768];
                for (i, c) in text.chars().enumerate() {
                    vec[i % 768] += (c as u32) as f32 * 0.001;
                }
                l2_normalize(&mut vec);
                vec
            })
            .collect();
        Ok(embeddings)
    })
}

/// Cosine similarity between two 768-dim vectors.
/// Returns 0.0 on dimension mismatch or zero-norm input.
#[pyfunction]
fn cosine_similarity(a: Vec<f32>, b: Vec<f32>) -> PyResult<f32> {
    if a.len() != b.len() || a.is_empty() {
        return Ok(0.0);
    }
    let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm_a < 1e-10 || norm_b < 1e-10 {
        return Ok(0.0);
    }
    Ok(cosine(&a, &b) / (norm_a * norm_b))
}

/// Find the top-k most similar vectors in `corpus` to `query`.
///
/// Returns `Vec<(index, cosine_similarity)>` sorted descending by score.
/// Fully parallel via rayon — GIL released for the entire search.
#[pyfunction]
fn batch_top_k(
    py: Python,
    query: Vec<f32>,
    corpus: Vec<Vec<f32>>,
    k: usize,
) -> PyResult<Vec<(usize, f32)>> {
    py.allow_threads(|| {
        let query_norm: f32 = query.iter().map(|x| x * x).sum::<f32>().sqrt();
        if query_norm < 1e-10 || corpus.is_empty() {
            return Ok(vec![]);
        }

        let mut scores: Vec<(usize, f32)> = corpus
            .par_iter()
            .enumerate()
            .map(|(i, vec)| {
                if vec.len() != query.len() {
                    return (i, 0.0_f32);
                }
                let norm_v: f32 = vec.iter().map(|x| x * x).sum::<f32>().sqrt();
                if norm_v < 1e-10 {
                    return (i, 0.0);
                }
                let sim = cosine(&query, vec) / (query_norm * norm_v);
                (i, sim)
            })
            .collect();

        scores.sort_unstable_by(|a, b| {
            b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal)
        });
        scores.truncate(k);
        Ok(scores)
    })
}

/// Pack a Vec<f32> into a raw bytes buffer (little-endian float32).
/// Mirrors `db.pack_vector_f32()` for zero-copy SQLite BLOB writes.
#[pyfunction]
fn pack_f32(vec: Vec<f32>) -> PyResult<Vec<u8>> {
    let bytes: Vec<u8> = vec
        .iter()
        .flat_map(|f| f.to_le_bytes())
        .collect();
    Ok(bytes)
}

/// Unpack a raw bytes buffer back to Vec<f32>.
/// Mirrors `db.unpack_vector_f32()`.
#[pyfunction]
fn unpack_f32(bytes: Vec<u8>) -> PyResult<Vec<f32>> {
    let floats: Vec<f32> = bytes
        .chunks_exact(4)
        .map(|c| f32::from_le_bytes([c[0], c[1], c[2], c[3]]))
        .collect();
    Ok(floats)
}

// ---------------------------------------------------------------------------
// Module registration
// ---------------------------------------------------------------------------

#[pymodule]
fn vazus_embedder(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(embed_texts, m)?)?;
    m.add_function(wrap_pyfunction!(cosine_similarity, m)?)?;
    m.add_function(wrap_pyfunction!(batch_top_k, m)?)?;
    m.add_function(wrap_pyfunction!(pack_f32, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_f32, m)?)?;
    Ok(())
}
