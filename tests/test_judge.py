import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
import judge  # noqa: E402


def test_parse_verdict_valid_json():
    v = judge.parse_verdict('ok: {"pass": true, "evidence": "q?", "reasoning": "asked"}')
    assert v["pass"] is True
    assert v["evidence"] == "q?"


def test_parse_verdict_false():
    v = judge.parse_verdict('{"pass": false, "evidence": "", "reasoning": "dumped"}')
    assert v["pass"] is False


def test_parse_verdict_ignores_brace_prose_around_json():
    # A reasoning-heavy model can emit brace-containing prose before the verdict;
    # first-'{'-to-last-'}' slicing would corrupt the JSON and mis-flag a pass.
    raw = ('Checking rubric {clause 1, clause 2}... looks good.\n'
           '{"pass": true, "evidence": "why?", "reasoning": "asked a question"}')
    v = judge.parse_verdict(raw)
    assert v["pass"] is True
    assert v["evidence"] == "why?"


def test_parse_verdict_unparseable_is_flagged_failure():
    v = judge.parse_verdict("no json at all")
    assert v["pass"] is False
    assert "unparseable" in v["reasoning"]


class _FakeChat:
    def __init__(self, reply): self._reply = reply; self.calls = []
    def complete(self, *, system, user, max_tokens, temperature):
        self.calls.append({"system": system, "user": user,
                           "max_tokens": max_tokens, "temperature": temperature})
        return self._reply


def test_judge_calls_chat_and_parses_verdict():
    chat = _FakeChat('{"pass": true, "evidence": "e", "reasoning": "r"}')
    v = judge.judge(chat, rubric="RUBRIC", judge_input="INPUT")
    assert v["pass"] is True and v["evidence"] == "e"
    sent = chat.calls[0]
    assert sent["max_tokens"] == 2048           # carried-forward fix
    assert sent["temperature"] == 0
    assert "RUBRIC" in sent["user"] and "INPUT" in sent["user"]
