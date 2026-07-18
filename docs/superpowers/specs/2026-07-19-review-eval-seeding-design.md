# Review behavioral eval — store seeding — design

**Date:** 2026-07-19
**Status:** Approved (brainstorming complete; ready for writing-plans)

## 1. Motivation

The review & retention layer (shipped in 0.0.2) is covered only by the offline unit
suite for `store.py`. Its **conversational** behavior — what the coach does when a user
runs `/teach-me review` — has no behavioral coverage. The eval harness exists for exactly
this, but it cannot currently test the review flow, for one concrete reason:

**A review needs an already-due concept in the store, and the harness cannot produce one.**

- `/teach-me review` calls `store.py due`, which only surfaces concepts whose computed
  `due <= today`.
- The harness never sets `TEACH_ME_HOME` and has no seeding hook — `run_scenario` consumes
  only `turns`/`asserts`/`judge`; the `setup:` field in every scenario is unused. A review
  run would therefore scan the operator's real `~/.teach-me`, not an isolated fixture.
- A single session cannot create a due item either: a freshly-taught concept is written
  with `box=1, last_reviewed=today`, so it falls due **tomorrow**, not today.

This spec adds the missing capability: a small, offline-testable **store seeding** facility
that gives each review scenario an isolated `TEACH_ME_HOME` pre-loaded with a due concept,
plus the two review scenarios themselves.

## 2. Goals

- Let a scenario declare seed records via `setup.seed`; the harness materializes them into an
  isolated temp `TEACH_ME_HOME` before the turns run, and tears it down after.
- Re-seed fresh for **every sample** (review mutates the store: a pass promotes the box, a
  fail resets it — samples must not leak state into one another).
- Add two behavioral scenarios: `r1-review-recall` (pass path) and `r2-review-fail-relearn`
  (fail path), driven by the existing DeepSeek `.env` config.
- Keep the new seeding logic covered by the **offline** unit suite (no network, no cost).

## 3. Non-goals (YAGNI — explicitly out of scope)

- **No Claude targeting.** The coach and judge run on the existing DeepSeek `.env` config, as
  the rest of the suite does. Results carry the same "provisional on a flash model" caveat.
- **No changes to `store.py`.** `due`, `review`, and the schedule-less migration path already
  exist and are unit-tested; seeding rides on them, it does not reimplement them.
- **No general-purpose fixture framework.** Seeding writes only what the review flow needs
  (records with a self-test question). Checkpoints, archives, and multi-topic graphs are out.
- **No new assert primitives.** The scenarios reuse `transcript_matches`; the nuanced
  judgments live in the judge rubric.

## 4. Design decisions (approved during brainstorming)

1. **Coach/judge model:** existing DeepSeek `.env` — no Claude-target switch (dropped a whole
   blocker: no `.env.claude`, no auth change, no relaxing `load_env`).
2. **Seed a due item via the migration path:** the seed record is written in state
   `demonstrated` **without** `box`/`last_reviewed`/`review_count`. Per the existing rule "a
   schedule-less `demonstrated`/`retained` record is treated as due now," it is due the day it
   is seeded — no date arithmetic, and it exercises the migration write path realistically.
3. **Injection seam:** `AgentSDKCoach.run(turns, env_extra=None)` merges `{TEACH_ME_HOME: …}`
   into the SDK env for that run. Chosen over mutating a shared env dict (hidden) or rebuilding
   the coach per sample (wasteful); it is explicit and unit-testable with the fake client.
4. **Per-sample isolation:** `run_scenario` builds a fresh seeded home for each sample and
   removes it afterward.
5. **Coverage:** two scenarios — the pass path and the fail→relearn path. "Never auto-start"
   is acknowledged as the most safety-critical behavior but deferred to a future scenario.

## 5. Seed spec (scenario YAML)

`setup.seed` is a list of record descriptors. Minimal shape:

```yaml
setup:
  platform: claude-code
  seed:
    - topic: python-async
      concept: event-loop
      state: demonstrated          # schedule-less -> due now via migration
      review_question: "Without looking, explain what the event loop does when a coroutine hits await."
      # optional: extra body prose; deps: [...]; explicit box/last_reviewed to force a date
```

The seeder writes, under a fresh temp dir `H`:

- `H/config.json` = `{"root": "<H>"}` (so `store.py` resolves the store to `H`).
- `H/records/<topic>/<concept>.md` = frontmatter (`topic`, `concept`, `state`, plus `deps`
  and explicit schedule fields **only if given**) + a body containing the required
  `Review question (self-test prompt)` section carrying `review_question`.

