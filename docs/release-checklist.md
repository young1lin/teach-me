# Release checklist

Run this checklist before publishing a public teach-me release.

## Automated gates

- [ ] `python scripts/validate.py` passes.
- [ ] `python scripts/validate_skill.py` passes.
- [ ] `uv run --with pytest pytest -q` passes.
- [ ] `python scripts/bump-version.py --check` passes.
- [ ] Release tags use `v<package.json version>` and pass the workflow tag check.

## Platform validation

- [ ] Codex plugin installs or passes the current Codex plugin validator.
- [ ] Claude Code plugin / skill installs or passes the current Claude validator.
- [ ] Cursor plugin installs or passes the current Cursor validator.
- [ ] `.agents/` marketplace metadata uses a valid source for the intended release path.

If a platform validator cannot run in CI, record the manual command, platform version, date,
and result in the release notes before tagging.

## Drift checks

- [ ] README, changelog, package metadata, and plugin manifests describe only shipped behavior.
- [ ] Same-session E1/E2/E3 is described as `demonstrated`, not durable retention.
- [ ] `retained` is used only for delayed retrieval evidence from a later session.
- [ ] Behavior scenarios do not contain obsolete storage paths, commands, or stale PASS claims.
- [ ] Optional archive behavior is described as copy/update unless safe pruning is implemented.
