"""LLM judge — provider-agnostic scoring over a ChatModel."""
from __future__ import annotations

import json

SYSTEM = (
    "You are a strict grader. Given a RUBRIC and a transcript EXCERPT, decide "
    "whether the excerpt satisfies EVERY clause of the rubric. Output ONLY a JSON "
    'object: {"pass": true|false, "evidence": "<short quote>", "reasoning": "<one line>"}. '
    "Do not be lenient; a missed clause is a fail."
)


def parse_verdict(text: str) -> dict:
    """Extract the JSON verdict from model text. Unparseable => flagged failure.

    Scans each '{' and balance-decodes from there (json.raw_decode), returning the
    first object that carries a "pass" key. This tolerates reasoning prose — even
    brace-containing prose — before or after the verdict object, which a naive
    first-'{'-to-last-'}' slice would turn into invalid JSON and mis-flag as a fail.
    """
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "pass" in obj:
            return {"pass": bool(obj.get("pass", False)),
                    "evidence": str(obj.get("evidence", "")),
                    "reasoning": str(obj.get("reasoning", ""))}
    return {"pass": False, "evidence": "",
            "reasoning": f"unparseable judge output: {text[:120]!r}"}


def judge(chat, rubric: str, judge_input: str) -> dict:
    """Score judge_input against rubric via the injected ChatModel.

    max_tokens=2048: deepseek spends budget on reasoning; 512 truncated verdicts
    or returned empty text.
    """
    text = chat.complete(
        system=SYSTEM,
        user=f"RUBRIC:\n{rubric}\n\nEXCERPT:\n{judge_input}",
        max_tokens=2048,
        temperature=0,
    )
    return parse_verdict(text)
