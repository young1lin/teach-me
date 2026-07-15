# teach-me Eval Harness — SDK Redesign

## Status

Revises the **transport layer** of `docs/superpowers/specs/2026-07-15-teach-me-eval-harness-design.md`.
The behavioral-eval *goals* are unchanged: six behavioral scenarios, hybrid scoring
(deterministic transcript asserts **and** an LLM judge, both must pass), N-sample
majority threshold, the coach and judge both driven by the DeepSeek endpoint from a
local `.env`, `uv` for reproducible runs, and **no CI** (runs cost money; self-tested
locally). This spec changes only **how the coach and judge talk to models**.

## Motivation

The first implementation had five structural gaps:

1. The coach shelled out to the `claude -p` CLI via `subprocess` and reconstructed
   turns by parsing JSONL transcript files — fragile, and not the supported
   programmatic entry point.
2. The judge issued raw `urllib` HTTP calls instead of an official SDK.
3. There was no provider abstraction; backend compatibility was ad hoc.
4. There was no dependency injection, so unit tests could not exercise the harness
   without hitting the network.
5. `.env` sat at the repository root with no committed `.env.example` to document
   the required variables.

## Goals

- Drive the real `teach-me` skill through the **Claude Agent SDK** (`claude-agent-sdk`)
  as a locally-loaded plugin — the supported programmatic path, Skills-aware.
- Replace the raw-HTTP judge with the **official Anthropic and OpenAI SDKs**, both
  pointed at DeepSeek, selectable at runtime.
- Introduce a thin, self-built **provider glue layer** (a small compatibility seam,
  LangChain-like in spirit but ~1 file, no external framework dependency).
- Make every collaborator **injectable** so the pure unit-test suite runs offline at
  zero cost, and the paid live acceptance run uses the real SDK clients.
- Turn `evals/` into a self-contained **uv project** with a committed lockfile; move
  `.env` under `evals/` and add a committed `.env.example`.

## Non-goals

- No change to the six scenarios, the assert semantics, the majority-threshold logic,
  or the hybrid (asserts + judge) scoring model.
- No CI. Runs are deliberate and paid; the developer self-tests locally.
- **Codex / OpenAI Responses API is out of scope** — DeepSeek does not support it.
  Only the Claude Agent SDK (coach) and the OpenAI chat-completions + Anthropic
  messages APIs (judge) are exercised.

## Architecture

### Provider glue layer — `evals/providers.py` (the single SDK seam)

Two provider-agnostic ports, each with concrete adapters and a factory. This is the
only module that imports an LLM SDK; everything else is provider-agnostic.

```python
class ChatModel(Protocol):                       # single-shot chat — the judge sits here
    def complete(self, *, system: str, user: str,
                 max_tokens: int, temperature: float) -> str: ...

class AnthropicChat:   # wraps anthropic.Anthropic → DeepSeek Anthropic endpoint
    ...                #   (ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN + ANTHROPIC_MODEL)
class OpenAIChat:      # wraps openai.OpenAI → DeepSeek chat-completions endpoint
    ...                #   (base_url + DEEPSEEK_API_KEY)
def make_chat(backend: str, env: dict) -> ChatModel: ...   # backend ∈ {"anthropic","openai"}

class CoachSession(Protocol):                    # agentic skill run — the coach sits here
    def run(self, turns: list[str]) -> list[str]: ...   # returns coach text turns, in order

class AgentSDKCoach:   # wraps claude-agent-sdk ClaudeSDKClient (multi-turn, Skills-aware)
    ...
def make_coach(env: dict) -> CoachSession: ...
```

The two ports are deliberately separate: a judge call is one chat completion; a coach
run is an agentic session that loads and runs a Skill. LangChain would abstract the
first but not the second, which is one reason the framework is not adopted.

### Coach — `AgentSDKCoach` over `claude-agent-sdk`

- Uses `ClaudeSDKClient` for genuine multi-turn with retained context (replaces the
  previous `--resume` subprocess plumbing).
- `ClaudeAgentOptions` configuration:
  - `env=<.env overlay>` — the SDK forwards this to the Claude Code CLI subprocess,
    which is how requests route to DeepSeek (the SDK does not read
    `ANTHROPIC_BASE_URL` itself).
  - `cwd=<repo root>`, `plugins=[{"type": "local", "path": <repo root>}]`,
    `setting_sources=["project"]` — loads this repository's `teach-me` skill.
  - `permission_mode="bypassPermissions"` — headless, no interactive prompts.
- `run(turns)` is **synchronous**; the adapter hides the SDK's async API behind
  `asyncio.run(...)` internally, so the orchestrator stays synchronous.
- Each scripted turn is sent with `client.query(turn)`; assistant text is collected
  from the streamed `AssistantMessage`/`TextBlock` objects. The teach-me preamble turn
  is still emitted first, so asserts remain position-robust (unchanged).

### `transcript.py` — SDK-message → turns adapter

`coach_turns(messages) -> list[str]` extracts assistant `TextBlock` text from the
SDK's structured messages (replacing JSONL parsing), skipping thinking/tool-only
blocks. Output contract is unchanged (`list[str]`), so `asserts.py` is untouched and
the function is unit-testable with lightweight fake message objects.

### Judge — `judge.py`, provider-agnostic logic over `ChatModel`

