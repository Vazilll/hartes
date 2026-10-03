"""
Unit tests for Spectrum-Based Fault Localization (SBFL Ochiai) and Dialectical Synthesizer.
"""

import pytest
from vazus_core.verification.sbfl_localizer import SBFLLocalizer
from vazus_core.engine.dialectical_synthesizer import DialecticalSynthesizer


def test_sbfl_ochiai_ranking():
    localizer = SBFLLocalizer()

    # Suppose we have 3 lines: L1, L2, L3
    # Test 1 (Pass): covers {1, 2}
    # Test 2 (Fail): covers {2, 3}
    # Test 3 (Fail): covers {3}
    pass_cov = [{1, 2}]
    fail_cov = [{2, 3}, {3}]
    executable = {1, 2, 3}

    scores = localizer.calculate_ochiai_scores(pass_cov, fail_cov, executable)

    # Line 3 is executed in 2/2 failing tests and 0/1 passing tests -> Ochiai(3) = 2 / sqrt((2+0)*(2+0)) = 1.0 (Maximum Suspiciousness!)
    assert scores[0][0] == 3
    assert scores[0][1] == 1.0


def test_sbfl_extract_snippets():
    localizer = SBFLLocalizer()
    src = "line1\nline2\nbuggy_line3\nline4\nline5"
    ranked = [(3, 1.0), (2, 0.5)]

    snippets = localizer.extract_suspicious_snippets(src, ranked, top_k=1)
    assert len(snippets) == 1
    assert snippets[0]["line"] == 3
    assert ">> L003: buggy_line3" in snippets[0]["context"]


def test_dialectical_extract_code():
    synth = DialecticalSynthesizer()
    raw = "```python\ndef solve():\n    return 42\n```"
    assert synth._extract_code(raw) == "def solve():\n    return 42"
