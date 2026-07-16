#!/usr/bin/env python3
"""teach-me archive layer — copy/update learning records to external tools.

Usage:
    python archive.py                  # config: ${TEACH_ME_HOME:-~/.teach-me}/config.json
    python archive.py --config PATH    # explicit config (used by tests)
    python archive.py --dry-run        # print what would happen, write nothing

Reads records from <root>/records/<topic>/<concept>.md and copies/updates them to every
destination configured under config.json's "archive" section:

    {
      "root": "~/.teach-me",
      "archive": {
        "obsidian": { "vault_path": "D:/vault", "folder": "teach-me" }
      }
    }

A destination that is not configured is never touched (config = consent).
One-way copy/update: records are the single source of truth; nothing is read back.
Best-effort contract: every failure degrades to a one-line note and exit code 0 —
archiving must never block teaching.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

DEFAULT_HOME = Path("~/.teach-me").expanduser()
CONFIG_NAME = "config.json"


def default_config() -> Path:
    raw = os.environ.get("TEACH_ME_HOME") or str(DEFAULT_HOME)
    return Path(raw).expanduser() / CONFIG_NAME


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
    try:
        if not records_dir.is_dir():
            return records
        paths = sorted(records_dir.glob("*/*.md"))
    except OSError as err:
        print(f"archive: unreadable records root ({err}) — nothing to do")
        return records
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as err:
            print(f"archive: skipped unreadable record {path} ({err})")
            continue
        records.append({
            "topic": path.parent.name,
            "concept": path.stem,
            "frontmatter": parse_frontmatter(text),
            "text": text,
        })
    return records


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(text)
        Path(tmp_name).replace(path)
    except Exception:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        finally:
            raise


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
        """Idempotent copy/update; returns a one-line summary."""
        raise NotImplementedError


class ObsidianExporter(Exporter):
    """A vault is a folder of markdown — copy/update = writing files into it.
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
                atomic_write_text(dest, record["text"])
        return f"{len(records)} notes copied/updated to {folder}"


EXPORTERS: list[Exporter] = [ObsidianExporter()]


# --------------------------------------------------------------------- main

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", type=Path,
                        help="config.json path (default: ${TEACH_ME_HOME:-~/.teach-me}/config.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would happen; write nothing")
    args = parser.parse_args(argv)

    config = args.config or default_config()

    if not config.is_file():
        print("archive: no config.json — nothing to do")
        return 0
    try:
        cfg = json.loads(config.read_text(encoding="utf-8"))
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