- `parse_verdict(text) -> dict` — robust JSON extraction; unparseable ⇒ flagged
  failure (carried forward unchanged).
- `judge(chat: ChatModel, rubric: str, judge_input: str) -> dict` — pure logic:
  build the grading prompt, call `chat.complete(system=SYSTEM, user=..., max_tokens=2048,
  temperature=0)`, return `parse_verdict(...)`.
- The two prior fixes are carried forward: `max_tokens=2048` (DeepSeek spends budget on
  reasoning and truncated smaller verdicts) and a judge input that includes the scripted
  learner turns ahead of the coach response (`_judge_input`).

### Dependency injection

- `run_scenario(scenario, *, coach: CoachSession, judge_chat: ChatModel | None, ...)`
  receives its collaborators; the orchestrator builds real ones via `make_coach` /
  `make_chat`, and unit tests inject fakes that return canned turns / verdicts with no
  network and no cost.

### `run_evals.py` — orchestrator

- Synchronous. Scenarios run **sequentially** (paid; avoids DeepSeek rate-limit races).
- Wiring: `load_env` → `make_coach(env)` → per scenario: `coach.run(turns)` →
  `coach_turns` → `run_asserts` → (if judging) `make_chat(backend, env)` +
  `judge(chat, rubric, _judge_input(...))` → `aggregate` / `effective_threshold`.
- CLI: existing `--scenario / --samples / --no-judge / --verbose` plus a new
  `--judge-backend {anthropic,openai}` (default `anthropic`).
- `run_asserts`, `aggregate`, `effective_threshold`, `_excerpt`, `_judge_input` are
  reused unchanged (already covered by tests).

### uv project + `.env` layout

- `evals/pyproject.toml`: `requires-python = ">=3.11"` (avoids the 3.14-alpha segfault);
  dependencies `claude-agent-sdk`, `anthropic`, `openai`, `pyyaml`; dev group `pytest`.
- `evals/uv.lock` committed.
- `.env` moves to `evals/.env` (still gitignored).
- `evals/.env.example` committed with **placeholder** values only, documenting:
  `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_MODEL`,
  `ANTHROPIC_SMALL_FAST_MODEL`, `API_TIMEOUT_MS`,
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, `DEEPSEEK_API_KEY`.
- `.gitignore`: add `!.env.example` so the example is not swallowed by `.env.*`.
- Run command: `uv run --project evals evals/run_evals.py [...]`.

## File changes

| File | Change |
|------|--------|
| `evals/providers.py` | **new** — glue seam: both ports, adapters, `make_chat` / `make_coach` |
| `evals/session.py` | **rewrite** — keep `load_env` / `SetupError` / `REPO`; delete subprocess/`--resume`/`transcript_path`/`build_claude_cmd` |
| `evals/transcript.py` | **rewrite** — SDK-message extraction instead of JSONL parsing |
| `evals/judge.py` | **rewrite** — `parse_verdict` + `judge(chat, ...)`; SDK clients move to `providers.py` |
| `evals/run_evals.py` | **rewrite** — DI wiring + `--judge-backend` |
| `evals/asserts.py` | **unchanged** (operates on `list[str]`) |
| `evals/scenarios/*.yaml` | unchanged (optional per-scenario `judge.backend` default) |
| `evals/pyproject.toml`, `evals/uv.lock`, `evals/.env.example` | **new** |
| `.env` → `evals/.env` | **move** (gitignored) |
| `.gitignore` | add `!.env.example` exception |
| `evals/README.md` | update: uv-project run, `.env` location, SDK backends |
| `tests/test_providers.py` | **new** — adapters/factories with fakes, no network |
| `tests/test_session.py` | update — `load_env` only |
| `tests/test_transcript.py` | update — fake SDK messages |
| `tests/test_run_evals.py` | update — inject fake coach + fake judge |
| `tests/test_asserts.py` | unchanged |

## Testing strategy

- **Pure unit suite (CI-safe, offline, free):** `parse_verdict`, `judge` over a fake
  `ChatModel`, `coach_turns` over fake SDK messages, `run_asserts`, `aggregate`,
  `effective_threshold`, `_excerpt`, `_judge_input`, scenario-integrity, and the
  provider adapters exercised with fake underlying clients (assert request shaping,
  not live responses). Run via `uv run --project evals -m pytest`.
- **Live acceptance (paid, manual):** the full six-scenario × N-sample run against
  DeepSeek, invoked explicitly by the developer.

## Open items to verify during implementation (do not assume)

1. `/teach-me` slash-command triggers correctly through the Agent SDK when the repo is
   loaded as a local plugin with `setting_sources=["project"]`.
2. The Anthropic SDK's default headers (`anthropic-version`, auth) are accepted by the
   DeepSeek Anthropic-compatible endpoint.
3. The correct DeepSeek **model name for the OpenAI chat-completions endpoint** (likely
   differs from the Anthropic-endpoint alias).
4. The `claude` CLI is a prerequisite the Agent SDK spawns (already present in this
   environment).

Each is a first-step live check in the implementation plan, not an assumed fact.

## Security / policy

- No secrets in tracked files. The DeepSeek key lives only in `evals/.env` (gitignored).
- `evals/.env.example` contains placeholder values only.
- No personal information (usernames, emails, home paths) in tracked file contents.
