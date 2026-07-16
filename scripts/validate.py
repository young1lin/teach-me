#!/usr/bin/env python3
"""Acceptance check for teach-me multi-agent packaging (spec AC1-AC7)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "skills/teach-me/SKILL.md",
    "skills/teach-me/agents/openai.yaml",
    "skills/teach-me/references/flows.md",
    "skills/teach-me/references/state.md",
    "skills/teach-me/references/teaching.md",
    "skills/teach-me/references/modes/socratic.md",
    "skills/teach-me/references/modes/feynman.md",
    "skills/teach-me/references/modes/drill.md",
    "skills/teach-me/scripts/archive.py",
    "skills/teach-me/scripts/store.py",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".codex-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    ".kimi-plugin/plugin.json",
    ".agents/plugins/marketplace.json",
    ".opencode/INSTALL.md",
    "package.json",
    "CLAUDE.md",
    "AGENTS.md",
    "README.md",
    "LICENSE",
    "assets/teach-me.svg",
    ".version-bump.json",
    "scripts/bump-version.py",
    "CHANGELOG.md",
    ".github/workflows/release.yml",
    "tests/test_archive.py",
    "tests/test_store.py",
    "docs/release-checklist.md",
]

JSON_FILES = [p for p in REQUIRED_FILES if p.endswith(".json")]

FORBIDDEN_FILES = [
    "teach-me.skill",        # D2: deleted
    "gemini-extension.json", # Gemini dropped
    "GEMINI.md",             # Gemini dropped
]

FORBIDDEN_DIRS = ["hooks", ".pi/extensions"]  # D4: no bootstrap machinery

errors = []

# AC1, AC5: required files exist
for rel in REQUIRED_FILES:
    if not (ROOT / rel).is_file():
        errors.append(f"missing required file: {rel}")

# Forbidden files/dirs absent
for rel in FORBIDDEN_FILES:
    if (ROOT / rel).exists():
        errors.append(f"forbidden file present: {rel}")
for rel in FORBIDDEN_DIRS:
    if (ROOT / rel).exists():
        errors.append(f"forbidden bootstrap path present: {rel}")

# Old skill location must be gone
if (ROOT / "teach-me").is_dir():
    errors.append("old teach-me/ dir still present (should be skills/teach-me/)")

# AC2-AC5: every JSON parses
for rel in JSON_FILES:
    p = ROOT / rel
    if p.is_file():
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"invalid JSON {rel}: {e}")

# AC5/D4: no sessionStart anywhere (explicit invocation)
for rel in [".kimi-plugin/plugin.json"]:
    p = ROOT / rel
    if p.is_file() and "sessionStart" in p.read_text(encoding="utf-8"):
        errors.append(f"{rel} must not contain sessionStart (explicit invocation)")

# AC1: SKILL.md kept its frontmatter name
skill = ROOT / "skills/teach-me/SKILL.md"
if skill.is_file():
    head = skill.read_text(encoding="utf-8")[:200]
    if "name: teach-me" not in head:
        errors.append("skills/teach-me/SKILL.md frontmatter lost 'name: teach-me'")

# AC: version single-source — every declared manifest matches package.json
vb = ROOT / ".version-bump.json"
if vb.is_file():
    ref = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    for entry in json.loads(vb.read_text(encoding="utf-8"))["files"]:
        p = ROOT / entry["path"]
        if p.is_file():
            cur = json.loads(p.read_text(encoding="utf-8"))
            for part in entry["field"].split("."):
                cur = cur[int(part)] if part.isdigit() else cur[part]
            if cur != ref:
                errors.append(f"version drift: {entry['path']} ({entry['field']}) = {cur}, expected {ref}")

if errors:
    print("VALIDATION FAILED:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
print(f"OK — {len(REQUIRED_FILES)} required files present, all JSON valid, no bootstrap.")
