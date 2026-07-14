# Changelog

All notable changes to **teach-me** are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

English | [中文](CHANGELOG.zh-CN.md)

## [0.0.1] - 2026-07-14

### Added

- **The teach-me skill** — a learning coach for coding agents, explicitly invoked with
  `/teach-me` (Claude Code / Cursor / Antigravity) or `$teach-me` (Codex / OpenCode);
  never auto-activates. Two branches: debrief the work you just shipped (no topic), or
  learn a topic to observable mastery (explain / apply / transfer), with fatigue rules,
  consent-gated persistence, checkpoints, and `resume`.
- **Teaching modes**: `socratic` (the no-flag default), `feynman` (`--feynman`/`--fey`),
  `drill` (`--drill`/`--dri`) — style changes only, the mastery rubric is invariant;
  mid-session switching in any language; mode persists in checkpoints. Plus repo-grounded
  exercises (predict-then-run / modify-without-peeking / spot-the-planted-bug, with
  consent + cleanup safety rules).
- **Unified learning storage** — one user-configurable root (default `~/.teach-me/`,
  discovery via `~/.teach-me/config.json`, asked once at the first save), records
  organized by topic (`records/<topic>/<concept>.md`) with the source project as
  frontmatter metadata; checkpoints under `checkpoints/`. Recall is grep-first — no
  database and no index; if nothing matches, teach-me says so and never fabricates prior
  learning.
- **Archive layer** (`skills/teach-me/scripts/archive.py`, Python 3.8+) — mirrors
  records to **Obsidian** (markdown into your vault). A configured destination is standing
  consent; best-effort — archiving never blocks teaching.
- **Multi-agent packaging**: Claude Code, Codex, Cursor, Kimi, OpenCode, Pi, and the
  universal `.agents/` standard (`npx skills add`).
- **Tooling & tests**: `scripts/validate.py` packaging gate and
  `scripts/validate_skill.py` SKILL-standard gate, `scripts/bump-version.py`
  single-source versioning, release workflow (validate on PR, release on `v*` tag),
  behavior scenarios, and a pytest suite for the archive layer.

[0.0.1]: https://github.com/young1lin/teach-me/releases/tag/v0.0.1
