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

Exit 0 = all pass, 1 = a failure, 2 = a setup problem.

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
`samples`/`pass_threshold`. A scenario passes a sample when every assert passes
AND the judge passes; it passes overall when `>= pass_threshold` of `samples`
pass (default 3/2). Assertions are position-robust: teach-me emits a preamble
turn first, so never key off `turns[0]`. The integrity test in
`tests/test_run_evals.py` checks that every scenario loads and references known
asserts.
