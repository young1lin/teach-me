# teach-me

![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

**AI wrote it. Do you understand it?**

English | [中文](README.zh-CN.md)

A learning-coach skill for coding agents. Turn LLM-era work and reading into observable
understanding — and keep it: debrief work you just did, learn a topic to observable
understanding, then come back for spaced-repetition reviews so it actually sticks. Resumable
checkpoints throughout. **Explicitly invoked** — it never auto-activates.

Invoke with `/teach-me` (Claude Code / Cursor / Antigravity) or `$teach-me` (Codex /
OpenCode).

> Python 3.8+ is required for deterministic store helpers, optional Obsidian archive copy/update,
> and the dev tooling (`scripts/`); the teaching skill itself runs inside your agent.

## Teaching modes

Pick how you want to be taught. A mode changes the teaching style only — evidence is
always measured the same way (explain / apply / transfer). Socratic is the default; the
others are opt-in flags.

| Mode | Flag (alias) | Style |
|---|---|---|
| socratic (default) | `--socratic` (`--soc`), or no flag | Question-led discovery |
| feynman | `--feynman` (`--fey`) | You explain first; the coach finds and fills gaps |
| drill | `--drill` (`--dri`) | Deliberate-practice reps on your weakest sub-skill |

```bash
/teach-me TCP congestion control              # Claude Code / Cursor / Antigravity (socratic default)
/teach-me --fey                               # Feynman-style debrief of work you just did
$teach-me --dri regex                         # Codex / OpenCode
```

Mid-session, just say "switch to feynman" (any language) — no re-invocation needed.

Example (illustrative):

```text
> /teach-me
1 candidate from this session: "why the retry uses exponential backoff + jitter"
(agent-written). In one sentence — why the jitter?
> so retries don't all wake up at the same time
Verdict: correct — thundering-herd avoidance.
Your turn: we drop the jitter but keep backoff — what failure returns, and when?
```

Pairs well with [grill-me](https://github.com/mattpocock/skills): grill your plan before
you build; run teach-me after you ship, so the speed AI gives you doesn't cost you the
understanding.

## Review & retention

Reaching "observable understanding" in one session isn't the finish line — teach-me schedules
every demonstrated concept for later retrieval checks so it actually sticks. Run a review when
you want; nothing is auto-started.

```bash
/teach-me review        # quiz the concepts that are due today
$teach-me review        # Codex / OpenCode
```

- **Spaced repetition** — each concept rides a Leitner ladder (`1 → 3 → 7 → 21 → 60` days).
  Recall it and the interval grows; miss it and it resets to `stale`, and teach-me offers to
  reteach it on the spot.
- **Due, never nagging** — a review runs only when you ask. At the end of a session, or on
  `resume`, teach-me prints one quiet line if anything is due — never more, never elsewhere.
- **Prerequisites first** — concepts record what they depend on, so reviews check foundations
  before the things built on them.

Reviews are batch-capped (5 by default) and obey the same fatigue rules as teaching — one
question at a time, and they stop the moment you're done.

## Your learning data

Everything you demonstrate is saved as plain markdown under one root. Agents that share the same OS user home share this root by default; Windows apps, WSL, SSH remotes, and dev containers may each have a different home. Use `TEACH_ME_HOME` when you need those environments to point at the same learning store. Records are organized by topic (which project they came from is metadata inside each file):

```text
${TEACH_ME_HOME:-~/.teach-me}/config.json  # where your root is configured
<root>/records/<topic>/<concept>.md
<root>/checkpoints/<topic>.md
```

The first time a session saves anything, teach-me asks once: keep the default
`~/.teach-me/` (or `TEACH_ME_HOME` when set) or name your own directory. The answer is remembered in
`${TEACH_ME_HOME:-~/.teach-me}/config.json` — you're never asked again. Browse or grep the records freely;
they're just markdown with frontmatter (`topic`, `project`, `state`, `evidence`).

There is no database and no search index — your agent's own `grep` / `Glob` / `Read` is
the retrieval engine. To pick a topic back up, `/teach-me resume <topic>`; if nothing
matches, teach-me says so — it never invents prior learning.

## Archive to Obsidian (optional)

Copy/update everything you have demonstrated into your own vault. Add an `archive` section to
`${TEACH_ME_HOME:-~/.teach-me}/config.json` — a configured destination is your standing consent; teach-me
copies/updates after every save, automatically:

```json
{
  "root": "~/.teach-me",
  "archive": {
    "obsidian": { "vault_path": "D:/vault", "folder": "teach-me" }
  }
}
```

- **Obsidian** — records land in your vault as plain markdown (`teach-me/<topic>/…`).
  Works even while Obsidian is closed.

Archiving is best-effort: if the vault path is missing, you get a one-line note and the
lesson continues. Preview anytime with `python skills/teach-me/scripts/archive.py --dry-run`.

## Installation

Install differs by harness. If you use more than one, install teach-me separately for
each.

### Claude Code

Register this repo as a marketplace, then install:

```bash
/plugin marketplace add young1lin/teach-me
/plugin install teach-me@teach-me-marketplace
```

### Codex

Install from this repository:

```bash
/plugins install https://github.com/young1lin/teach-me
```

Then invoke with `$teach-me`.

### Cursor

```text
/add-plugin teach-me
```

Or search for "teach-me" in the plugin marketplace and point it at
`https://github.com/young1lin/teach-me`.

### Kimi Code

```text
/plugins install https://github.com/young1lin/teach-me
```

### OpenCode

See [`.opencode/INSTALL.md`](.opencode/INSTALL.md) — add this repo's `skills/` to
OpenCode's `skills.paths`, then invoke with `$teach-me`.

### Pi

```bash
pi install git:github.com/young1lin/teach-me
```

### Antigravity

```bash
agy plugin install https://github.com/young1lin/teach-me
```

### Any `.agents/`-compatible tool (universal)

```bash
npx skills add young1lin/teach-me
```

This installs the skill into your agent's skills directory (Claude Code, Cursor, Codex,
OpenCode, and 70+ others).

## Layout

- `skills/teach-me/` — the skill (`SKILL.md`, `references/`, `agents/`, `scripts/`).
- `.<agent>-plugin/`, `.agents/`, `.opencode/`, `package.json` — per-agent packaging.
- `scripts/` — `validate.py` (packaging) and `validate_skill.py` (SKILL-standard) gates.
- `tests/` — behavior scenarios + pytest suites for the archive and store layers (run with `uv run --project evals python -m pytest -q tests/`).

## License

MIT — see [LICENSE](LICENSE).
