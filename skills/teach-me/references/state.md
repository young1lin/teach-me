# teach-me state & persistence

## Storage discovery (do this first, every run)

- The default discovery point is `${TEACH_ME_HOME:-~/.teach-me}/config.json` — the same file on every agent
  (Claude Code, Codex, Cursor, ...), so one person's learning history can be shared by agents that use the same OS user
  home. WSL, containers, SSH hosts, and remote IDEs can each have a different home. Resolve `~` to the OS home dir (Windows → `C:\Users\<user>\...`). Minimum content:

      { "root": "~/.teach-me" }

- `root` is where all learning data lives: records `<root>/records/`, checkpoints
  `<root>/checkpoints/`. Expand `~` inside `root` the same way.
- config.json exists → use its `root`; never ask about storage.
- config.json missing → the store is unconfigured: read nothing and create nothing until a
  write is needed. Ask about storage only at the session's FIRST write, folded into the
  first-write consent gate as ONE question: whether to save AND where — the default
  `~/.teach-me/` (or `TEACH_ME_HOME` when set) or a directory the user names. Write the answer to
  `${TEACH_ME_HOME:-~/.teach-me}/config.json`, then proceed. Sessions that never save are never asked.
- **Legacy migration (once, when creating config.json):** check the old stores
  `~/.claude/teach-me/records/`, `$CODEX_HOME/teach-me/records/`, `~/.codex/teach-me/records/`.
  If any holds records, offer once to migrate. The mapping is mechanical (old frontmatter
  already carries `topic:`): `<topic>--<concept>.md` → `records/<topic>/<concept>.md`;
  `<YYYY-MM-DD>-<concept>.md` → `records/<topic-from-frontmatter>/<concept>.md`;
  `*--checkpoint.md` → `checkpoints/`. On a name collision keep the newer `date:` and say
  so. Move only after the user agrees; report how many files moved.
- Project-scoped save target (on explicit request): `<project>/.teach-me/records/` with
  the same layout; needs no config.
- Create `records/` and `checkpoints/` lazily, only when writing.


## Deterministic store script

Use `python scripts/store.py` (path relative to this skill directory) for low-freedom
persistence operations whenever the runtime can execute Python. The script owns config
discovery, slug generation, JSON-valued frontmatter serialization, atomic writes, and
coarse lock-file protection. Do not hand-compose record/checkpoint files when the script
is available; decide *what* to save, then pass that content to the script. If Python is
unavailable, fall back to the templates below and report that deterministic storage tooling
was unavailable.

Supported operations: `init`, `list-topics`, `save-record`, `save-checkpoint`, `resume`,
`review`, `due`, and `migrate`. `init` preserves existing config sections such as `archive`; `resume` returns the
checkpoint path when present, otherwise all concept-note paths for the topic; no-topic debrief
checkpoints are saved as `<YYYY-MM-DD>-<project>.md`; `migrate` uses legacy frontmatter `topic:`
for dated records and keeps the newer `date:` on collisions.

## Layout — topic is the axis, project is metadata

    <root>/
    ├── records/<topic-slug>/<concept-slug>.md
    └── checkpoints/<topic-slug>.md      # no-topic debrief: <YYYY-MM-DD>-<project>.md

- One directory per topic; a record's `project:` frontmatter says where it was learned.
  Knowledge accumulates across projects: JWT learned in two projects lands in the same
  `records/jwt/`. "What did I learn in project X" = filter records on `project:`.
