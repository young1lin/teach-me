# teach-me Eval Harness — SDK Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-architect the teach-me behavioral eval harness so the coach runs the real teach-me skill through the Claude Agent SDK, the judge runs through the official Anthropic/OpenAI SDKs, both sit behind a thin self-built provider glue layer, and every collaborator is dependency-injected so the unit suite runs offline.

**Architecture:** A single glue module (`evals/providers.py`) owns all SDK contact via two Protocols — `ChatModel` (judge) and `CoachSession` (coach) — each with concrete adapters and a factory. Judge scoring, transcript extraction, asserts, and the orchestrator are provider-agnostic and injected with fakes in tests. `evals/` becomes a `uv` project; `.env` moves under it with a committed placeholder `.env.example`.

**Tech Stack:** Python ≥3.11, `uv`, `claude-agent-sdk`, `anthropic`, `openai`, `pyyaml`, `pytest`. DeepSeek endpoints (Anthropic-compatible + OpenAI chat-completions) via a local `evals/.env`.

## Global Constraints

- **Commit author:** every commit authored as `young1lin` (the repo's configured git identity — do not override it). Claude credited **only** via trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Never as author.
- **No secrets/PII in tracked files.** The DeepSeek key lives only in `evals/.env` (gitignored). `evals/.env.example` holds placeholder values only. No usernames, emails, or home paths in tracked content.
- **Python floor `>=3.11`; never run under 3.14** (its alpha segfaults on C-extensions). All pytest/harness commands use `uv run --project evals`.
- **No CI.** Runs are deliberate and paid; self-tested locally.
- **Pure unit suite must stay green and offline** (no network, no cost) at every commit: `uv run --project evals -m pytest -q tests/` run from the repo root.
- **Codex / OpenAI Responses API is out of scope** — DeepSeek does not support it.
- Reference spec: `docs/superpowers/specs/2026-07-15-teach-me-eval-harness-sdk-redesign.md`.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `evals/pyproject.toml` | uv project: runtime + dev deps, python floor |
| `evals/.env` | local secrets (gitignored, moved from repo root) |
| `evals/.env.example` | committed placeholder documentation of env vars |
| `evals/providers.py` | **the only SDK seam** — `ChatModel`/`CoachSession` Protocols, `AnthropicChat`, `OpenAIChat`, `AgentSDKCoach`, `make_chat`, `make_coach` |
| `evals/session.py` | env/config bootstrap only — `load_env`, `SetupError`, `REPO`, `EVALS` |
| `evals/transcript.py` | `coach_turns(messages)` — extract assistant text turns from SDK messages (duck-typed, no SDK import) |
| `evals/judge.py` | `parse_verdict`, `judge(chat, rubric, judge_input)` — provider-agnostic scoring over `ChatModel` |
| `evals/asserts.py` | **unchanged** — deterministic asserts over `list[str]` |
| `evals/run_evals.py` | orchestrator — DI wiring, `--judge-backend`, sample/threshold logic |
| `evals/scenarios/*.yaml` | unchanged |
| `evals/README.md` | run instructions |
| `tests/test_providers.py` | adapters/factories with fake underlying clients |
| `tests/test_session.py` | `load_env` |
| `tests/test_transcript.py` | `coach_turns` with fake SDK messages |
| `tests/test_judge.py` | `parse_verdict` + `judge` over a fake `ChatModel` |
| `tests/test_run_evals.py` | orchestrator with fake coach + fake chat |
| `tests/test_asserts.py` | unchanged |

---

## Task 1: uv project scaffold + env relocation

**Files:**
- Create: `evals/pyproject.toml`
- Create: `evals/.env.example`
- Move: `.env` → `evals/.env`
- Modify: `.gitignore` (add `!.env.example`)

**Interfaces:**
- Consumes: nothing.
- Produces: a runnable `uv --project evals` environment. No code API changes yet; existing modules and tests are untouched and must stay green.

- [ ] **Step 1: Create the uv project file**

Create `evals/pyproject.toml`:

```toml
[project]
name = "teach-me-evals"
version = "0.1.0"
description = "Behavioral eval harness for the teach-me skill (paid, local, non-CI)."
requires-python = ">=3.11"
dependencies = [
    "claude-agent-sdk>=0.1",
    "anthropic>=0.40",
    "openai>=1.40",
    "pyyaml>=6,<7",
]

[dependency-groups]
dev = ["pytest>=8"]
```

- [ ] **Step 2: Create the placeholder env example**

Create `evals/.env.example` (placeholders only — no real values):

```bash
# DeepSeek Anthropic-compatible endpoint — used by the coach (Claude Agent SDK)
# and the Anthropic judge backend. Copy to evals/.env and fill in.
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_AUTH_TOKEN=sk-your-deepseek-key-here
ANTHROPIC_MODEL=deepseek-model-alias-here
ANTHROPIC_SMALL_FAST_MODEL=deepseek-model-alias-here
API_TIMEOUT_MS=600000
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

# DeepSeek OpenAI-compatible chat-completions — used by the OpenAI judge backend.
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
# Optional overrides for the OpenAI judge backend (defaults shown):
# OPENAI_BASE_URL=https://api.deepseek.com
# OPENAI_MODEL=deepseek-chat
```

- [ ] **Step 3: Move the real .env under evals/**

Run (from repo root):

```bash
git mv .env evals/.env 2>/dev/null || mv .env evals/.env
```

Expected: `evals/.env` exists; repo-root `.env` is gone. (`.env` is gitignored, so `git mv` may report it as untracked — the `|| mv` fallback handles that.)

- [ ] **Step 4: Add the .env.example gitignore exception**

In `.gitignore`, under the secrets block, change:

```
.env
.env.*
```

to:

```
.env
.env.*
!.env.example
!evals/.env.example
```

- [ ] **Step 5: Verify the example is tracked and the real env is not**

Run:

```bash
git check-ignore evals/.env && echo "IGNORED (correct)"
git check-ignore evals/.env.example; echo "exit=$?  (expect exit=1: NOT ignored)"
```

Expected: `evals/.env` prints `IGNORED (correct)`; `evals/.env.example` prints `exit=1`.

- [ ] **Step 6: Verify the existing suite still passes under uv**

Run (from repo root):

```bash
uv run --project evals -m pytest -q tests/
```

Expected: all existing tests PASS (code unchanged; only the toolchain moved). If `uv` resolves the SDK deps this is also the first proof they install cleanly.

- [ ] **Step 7: Commit**

```bash
git add evals/pyproject.toml evals/.env.example .gitignore
git commit -m "$(cat <<'EOF'
build(evals): uv project + .env relocation + .env.example

Turn evals/ into a self-contained uv project (python >=3.11, pins
claude-agent-sdk/anthropic/openai/pyyaml). Move .env under evals/ and add a
placeholder .env.example (gitignore exception so it is tracked).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: providers.py — ChatModel port + adapters (judge side)

**Files:**
- Create: `evals/providers.py`
- Test: `tests/test_providers.py`

**Interfaces:**
- Consumes: `load_env` output dict (keys `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_MODEL`, `DEEPSEEK_API_KEY`, optional `OPENAI_BASE_URL`/`OPENAI_MODEL`).
- Produces:
  - `ChatModel` Protocol: `complete(self, *, system: str, user: str, max_tokens: int, temperature: float) -> str`
  - `AnthropicChat(client, model)` and `OpenAIChat(client, model)` implementing it.
  - `make_chat(backend: str, env: dict) -> ChatModel`, `backend ∈ {"anthropic", "openai"}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_providers.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project evals -m pytest tests/test_providers.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'providers'`.

- [ ] **Step 3: Write the ChatModel port and adapters**

Create `evals/providers.py`:

```python
"""The single SDK seam for the eval harness.

Everything that touches an LLM SDK lives here behind two provider-agnostic
ports: ChatModel (judge) and CoachSession (coach). The rest of the harness is
provider-neutral and injected with fakes in tests.
"""
from __future__ import annotations

from typing import Protocol


class SetupError(RuntimeError):
    """Raised on misconfiguration (bad backend, missing env)."""


class ChatModel(Protocol):
    """A single-shot chat completion. The judge sits on this."""

    def complete(self, *, system: str, user: str,
                 max_tokens: int, temperature: float) -> str: ...


class AnthropicChat:
    """anthropic SDK → DeepSeek Anthropic-compatible endpoint."""

    def __init__(self, client, model: str):
        self._client = client
        self._model = model

    def complete(self, *, system: str, user: str,
                 max_tokens: int, temperature: float) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(getattr(b, "text", "") for b in msg.content
                       if getattr(b, "type", None) == "text")


class OpenAIChat:
    """openai SDK → DeepSeek chat-completions endpoint."""

    def __init__(self, client, model: str):
        self._client = client
        self._model = model

    def complete(self, *, system: str, user: str,
                 max_tokens: int, temperature: float) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""


def make_chat(backend: str, env: dict) -> ChatModel:
    if backend == "anthropic":
        from anthropic import Anthropic
        # DeepSeek's Anthropic endpoint accepts the token via x-api-key, which
        # is what api_key= sends (matches the previously-working raw call).
        client = Anthropic(base_url=env["ANTHROPIC_BASE_URL"],
                           api_key=env["ANTHROPIC_AUTH_TOKEN"])
        return AnthropicChat(client, env["ANTHROPIC_MODEL"])
    if backend == "openai":
        from openai import OpenAI
        client = OpenAI(base_url=env.get("OPENAI_BASE_URL", "https://api.deepseek.com"),
                        api_key=env["DEEPSEEK_API_KEY"])
        return OpenAIChat(client, env.get("OPENAI_MODEL", "deepseek-chat"))
    raise SetupError(f"unknown judge backend {backend!r} (want 'anthropic' or 'openai')")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --project evals -m pytest tests/test_providers.py -q
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add evals/providers.py tests/test_providers.py
git commit -m "$(cat <<'EOF'
feat(evals): ChatModel provider port + Anthropic/OpenAI adapters

The single SDK seam. AnthropicChat/OpenAIChat wrap the official SDKs pointed
at DeepSeek; make_chat selects by backend. Tested with fake underlying clients
(request shaping + response extraction), no network.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: judge.py — provider-agnostic scoring over ChatModel

**Files:**
- Modify: `evals/judge.py` (full rewrite)
- Test: `tests/test_judge.py` (new)

**Interfaces:**
- Consumes: `ChatModel` (Task 2).
- Produces:
  - `parse_verdict(text: str) -> dict` with keys `pass` (bool), `evidence` (str), `reasoning` (str).
  - `judge(chat: ChatModel, rubric: str, judge_input: str) -> dict` — same return shape.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_judge.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project evals -m pytest tests/test_judge.py -q
```

Expected: FAIL — `judge.judge` has the old `(rubric, excerpt, env)` signature and `AttributeError`/`TypeError`, or the old module still POSTs via urllib.

- [ ] **Step 3: Rewrite judge.py onto ChatModel**

Replace `evals/judge.py` entirely with:

```python
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
    """Extract the JSON verdict from model text. Unparseable => flagged failure."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {"pass": False, "evidence": "",
                "reasoning": f"unparseable judge output: {text[:120]!r}"}
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError as err:
        return {"pass": False, "evidence": "",
                "reasoning": f"invalid judge JSON: {err}"}
    return {"pass": bool(obj.get("pass", False)),
            "evidence": str(obj.get("evidence", "")),
            "reasoning": str(obj.get("reasoning", ""))}


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --project evals -m pytest tests/test_judge.py -q
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add evals/judge.py tests/test_judge.py
git commit -m "$(cat <<'EOF'
refactor(evals): judge scores over injected ChatModel, not raw HTTP

judge(chat, rubric, judge_input) is now pure logic over the ChatModel port;
the urllib POST is gone (SDK clients live in providers.py). Keeps parse_verdict
and the max_tokens=2048 fix. Tested with a fake ChatModel.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: transcript.py — SDK-message → turns

**Files:**
- Modify: `evals/transcript.py` (full rewrite)
- Test: `tests/test_transcript.py` (rewrite)

**Interfaces:**
- Consumes: a list of SDK message objects (duck-typed: assistant messages have a `.model` attribute and a list `.content` of blocks; text blocks have `.type == "text"` and `.text`).
- Produces: `coach_turns(messages) -> list[str]` — one entry per assistant message that has non-empty text, in order.

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_transcript.py` entirely with:

```python
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
from transcript import coach_turns  # noqa: E402


class _Text:
    def __init__(self, text): self.type = "text"; self.text = text


class _Thinking:
    def __init__(self, text): self.type = "thinking"; self.thinking = text


class _Assistant:
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


def test_skips_thinking_and_tool_only_messages():
    assert coach_turns([_Assistant([_Thinking("hmm")])]) == []


def test_skips_user_and_result_messages():
    msgs = [_User("prompt"), _Assistant([_Text("coach")]), _Result()]
    assert coach_turns(msgs) == ["coach"]


def test_skips_whitespace_only_text():
    assert coach_turns([_Assistant([_Text("   ")])]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project evals -m pytest tests/test_transcript.py -q
```

Expected: FAIL — the old `coach_turns` parses a JSONL string and errors on a list of objects.

- [ ] **Step 3: Rewrite transcript.py**

Replace `evals/transcript.py` entirely with:

```python
"""Extract coach text turns from Claude Agent SDK messages.

Duck-typed (no SDK import): an assistant message has a `.model` attribute and a
list `.content` of blocks; a text block has `.type == "text"` and `.text`.
User and result messages lack `.model` (or lack a list `.content`) and are
skipped, as are thinking/tool-only assistant turns.
"""
from __future__ import annotations


def coach_turns(messages) -> list[str]:
    turns: list[str] = []
    for msg in messages:
        content = getattr(msg, "content", None)
        if getattr(msg, "model", None) is None or not isinstance(content, list):
            continue
        text = "".join(
            getattr(b, "text", "") for b in content
            if getattr(b, "type", None) == "text"
        )
        if text.strip():
            turns.append(text)
    return turns
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --project evals -m pytest tests/test_transcript.py -q
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add evals/transcript.py tests/test_transcript.py
git commit -m "$(cat <<'EOF'
refactor(evals): coach_turns reads SDK messages, not JSONL

The Claude Agent SDK returns structured AssistantMessage/TextBlock objects, so
transcript extraction is now duck-typed over those (no JSONL parsing, no SDK
import). Output contract unchanged (list[str]); asserts.py untouched.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: providers.py CoachSession + AgentSDKCoach; session.py bootstrap

**Files:**
- Modify: `evals/providers.py` (add coach port + adapter + factory)
- Modify: `evals/session.py` (strip to bootstrap; retarget `.env` path)
- Test: `tests/test_session.py` (rewrite), `tests/test_providers.py` (append coach tests)

**Interfaces:**
- Consumes: `coach_turns` (Task 4); `load_env` output dict.
- Produces:
  - `CoachSession` Protocol: `run(self, turns: list[str]) -> list[str]`
  - `AgentSDKCoach(env, repo, client_factory=None)` implementing it (sync `run`, async hidden internally).
  - `make_coach(env: dict) -> CoachSession`.
  - `session.load_env(dotenv=None) -> dict`, `session.SetupError`, `session.REPO`, `session.EVALS`.

- [ ] **Step 1: Write the failing coach tests**

Append to `tests/test_providers.py`:

```python
class _FakeSDKClient:
    """Mimics ClaudeSDKClient's async context + query/receive_response."""
    def __init__(self, scripted_turns): self._scripted = list(scripted_turns); self.queries = []
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def query(self, prompt): self.queries.append(prompt)
    async def receive_response(self):
        for msg in self._scripted.pop(0):
            yield msg


class _Text2:
    def __init__(self, text): self.type = "text"; self.text = text


class _Assistant2:
    def __init__(self, content): self.content = content; self.model = "deepseek"


def test_agent_sdk_coach_runs_turns_and_returns_coach_text():
    scripted = [[_Assistant2([_Text2("preamble")])],
                [_Assistant2([_Text2("a question?")])]]
    fake = _FakeSDKClient(scripted)
    coach = providers.AgentSDKCoach(env={}, repo="/repo", client_factory=lambda: fake)
    out = coach.run(["/teach-me recursion", "我懂了"])
    assert out == ["preamble", "a question?"]
    assert fake.queries == ["/teach-me recursion", "我懂了"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project evals -m pytest tests/test_providers.py::test_agent_sdk_coach_runs_turns_and_returns_coach_text -q
```

Expected: FAIL — `AttributeError: module 'providers' has no attribute 'AgentSDKCoach'`.

- [ ] **Step 3: Add the coach port + adapter to providers.py**

Append to `evals/providers.py`:

```python
from transcript import coach_turns


class CoachSession(Protocol):
    """An agentic skill run over scripted turns. The coach sits on this."""

    def run(self, turns: list[str]) -> list[str]: ...


class AgentSDKCoach:
    """Runs the real teach-me skill via the Claude Agent SDK.

    `run` is synchronous; the SDK's async API is hidden behind asyncio.run so
    the orchestrator stays synchronous. Pass client_factory in tests to inject
    a fake SDK client.
    """

    def __init__(self, env: dict, repo, client_factory=None):
        self._env = env
        self._repo = str(repo)
        self._client_factory = client_factory or self._default_client

    def _default_client(self):
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
        options = ClaudeAgentOptions(
            env=self._env,                 # forwarded to the CLI → routes to DeepSeek
            cwd=self._repo,
            plugins=[{"type": "local", "path": self._repo}],
            setting_sources=["project"],   # load this repo's teach-me skill
            permission_mode="bypassPermissions",
        )
        return ClaudeSDKClient(options=options)

    def run(self, turns: list[str]) -> list[str]:
        import asyncio
        return asyncio.run(self._run_async(turns))

    async def _run_async(self, turns: list[str]) -> list[str]:
        messages = []
        client = self._client_factory()
        async with client:
            for turn in turns:
                await client.query(turn)
                async for msg in client.receive_response():
                    messages.append(msg)
        return coach_turns(messages)


def make_coach(env: dict) -> CoachSession:
    from session import REPO
    return AgentSDKCoach(env=env, repo=REPO)
```

- [ ] **Step 4: Rewrite session.py to bootstrap-only**

Replace `evals/session.py` entirely with:

```python
"""Env/config bootstrap for the eval harness.

Loads evals/.env as an overlay on the current environment so nested SDK clients
(coach + judge) reach DeepSeek. No subprocess/transport code lives here anymore
— that moved to providers.py.
"""
from __future__ import annotations

import os
from pathlib import Path

EVALS = Path(__file__).resolve().parent
REPO = EVALS.parent

REQUIRED = ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL")


class SetupError(RuntimeError):
    """Raised when the harness is misconfigured."""


def load_env(dotenv=None) -> dict:
    """Overlay a dotenv file onto a copy of os.environ; validate required keys."""
    path = Path(dotenv) if dotenv else EVALS / ".env"
    if not path.exists():
        raise SetupError(f"missing env file: {path} (copy .env.example to evals/.env)")
    env = os.environ.copy()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    missing = [k for k in REQUIRED if not env.get(k)]
    if missing:
        raise SetupError(f"missing required env keys: {', '.join(missing)}")
    return env
```

- [ ] **Step 5: Rewrite session tests**

Replace `tests/test_session.py` entirely with:

```python
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
import session  # noqa: E402
import pytest  # noqa: E402


def test_load_env_overlays_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    f = tmp_path / ".env"
    f.write_text(
        "# comment\n"
        "ANTHROPIC_BASE_URL=https://x/anthropic\n"
        "ANTHROPIC_AUTH_TOKEN=tok\n"
        "ANTHROPIC_MODEL=m\n"
        "\n",
        encoding="utf-8",
    )
    env = session.load_env(dotenv=f)
    assert env["ANTHROPIC_BASE_URL"] == "https://x/anthropic"
    assert env["ANTHROPIC_MODEL"] == "m"


def test_load_env_missing_file_raises(tmp_path):
    with pytest.raises(session.SetupError):
        session.load_env(dotenv=tmp_path / "nope.env")


def test_load_env_missing_required_key_raises(tmp_path):
    f = tmp_path / ".env"
    f.write_text("ANTHROPIC_BASE_URL=https://x\n", encoding="utf-8")
    with pytest.raises(session.SetupError):
        session.load_env(dotenv=f)


def test_repo_is_parent_of_evals():
    assert session.EVALS.name == "evals"
    assert session.REPO == session.EVALS.parent
```

- [ ] **Step 6: Run the affected tests to verify they pass**

Run:

```bash
uv run --project evals -m pytest tests/test_providers.py tests/test_session.py -q
```

Expected: all passed (Task 2 chat tests + new coach test + 4 session tests).

- [ ] **Step 7: Commit**

```bash
git add evals/providers.py evals/session.py tests/test_providers.py tests/test_session.py
git commit -m "$(cat <<'EOF'
feat(evals): CoachSession port + AgentSDKCoach; session.py bootstrap-only

AgentSDKCoach runs the real teach-me skill via claude-agent-sdk (local plugin,
DeepSeek via ClaudeAgentOptions.env); sync run() hides asyncio. session.py is
reduced to load_env/REPO/EVALS and now reads evals/.env. Coach tested with a
fake SDK client (no network). Deletes the subprocess/--resume path.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: run_evals.py — DI wiring + `--judge-backend`

**Files:**
- Modify: `evals/run_evals.py` (rewrite orchestration)
- Test: `tests/test_run_evals.py` (rewrite)

**Interfaces:**
- Consumes: `session.load_env`/`SetupError`, `providers.make_coach`/`make_chat`, `judge.judge`, `asserts.REGISTRY`.
- Produces (reused by tests, kept from prior implementation): `run_asserts`, `aggregate`, `effective_threshold`, `_excerpt`, `_judge_input`, `load_scenarios`; plus `run_scenario(scenario, *, coach, judge_chat, samples_override, judge_on)`.

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_run_evals.py` entirely with:

```python
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
import run_evals  # noqa: E402
from asserts import REGISTRY  # noqa: E402


def test_run_asserts_bare_and_parameterized():
    turns = ["intro", "final answer."]
    specs = ["last_coach_turn_has_no_question", {"transcript_matches": "final"}]
    results = run_evals.run_asserts(turns, specs)
    assert results == [("last_coach_turn_has_no_question", True),
                       ("transcript_matches", True)]


def test_aggregate_majority():
    assert run_evals.aggregate([True, True, False], 2) is True
    assert run_evals.aggregate([True, False, False], 2) is False


def test_effective_threshold_caps_at_samples():
    assert run_evals.effective_threshold(2, 1) == 1
    assert run_evals.effective_threshold(2, 3) == 2


def test_excerpt_preserves_both_ends_when_long():
    ex = run_evals._excerpt(["A" * 6000, "Z" * 6000], limit=1000)
    assert ex.startswith("A") and ex.endswith("Z") and "trimmed" in ex


def test_judge_input_includes_user_turns():
    framed = run_evals._judge_input(["/teach-me x", "我懂了"],
                                    ["Let me ask...", "Now apply it."])
    assert "我懂了" in framed and "/teach-me x" in framed and "Now apply it." in framed
    assert framed.index("我懂了") < framed.index("Now apply it.")


class _FakeCoach:
    def __init__(self, turns): self._turns = turns
    def run(self, turns): return list(self._turns)


class _FakeChat:
    def __init__(self, reply): self._reply = reply
    def complete(self, *, system, user, max_tokens, temperature): return self._reply


def test_run_scenario_injects_coach_and_judge():
    scenario = {"id": "x", "turns": ["/teach-me x"], "asserts": [],
                "judge": {"rubric": "must ask a question"}, "samples": 1}
    coach = _FakeCoach(["preamble", "a question?"])
    chat = _FakeChat('{"pass": true, "evidence": "?", "reasoning": "ok"}')
    r = run_evals.run_scenario(scenario, coach=coach, judge_chat=chat,
                               samples_override=1, judge_on=True)
    assert r["passed"] is True and r["n_pass"] == 1


def test_run_scenario_no_judge_skips_chat():
    scenario = {"id": "x", "turns": ["/teach-me x"], "asserts": [], "samples": 1}
    coach = _FakeCoach(["preamble", "final."])
    r = run_evals.run_scenario(scenario, coach=coach, judge_chat=None,
                               samples_override=1, judge_on=False)
    assert r["passed"] is True


def test_all_shipped_scenarios_load_and_reference_known_asserts():
    scenarios_dir = Path(__file__).resolve().parent.parent / "evals" / "scenarios"
    scenarios = run_evals.load_scenarios(scenarios_dir)
    assert len(scenarios) == 6
    ids = {s["id"] for s in scenarios}
    assert ids == {"f1-no-dump", "m1-socratic-first", "m10-unknown-flag",
                   "f3-mastery-gate", "m5-just-tell-me", "f5-fatigue-terminal"}
    for s in scenarios:
        assert s["turns"] and isinstance(s["turns"], list)
        assert s.get("judge", {}).get("rubric")
        for spec in s.get("asserts") or []:
            name = spec if isinstance(spec, str) else next(iter(spec))
            assert name in REGISTRY, f"{s['id']} references unknown assert {name}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project evals -m pytest tests/test_run_evals.py -q
```

Expected: FAIL — `run_scenario` has the old signature (`env`, no injected `coach`/`judge_chat`) and imports the old session/judge APIs.

- [ ] **Step 3: Rewrite run_evals.py**

Replace `evals/run_evals.py` entirely with:

```python
#!/usr/bin/env python3
"""Run teach-me behavioral evals: real teach-me sessions scored by asserts + judge.

Deliberate, paid, non-CI. Coach runs via the Claude Agent SDK; judge runs via
the Anthropic or OpenAI SDK. Both reach DeepSeek through evals/.env.

Usage (from repo root):
    uv run --project evals evals/run_evals.py
    uv run --project evals evals/run_evals.py --scenario m1-socratic-first
    uv run --project evals evals/run_evals.py --judge-backend openai
    uv run --project evals evals/run_evals.py --samples 1 --no-judge   # cheap smoke
    uv run --project evals evals/run_evals.py --verbose
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from session import load_env, SetupError
from providers import make_coach, make_chat
from asserts import REGISTRY
from judge import judge as run_judge

EVALS_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = EVALS_DIR / "scenarios"


def load_scenarios(directory: Path) -> list[dict]:
    return [yaml.safe_load(p.read_text(encoding="utf-8"))
            for p in sorted(directory.glob("*.yaml"))]


def run_asserts(turns, assert_specs) -> list[tuple[str, bool]]:
    results = []
    for spec in assert_specs or []:
        if isinstance(spec, str):
            name, arg = spec, None
        else:
            (name, arg), = spec.items()
        fn = REGISTRY[name]
        ok = fn(turns, arg) if arg is not None else fn(turns)
        results.append((name, bool(ok)))
    return results


def aggregate(sample_passes: list[bool], threshold: int) -> bool:
    return sum(sample_passes) >= threshold


def effective_threshold(pass_threshold: int, samples: int) -> int:
    """Cap the pass threshold at the sample count (2-of-1 can never pass)."""
    return min(pass_threshold, samples)


def _excerpt(turns: list[str], limit: int = 8000) -> str:
    joined = "\n\n---\n\n".join(turns)
    if len(joined) <= limit:
        return joined
    half = limit // 2
    return joined[:half] + "\n\n…[trimmed]…\n\n" + joined[-half:]


def _judge_input(user_turns: list[str], turns: list[str], limit: int = 8000) -> str:
    """Frame BOTH sides so learner-keyed rubrics can see the scripted messages."""
    convo = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(user_turns))
    return (f"LEARNER MESSAGES (scripted, in order):\n{convo}\n\n"
            f"COACH RESPONSE(S):\n{_excerpt(turns, limit)}")


def run_scenario(scenario: dict, *, coach, judge_chat, samples_override, judge_on) -> dict:
    samples = samples_override or scenario.get("samples", 3)
    threshold = effective_threshold(scenario.get("pass_threshold", 2), samples)
    per_sample = []
    for _ in range(samples):
        turns = coach.run(scenario["turns"])
        assert_results = run_asserts(turns, scenario.get("asserts"))
        asserts_ok = all(ok for _, ok in assert_results)
        verdict = {"pass": True, "evidence": "", "reasoning": "judge skipped"}
        if judge_on and judge_chat is not None and scenario.get("judge"):
            ji = _judge_input(scenario["turns"], turns)
            verdict = run_judge(judge_chat, scenario["judge"]["rubric"], ji)
        per_sample.append({"asserts": assert_results, "judge": verdict,
                           "ok": asserts_ok and verdict["pass"]})
    n_pass = sum(s["ok"] for s in per_sample)
    return {"id": scenario["id"], "n": samples, "n_pass": n_pass,
            "passed": aggregate([s["ok"] for s in per_sample], threshold),
            "samples": per_sample}


def _print_report(results: list[dict], verbose: bool) -> None:
    for r in results:
        flag = "PASS" if r["passed"] else "FAIL"
        print(f"[{flag}] {r['id']}  {r['n_pass']}/{r['n']}")
        for i, s in enumerate(r["samples"]):
            if s["ok"] and not verbose:
                continue
            fails = [n for n, ok in s["asserts"] if not ok]
            print(f"    sample {i}: asserts_failed={fails} "
                  f"judge={s['judge']['pass']} :: {s['judge']['reasoning']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--scenario", help="run only this scenario id")
    parser.add_argument("--samples", type=int, default=None)
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--judge-backend", choices=["anthropic", "openai"],
                        default="anthropic")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    try:
        env = load_env()
    except SetupError as err:
        print(f"SETUP FAIL - {err}")
        return 2

    scenarios = load_scenarios(SCENARIOS_DIR)
    if args.scenario:
        scenarios = [s for s in scenarios if s["id"] == args.scenario]
        if not scenarios:
            print(f"SETUP FAIL - no scenario id {args.scenario!r}")
            return 2

    try:
        coach = make_coach(env)
        judge_chat = None if args.no_judge else make_chat(args.judge_backend, env)
        results = [run_scenario(s, coach=coach, judge_chat=judge_chat,
                                samples_override=args.samples, judge_on=not args.no_judge)
                   for s in scenarios]
    except SetupError as err:
        print(f"SETUP FAIL - {err}")
        return 2

    _print_report(results, args.verbose)
    ok = all(r["passed"] for r in results)
    print("ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --project evals -m pytest tests/test_run_evals.py -q
```

Expected: all passed.

- [ ] **Step 5: Run the full pure suite**

Run:

```bash
uv run --project evals -m pytest -q tests/
```

Expected: all tests across `test_providers/session/transcript/judge/run_evals/asserts` PASS, offline.

- [ ] **Step 6: Commit**

```bash
git add evals/run_evals.py tests/test_run_evals.py
git commit -m "$(cat <<'EOF'
refactor(evals): orchestrator injects coach + judge, adds --judge-backend

run_scenario now takes an injected CoachSession and ChatModel; main() wires
real ones via make_coach/make_chat and selects the judge backend by flag.
Sample/threshold/excerpt/judge-input logic unchanged. Full pure suite green.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: README update

**Files:**
- Modify: `evals/README.md`

**Interfaces:**
- Consumes: the finished harness.
- Produces: accurate run docs. No code.

- [ ] **Step 1: Rewrite evals/README.md**

Replace `evals/README.md` entirely with:

```markdown
# teach-me behavioral evals

Deliberate, **paid**, non-CI behavioral tests for the teach-me skill. The coach
runs the real teach-me skill via the Claude Agent SDK; the judge scores each
sample via the Anthropic or OpenAI SDK. Both reach DeepSeek through `evals/.env`.

## Setup

```bash
cp evals/.env.example evals/.env    # then fill in your DeepSeek key/values
```

Requires the `claude` CLI on PATH (the Agent SDK spawns it). Never run under
Python 3.14 (alpha segfaults on C-extensions) — the uv project pins `>=3.11`.

## Run (from the repo root)

```bash
uv run --project evals evals/run_evals.py                       # all scenarios, 3 samples
uv run --project evals evals/run_evals.py --scenario m1-socratic-first
uv run --project evals evals/run_evals.py --judge-backend openai
uv run --project evals evals/run_evals.py --samples 1 --no-judge   # cheap smoke
uv run --project evals evals/run_evals.py --verbose
```

## Unit tests (offline, free)

```bash
uv run --project evals -m pytest -q tests/
```

The unit suite injects fakes for the coach and judge, so it never hits the
network or spends money. Only `run_evals.py` (above) makes real calls.

## Architecture

- `providers.py` — the only SDK seam: `ChatModel`/`CoachSession` ports,
  `AnthropicChat`/`OpenAIChat`/`AgentSDKCoach` adapters, `make_chat`/`make_coach`.
- `session.py` — `load_env` (overlays `evals/.env`), `REPO`, `EVALS`.
- `transcript.py` — `coach_turns` extracts assistant text from SDK messages.
- `judge.py` — `judge(chat, rubric, judge_input)` over a `ChatModel`.
- `asserts.py` — deterministic, position-robust transcript asserts.
- `run_evals.py` — orchestrator (DI, sampling, majority threshold, report).
- `scenarios/*.yaml` — the six behavioral scenarios.

## Adding a scenario

Add `scenarios/<id>.yaml` with `id`, `turns` (list of scripted user messages),
optional `asserts` (see `asserts.py` REGISTRY), a `judge.rubric`, and optional
`samples`/`pass_threshold`. The integrity test in `tests/test_run_evals.py`
checks that every scenario loads and references known asserts.
```

- [ ] **Step 2: Verify the pure suite is still green**

Run:

```bash
uv run --project evals -m pytest -q tests/
```

Expected: all passed (docs-only change).

- [ ] **Step 3: Commit**

```bash
git add evals/README.md
git commit -m "$(cat <<'EOF'
docs(evals): README for the SDK-driven, uv-project harness

Document setup (.env from example, claude CLI prereq), uv run commands, the
--judge-backend flag, the offline unit suite, and the provider-seam layout.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Live acceptance (paid, manual — gated on explicit go-ahead)

**Files:**
- None expected (this is verification). If a live check reveals a needed tweak
  (e.g. the OpenAI-endpoint model name), fix it in the relevant module + test
  and commit under that module's message.

**Interfaces:**
- Consumes: the whole harness + a filled-in `evals/.env`.

> **⚠️ This task spends DeepSeek credits. Do NOT run any step here without an explicit human go-ahead each time.** Steps 2–4 make paid calls.

- [ ] **Step 1: Resolve the four "verify-live" open items (from the spec)**

Confirm before spending broadly:
1. `/teach-me` triggers through the Agent SDK with `setting_sources=["project"]` +
   local plugin.
2. The Anthropic SDK's default headers are accepted by the DeepSeek Anthropic
   endpoint (judge returns parseable JSON).
3. The correct DeepSeek **OpenAI-endpoint model name** (default `deepseek-chat`;
   override via `OPENAI_MODEL` in `evals/.env` if different — do not hard-code a
   guess).
4. The `claude` CLI is on PATH.

- [ ] **Step 2: Cheapest smoke — one scenario, one sample, no judge**

Run:

```bash
uv run --project evals evals/run_evals.py --scenario m1-socratic-first --samples 1 --no-judge --verbose
```

Expected: a coach transcript is produced (asserts may pass or fail — the point
is that the Agent SDK path works and `/teach-me` fired). If this errors on SDK
wiring, fix in `providers.py` before spending more.

- [ ] **Step 3: Add the judge — one scenario, one sample, each backend**

Run:

```bash
uv run --project evals evals/run_evals.py --scenario m1-socratic-first --samples 1 --judge-backend anthropic --verbose
uv run --project evals evals/run_evals.py --scenario m1-socratic-first --samples 1 --judge-backend openai --verbose
```

Expected: a non-empty judge verdict (`judge=True/False` with a reasoning line),
not `unparseable`/empty, on **both** backends. If the OpenAI backend errors on
the model name, set `OPENAI_MODEL` in `evals/.env` and re-run.

- [ ] **Step 4: Full acceptance (only after Steps 2–3 are clean)**

Run:

```bash
uv run --project evals evals/run_evals.py --verbose
```

Triage the board: separate genuine teach-me misbehavior from harness artifacts.
**Do not weaken an assert or rubric to make a real teach-me miss go green** —
investigate real misses. If any change is needed, make it in the offending
module + its test and commit.

---

## Self-Review

**Spec coverage:**
- uv project + python floor → Task 1. ✓
- `.env` under `evals/` + `.env.example` + gitignore exception → Task 1. ✓
- `ChatModel` port + Anthropic/OpenAI adapters + `make_chat` → Task 2. ✓
- Judge over `ChatModel` (parse_verdict + max_tokens=2048 + judge_input) → Task 3 (+ _judge_input in Task 6). ✓
- `coach_turns` from SDK messages → Task 4. ✓
- `CoachSession` + `AgentSDKCoach` (local plugin, env overlay, sync run) + `make_coach`; `session.py` bootstrap → Task 5. ✓
- DI wiring + `--judge-backend` + kept sampling/threshold/excerpt → Task 6. ✓
- README → Task 7. ✓
- Four "verify-live" open items + paid acceptance gating → Task 8. ✓
- `asserts.py` unchanged → not modified in any task. ✓
- Codex/Responses API excluded → never introduced. ✓

**Placeholder scan:** every code step contains complete code; no TBD/TODO/"similar to". ✓

**Type consistency:** `ChatModel.complete(*, system, user, max_tokens, temperature) -> str` is defined in Task 2 and consumed identically in Tasks 3 and 6. `CoachSession.run(turns) -> list[str]` defined in Task 5 and consumed in Task 6. `judge(chat, rubric, judge_input)` defined in Task 3, called in Task 6. `coach_turns(messages)` defined in Task 4, used in Task 5. `load_env`/`SetupError`/`REPO`/`EVALS` defined in Task 5, imported in Task 6 and by `make_coach`. `make_chat`/`make_coach` defined in Tasks 2/5, imported in Task 6. Consistent. ✓