The record body format matches what `store.py` reads; a round-trip unit test (§8) guards
against drift. `TEACH_ME_HOME=H` is passed to the coach for that run.

## 6. Components

| File | Change | Responsibility |
|---|---|---|
| `evals/seed.py` | new | `seeded_home(seed_spec)` context manager: make temp dir, write `config.json` + records, yield the path, clean up. Pure filesystem; no network. |
| `evals/providers.py` | modify | `CoachSession.run` / `AgentSDKCoach.run` gain `env_extra=None`, merged into the per-run SDK env. |
| `evals/run_evals.py` | modify | Read `scenario["setup"]["seed"]`; per sample, open a `seeded_home`, pass `TEACH_ME_HOME` via `env_extra`, tear down. Scenarios without `seed` are unchanged. |
| `evals/scenarios/r1-review-recall.yaml` | new | Pass path. |
| `evals/scenarios/r2-review-fail-relearn.yaml` | new | Fail → relearn path. |
| `tests/test_seed.py` | new | Offline: seeded record is surfaced by `store.py due` and updated by `store.py review` (subprocess round-trip); per-sample isolation. |
| `tests/test_run_evals.py` | modify | Integrity: new scenarios load and reference known asserts; `setup.seed` parses; coach receives `TEACH_ME_HOME` (fake client). |

## 7. Scenarios

**`r1-review-recall` (pass path)**
- `seed`: one due concept with a distinctive `review_question`.
- `turns`: `["/teach-me review"]`.
- `asserts`: `transcript_matches` on a distinctive keyword from the seeded question (evidence
  the coach used the **stored** question, not an invented one).
- `judge.rubric`: the coach poses the stored self-test question as a retrieval check and lets
  the learner attempt it — it does **not** dump the answer or lecture first. Fail if it hands
  over the answer or auto-advances without a retrieval attempt.

**`r2-review-fail-relearn` (fail path)**
- `seed`: one due concept.
- `turns`: `["/teach-me review", "不会"]`.
- `judge.rubric`: after the learner cannot answer, the coach treats the concept as needing
  relearning (stale) and **asks** whether to relearn it now — it does not force a relearn and
  does not silently skip on. Fail if it just moves to the next item or ignores the miss.

Both: `samples`/`pass_threshold` follow the suite default (3 / 2); position-robust asserts
(teach-me emits a preamble turn first — never key off `turns[0]`).

## 8. Testing

Offline unit suite only (free, CI-safe — `uv run --project evals python -m pytest -q tests/`):

- **Seed round-trip:** `seeded_home` writes a record → `store.py due --config <H>/config.json`
  (or `TEACH_ME_HOME=<H>`) lists it as due → `store.py review … pass` updates it (box set,
  `state=retained`, `review_count=1`). Guarantees the seed format matches `store.py`.
- **Isolation:** two `seeded_home` calls produce independent dirs; mutating one does not affect
  the other; the context manager removes its dir on exit.
- **`env_extra` plumbing:** `AgentSDKCoach.run(turns, env_extra={"TEACH_ME_HOME": …})` passes
  the value into the client options (asserted via the injected fake client factory).
- **Scenario integrity:** `r1`/`r2` load, reference known asserts, and their `setup.seed`
  parses.

The paid run of `r1`/`r2` against DeepSeek is **manual** and gated on an explicit go-ahead
(§9); it is never part of the unit suite or CI.

## 9. Global constraints

- **Paid-run gate:** a live `run_evals.py` costs real tokens. Pause and get an explicit
  go-ahead before the run, even though the coverage was pre-authorized.
- **Never weaken an assert or rubric to turn a genuine teach-me miss green.** The review
  rubrics mirror teach-me's own Red Flags (SKILL.md / references/review.md). A real miss is a
  finding about the skill, not a reason to loosen the eval.
- **Offline unit suite stays green at every commit.** New seed logic is covered offline.
- **No secrets/PII in tracked files.** `.env` stays gitignored; seeds use `tmp_path` /
  temp dirs and `TEACH_ME_HOME`, never the operator's real home.
- **Commit author:** every commit authored as `young1lin <2550110827@qq.com>`; AI credited only
  via a `Co-Authored-By:` trailer naming the actual model. English commit messages.
- **`store.py` is not modified** by this work.

## 10. Migration & back-compatibility

- Scenarios without a `setup.seed` key are unaffected — `run_scenario` seeds only when the key
  is present, and the coach's `env_extra` defaults to `None` (identical behavior to today).
- The seed relies on the already-shipped schedule-less-record migration; no new store behavior
  is introduced, so existing records and readers are untouched.
