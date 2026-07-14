#!/usr/bin/env python3
"""teach-me archive layer — mirror learning records to external tools.

Usage:
    python archive.py                  # config: ~/.teach-me/config.json
    python archive.py --config PATH    # explicit config (used by tests)
    python archive.py --dry-run        # print what would happen, write nothing

Reads records from <root>/records/<topic>/<concept>.md and mirrors them to every
destination configured under config.json's "archive" section:

    {
      "root": "~/.teach-me",
      "archive": {
        "obsidian": { "vault_path": "D:/vault", "folder": "teach-me" }
      }
    }

A destination that is not configured is never touched (config = consent).
One-way mirror: records are the single source of truth; nothing is read back.
Best-effort contract: every failure degrades to a one-line note and exit code 0 —
archiving must never block teaching.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_CONFIG = Path("~/.teach-me/config.json").expanduser()


# ------------------------------------------------------------------ records

def parse_frontmatter(text: str) -> dict:
    """Flat `key: value` frontmatter parser — records only, not full YAML."""
    if not text.startswith("---"):
        return {}
    fm: dict[str, str] = {}
    for line in text.split("\n")[1:]:
        if line.strip() == "---":
            break
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, value = line.partition(":")
            fm[key.strip()] = value.split("#", 1)[0].strip().strip('"')
    return fm


def load_records(root: Path) -> list[dict]:
    records = []
    records_dir = root / "records"
    if not records_dir.is_dir():
        return records
    for path in sorted(records_dir.glob("*/*.md")):
        text = path.read_text(encoding="utf-8")
        records.append({
            "topic": path.parent.name,
            "concept": path.stem,
            "frontmatter": parse_frontmatter(text),
            "text": text,
        })
    return records


# ---------------------------------------------------------------- exporters

class Exporter:
    """One archive destination. Adding a destination = adding one subclass
    and listing it in EXPORTERS."""

    name = "base"

    def available(self, cfg: dict) -> tuple[bool, str]:
        """Can this exporter run with this config? (ok, reason-if-not)."""
        raise NotImplementedError

    def export(self, records: list[dict], cfg: dict, root: Path,
               dry_run: bool) -> str:
        """Idempotent mirror; returns a one-line summary."""
        raise NotImplementedError


class ObsidianExporter(Exporter):
    """A vault is a folder of markdown — mirroring = writing files into it.
    Works with Obsidian closed; the app indexes on next open."""

    name = "obsidian"

    def available(self, cfg):
        vault = cfg.get("vault_path", "")
        if not vault:
            return False, "vault_path not set"
        if not Path(vault).expanduser().is_dir():
            return False, f"vault_path does not exist: {vault}"
        return True, ""

    def export(self, records, cfg, root, dry_run):
        folder = Path(cfg["vault_path"]).expanduser() / cfg.get("folder", "teach-me")
        for record in records:
            dest = folder / record["topic"] / (record["concept"] + ".md")
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(record["text"], encoding="utf-8")
        return f"{len(records)} notes mirrored to {folder}"


EXPORTERS: list[Exporter] = [ObsidianExporter()]


# --------------------------------------------------------------------- main

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="config.json path (default: ~/.teach-me/config.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would happen; write nothing")
    args = parser.parse_args(argv)

    if not args.config.is_file():
        print("archive: no config.json — nothing to do")
        return 0
    try:
        cfg = json.loads(args.config.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as err:
        print(f"archive: unreadable config ({err}) — nothing to do")
        return 0

    destinations = cfg.get("archive") or {}
    if not destinations:
        print("archive: no destinations configured — nothing to do")
        return 0

    root = Path(cfg.get("root", "~/.teach-me")).expanduser()
    records = load_records(root)

    for exporter in EXPORTERS:
        dest_cfg = destinations.get(exporter.name)
        if dest_cfg is None:
            continue  # not configured = no consent = never touched
        ok, reason = exporter.available(dest_cfg)
        if not ok:
            print(f"{exporter.name}: skipped ({reason})")
            continue
        try:
            summary = exporter.export(records, dest_cfg, root, args.dry_run)
            prefix = "[dry-run] " if args.dry_run else ""
            print(f"{exporter.name}: {prefix}{summary}")
        except Exception as err:  # best-effort: teaching is never blocked
            print(f"{exporter.name}: failed ({err}) — teaching is unaffected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
