"""
vazus_core.memory.intent_similarity
===================================
Lexical, polarity-aware comparison of two intent statements.

Why not embeddings: measured on this machine, the NPU/fallback embedder does not separate meaning
(paraphrase 0.76 < unrelated 0.83 < opposite meaning 0.98), so it cannot gate anything.
This module is deliberately honest: it only sees shared word stems (RU/EN), it does NOT understand
paraphrases that share no words. Its job is to catch repeats and contradictions of the *same wording*,
and to show the user only the small difference.

Relations returned by compare():
    duplicate  same polarity, stem overlap >= DUPLICATE
    refines    same polarity, stem overlap >= RELATED
    conflicts  opposite polarity, stem overlap >= RELATED  (e.g. "не решать задачи" vs "решать задачи")
    new        otherwise
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import List, Set

DUPLICATE = 1.0  # identical stems: nothing but case/punctuation/stopwords differs
RELATED = 0.4

_WORD = re.compile(r"\w+", re.U)
_NEGATION = {"не", "ни", "нет", "без", "никогда", "нельзя", "not", "never", "no", "don't", "dont"}
_NEGATION_PREFIX = ("запрещ", "недопуст", "прекрат", "избег", "исключ", "отказ", "предотвращ", "нельз", "невозможн")
_STOP = {
    "и", "а", "но", "в", "во", "на", "за", "по", "к", "с", "со", "у", "о", "об", "от", "до", "из", "для", "что",
    "чтобы", "это", "как", "то", "же", "бы", "ли", "нужно", "надо", "должен", "должна", "должны", "мне", "мы",
    "the", "a", "an", "to", "of", "and", "or", "is", "be", "we", "i", "must", "need", "should",
}


@dataclass(frozen=True)
class Comparison:
    relation: str  # duplicate | refines | conflicts | new
    similarity: float  # stem Jaccard, negations/stopwords excluded
    diff: str  # compact word-level difference ("" when texts are equal)


def _words(text: str) -> List[str]:
    return [w.lower() for w in _WORD.findall(text)]


def is_negative(text: str) -> bool:
    """True when the statement is a negative constraint or prohibition."""
    words = _words(text)
    negs = [w for w in words if w in _NEGATION or w.startswith(_NEGATION_PREFIX)]
    if not negs:
        return False
    # Russian negative concord: 'никогда не' reinforces negation, does not cancel it
    if any(w.startswith("ни") for w in negs) and any(w == "не" or w.startswith(_NEGATION_PREFIX) for w in negs):
        return True
    return len(negs) % 2 == 1


def stems(text: str) -> Set[str]:
    return {
        w[:5]
        for w in _words(text)
        if len(w) > 3 and w not in _STOP and w not in _NEGATION and not w.startswith(_NEGATION_PREFIX)
    }


def similarity(a: str, b: str) -> float:
    sa, sb = stems(a), stems(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def word_diff(a: str, b: str) -> str:
    """'-removed +added' summary between two statements, word-level and case-insensitive."""
    wa, wb = _words(a), _words(b)
    parts: List[str] = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        if i2 > i1:
            parts.append("-" + " ".join(wa[i1:i2]))
        if j2 > j1:
            parts.append("+" + " ".join(wb[j1:j2]))
    return " ".join(parts)


def compare(existing: str, candidate: str) -> Comparison:
    sim = similarity(existing, candidate)
    same_polarity = is_negative(existing) == is_negative(candidate)
    if sim >= RELATED and not same_polarity:
        relation = "conflicts"
    elif sim >= DUPLICATE:
        relation = "duplicate"
    elif sim >= RELATED:
        relation = "refines"
    else:
        relation = "new"
    return Comparison(relation, round(sim, 3), word_diff(existing, candidate))
