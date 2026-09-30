## 2024-09-30 - Optimize pure Python vector math operations
**Learning:** Dense vector operations in pure Python suffer significant overhead when using `zip()` and list comprehensions. While `math.hypot(*vec)` is fast, it fails on empty lists and has a max argument limit in Python 3.7.
**Action:** Replace `sum(a * b for a, b in zip(v1, v2))` with `sum(map(operator.mul, v1, v2))` for dot products, and use `math.sqrt(sum(map(operator.mul, vec, vec)))` for L2 norms, which yields a reliable speedup without the `math.hypot` edge cases.
