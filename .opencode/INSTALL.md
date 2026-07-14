# Installing teach-me for OpenCode

## Prerequisites

- [OpenCode.ai](https://opencode.ai) installed

## Installation

Add teach-me's skills directory to the `skills.paths` array in your `opencode.json`
(global or project-level):

```json
{
  "skills": {
    "paths": ["~/.config/opencode/teach-me/skills"]
  }
}
```

After cloning this repo to `~/.config/opencode/teach-me`, restart OpenCode, then verify:

```
use the skill tool to list skills
```

`teach-me` should appear. Invoke it explicitly with `$teach-me` (it is never
auto-activated).

## Tool mapping

teach-me speaks in actions; on OpenCode these resolve to: read → `read`, edit/write →
`apply_patch`, shell → `bash`, search → `grep`/`glob`, todos → `todowrite`, skill load →
OpenCode's native `skill` tool.
