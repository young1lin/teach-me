# teach-me eval harness — design

**Date:** 2026-07-15
**Status:** Approved (brainstorming complete; ready for writing-plans)

## 1. Motivation

teach-me already ships two halves of an evaluation system that never got joined:

- `tests/teach-me-scenarios.md` — a rich catalog of ~40 behavioral scenarios (trigger
  discipline, teaching-failure baselines F1–F7, modes M1–M12, storage, retrieval). But the
  RED/GREEN evidence in it was gathered **by hand, once** ("all 50 completed outputs were
  read manually"; "five parallel read-only agents ... judged"). It is documentation of a
  one-time validation, not a repeatable regression harness.
- `tests/skill_live_check.py` — an executable harness that drives the real Claude Code CLI
  (`claude -p`), loads the DeepSeek endpoint from `.env`, and inspects the on-disk session
  transcript. But it only covers **two trigger checks** (T1 explicit-invoke loads the skill,
  T2 no auto-invoke). It tests nothing about *teaching behavior*.

The gap: teach-me's design decisions (socratic as the no-flag default, the "just tell me"
and base-missing escape hatches, the E1/E2/E3 mastery gate, the fatigue-terminal rule) are
currently defended by **judgment**, not measurement. The recent slimming refactor (cutting
Leitner/Anki/challenge, making socratic default) was the right call but was made without a
way to prove it did not regress a guardrail.

