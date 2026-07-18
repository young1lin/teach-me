# Changelog

All notable changes to **teach-me** are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

English | [中文](CHANGELOG.zh-CN.md)

## [0.0.2] - 2026-07-18

### Added

- **Review & retention layer** — closes the retention loop: a concept is no longer only
  taught to observable understanding within a session, but scheduled for later retrieval
  checks and tracked as it decays. Activates dormant schema fields (`deps`, the
  `retained`/`stale` states, per-record dates) with a small deterministic engine rather
  than new subsystems.
  - **Spaced repetition** — a Leitner box ladder (`[1, 3, 7, 21, 60]`-day intervals): a
    passed review promotes a concept one box (longer interval); a failed review resets it
    to box 1.
  - **`/teach-me review`** (`$teach-me review`) — quizzes due concepts using their stored
    self-test question and updates the schedule; batch-capped at 5 and bound by the usual
    fatigue rules. Due items are also surfaced as a single passive line at the end of a
    session or on `resume` — never auto-started, never surfaced outside an invoked session.
  - **Prerequisites (`deps`)** — concepts record their prerequisites, used to order reviews
    (prerequisite before dependent) and, on a failed review, to offer checking a shaky
    prerequisite first.
  - `store.py` gains `due`, `review`, and `save-record --deps`; all schedule math is
    deterministic and covered by offline unit tests. Pre-existing records migrate in
    automatically on their first review (no breaking change).

## [0.0.1] - 2026-07-14

### Added

- **The teach-me skill** — a learning coach for coding agents, explicitly invoked with
  `/teach-me` (Claude Code / Cursor / Antigravity) or `$teach-me` (Codex / OpenCode);
  never auto-activates. Two branches: debrief the work you just shipped (no topic), or
  learn a topic to observable understanding (explain / apply / transfer), with fatigue rules,
  consent-gated persistence, checkpoints, and `resume`.
- **Teaching modes**: `socratic` (the no-flag default), `feynman` (`--feynman`/`--fey`),
  `drill` (`--drill`/`--dri`) — style changes only, the E1/E2/E3 evidence rubric is invariant;
  mid-session switching in any language; mode persists in checkpoints. Plus repo-grounded
  exercises (predict-then-run / modify-without-peeking / spot-the-planted-bug, with
  consent + cleanup safety rules).
- **Unified learning storage** — one user-configurable root (default `~/.teach-me/`,
  discovery via `~/.teach-me/config.json`, asked once at the first save), records
  organized by topic (`records/<topic>/<concept>.md`) with the source project as
  frontmatter metadata; checkpoints under `checkpoints/`. Recall is grep-first — no
  database and no index; if nothing matches, teach-me says so and never fabricates prior
  learning.
- **Archive layer** (`skills/teach-me/scripts/archive.py`, Python 3.8+) — copies/updates
  records to **Obsidian** (markdown into your vault). A configured destination is standing
  consent; best-effort — archiving never blocks teaching.
- **Multi-agent packaging**: Claude Code, Codex, Cursor, Kimi, OpenCode, Pi, and the
  universal `.agents/` standard (`npx skills add`).
- **Tooling & tests**: `scripts/validate.py` packaging gate and
  `scripts/validate_skill.py` SKILL-standard gate, `scripts/bump-version.py`
  single-source versioning, release workflow (validate on PR, release on `v*` tag),
  behavior scenarios, and pytest suites for the archive/store layers.

[0.0.2]: https://github.com/young1lin/teach-me/releases/tag/v0.0.2
[0.0.1]: https://github.com/young1lin/teach-me/releases/tag/v0.0.1
