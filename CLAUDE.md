# teach-me

This repository packages the **teach-me** learning-coach skill for multiple coding
agents: Claude Code, Codex, Cursor, Kimi, OpenCode, Pi, Antigravity, and any
`.agents/`-compatible tool (via `npx skills add`).

## Important — explicit invocation only

teach-me is **never** auto-invoked. It activates only when the user explicitly runs:

- `/teach-me` on Claude Code, Cursor, Antigravity
- `$teach-me` on Codex, OpenCode

Do not start a lesson because a request *sounds* like it could be taught — only an
explicit token triggers it. Full trigger rules live in `skills/teach-me/SKILL.md`.

## Layout

- `skills/teach-me/` — the skill (`SKILL.md` + `references/` + `agents/` + `scripts/`).
- `.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`, `.kimi-plugin/`, `.agents/`,
  `.opencode/` — per-agent install manifests.
- `package.json` — version + Pi skill discovery (`pi.skills`).
- `tests/teach-me-scenarios.md` — behavior scenarios.
- `evals/` — paid, local behavioral eval harness (uv project). Full docs: `evals/README.md`.

## Releasing & versioning

**All release process lives in [`.claude/harness/VERSION.md`](.claude/harness/VERSION.md).**
For anything about cutting a release — SemVer policy, the version bump
(`scripts/bump-version.py`, six manifests kept in lockstep), the CRLF gotcha,
changelogs (EN + zh-CN), the pre-tag gates, tagging, and the automated GitHub
release workflow — follow that file. Do not re-derive the steps here.

## Evals (paid, local — never CI)

Behavioral tests that drive the **real** teach-me skill via the Claude Agent SDK and
grade it with an LLM judge. They spend real model tokens and are run by hand — never
in CI. Full docs live in `evals/README.md`; this is the operating summary.

**Prerequisites:** `uv`, the `claude` CLI on PATH (the Agent SDK spawns it), and
`evals/.env` (copy `evals/.env.example`, fill in the DeepSeek key/values). `evals/.env`
is gitignored — never commit it, and never put its secrets in any tracked file.

**Run from the repo root:**

```bash
uv run --project evals evals/run_evals.py                         # all scenarios, 3 samples, anthropic judge
uv run --project evals evals/run_evals.py --scenario m1-socratic-first
uv run --project evals evals/run_evals.py --samples 1 --no-judge  # smoke: asserts only, no judge calls
uv run --project evals evals/run_evals.py --judge-backend openai  # judge via the OpenAI SDK instead
uv run --project evals evals/run_evals.py --verbose               # per-sample assert/judge detail
```

Exit code: `0` all pass · `1` a behavioral failure · `2` a setup problem.

**Offline unit suite (no network, no cost):**

```bash
uv run --project evals python -m pytest -q tests/
```

The unit suite injects fakes for the coach and judge, so it never spends money; only
`run_evals.py` makes real calls.

**Rules when running evals:**
- **Never weaken an assert or rubric to turn a real teach-me miss green.** The rubrics
  mirror teach-me's own Red Flags (SKILL.md) — investigate a genuine miss instead.
- A live run costs real tokens; pause and get an explicit go-ahead before each paid run.

**Status (last live run, 2026-07-15 — treat "green" as provisional):** coach *and*
judge both ran on `deepseek-v4-flash[1m]` (a flash-tier model, via `evals/.env`) — not
yet on Claude, the primary target. 4/6 scenarios passed; `f1-no-dump` and
`m1-socratic-first` are genuine misses on that model. Trigger-discipline (never
auto-invoke) and F6 expert-isolation are **not yet automated**, so the current suite
does not cover teach-me's most safety-critical behavior.