The Superpowers project (obra/superpowers) treats this exact capability — `evals/`, real
sessions judged by an LLM ("drill") — as its engine of improvement. Its biggest wins (v5.0.6
removing a subagent review loop that evals proved useless; v6.0.0's ~50% token reduction)
came from **measuring, then cutting**. teach-me needs the same feedback loop.

This spec designs a **thin-slice** eval harness: turn the 6 highest-value teaching-behavior
scenarios into repeatable, automated pass/fail evals, proving the mechanism end-to-end before
expanding.

## 2. Goals and non-goals

### Goals

- Run the 6 chosen scenarios against a **real** `claude -p` session using the DeepSeek
  endpoint from `.env`, and produce a per-scenario PASS/FAIL verdict with evidence.
- Score each scenario with a **hybrid** verdict: deterministic transcript **assertions**
  (free, repeatable) AND a **DeepSeek LLM judge** for the fuzzy residue. Both must pass.
- Smooth model nondeterminism with **N samples + a pass threshold**.
- Run entirely via **`uv`** with PEP 723 inline metadata, so version drift cannot cause
  spurious failures.
- Keep the deterministic core (transcript parsing, assertion library) as **pure functions
  with pytest unit tests** that are safe to run in CI (no API cost).

### Non-goals (YAGNI — explicitly out of scope for v1)

- Porting all ~40 scenarios. Storage/paths/consent scenarios (S1–S9, G-platform) stay as
  today: the manual catalog plus `tests/test_archive.py` unit tests. They are better served
  by offline unit tests than by paid live sessions.
- **No CI integration.** Every live run costs money and is nondeterministic. The harness is
  run **deliberately** — the user self-tests locally before committing. There is no
  pre-commit hook that runs the paid evals.
- No HTML report, no historical trend tracking, no multi-model comparison, no parallel
  execution, no flaky-quarantine beyond the N-sample threshold.

## 3. Architecture

```
evals/
├── README.md            # how to run, cost note, how to add a scenario, .env requirement
├── run_evals.py         # CLI orchestrator: load .env → per scenario × N samples →
│                        #   drive session → asserts + judge → aggregate → report → exit code
├── session.py           # drive claude -p (1–2 turns via --resume); return transcript text
├── transcript.py        # parse a transcript JSONL → ordered list of coach (assistant) turns
├── asserts.py           # deterministic assertion library (pure: turns → bool)
├── judge.py             # DeepSeek judge via .env; rubric + excerpt → {pass, evidence, reasoning}
└── scenarios/
    ├── f1-no-dump.yaml
    ├── m1-socratic-first.yaml
    ├── m10-unknown-flag.yaml
    ├── f3-mastery-gate.yaml
    ├── m5-just-tell-me.yaml
    └── f5-fatigue-terminal.yaml

tests/
├── test_transcript.py   # NEW: unit-test transcript parsing (CI-safe, offline)
└── test_asserts.py      # NEW: unit-test the assertion library (CI-safe, offline)
```

**Boundary rationale.** `transcript.py` and `asserts.py` are pure (input → bool/list, no I/O)
so they are unit-testable offline and safe in CI. `session.py` and `judge.py` are the only
components that touch the network / subprocess; they are exercised by running the harness
itself, not by CI. This mirrors Superpowers' split: `tests/` = code tests (CI), `evals/` =
behavior tests (deliberate, paid).

### 3.1 `session.py` — session driver

Responsibility: run a scripted 1–2 turn `claude -p` conversation and return the final
transcript text.

- Reuses the proven pieces of `skill_live_check.py`: `load_env()` (reads `.env` into the
  subprocess environment), `transcript_path(session_id)` (munges the repo path to locate
  `~/.claude/projects/<munged>/<session_id>.jsonl`), and the `claude -p --output-format
  stream-json --verbose` invocation that yields the `session_id`.
- Multi-turn: capture `session_id` from the first turn's stream-json, then send subsequent
  turns with `claude -p --resume <session_id> "<next prompt>"`. The transcript file
  accumulates all turns. A single-turn scenario is just a one-element `turns` list.
- Interface: `run_session(turns: list[str], env: dict) -> str` (returns transcript text).
- Setup problems (missing `.env`, `claude` not on PATH, no `session_id`, transcript file not
  found) raise a `SetupError` that the runner surfaces as exit code 2 — same contract as
  `skill_live_check.py`.

### 3.2 `transcript.py` — transcript parser

Responsibility: turn a transcript JSONL into an ordered list of coach (assistant) text turns.

- Interface: `coach_turns(transcript_text: str) -> list[str]` — one entry per assistant
  message, in order, concatenating its text blocks.
- Pure, no I/O. Unit-tested with fixture transcripts in `tests/test_transcript.py`.

### 3.3 `asserts.py` — deterministic assertion library

Responsibility: crisp, free, repeatable checks on the coach turns. These catch the sharp
failures deterministically; the judge carries the fuzzy verdict.

Assertion functions (each `list[str] -> bool`, plus parameterized variants):

- `last_coach_turn_has_no_question(turns)` — the final coach turn does not end with a
  question and contains no "再来一道 / one more / 下一题" trailing-prompt pattern. (F5, M5)
- `first_coach_turn_is_question(turns)` — the first substantive coach turn contains a
  question mark (`?` or `？`). (M1)
- `transcript_matches(turns, pattern)` — any coach turn matches the regex. (M10 mode list,
  F5 checkpoint marker)
- `transcript_not_matches(turns, pattern)` — no coach turn matches the regex. (F3 mastery
  claim: `掌握|mastered|已经会了|你已经`)
- `first_turn_heading_count_below(turns, n)` — the first coach turn has fewer than `n`
  markdown headings (a crude "not an encyclopedia dump" signal for F1; the judge makes the
  real call).

The scenario YAML references assertions by name; `run_evals.py` holds a `name -> callable`
registry. Adding a novel assertion = add one pure function + one registry entry + a unit test.

### 3.4 `judge.py` — DeepSeek LLM judge

Responsibility: judge the fuzzy part of a scenario the assertions cannot capture.

- Endpoint: direct POST to `${ANTHROPIC_BASE_URL}/v1/messages` using the same DeepSeek
  wiring the coach session uses — `${ANTHROPIC_AUTH_TOKEN}` for auth, model
  `${ANTHROPIC_MODEL}`. One auth path, no new config, reuses `load_env()`. Implemented with
  stdlib `urllib.request` (no third-party HTTP dependency).
- Prompt: a strict grader system message + the rubric + the relevant coach turn(s). The model
  must return JSON: `{"pass": <bool>, "evidence": "<quote>", "reasoning": "<one line>"}`,
  temperature 0.
- Parsing: extract and parse the JSON. **A response that cannot be parsed is recorded as a
  sample failure and flagged — never silently treated as pass.** This closes the false-pass
  hole of a pure-LLM verdict.
- Interface: `judge(rubric: str, excerpt: str, env: dict) -> Verdict` where
  `Verdict = {pass: bool, evidence: str, reasoning: str}`.
- Fallback (implementation-time): if the Anthropic-compatible proxy's auth header proves
  incompatible, fall back to DeepSeek's native OpenAI-style endpoint using
  `${DEEPSEEK_API_KEY}`. The exact working header is confirmed with one smoke call during
  implementation (see §9).

### 3.5 `run_evals.py` — orchestrator / CLI

- Loads `.env`; for each scenario YAML, for each of N samples: `run_session(turns)` →
  `coach_turns()` → run each named assertion → call `judge()` → `sample_pass = (all asserts
  pass) AND judge.pass`.
- Scenario PASS when `count(sample_pass) >= pass_threshold`.
- Report: per scenario `PASS 3/3` / `FAIL 1/3`, and for each failing sample, which assertion
  failed and the judge's `evidence` + `reasoning`. Exit 0 if every scenario passes, else 1;
  exit 2 on setup problems.
- CLI flags: `--scenario <id>` (run one), `--samples N` (override per-scenario default),
  `--no-judge` (assertions only — offline, free smoke test), `--verbose` (dump transcripts),
  `--json` (machine-readable output).

## 4. Scenario schema (YAML)

```yaml
id: f5-fatigue-terminal
source: teach-me-scenarios.md#F5
description: fatigue signal mid-test → stop, checkpoint, terminal (no trailing question)
setup:
  platform: claude-code
turns:
  - "/teach-me --drill 条件概率"     # drill mode reaches a "testing" state quickly & reliably
  - "太累了"
asserts:
  - last_coach_turn_has_no_question
  - { transcript_matches: "checkpoint|检查点|小结" }
judge:
  rubric: |
    The final coach turn must: (1) stop testing immediately,
    (2) give a light checkpoint in the same turn,
    (3) end declaratively — no question, no choice, no "one more".
samples: 3
pass_threshold: 2
```

`asserts` entries are either a bare assertion name or a single-key map `{ name: arg }` for
parameterized assertions. `samples`/`pass_threshold` default to 3/2 if omitted. `pyyaml` is
declared and pinned in the PEP 723 metadata of `run_evals.py`.

## 5. The six v1 scenarios

| id | trigger (scripted user turns) | guardrail under test | turns |
|---|---|---|---|
| `f1-no-dump` | `/teach-me quantum mechanics（我完全零基础）` | first turn diagnoses + takes one minimal step, not an encyclopedia curriculum + equation dump (RED F1 failure) | 1 |
| `m1-socratic-first` | `/teach-me --socratic recursion` | socratic first teaching turn opens with a probing question, not a lecture | 1 |
| `m10-unknown-flag` | `/teach-me --sacratic recursion` | reports the unknown flag, lists the three modes, asks — does not silently guess or fall back | 1 |
| `f3-mastery-gate` | `/teach-me Python generators` → `我懂了` | no mastery claim without evidence; elicits E2/E3 application/transfer instead | 2 |
| `m5-just-tell-me` | `/teach-me --socratic recursion` → `别问了，直接告诉我` | fatigue/escape rule outranks the mode: second turn gives a direct explanation, stops asking | 2 |
| `f5-fatigue-terminal` | `/teach-me --drill 条件概率` → `太累了` | stop testing + light checkpoint + declarative close, no trailing question | 2 |

Three single-turn scenarios (f1, m1, m10) prove the mechanism most reliably; three two-turn
scenarios (f3, m5, f5) unlock the highest-value guardrails (mastery gate, just-tell-me,
fatigue-terminal). f5 is scripted in `--drill` mode specifically so the "testing" state is
reliably reached before the fatigue signal.

## 6. Sampling and threshold

Teaching behavior is stochastic; a single sample is noisy (Superpowers' "micro-test"
wisdom). Default `samples: 3`, `pass_threshold: 2` (majority). Both configurable per scenario
and overridable with `--samples`. The report always shows per-sample verdicts so a 2/3 pass
is visibly distinguishable from a 3/3 pass.

## 7. uv and reproducibility

Every eval script carries PEP 723 inline metadata (`# /// script` … `requires-python`,
`dependencies`) and is run via `uv run --python 3.14 evals/run_evals.py`. This matches the
existing `tests/skill_live_check.py` pattern and the project's established `uv run
--python 3.14`. `uv` resolves a consistent, pinned environment per run, so a differing local
Python or library version can never produce a spurious eval failure. Third-party dependencies
are kept minimal: `pyyaml` only (the judge uses stdlib `urllib`; the session driver uses
stdlib `subprocess`/`json`).

## 8. Cost and CI posture

- **Not in CI.** Live runs cost money (real DeepSeek calls) and are nondeterministic. The
  files live under `evals/` and are **not** named `test_*.py`, so pytest never collects them
  — the same convention that keeps `skill_live_check.py` out of the unit suite. The user runs
  the harness deliberately and self-tests locally before committing. No paid pre-commit hook.
- Cost envelope: 6 scenarios × 3 samples = 18 coach sessions + ≤18 judge calls, plus one
  extra `claude -p` per additional turn in the three 2-turn scenarios — all on DeepSeek,
  small. `--samples 1` gives a fast, cheap smoke run; `--no-judge` runs the assertions with
  zero judge calls.
- The **pure** modules (`transcript.py`, `asserts.py`) DO get pytest unit tests that are free
  and CI-safe — only the live layer is excluded.

## 9. Implementation-time verifications (must be resolved by the first tasks)

1. **Headless multi-turn continuation.** `claude -p --resume <session_id> "<next>"` producing
   a transcript that contains both turns has not yet been verified on this machine. The
   **first implementation task is a walking skeleton** that confirms a 2-turn headless session
   works and yields a combined transcript, before any scenario is built. If `--resume` does
   not work headlessly, fall back to `-c/--continue` or restrict v1 to single-turn scenarios
   (dropping f3/m5/f5 to a later iteration) — decided against real output, not assumed.
2. **Judge auth header.** The exact working auth header for the DeepSeek Anthropic-compatible
   endpoint (`x-api-key` vs `Authorization: Bearer`, `anthropic-version`) is confirmed with a
   single smoke call, with the `DEEPSEEK_API_KEY` native OpenAI-style endpoint as the
   fallback.

## 10. Success criteria

- `uv run --python 3.14 evals/run_evals.py` runs all six scenarios against real DeepSeek,
  prints per-scenario PASS/FAIL with assertion + judge evidence, and exits 0/1 (2 on setup
  error).
- `--no-judge` and `--scenario <id>` and `--samples N` work as described.
- `tests/test_transcript.py` and `tests/test_asserts.py` pass under the existing pytest suite
  with no API calls.
- Adding a standard scenario is a single YAML drop (plus, at most, one new pure assertion +
  its unit test) — no orchestrator change.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Judge false pass/fail | Hybrid design: assertions catch crisp failures deterministically; judge returns a structured evidence quote for spot-check; `--verbose` dumps transcripts; unparseable judge output = flagged failure, never silent pass. |
| Multi-turn state fragility (f3/f5 may not reach the target state) | f5 scripted in `--drill` mode to reach "testing" fast; samples + threshold absorb variance; the walking-skeleton task (§9.1) de-risks the mechanism before scenarios are built. |
| DeepSeek judge auth header unknown | Resolved at build time with one smoke call (§9.2); native `DEEPSEEK_API_KEY` fallback. |
| Model nondeterminism → flaky verdicts | N=3 with threshold ≥2; harness is run deliberately, never gates CI. |
| Secret leakage | The `.env` (DeepSeek key) is already gitignored; the harness only reads env var *values* at runtime and never writes them to transcripts, reports, or committed files. |
