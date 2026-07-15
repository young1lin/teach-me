import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
from transcript import coach_turns  # noqa: E402


# Fakes mirror the SDK's real dataclass shapes (verified): blocks have NO
# discriminator field — they are told apart by their fields.
class _Text:                       # SDK TextBlock -> {text}
    def __init__(self, text): self.text = text


class _Thinking:                   # SDK ThinkingBlock -> {thinking, signature}
    def __init__(self, thinking): self.thinking = thinking; self.signature = ""


class _ToolUse:                    # SDK ToolUseBlock -> {id, name, input}
    def __init__(self, name): self.id = "t1"; self.name = name; self.input = {}


class _Assistant:                  # SDK AssistantMessage -> has .model + list .content
    def __init__(self, content): self.content = content; self.model = "deepseek"


class _User:                       # no .model — must be skipped
    def __init__(self, content): self.content = content


class _Result:                     # ResultMessage-like — must be skipped
    def __init__(self): self.subtype = "success"; self.result = "done"


def test_extracts_assistant_text_in_order():
    msgs = [_Assistant([_Text("first")]), _Assistant([_Text("second")])]
    assert coach_turns(msgs) == ["first", "second"]


def test_joins_multiple_text_blocks_in_one_message():
    assert coach_turns([_Assistant([_Text("a"), _Text("b")])]) == ["ab"]


def test_keeps_text_and_drops_tool_use_in_same_message():
    # Real preamble turns carry a TextBlock alongside a ToolUseBlock.
    assert coach_turns([_Assistant([_Text("reading files"), _ToolUse("Read")])]) == ["reading files"]


def test_skips_thinking_and_tool_only_messages():
    assert coach_turns([_Assistant([_Thinking("hmm")])]) == []
    assert coach_turns([_Assistant([_ToolUse("Read")])]) == []


def test_skips_user_and_result_messages():
    msgs = [_User("prompt"), _Assistant([_Text("coach")]), _Result()]
    assert coach_turns(msgs) == ["coach"]


def test_skips_whitespace_only_text():
    assert coach_turns([_Assistant([_Text("   ")])]) == []


def test_strips_surrounding_whitespace():
    assert coach_turns([_Assistant([_Text("  kept  ")])]) == ["kept"]
