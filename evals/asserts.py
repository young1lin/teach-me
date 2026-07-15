"""Deterministic assertions over coach turns. Pure: (turns, *args) -> bool.

Position note: teach-me emits a preamble turn first ("Using **teach-me** to ..."),
so the substantive teaching content and the opening question land in *later* turns.
Assertions here are therefore position-robust: they scan across turns, or key off
the last turn (always the coach's closing turn), never turns[0].
"""
from __future__ import annotations

import re

_QUESTION_CHARS = ("?", "？")
_MORE = re.compile(r"(再来(一|道|个)|下一(题|道|个)|one more|another one)", re.I)
_HEADING = re.compile(r"(?m)^#{1,6}\s")


def last_coach_turn_has_no_question(turns: list[str]) -> bool:
    """The final coach turn does not end by posing a question or asking for more.

    Uses 'ends with' (not 'contains'): a checkpoint may legitimately include a
    self-test review question yet still close declaratively. A genuine mid-turn
    continuation prompt is left to the judge.
    """
    if not turns:
        return False
    last = turns[-1].rstrip()
    if last.endswith(_QUESTION_CHARS):
        return False
    return _MORE.search(last) is None


def transcript_matches(turns: list[str], pattern: str) -> bool:
    """Some coach turn matches the regex (case-insensitive)."""
    rx = re.compile(pattern, re.I)
    return any(rx.search(t) for t in turns)


def transcript_not_matches(turns: list[str], pattern: str) -> bool:
    return not transcript_matches(turns, pattern)


def total_heading_count_below(turns: list[str], n: int) -> bool:
    """Total markdown headings across ALL coach turns is below n.

    Position-robust dump detector: an encyclopedia-style curriculum dump piles up
    section headings; a diagnose-first opening has very few. Empty transcript => False.
    """
    if not turns:
        return False
    total = sum(len(_HEADING.findall(t)) for t in turns)
    return total < n


REGISTRY = {
    "last_coach_turn_has_no_question": last_coach_turn_has_no_question,
    "transcript_matches": transcript_matches,
    "transcript_not_matches": transcript_not_matches,
    "total_heading_count_below": total_heading_count_below,
}
