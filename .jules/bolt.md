## 2025-02-28 - [Cosine Similarity Vector Redundancy]
**Learning:** In heavily invoked loops like Pre-Flight AST checks iterating thousands of constraints over candidate ast elements, the raw computational overhead of multiple unrolled generator structures scaling O(3*N) in vector iterations (`[a * b for a, b in zip(v1, v2)]`) dwarfs the actual floating point math compute bounds in C-python implementations, especially against high-dimensional (768D) vectors.
**Action:** When vectorizing distance metrics without `numpy` available, aggressively consolidate multi-pass generators and unroll calculations into a single `for zip(a,b)` accumulator structure to mitigate interpreter context switching overhead.

## 2024-09-30 - Optimize pure Python vector math operations
**Learning:** Dense vector operations in pure Python suffer significant overhead when using `zip()` and list comprehensions. While `math.hypot(*vec)` is fast, it fails on empty lists and has a max argument limit in Python 3.7.
**Action:** Replace `sum(a * b for a, b in zip(v1, v2))` with `sum(map(operator.mul, v1, v2))` for dot products, and use `math.sqrt(sum(map(operator.mul, vec, vec)))` for L2 norms, which yields a reliable speedup without the `math.hypot` edge cases.

## 2025-03-05 - [Cosine Similarity Vector Redundancy 2]
**Learning:** Dense vector operations in pure Python suffer significant overhead when using `zip()` in a for loop. While `math.hypot(*vec)` is fast, we previously thought it had limits or failed. However, the project development environment runs on Python 3.12+, which natively supports unpacking large vectors into functions like `math.hypot(*vec)` without hitting legacy limits found in older versions. Additionally, Python 3.12 introduced `math.sumprod(v1, v2)` which computes the dot product directly in C. Note that CI checks also run on Python 3.11, so a fallback to `map(operator.mul)` is required when `math.sumprod` is missing.
**Action:** Replace `zip()` based loops with `math.sumprod(v1, v2)` (with a fallback) for dot products and `math.hypot(*v)` for calculating norms in `_cosine_similarity` for a significant performance speed up.
