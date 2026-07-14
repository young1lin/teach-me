#!/usr/bin/env python3
"""bump-version.py — set/check the teach-me version across all declared files.

Single source of truth: .version-bump.json lists every file+field that holds a
version string. The canonical current version is read from package.json.

Usage:
  bump-version.py <new-version>   Set the version in every declared file (text replace).
  bump-version.py --check         Print each file's version; exit 1 on any drift.

Examples:
  python scripts/bump-version.py 0.0.2
  python scripts/bump-version.py --check
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / ".version-bump.json"


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def read_field(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        cur = cur[int(part)] if part.isdigit() else cur[part]
    return cur


def current_version():
    return json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]


def cmd_bump(new):
    old = current_version()
    cfg = load_config()
    changed = []
    for entry in cfg["files"]:
        p = ROOT / entry["path"]
        text = p.read_text(encoding="utf-8")
        # Match "version": "OLD" with flexible whitespace; preserves formatting.
        pattern = re.compile(r'("version"\s*:\s*")' + re.escape(old) + r'(")')
        new_text, n = pattern.subn(lambda m: m.group(1) + new + m.group(2), text)
        if n == 0:
            print(f"  WARN: version '{old}' not found in {entry['path']}")
        else:
            p.write_text(new_text, encoding="utf-8")
            changed.append(entry["path"])
    print(f"bumped {old} -> {new} in {len(changed)}/{len(cfg['files'])} files:")
    for c in changed:
        print(f"  - {c}")


def cmd_check():
    cfg = load_config()
    ref = current_version()
    print(f"canonical version (package.json): {ref}")
    drift = False
    for entry in cfg["files"]:
        p = ROOT / entry["path"]
        data = json.loads(p.read_text(encoding="utf-8"))
        v = read_field(data, entry["field"])
        ok = v == ref
        print(f"  {'OK  ' if ok else 'DRIFT'} {entry['path']} ({entry['field']}) = {v}")
        drift = drift or not ok
    sys.exit(1 if drift else 0)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    if args[0] == "--check":
        cmd_check()
    else:
        cmd_bump(args[0])
