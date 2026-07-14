---
name: teach-me
description: Use when the user explicitly invokes the learning coach — /teach-me on Claude Code or $teach-me on Codex — optionally with a topic, the resume sub-command, or a teaching-mode flag (--socratic/--soc, --feynman/--fey, --drill/--dri). Do NOT auto-invoke, infer, or load from any general request to explain, teach, summarize, review, debrief, or learn; without the explicit invocation token this skill does not apply.
argument-hint: "[no args = debrief this conversation] [topic] [resume] [--socratic (default)|--feynman|--drill]"
---

# teach-me

## Overview

Turn LLM-era work and reading into durable understanding without extra fatigue. Two branches, one loop:
with no topic it debriefs the work you just did; with a topic it teaches a subject to observable mastery.
Core principle: make understanding observable (explain/apply/transfer), manage cognitive load, keep the
user in control.

## When to Use — trigger is explicit and manual

Run this skill ONLY when the user explicitly invokes it (`/teach-me` on Claude Code, `$teach-me` on
Codex). NEVER auto-invoke it. "explain this", "teach me how this works", or a filename containing
`teach-me` are NOT triggers — answer normally instead. **Violating the letter of this rule violates its
spirit:** the user wants a deliberate command, not an assistant that starts lessons on its own.

## Commands

| Input | Branch → see |
|---|---|
| `/teach-me` (no topic) | Work debrief → `references/flows.md` (Branch A) |
| `/teach-me <topic>` | Topic mastery → `references/flows.md` (Branch B) |
| `/teach-me resume [topic]` | Resume procedure → `references/flows.md`; checkpoint storage + lookup → `references/state.md` |

(Rows show the Claude Code token `/teach-me`; on Codex the same forms are invoked as `$teach-me …`.)
For `resume`, `flows.md` owns the interaction procedure; `state.md` owns persistence and
checkpoint lookup.

## Teaching modes

Orthogonal to the commands above: a mode changes *how* teaching turns run, never what is
measured. The default mode is socratic (no flag needed); it still yields to "just tell me"
and to a missing base (escape hatches in socratic.md / teaching.md).

| Mode | Flag (alias) | One line | Protocol |
|---|---|---|---|
| socratic (default) | `--socratic` (`--soc`), or no flag | Question-led discovery; the no-flag default | `references/modes/socratic.md` |
| feynman | `--feynman` (`--fey`) | Learner explains first; coach fills gaps | `references/modes/feynman.md` |
| drill | `--drill` (`--dri`) | Deliberate-practice reps on the weakest sub-skill | `references/modes/drill.md` |

The shared teaching loop and the invariant E1/E2/E3 rubric live in `references/teaching.md`;
every mode re-skins that loop.

Examples: `/teach-me` (socratic debrief, the default) · `/teach-me --fey` (Feynman-style
debrief) · `$teach-me --dri regex` (Codex drill). Mid-session "switch to feynman" (any
language) works without re-invoking. Composition and precedence: `references/flows.md`. An
unknown mode flag → say so, list the modes, ask; never guess. Two mode flags together
conflict — name the conflict and ask; never pick silently.

## How to teach (never skip)

Follow the load-managed loop and the E1/E2/E3 mastery rubric in `references/teaching.md` — the shared
substrate every mode re-skins. The default mode is socratic (`references/modes/socratic.md`), loaded ON
TOP of teaching.md when no flag is given; another mode flag loads its own file instead. Socratic is
asking-first but never pure-ask: a missing base or a "just tell me" makes it explain directly (escape
hatches in socratic.md / teaching.md). Modes change style only, never the rubric or fatigue rules. One
main cognitive action per turn. Teach in the user's language; leave code and identifiers unchanged.

## Persistence & platform

State and checkpoints live in `references/state.md`. All learning data sits under one root
shared by every agent — default `~/.teach-me/`, user-customizable; discovery via
`~/.teach-me/config.json`; the location is asked ONCE, at the first save. Optionally mirror
records to Obsidian via `python scripts/archive.py` — a configured destination in
config.json is standing consent (see `references/state.md`, "Archive"). Ask and wait before
the first AUTO milestone write of a session — but an explicit "save" writes immediately
without the gate (see state.md). Only mastered concepts are eligible for auto-writes unless
the user explicitly saves progress. Always end with a copyable checkpoint. To recall prior
work, grep `records/` — they are plain markdown; if nothing matches, say so and never
fabricate prior learning.

## Red Flags

- Starting a lesson when the message has NO explicit `/teach-me` or `$teach-me` token → STOP, don't invoke.
- Invoking because a file, path, or repo content contains the text `teach-me` (e.g. opening `teach-me.md`) → STOP; only an explicit token in the user's message counts.
- Dumping an encyclopedia instead of gauging level and giving a minimal step → STOP, diagnose first.
- Teaching every domain with one generic recipe → STOP, classify the unit's domain and use its matching cross-domain row (teaching.md).
- Marking a concept mastered on a bare "I got it" (in any language) without apply/transfer → STOP, get E2/E3 evidence.
- Re-asking the same question after two stalls → STOP, change the scaffold (ladder in teaching.md).
- Continuing to quiz after a stop or fatigue signal (e.g. "enough", "I'm tired", "stop" — in any language) → STOP, checkpoint, no "one more".
- Writing files for unmastered material without an explicit "save" → STOP, only checkpoint.
- Writing even mastered material before session write consent → STOP, ask and wait first.
- Teaching time-sensitive / medical / legal / financial / high-stakes content without verifying → STOP, verify first and separate fact from inference (see teaching.md "Source discipline").
- A teaching mode loosening the fatigue rules or the E1/E2/E3 gate (e.g. staying in question-only mode after "just tell me", or calling a fluent Feynman explanation mastered) → STOP, teaching.md invariants win over any mode.
- An archive failure (bad vault path) interrupting or delaying the lesson → STOP the archiving with a one-line note, never the lesson (best-effort rule in state.md).
- Inventing prior learning ("you already mastered X") when a grep of `records/` finds nothing, instead of saying it was not found → STOP, report not-found.
