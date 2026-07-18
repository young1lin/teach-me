# Release & Versioning — teach-me

Single home for everything about cutting a release: version policy, the bump
procedure, changelogs, gates, tagging, and the automated release workflow.
Anything release-related lives here — CLAUDE.md only points at this file.

---

## 1. Versioning policy (SemVer)

Version numbers follow [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

| Bump | When |
|---|---|
| **MAJOR** | Backward-incompatible change (removed/renamed command, changed record schema readers can't tolerate). |
| **MINOR** | New backward-compatible capability (a new command, a new teaching mode). |
| **PATCH** | Backward-compatible bug fix or docs-only change — no new capability. |

**Pre-1.0 note:** the project is still `0.x`. SemVer permits anything to change
in `0.x`, so the MINOR-vs-PATCH line is softer here than post-1.0 — but keep the
intent honest: a new feature is a MINOR (`0.1.0`), a fix is a PATCH (`0.0.z`). If
the user picks a smaller bump than SemVer would suggest, that's their call —
record it and move on; do not silently "correct" it.

## 2. Single source of the version

The version string lives in **six files**, listed in `.version-bump.json`. The
canonical value is `package.json`'s `version`. **Never hand-edit the six files** —
use the script, which keeps them in lockstep:

- `package.json`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json` (`plugins.0.version`)
- `.codex-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.kimi-plugin/plugin.json`

```bash
python scripts/bump-version.py <new-version>   # set the version everywhere
python scripts/bump-version.py --check         # verify all six agree; exit 1 on drift
```

## 3. Cutting a release — step by step

1. **Pick the version** per §1. If the user hasn't named it, ask; do not assume.
2. **Bump:** `python scripts/bump-version.py <new>`.
3. **Verify no drift:** `python scripts/bump-version.py --check` (all six `OK`).
4. **⚠️ Line-ending gotcha (Windows):** `bump-version.py` rewrites files with
   Python's text-mode write, which flips **LF-only** files to CRLF on Windows —
   turning a one-line version bump into a whole-file diff. After bumping, run
   `git diff --stat`. Any manifest showing far more than `1 insertion(+), 1
   deletion(-)` had its endings flipped. Restore LF on that file only:
   ```bash
   git show HEAD:<file> | sed 's/"version": "<old>"/"version": "<new>"/' > <file>
   ```
   As of 2026-07-18 only **`.codex-plugin/plugin.json`** is LF-only; the other
   manifests are already CRLF and bump cleanly. (Fixing the script to preserve
   per-file endings would remove this step — until then, check every bump.)
5. **Update BOTH changelogs** — `CHANGELOG.md` (English) and `CHANGELOG.zh-CN.md`
   (中文), kept in sync:
   - Add a section above the previous one:
     `## [x.y.z] - YYYY-MM-DD` with `### Added` / `### Changed` / `### Fixed`.
   - Add a link reference at the bottom:
     `[x.y.z]: https://github.com/young1lin/teach-me/releases/tag/vx.y.z`.
   - Use the actual release date (today), which may differ from the underlying
     commit dates.
6. **Run all gates** (§4) — every one must pass.
7. **Commit** — English message; author `young1lin <2550110827@qq.com>`; AI only
   via `Co-Authored-By:` naming the **actual model** (§6). A version bump is one
   commit, e.g. `chore(release): bump version to x.y.z`.
8. **Tag & release** (§5) — only for the exact version the user named (§7).

## 4. Gates (must pass before tagging)

These mirror the CI `validate` job — run them locally first:

- [ ] `python scripts/validate.py` — packaging acceptance (required files, valid JSON).
- [ ] `python scripts/validate_skill.py` — SKILL standard.
- [ ] `uv run --project evals python -m pytest -q tests/` — offline unit suite
      (no network, no cost). CI uses `uv run --with pytest --with pyyaml …`.
- [ ] `python scripts/bump-version.py --check` — version consistency.

**Platform validation** (record command, platform version, date, result in the
release notes if a validator can't run in CI):

- [ ] Codex plugin installs / passes the current Codex validator.
- [ ] Claude Code plugin/skill installs / passes the current Claude validator.
- [ ] Cursor plugin installs / passes the current Cursor validator.
- [ ] `.agents/` marketplace metadata uses a valid source for the release path.

**Drift checks** (docs must describe only shipped behavior):

- [ ] README, changelogs, package metadata, and plugin manifests describe only
      shipped behavior.
- [ ] Same-session E1/E2/E3 is described as `demonstrated`, not durable retention.
- [ ] `retained` is used only for delayed-retrieval evidence from a later session.
- [ ] Behavior scenarios contain no obsolete storage paths, commands, or stale
      PASS claims.
- [ ] Optional archive behavior is described as copy/update unless safe pruning
      is implemented.

## 5. Tagging & the automated release workflow

Automation lives in `.github/workflows/release.yml`:

- **`validate` job** runs on push to `main`, on PRs to `main`, and on `v*` tags —
  the same gates as §4, plus (on a tag) a check that the tag equals
  `v<package.json version>`.
- **`release` job** runs **only on `v*` tags**, after `validate` passes: it
  creates a GitHub Release with `gh release create <tag> --generate-notes`.

To publish (only once the user has named the version and gates are green):

```bash
git tag v<x.y.z>            # tag MUST equal v<package.json version> — CI enforces it
git push origin v<x.y.z>    # triggers validate → release → GitHub Release
```

Push commits/tags with the gh credential helper on this machine (GCM hangs
non-interactively); retry on flaky network.

## 6. Commit-author policy (applies to every release commit)

- **Author is always `young1lin <2550110827@qq.com>`.** No exceptions.
- AI is credited **only** via a trailer naming the **actual model** that did the
  work, e.g. `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` — never a
  bare `Claude`, never as the author.
- **Audit before any push** (and before merge/rebase/cherry-pick):
  `git log --format='%an <%ae>' | sort -u` must show only `young1lin`.

## 7. Release only what was named

Never create or push tags/releases beyond the exact version(s) the user
explicitly named. "重新发布 / re-publish" means re-publishing the **existing**
named version(s) — never inventing a new version number. When in doubt, ask.
