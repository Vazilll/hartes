## 2023-09-29 - Vector Similarity Optimization
**Learning:** Pure Python mathematical operations in vector embedding comparisons (`_cosine_similarity`) represent a bottleneck, taking ~3.4x longer than necessary.
**Action:** Use `math.hypot(*vec)` for L2 norms instead of `math.sqrt(sum(a*a))`, and `sum(map(operator.mul, v1, v2))` for dot products to reduce pure Python overhead in FTS matching.
