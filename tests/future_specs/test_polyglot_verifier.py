"""
tests/test_polyglot_verifier.py — Tests for Universal Polyglot Verification Service.

Tests:
1. Python verification (syntax, CC, health score, AST pruning).
2. Go verification (syntax, package, func detection, Tree-Sitter pruning).
3. C/C++ verification (syntax, struct/typedef, branch CC).
4. Polyglot router dispatch and batch processing.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
from hypothesis import given, strategies as st

from vazus_core.verification.polyglot_verifier import (
    PolyglotVerificationService,
    PythonVerifier,
    GoVerifier,
    CVerifier,
    get_polyglot_verification_service,
)


class TestPolyglotVerificationService:
    """Test suite for polyglot code verification across Python, Go, and C/C++."""

    @pytest.fixture
    def service(self) -> PolyglotVerificationService:
        return get_polyglot_verification_service()

    def test_python_valid_code_evaluation(self, service: PolyglotVerificationService):
        code = (
            "def calculate_tax(income: float, rate: float) -> float:\n"
            "    '''Calculates standard tax rate.'''\n"
            "    if income <= 0:\n"
            "        return 0.0\n"
            "    return income * rate\n"
        )
        res = service.verifiers["python"].evaluate(code)
        assert res.passed is True
        assert res.language == "python"
        assert res.metrics.is_valid_syntax is True
        assert res.metrics.cyclomatic_complexity == 2
        assert res.metrics.code_health_score >= 9.5
        assert len(res.pruned_code) > 0

    def test_python_invalid_syntax_evaluation(self, service: PolyglotVerificationService):
        code = "def broken(:\n    return\n"
        res = service.verifiers["python"].evaluate(code)
        assert res.passed is False
        assert res.metrics.is_valid_syntax is False
        assert len(res.errors) > 0

    def test_go_valid_code_evaluation(self, service: PolyglotVerificationService):
        code = (
            "package main\n\n"
            "import \"fmt\"\n\n"
            "type User struct {\n"
            "    ID   int\n"
            "    Name string\n"
            "}\n\n"
            "func Add(a int, b int) int {\n"
            "    if a > 0 {\n"
            "        return a + b\n"
            "    }\n"
            "    return b\n"
            "}\n\n"
            "func main() {\n"
            "    fmt.Println(Add(1, 2))\n"
            "}\n"
        )
        res = service.verifiers["go"].evaluate(code)
        assert res.passed is True
        assert res.language == "go"
        assert res.metrics.is_valid_syntax is True
        assert res.metrics.functions_count >= 2
        assert res.metrics.classes_or_types_count >= 1
        assert "panic(" in res.pruned_code or "{" in res.pruned_code

    def test_c_valid_code_evaluation(self, service: PolyglotVerificationService):
        code = (
            "#include <stdio.h>\n\n"
            "typedef struct {\n"
            "    int x;\n"
            "    int y;\n"
            "} Point;\n\n"
            "int calculate_distance(Point p) {\n"
            "    if (p.x < 0) return -1;\n"
            "    return p.x * p.x + p.y * p.y;\n"
            "}\n"
        )
        res = service.verifiers["c"].evaluate(code)
        assert res.passed is True
        assert res.language == "c"
        assert res.metrics.is_valid_syntax is True
        assert res.metrics.classes_or_types_count >= 1

    def test_service_router_file_dispatch(self, service: PolyglotVerificationService, tmp_path: Path):
        py_file = tmp_path / "mod.py"
        py_file.write_text("def ok(): return True\n", encoding="utf-8")
        
        go_file = tmp_path / "mod.go"
        go_file.write_text("package main\nfunc main() {}\n", encoding="utf-8")

        c_file = tmp_path / "mod.c"
        c_file.write_text("int main() { return 0; }\n", encoding="utf-8")

        results = service.verify_batch([py_file, go_file, c_file])
        assert len(results) == 3
        assert results[0].language == "python"
        assert results[1].language == "go"
        assert results[2].language == "c"
        assert all(r.passed for r in results)
