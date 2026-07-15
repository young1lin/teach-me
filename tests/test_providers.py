import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
import providers  # noqa: E402
import pytest  # noqa: E402


class _FakeAnthropicBlock:
    def __init__(self, text): self.type = "text"; self.text = text


class _FakeAnthropicMsg:
    def __init__(self, blocks): self.content = blocks


class _FakeAnthropicClient:
    def __init__(self, blocks): self._blocks = blocks; self.calls = []

    class _Messages:
        def __init__(self, outer): self._outer = outer
        def create(self, **kwargs):
            self._outer.calls.append(kwargs)
            return _FakeAnthropicMsg(self._outer._blocks)

    @property
    def messages(self): return _FakeAnthropicClient._Messages(self)


def test_anthropic_chat_joins_text_blocks_and_shapes_request():
    client = _FakeAnthropicClient([_FakeAnthropicBlock("ver"), _FakeAnthropicBlock("dict")])
    chat = providers.AnthropicChat(client, "m-alias")
    out = chat.complete(system="S", user="U", max_tokens=2048, temperature=0)
    assert out == "verdict"
    sent = client.calls[0]
    assert sent["model"] == "m-alias"
    assert sent["max_tokens"] == 2048
    assert sent["system"] == "S"
    assert sent["messages"] == [{"role": "user", "content": "U"}]


class _FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _FakeOpenAIResp:
    def __init__(self, content): self.choices = [_FakeChoice(content)]


class _FakeOpenAIClient:
    def __init__(self, content): self._content = content; self.calls = []

    class _Completions:
        def __init__(self, outer): self._outer = outer
        def create(self, **kwargs):
            self._outer.calls.append(kwargs)
            return _FakeOpenAIResp(self._outer._content)

    class _Chat:
        def __init__(self, outer): self.completions = _FakeOpenAIClient._Completions(outer)

    @property
    def chat(self): return _FakeOpenAIClient._Chat(self)


def test_openai_chat_reads_message_content_and_shapes_request():
    client = _FakeOpenAIClient("verdict")
    chat = providers.OpenAIChat(client, "deepseek-chat")
    out = chat.complete(system="S", user="U", max_tokens=2048, temperature=0)
    assert out == "verdict"
    sent = client.calls[0]
    assert sent["model"] == "deepseek-chat"
    assert sent["messages"] == [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "U"},
    ]


def test_openai_chat_handles_none_content():
    chat = providers.OpenAIChat(_FakeOpenAIClient(None), "deepseek-chat")
    assert chat.complete(system="S", user="U", max_tokens=10, temperature=0) == ""


def test_make_chat_rejects_unknown_backend():
    with pytest.raises(providers.SetupError):
        providers.make_chat("gemini", {})


class _FakeSDKClient:
    """Mimics ClaudeSDKClient's async context + query/receive_response."""
    def __init__(self, scripted_turns): self._scripted = list(scripted_turns); self.queries = []
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def query(self, prompt): self.queries.append(prompt)
    async def receive_response(self):
        for msg in self._scripted.pop(0):
            yield msg


class _Text2:                      # SDK TextBlock -> {text} only (no .type)
    def __init__(self, text): self.text = text


class _Assistant2:                 # SDK AssistantMessage -> has .model + list .content
    def __init__(self, content): self.content = content; self.model = "deepseek"


def test_agent_sdk_coach_runs_turns_and_returns_coach_text():
    scripted = [[_Assistant2([_Text2("preamble")])],
                [_Assistant2([_Text2("a question?")])]]
    fake = _FakeSDKClient(scripted)
    coach = providers.AgentSDKCoach(env={}, repo="/repo", client_factory=lambda: fake)
    out = coach.run(["/teach-me recursion", "我懂了"])
    assert out == ["preamble", "a question?"]
    assert fake.queries == ["/teach-me recursion", "我懂了"]
