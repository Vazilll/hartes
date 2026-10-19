"""
vazus_core.memory.intent_extractor
==================================
Heuristic "meaning" extraction for J-Space intent anchors, plus a tiny CLI to review them.

The agent only PROPOSES (status='proposed'); nothing influences prompts until the user confirms:
    python -m vazus_core.memory.intent_extractor list
    python -m vazus_core.memory.intent_extractor confirm <intent_id>
    python -m vazus_core.memory.intent_extractor reject  <intent_id>
"""

from __future__ import annotations

import re
import sys
from typing import Any, Iterable, List, Optional, Tuple

_USER_REQUEST = re.compile(r"<USER_REQUEST>(.*?)</USER_REQUEST>", re.S)
_SENTENCE = re.compile(r"(?<=[.!?\n])\s+")

_CONSTRAINT = re.compile(
    r"\b(никогда|запрещ\w*|нельзя|не\s+(?:делай|решай|создавай|удаляй|отключай|меняй)|не\s+допуска\w*|"
    r"всегда|обязательно|должн\w*|важно|принцип|"
    r"never|always|must(?:\s+not)?|do not|don't)\b",
    re.I,
)
_GOAL = re.compile(
    r"\b(цель|хочу,?\s+чтобы|нужно,?\s+чтобы|надо,?\s+чтобы|мне\s+нужно|сделай\s+так|"
    r"смысл\w*|не\s+менял\w*|the goal is|i want|we need to)\b",
    re.I,
)
MAX_PER_SESSION = 3
MAX_LEN = 300


def _texts(messages: Iterable[dict]) -> List[str]:
    out: List[str] = []
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
        if not isinstance(content, str):
            continue
        m = _USER_REQUEST.search(content)
        out.append((m.group(1) if m else content).strip())
    return out


def extract_intent_candidates(messages: Iterable[dict]) -> List[Tuple[str, str]]:
    """Returns up to MAX_PER_SESSION (kind, statement) pairs, most rule-like sentences first."""
    scored: List[Tuple[int, int, str, str]] = []  # (-score, order, kind, sentence)
    seen = set()
    for text in _texts(messages):
        for sentence in _SENTENCE.split(text):
            s = sentence.strip()
            if not (10 <= len(s) <= MAX_LEN) or s.startswith(("<", "```")) or s.casefold() in seen:
                continue
            n_con, n_goal = len(_CONSTRAINT.findall(s)), len(_GOAL.findall(s))
            if n_con or n_goal:
                seen.add(s.casefold())
                scored.append((-(n_con + n_goal), len(scored), "constraint" if n_con >= n_goal else "goal", s))
    scored.sort()
    return [(kind, s) for _, _, kind, s in scored[:MAX_PER_SESSION]]


def propose_from_session(messages: Iterable[dict], workspace: Optional[Any] = None) -> List[dict]:
    """Proposes extracted candidates into J-Space. Never confirms anything."""
    if workspace is None:
        from vazus_core.memory.unified_j_workspace import UnifiedJWorkspace

        workspace = UnifiedJWorkspace()
    return [workspace.propose_intent(stmt, kind=kind, source="stop_hook", semantic=True) for kind, stmt in extract_intent_candidates(messages)]


def main(argv: Optional[List[str]] = None) -> int:
    from vazus_core.memory.unified_j_workspace import UnifiedJWorkspace

    args = list(sys.argv[1:] if argv is None else argv)
    ws = UnifiedJWorkspace()
    if not args or args[0] == "list":
        for status in ("proposed", "confirmed"):
            for i in ws.get_intents(status):
                rel = f" [{i['relation']}: {i['diff']}]" if i["relation"] != "new" else ""
                print(f"{status:9} {i['intent_id']} ({i['kind']}) {i['statement']}{rel}")
        return 0
    if len(args) == 2 and args[0] in ("confirm", "reject"):
        ok = (ws.confirm_intent if args[0] == "confirm" else ws.reject_intent)(args[1])
        print("ok" if ok else "not found or not in 'proposed' state")
        return 0 if ok else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