- **Anti-drift rule (hard):** before writing, LIST the existing `records/*/` topic
  directories and reuse a fitting one; create a new topic directory only when nothing
  fits. A debrief record gets its topic assigned at write time — name the chosen topic
  inside the consent question so the user can correct it (e.g. "save under topic
  `http-retries`?").
- Re-learning a concept updates its existing file; never write a dated duplicate.

## In-session state (keep in memory)

    flow: debrief | topic | resume
    mode: socratic | feynman | drill    # teaching mode — see references/modes/ (socratic = default)
    topic, goal, starting_level
    concepts: [ {name, deps, state, E1, E2, E3} ]
    misconceptions, current_scaffold, fatigue_signals, next_step


## Learning-state vocabulary

- `unseen`: not yet diagnosed.
- `learning`: being taught, no complete evidence set yet.
- `unstable`: can explain part of it, but apply/transfer evidence is missing or weak.
- `demonstrated`: passed E1/E2/E3 in the current session. This is current-session evidence, not durable retention.
- `retained`: passed a delayed retrieval check in a later session.
- `stale`: previously demonstrated/retained, but due for re-check before relying on it.

Do not call a concept retained from same-session E1/E2/E3 alone; describe it as
`demonstrated` until a later retrieval check supports `retained`.

## Spaced-repetition schedule (records carry their own review clock)

Every concept record carries a Leitner schedule in frontmatter:

- `deps: [<concept-slug>, ...]` — prerequisites, used only to order reviews and to flag a
  shaky prerequisite behind a failed review.
- `box: <1..5>` — Leitner level; `last_reviewed: <ISO date>`; `review_count: <int>`.
- Intervals ladder: `[1, 3, 7, 21, 60]` days. A concept at `box` is **due** on
  `last_reviewed + LADDER[box - 1]` days; the date is computed, never stored.
- A concept enters the schedule when first written `demonstrated` (`box 1`,
  `last_reviewed` = write date, `review_count 0`), so its first check falls due one day later.
- Review outcomes (via `store.py review`): a pass promotes one box and sets `retained`; a fail
  resets to box 1 and sets `stale`. `store.py due` lists concepts whose due date has passed;
  a `demonstrated`/`retained`/`stale` record with no `last_reviewed` counts as due now.

The **"Review question (self-test prompt)"** section of each record is **required** — the
review flow uses it as the retrieval prompt.

## Write rules (session-consented milestones)

- A concept that reached `demonstrated` (E1+E2+E3 in this session) is eligible for one concept note after session consent.
- Write nothing for unseen/learning/unstable items — no data pile. Demonstrated understanding is NOT required to end a
  session; stopping at `unstable` writes nothing but the checkpoint.
- **First-write consent gate (AUTO milestone writes):** the FIRST time in a session an automatic
  milestone write would happen (a concept just reached `demonstrated`), name the target path, ask whether
  to save demonstrated concepts, and WAIT. If `${TEACH_ME_HOME:-~/.teach-me}/config.json` does not exist yet, the same
  single question also asks WHERE: the default `~/.teach-me/` or a custom directory (see Storage
  discovery) — never two separate questions. Yes applies to later demonstrated concepts this session. No
  keeps the session free of AUTO writes; do not ask again that session.
- **An explicit user "save" / "save progress" command grants consent by itself.** Write immediately —
  no ask-and-wait gate — even if it is the session's first write, and even if the user earlier declined
  the AUTO gate (an explicit save overrides an earlier "No"). Exception: if config.json is missing, a
  root is still needed — ask only the where-half (default `~/.teach-me/` or custom), then write. It
  writes the current topic's full state to a checkpoint file (see the Checkpoint section), not only
  the demonstrated concept notes.
- User may target the project (`<project>/.teach-me/records/`) instead of the global store.

## Privacy and redaction

Before saving a debrief or checkpoint outside the project, abstract the lesson and remove raw secrets,
tokens, internal domains, customer names, private source code, and business-sensitive details unless
the user explicitly asks to keep a specific item. On the first write of a session, show the short
summary that will be saved as part of the consent prompt so the user can correct or reject it.

## Record file template (dates are placeholders — compute at write time, never copy literals)

    ---
    date: <today>                 # ISO YYYY-MM-DD, current date
    kind: topic                   # topic | debrief
    project: <cwd-basename>       # cwd basename (debrief) or "-" (topic)
    topic: <topic-slug>
    concept: <concept-slug>
    state: demonstrated
    evidence: {E1: passed, E2: passed, E3: passed}
    ---
    ## What was demonstrated
    ## Key misconception fixed
    ## Transfer task passed
    ## Review question (self-test prompt)

Concept-note path (both branches): `<root>/records/<topic-slug>/<concept-slug>.md` — `kind:`,
`date:`, and `project:` distinguish debrief from topic records in frontmatter. An explicitly
saved checkpoint goes to `<root>/checkpoints/<topic-slug>.md` (topic branch) or
`<root>/checkpoints/<YYYY-MM-DD>-<project>.md` (no-topic debrief). Checkpoints live outside
`records/`.

## Checkpoint (print at EVERY session end, written or not)

    ## Learning checkpoint
    Topic:        <topic or "session debrief">
    Goal:         <observable goal>
    Demonstrated: <concepts with E1/E2/E3 this session>
    Unstable:     <can explain, missing apply/transfer>
    Key misconception: <if any>
    Evidence:     <what was observed>
    Next step:    <one action>

When a checkpoint is saved to disk (explicit "save" only — see Write rules), the file in
`<root>/checkpoints/` carries the structured in-session state as frontmatter so `resume` can reload
it, followed by the printed block above:

    ---
    kind: checkpoint
    topic: <topic-slug or "-" for a no-topic debrief>
    mode: <socratic | feynman | drill>
    goal: <observable goal>
    concepts: [ {name, deps, state, E1, E2, E3} ]   # full per-concept evidence, not only demonstrated ones
    misconception: <if any>
    next_step: <one action>
    ---
    (the printed Learning checkpoint block above)

`resume` loads this file, then re-checks concepts whose saved state was `demonstrated`, `retained`, `stale`, or `unstable` for
decay BEFORE continuing (flows.md); it re-teaches only the evidence that now fails. It also restores
the saved `mode:` unless the user chose a mode explicitly this session (precedence in flows.md).

## Retrieval (grep-first — no index, no database)

There is no database and no search index. To recall prior work — a `resume` with a fuzzy
name, or "have I learned X?" — run `grep -ri "<query>" records/` over filenames and body,
or `Glob records/<topic>/*.md`. Cap at ~5 records; read only what the turn needs. Retrieved
understanding is STALE evidence: lightly re-check it before relying on the saved state, and never
let retrieval override saved E1/E2/E3. If grep finds nothing, SAY SO — do not fabricate
prior learning. A configured archive destination (below) is never read back; `records/`
stays the single source of truth.

## Archive (opt-in copy/update to Obsidian)

- config.json may carry an `archive` section. **A configured destination is standing
  consent** — copy/update it WITHOUT asking. No `archive` section → external apps are never
  touched, ever.

      {
        "root": "~/.teach-me",
        "archive": {
          "obsidian": { "vault_path": "D:/vault", "folder": "teach-me" }
        }
      }

- After a record write or an explicit save completes, run
  `python scripts/archive.py` (path relative to this skill's directory; it discovers
  `${TEACH_ME_HOME:-~/.teach-me}/config.json`; add `--dry-run` to preview). It copies/updates `records/` one-way: records stay the single source
  of truth; the archive is never read back.
- Obsidian = markdown copied/updated into `vault_path/folder/<topic>/<concept>.md` (a vault is
  a folder; works with the app closed).
- **Best-effort (hard rule):** missing Python or a bad vault path is a one-line note and
  nothing more — archiving never blocks or delays teaching, never retries in a loop, and
  never asks the user to fix tooling mid-lesson.
