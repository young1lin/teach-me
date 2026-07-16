# teach-me flows

Every flow MUST follow the teaching loop, one-main-action rule, fatigue rules, and E1/E2/E3 rubric in
`teaching.md`. Persistence, portable paths, write consent, records, and checkpoint format come from
`state.md`.

When printing an invocation hint, substitute the literal active-platform token: `/teach-me` on Claude
Code or `$teach-me` on Codex. Never print a token placeholder literally.

The user may stop any flow — a stop or fatigue signal always wins, and demonstrated understanding is never mandatory in
one session. A demonstrated concept becomes eligible for persistence only after the session-consent gate
in `state.md`.

## Teaching-mode composition

Mode flags (`--socratic|--soc`, `--feynman|--fey`, `--drill|--dri`; protocols in
`references/modes/`) shape teaching turns wherever the `teaching.md` loop runs (Branch A/B
teaching). Precedence: the latest explicit user choice wins — a mid-session switch
supersedes the invocation flag; otherwise a resumed checkpoint's saved `mode:`; otherwise
`socratic` (the default). A mid-session plain-language switch ("switch to drill", any
language) takes effect immediately: the skill was explicitly invoked, and changing mode is
not an invocation.

## Branch A — work debrief (no topic)

1. Inspect only work the agent actually did in this conversation, plus `git diff` when inside a
   repository. Do not invent session work.
2. Extract learning candidates from that evidence. For each candidate, show its value, difficulty,
   and authorship (`agent-written`, `user-written`, or `shared`).
3. Present at most five candidates, then wait for the user to select. Selecting candidates is the one
   main action for this turn. Do not teach yet, auto-select, or force unpicked candidates; unpicked
   candidates remain on offer for the user to choose later.
4. Teach only the selected candidates through `teaching.md`, subject to the stop and fatigue rules
   above.
5. End using the checkpoint procedure in `state.md`. Persist eligible demonstrated concepts only after
   session consent.

## Branch B — topic learning (topic present)

1. State one observable learning goal. Ask progressive diagnostic questions only while the relevant
   level remains unclear: no more than three total and one per turn when needed. Stop as soon as the
   level is clear; `I don't know` is a valid answer. If the initial message already establishes the
   relevant level, ask no diagnostic question and proceed to the concept map and current unit.
2. Once the level is clear, show a map of three to seven core units and their dependencies, ordered
   from foundation through mechanism, common misconception, application, and transfer. Expand only
   the current unit; do not pre-generate a textbook.
3. Teach one unit at a time through `teaching.md`. Use its E1/E2/E3 evidence to gate `demonstrated`;
   `unstable` is a valid stopping point that can be resumed later.
4. End using the checkpoint procedure in `state.md`. Persist eligible demonstrated concepts only after
   session consent.

## resume

Load the requested checkpoint through `state.md` and re-check likely decay before continuing. Re-teach
only failed evidence; never assume earlier evidence survived.

If no checkpoint exists in `<root>/checkpoints/` but concept notes for the topic do
(`<root>/records/<topic>/`), load their
saved state and evidence and re-check decay from those instead — an auto-saved session leaves
concept notes, not a checkpoint file. Only if neither exists, say it was not found and offer exactly
these routes: the user can provide a checkpoint, or begin the topic anew. Do not invent prior state.
