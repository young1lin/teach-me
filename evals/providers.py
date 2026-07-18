"""The single SDK seam for the eval harness.

Everything that touches an LLM SDK lives here behind two provider-agnostic
ports: ChatModel (judge) and CoachSession (coach). The rest of the harness is
provider-neutral and injected with fakes in tests.
"""
from __future__ import annotations

from typing import Protocol

# One SetupError, defined in session.py. run_evals.py catches session.SetupError,
# so make_chat below must raise that same class — not a second look-alike — for
# the "SETUP FAIL" exit-2 path to work. Re-exported here for callers/tests that
# reference providers.SetupError.
from session import SetupError  # noqa: E402,F401


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


from transcript import coach_turns  # noqa: E402


class CoachSession(Protocol):
    """An agentic skill run over scripted turns. The coach sits on this."""

    def run(self, turns: list[str], env_extra: dict | None = None) -> list[str]: ...


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

    def _default_client(self, env: dict):
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
        options = ClaudeAgentOptions(
            env=env,                       # forwarded to the CLI → routes to DeepSeek
            cwd=self._repo,
            plugins=[{"type": "local", "path": self._repo}],
            setting_sources=["project"],   # load this repo's teach-me skill
            permission_mode="bypassPermissions",
        )
        return ClaudeSDKClient(options=options)

    def run(self, turns: list[str], env_extra: dict | None = None) -> list[str]:
        import asyncio
        return asyncio.run(self._run_async(turns, env_extra or {}))

    async def _run_async(self, turns: list[str], env_extra: dict) -> list[str]:
        messages = []
        client = self._client_factory({**self._env, **env_extra})
        async with client:
            for turn in turns:
                await client.query(turn)
                async for msg in client.receive_response():
                    messages.append(msg)
        return coach_turns(messages)


def make_coach(env: dict) -> CoachSession:
    from session import REPO
    return AgentSDKCoach(env=env, repo=REPO)
