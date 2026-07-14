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
