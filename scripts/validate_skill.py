#!/usr/bin/env python3
"""Validate that a skill matches the Skill standard definition (skill-creator).

The existing `validate.py` checks multi-agent *packaging* requirements; this
script checks the *skill itself* against the standard definition:

  - SKILL.md exists in the skill directory
  - YAML frontmatter carries `name` + `description`, and beyond those only
    Agent-Skills standard fields or documented Claude Code extensions
    (argument-hint, allowed-tools, model, ...) — no stray/typo keys
  - `name` is a valid slug (lowercase letters, digits, hyphens)
  - `description` is non-empty and long enough to state when to trigger
  - SKILL.md body is <= 500 lines (progressive-disclosure ceiling)
  - no forbidden aux docs inside the skill (README / CHANGELOG / INSTALL ...)
  - no compiled-python cruft inside the skill (__pycache__ / *.pyc)
  - every `references/.../*.md` link in SKILL.md resolves to a real file

Usage:
    python scripts/validate_skill.py                       # default: skills/teach-me
    python scripts/validate_skill.py --skill PATH/TO/skill

Exit 0 if the skill conforms, 1 otherwise.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SKILL = ROOT / "skills" / "teach-me"

MAX_BODY_LINES = 500        # skill-creator: keep SKILL.md under 500 lines
MIN_DESC_LEN = 40           # a description must say enough to trigger correctly
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):")
REF_RE = re.compile(r"references/[A-Za-z0-9_/.-]+\.md")

# Frontmatter key policy — align with the broadest valid SKILL declaration.
# name + description are always required. Beyond those, accept the Agent-Skills
# standard fields and Claude Code's documented SKILL.md extensions; reject
# anything else as a likely typo or stray key.
REQUIRED_KEYS = {"name", "description"}
# Agent Skills standard (platform.claude.com/.../agent-skills/overview).
STANDARD_KEYS = {"license", "compatibility", "metadata", "allowed-tools"}
# Claude Code extensions (code.claude.com/docs/en/skills): argument-hint drives
# the slash-command placeholder; the rest gate invocation, context, and model.
CLAUDE_CODE_KEYS = {
    "argument-hint", "disable-model-invocation",
    "user-invocable", "context", "model",
}
ALLOWED_KEYS = REQUIRED_KEYS | STANDARD_KEYS | CLAUDE_CODE_KEYS

# skill-creator: a skill must not carry these auxiliary docs — they belong in
# the surrounding repo, not inside the skill package.
FORBIDDEN_FILES = {
    "README.md", "README.rst",
    "CHANGELOG.md",
    "INSTALLATION_GUIDE.md", "INSTALL.md",
    "QUICK_REFERENCE.md",
    "CONTRIBUTING.md",
}


def parse_frontmatter(text: str) -> tuple[set[str], dict[str, str], str]:
    """Return (top-level keys, single-line scalar values, error-or-empty)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return set(), {}, "no leading '---' frontmatter fence"
    keys: set[str] = set()
    simple: dict[str, str] = {}
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        m = KEY_RE.match(line)
        if m:
            key = m.group(1)
            keys.add(key)
            rest = line[m.end():].strip()
            # capture single-line scalars only (name/description are single-line);
            # skip block scalars (| or >) — their value lives on later lines.
            if rest and not rest.startswith(("|", ">")):
                simple[key] = rest.strip().strip('"').strip("'")
    if not closed:
        return set(), {}, "frontmatter never closes (no second '---')"
    return keys, simple, ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--skill", type=Path, default=DEFAULT_SKILL,
                    help="skill directory (default: skills/teach-me)")
    args = ap.parse_args()
    skill: Path = args.skill.resolve()

    if not skill.is_dir():
        print(f"SKILL VALIDATION FAILED: skill dir not found: {skill}")
        return 1

    errors: list[str] = []
    skill_md = skill / "SKILL.md"
    if not skill_md.is_file():
        return report([f"missing SKILL.md in {skill}"])

    text = skill_md.read_text(encoding="utf-8")
    keys, simple, fm_err = parse_frontmatter(text)
    if fm_err:
        errors.append(f"frontmatter: {fm_err}")

    # frontmatter must carry name + description; beyond those, only standard
    # Agent-Skills fields or documented Claude Code extensions are allowed.
    if keys:
        missing = REQUIRED_KEYS - keys
        if missing:
            errors.append(f"frontmatter missing required keys: {sorted(missing)}")
        unknown = keys - ALLOWED_KEYS
        if unknown:
            errors.append(
                "frontmatter has unknown keys (not in the Agent-Skills standard "
                f"or Claude Code extensions): {sorted(unknown)}")

    # name is a valid slug
    name = simple.get("name", "")
    if not name:
        errors.append("frontmatter: 'name' is empty")
    elif not NAME_RE.match(name):
        errors.append(f"frontmatter: 'name' must be a lowercase slug (a-z0-9-), got {name!r}")

    # description states enough to trigger
    desc = simple.get("description", "")
    if len(desc) < MIN_DESC_LEN:
        errors.append(
            f"frontmatter: 'description' too short ({len(desc)} chars) — it must say "
            f"what the skill does AND when to use it")

    # progressive-disclosure ceiling
    body_lines = len(text.split("\n"))
    if body_lines > MAX_BODY_LINES:
        errors.append(f"SKILL.md is {body_lines} lines — keep it under {MAX_BODY_LINES}")

    # forbidden aux docs + compiled-python cruft inside the skill
    for p in skill.rglob("*"):
        rel = p.relative_to(skill)
        if p.is_file() and p.name in FORBIDDEN_FILES:
            errors.append(f"forbidden aux file inside skill: {rel}")
        if p.is_dir() and p.name == "__pycache__":
            errors.append(f"compiled-python cache inside skill: {rel} (remove it)")
        if p.is_file() and p.suffix == ".pyc":
            errors.append(f"compiled-python file inside skill: {rel} (remove it)")

    # every concrete references/*.md link in SKILL.md must resolve.
    # generic placeholders like references/modes/<mode>.md don't match REF_RE,
    # so they are correctly skipped.
    for ref in sorted(set(REF_RE.findall(text))):
        ref_path = ref.split()[0]
        if not (skill / ref_path).is_file():
            errors.append(f"SKILL.md links a missing reference: {ref_path}")

    return report(errors)


def report(errors: list[str]) -> int:
    if errors:
        print("SKILL VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("OK — skill conforms to the Skill standard definition.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
