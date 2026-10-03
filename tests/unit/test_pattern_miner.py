"""
tests/test_pattern_miner.py — Tests for PatternMiner and Code Health Engine.
"""

from vazus_core.analysis.pattern_miner import PatternMiner


def test_pattern_miner_python_clean_code():
    code = """
class SafeResource:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def get_data(self, key: str) -> str:
        if key == "test":
            return "val"
        return "default"
"""
    res = PatternMiner.analyze_python_code(code)
    assert res["is_valid"] is True
    assert "ContextManager (RAII)" in res["patterns"]
    assert res["code_health"] >= 9.5
    assert res["ai_ready"] is True
    assert len(res["smells"]) == 0


def test_pattern_miner_python_smelly_code():
    code = """
def god_function(a, b, c, d, e, f):
    # Long parameter list & High CC
    if a:
        if b:
            if c:
                if d:
                    for i in range(10):
                        while e:
                            pass
    return a + b + c + d + e + f
"""
    res = PatternMiner.analyze_python_code(code)
    assert res["is_valid"] is True
    assert res["code_health"] < 9.0
    assert res["ai_ready"] is False
    assert len(res["smells"]) > 0
    assert len(res["refactoring_actions"]) > 0


def test_pattern_miner_go_code():
    code = """
package main

import (
    "context"
    "sync"
)

type WorkerPool struct {
    mu sync.Mutex
    jobs chan int
}

func (w *WorkerPool) Process(ctx context.Context) {
    w.mu.Lock()
    defer w.mu.Unlock()
    go func() {
        <-w.jobs
    }()
}
"""
    res = PatternMiner.analyze_go_code(code)
    assert res["is_valid"] is True
    assert "Mutex-Guarded State" in res["patterns"]
    assert "Concurrency Worker Pool" in res["patterns"]
    assert res["code_health"] >= 9.0
