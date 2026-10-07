## 2025-02-28 - [Cosine Similarity Vector Redundancy]
**Learning:** In heavily invoked loops like Pre-Flight AST checks iterating thousands of constraints over candidate ast elements, the raw computational overhead of multiple unrolled generator structures scaling O(3*N) in vector iterations (`[a * b for a, b in zip(v1, v2)]`) dwarfs the actual floating point math compute bounds in C-python implementations, especially against high-dimensional (768D) vectors.
**Action:** When vectorizing distance metrics without `numpy` available, aggressively consolidate multi-pass generators and unroll calculations into a single `for zip(a,b)` accumulator structure to mitigate interpreter context switching overhead.

## 2024-09-30 - Optimize pure Python vector math operations
**Learning:** Dense vector operations in pure Python suffer significant overhead when using `zip()` and list comprehensions. While `math.hypot(*vec)` is fast, it fails on empty lists and has a max argument limit in Python 3.7.
**Action:** Replace `sum(a * b for a, b in zip(v1, v2))` with `sum(map(operator.mul, v1, v2))` for dot products, and use `math.sqrt(sum(map(operator.mul, vec, vec)))` for L2 norms, which yields a reliable speedup without the `math.hypot` edge cases.

## 2025-03-01 - [Cosine Similarity Vector Redundancy via C-math]
**Learning:** Dense vector operations in pure Python can be vastly optimized in Python 3.12+ using `math.sumprod(v1, v2)` for dot products and `math.hypot(*vec)` for L2 norms, which operate at the C level. This bypasses the previously required slow single-pass Python loops or `map(operator.mul, ...)` workarounds, yielding ~3.8x - 5.3x speedups on 768D embeddings.
**Action:** When working in Python 3.12+, default to `math.sumprod` and `math.hypot(*vec)` for L2 norms and dot products instead of manual unrolled loops.

## 2025-03-01 - [Character Frequency Counting Overhead]
**Learning:** In the `compute_shannon_entropy` function, a manual pure Python character counting loop utilizing `dict.get(char, 0) + 1` exhibits significant overhead when processing large context strings (e.g. 150,000 characters).
**Action:** Always prefer `collections.Counter(text)` for frequency counting of elements in strings or iterables, as it utilizes a highly optimized C-level implementation, yielding roughly a ~2.8-3x speedup.
