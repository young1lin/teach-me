"""Extract coach text turns from Claude Agent SDK messages.

Duck-typed against the SDK's actual dataclasses (no SDK import): an assistant
message has a `.model` attribute and a list `.content` of blocks. The block
dataclasses have NO discriminator field — they are told apart by their fields:
  - TextBlock    -> {text}
  - ThinkingBlock-> {thinking, signature}
  - ToolUseBlock -> {id, name, input}
So a text block is one that has `.text` but neither `.thinking` nor `.input`.
User/result messages lack `.model` (or a list `.content`) and are skipped, as
are thinking/tool-only turns. Kept turns are stripped so downstream asserts
(e.g. endswith checks) are not tripped by trailing newlines.
"""
from __future__ import annotations


def _is_text_block(block) -> bool:
    return (hasattr(block, "text")
            and not hasattr(block, "thinking")
            and not hasattr(block, "input"))


def coach_turns(messages) -> list[str]:
    turns: list[str] = []
    for msg in messages:
        content = getattr(msg, "content", None)
        if getattr(msg, "model", None) is None or not isinstance(content, list):
            continue
        text = "".join(getattr(b, "text", "") for b in content
                       if _is_text_block(b)).strip()
        if text:
            turns.append(text)
    return turns
