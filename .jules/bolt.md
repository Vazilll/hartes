## 2025-02-28 - [Cosine Similarity Vector Redundancy]
**Learning:** In heavily invoked loops like Pre-Flight AST checks iterating thousands of constraints over candidate ast elements, the raw computational overhead of multiple unrolled generator structures scaling O(3*N) in vector iterations (`[a * b for a, b in zip(v1, v2)]`) dwarfs the actual floating point math compute bounds in C-python implementations, especially against high-dimensional (768D) vectors.
**Action:** When vectorizing distance metrics without `numpy` available, aggressively consolidate multi-pass generators and unroll calculations into a single `for zip(a,b)` accumulator structure to mitigate interpreter context switching overhead.

## 2024-09-30 - Optimize pure Python vector math operations
**Learning:** Dense vector operations in pure Python suffer significant overhead when using `zip()` and list comprehensions. While `math.hypot(*vec)` is fast, it fails on empty lists and has a max argument limit in Python 3.7.
**Action:** Replace `sum(a * b for a, b in zip(v1, v2))` with `sum(map(operator.mul, v1, v2))` for dot products, and use `math.sqrt(sum(map(operator.mul, vec, vec)))` for L2 norms, which yields a reliable speedup without the `math.hypot` edge cases.

## 2025-03-01 - [Cosine Similarity Vector Redundancy via C-math]
**Learning:** Dense vector operations in pure Python can be vastly optimized in Python 3.12+ using `math.sumprod(v1, v2)` for dot products and `math.hypot(*vec)` for L2 norms, which operate at the C level. This bypasses the previously required slow single-pass Python loops or `map(operator.mul, ...)` workarounds, yielding ~3.8x - 5.3x speedups on 768D embeddings.
**Action:** When working in Python 3.12+, default to `math.sumprod` and `math.hypot(*vec)` for L2 norms and dot products instead of manual unrolled loops.

## 2026-10-26 - [AST Pattern Parsing Overhead in Recursive Visitors]
**Learning:** Repeated string manipulation methods (`.replace()`, `.lower()`, `.rstrip()`) inside recursive `ast.NodeVisitor` handlers (like `visit_Call` or custom import checks) applied across a list of negative rules create significant overhead, especially during deep AST traversal.
**Action:** When optimizing `ast.NodeVisitor` implementations that evaluate many rule patterns, avoid string manipulation inside the recursive visit loops. Pre-compile rule patterns into dictionary lookups as class attributes during `__init__` to minimize interpreter overhead and achieve fast, single-pass lookups.
## 2026-10-29 - [Daemon Loop Hot-Path Instantiation]
**Learning:** In persistent daemons like AutonomousFlywheelDaemon, repeatedly instantiating heavy stateful classes (e.g., ContinuousReflexionGenerator, EpisodicMemoryStore) and performing local imports inside hot-path error handlers creates massive, hidden I/O and object creation overhead per exception.
**Action:** Lazily initialize and explicitly cache heavy, stateful components as instance attributes (e.g., self._episodic_store = None in __init__) to execute the instantiation cost exactly once and reuse the instance across the daemon's lifecycle.
