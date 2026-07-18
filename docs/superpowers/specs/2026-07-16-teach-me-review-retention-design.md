# teach-me review & retention layer — design

**Date:** 2026-07-16
**Status:** Approved (brainstorming complete; ready for writing-plans)

## 1. Motivation

teach-me teaches a concept to *observable understanding* within one session (the E1/E2/E3
rubric), but nothing brings that concept back later. Retention — the actual point of
learning — is left entirely to the user remembering to `resume`. Compared to mature
learning systems (Anki, Duolingo, intelligent tutoring systems), teach-me is a strong
single-session coach missing the loop that closes retention over time.

The important observation: **the schema already anticipates this loop; only the engine is
missing.**

- `references/state.md` already defines the states `retained` ("passed a delayed retrieval
  check in a later session") and `stale` ("previously demonstrated/retained, but due for
  re-check"). Nothing computes or assigns them across sessions.
- Record frontmatter already stores `date:`, and the in-session / checkpoint concept schema
  is already `{name, deps, state, E1, E2, E3}` — it carries a **`deps`** (prerequisites)
  field that is never persisted to a record and never acted on.
- `resume` already re-checks a topic's `demonstrated/retained/stale/unstable` concepts for
  decay before continuing — but only for the one topic you manually resume. There is no
  global "what is due today" view.

This design activates those dormant fields with a small, deterministic engine, rather than
bolting on new subsystems.

## 2. Goals

- Close the retention loop: after a concept is demonstrated, schedule it for later retrieval
  checks and track whether it was retained or has gone stale.
- Add a `review` flow that quizzes due concepts using their stored self-test question and
  updates their schedule deterministically.
- Persist and use concept prerequisites (`deps`) to order reviews and flag shaky prerequisites.
- Keep everything consistent with teach-me's identity: explicit invocation only, never nag,
  consent-gated, fatigue-bounded.

## 3. Non-goals (YAGNI — explicitly out of scope)

- **No SM-2 / per-item ease factors / forgetting-curve regression.** A fixed Leitner interval
  ladder is the v1 decay model. The stored schedule fields (`box`, `review_count`) leave a
  data path to a fancier model later, but that is a future spec.
- **No cron jobs, push notifications, or any surfacing outside an already-invoked teach-me
  session.** That would violate "never auto-invoke, never nag."
- **No curriculum / prerequisite-graph course sequencing.** `deps` is used only for review
  ordering and a "shaky prerequisite" hint — not full learning-path planning.
- **No progress dashboard / analytics UI.** Recall stays grep-first plain markdown.
- **No new paid behavioral eval in this spec.** Coverage is deterministic offline unit tests
  only; a behavioral review eval is deferred (the harness is not yet validated on Claude).

## 4. Design decisions (approved during brainstorming)

1. **Scope:** one integrated spec covering spaced-repetition scheduling (#1) + a simple
   decay model (#2) + `deps` persistence (#3). The three are coupled in the existing schema.
2. **Algorithm:** a **Leitner interval ladder**, intervals `[1, 3, 7, 21, 60]` days, capped at
   60. A pass promotes one box (longer interval); a fail resets to box 1. This *is* the v1
   decay model — "past its due interval" is the decay signal, no probabilistic estimate.
3. **Surfacing:** review is the explicit command `/teach-me review` (`$teach-me review`).
   Due items are additionally surfaced as a single passive line **only at the end of an
   already-invoked teach-me session or on `resume`** — never auto-started, never surfaced
   outside teach-me.
4. **Failed review:** mark the concept `stale`, then ask whether to relearn it now (the user
   decides); relearning runs a normal teach-me loop on that concept. Reviews are
   fatigue-bounded with a default batch cap of **5** due items per session.

## 5. Data model

Record frontmatter (`<root>/records/<topic>/<concept>.md`) gains, all with back-compatible
defaults:

| Field | Default | Meaning |
|---|---|---|
| `deps` | `[]` | prerequisite concept slugs |
| `box` | `1` | Leitner box level, index into the ladder |
| `last_reviewed` | write date | ISO date of the last review (or initial demonstration) |
| `review_count` | `0` | number of completed retrieval checks |

- **Ladder:** `LADDER = [1, 3, 7, 21, 60]` (days). `box` is a 1-based level indexing the
  ladder as `LADDER[box - 1]`; `box=1` → 1 day, `box=5` → 60 days; promotion past the top
  (`box == len(LADDER)`) stays at 60.
- **`due` is never stored** — it is computed as `last_reviewed + LADDER[box - 1]` days at read
  time, keeping a single source of truth (no denormalization drift).
- **Entry into the schedule:** the first time a concept is written as `demonstrated`, it
  initializes `box=1`, `last_reviewed=<write date>`, `review_count=0`, so its first retrieval
  check falls due one day later.
- **State lifecycle (extends the existing vocabulary, no new states):**
  `demonstrated` → (review pass) `retained`, box promoted → … ; (review fail) `stale`, box
  reset to 1.

## 6. `store.py` CLI (deterministic layer)

`store.py` owns all schedule math; the skill never hand-computes dates or box transitions.

- **`store.py due [--on DATE] [--limit N]`** — scan `records/`, emit the concepts whose
  computed `due <= today` (or `--on DATE`). Output per line: record path, topic, concept,
  state, box, days-overdue. **Ordering:** prerequisites (from `deps`) before their dependents
  (topological), then most-overdue first. `--limit` caps the count (the skill passes its
  batch cap). A record missing the schedule fields but in state `demonstrated`/`retained` is
  treated as **due now**, so pre-existing records migrate in on their first review.
- **`store.py review --topic T --concept C --result {pass|fail}`** — deterministically update
  the schedule: `pass` → promote `box` (cap 5), `state=retained`; `fail` → `box=1`,
  `state=stale`; both set `last_reviewed=today`, `review_count += 1`. Rewrites the record
  atomically (existing `atomic_write_text` + `file_lock`).
- **`save-record --deps a,b,c`** — accept prerequisites and initialize the schedule fields on
  the first `demonstrated` write.

## 7. Review flow & passive surfacing (skill layer)

- **`/teach-me review`** (Branch C, new): call `store.py due --limit 5`; for each due concept,
  ask its stored **"Review question (self-test prompt)"** as a retrieval check; honor the
  fatigue hard rules (one action per turn, stop immediately on any fatigue/stop signal).
  - `correct` → `store.py review --result pass`.
  - `partial` / `not yet` → `store.py review --result fail`; the concept is now `stale`; ask
    "review this now?" — yes runs a normal teach-me loop on it; no continues to the next due
    item. If a failed concept's `deps` include a stale/overdue prerequisite, surface
    "this may be because prerequisite Y is shaky — review Y?" (judgment layer, not store.py).
  - Stop when the batch (5) is done, the due list is exhausted, or a fatigue signal arrives;
    always end with the standard copyable checkpoint.
- **Passive surfacing:** at the end of an already-invoked teach-me session and at the start of
  `resume`, if `store.py due` reports any due concepts, print one line:
  "N concept(s) are due for review — run `/teach-me review` when you want." Never more; never
  outside an invoked teach-me session; never auto-start.

## 8. Prerequisites — `deps` (#3)

- **Source:** the coach identifies prerequisites during teaching and records them in `deps`
  on the `demonstrated` write (the in-session `concepts` schema already tracks `deps`).
- **Use, limited to two things:** (a) `store.py due` orders a prerequisite before its
  dependents; (b) on a failed review, the skill offers to check a stale prerequisite first.
- **Explicitly not** used for course/path planning or graph visualization (non-goal §3).

## 9. Documentation changes

- **`SKILL.md`** — add the `/teach-me review` command row; update `argument-hint` to include
  `review`; add two Red Flags: never auto-start review; never surface due items outside an
  invoked teach-me session.
- **`references/state.md`** — document the schedule fields, the Leitner ladder, `due`
  computation, the schedule-entry condition, and `deps` persistence in record frontmatter;
  mark the existing "Review question (self-test prompt)" record section as **required** (it
  is already in the record template) since the review flow depends on it.
- **`references/flows.md`** — add the review procedure (Branch C) and the passive-surfacing
  rule at session end / on resume.
- **`references/review.md`** (new) — the review loop detail (batch cap, fatigue, verdict →
  pass/fail mapping, fail → relearn, prerequisite hint), referenced from `flows.md`.

## 10. Testing

All new logic lands in `store.py`, which is deterministic and covered by the **offline unit
suite** (no network, no cost, CI-friendly — `uv run --with pytest --with pyyaml python -m
pytest -q tests/`). New `tests/test_store.py` cases:

- Ladder promotion/reset math across `pass`/`fail`, including the cap at box 5.
- `due` selection at a fixed `--on DATE` boundary (due vs not-yet), including the "pre-existing
  demonstrated record with no schedule fields is due now" migration path.
- `due` ordering: a prerequisite sorts before its dependent; most-overdue first within a tier.
- `save-record --deps` persists prerequisites and initializes schedule fields.
- `review` updates `box`/`state`/`last_reviewed`/`review_count` and rewrites atomically.

A behavioral eval scenario for the review conversation is **deferred** (paid; and the harness
is not yet validated on Claude — see repo CLAUDE.md).

## 11. Migration & back-compatibility

- Existing records have no `deps`/`box`/`last_reviewed`/`review_count`. `store.py due` treats a
  schedule-less `demonstrated`/`retained` record as due now; the fields are written on that
  record's first `review`. No bulk migration step; no breaking change to existing readers
  (`resume`, `list-topics`, `archive.py` ignore unknown-but-absent fields).
- The record frontmatter parser already tolerates extra keys; `deps` (a JSON list) round-trips
  through the existing `json`-valued frontmatter serialization.

## 12. Global constraints

- **Commit author:** every commit authored as `young1lin <2550110827@qq.com>` (the repo's
  configured identity). Claude credited **only** via trailer
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` — never as author.
- **`store.py` stays standard-library only and Python 3.8+ compatible** (it is a skill script
  that must run wherever the agent runs, not just under the `uv` eval project).
- **Offline unit suite stays green at every commit.**
- **No secrets/PII in tracked files.** No usernames, emails, or home paths in tracked content;
  tests use `tmp_path` and `TEACH_ME_HOME` overrides.
- **No new CI cost** — the review engine is tested by the offline deterministic suite only.
