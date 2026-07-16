"""Tests for skills/teach-me/scripts/archive.py (Obsidian copy/update)."""
import importlib.util
import json
import sys
from pathlib import Path

# Load archive.py without dropping a __pycache__ into the skill directory
# (validate_skill.py rejects compiled-python cruft inside skills/teach-me/).
sys.dont_write_bytecode = True
ARCHIVE_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills" / "teach-me" / "scripts" / "archive.py"
)
_spec = importlib.util.spec_from_file_location("archive", ARCHIVE_PATH)
archive = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(archive)

RECORD = """---
date: 2026-07-14
kind: topic
project: "-"
topic: tcp
concept: congestion-window
state: demonstrated
evidence: {E1: passed, E2: passed, E3: passed}
---
## What was demonstrated
cwnd grows by one MSS per RTT in congestion avoidance.
## Key misconception fixed
Confused cwnd with rwnd.
## Transfer task passed
Explained slow start on a satellite link.
## Review question (self-test prompt)
Why does congestion avoidance grow cwnd linearly instead of doubling it?
"""


def make_store(tmp_path, archive_cfg):
    """A store with one record + a config.json pointing at it."""
    root = tmp_path / "store"
    rec = root / "records" / "tcp" / "congestion-window.md"
    rec.parent.mkdir(parents=True)
    rec.write_text(RECORD, encoding="utf-8")
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"root": str(root), "archive": archive_cfg}), encoding="utf-8"
    )
    return root, config


def test_missing_config_is_noop(tmp_path):
    assert archive.main(["--config", str(tmp_path / "absent.json")]) == 0


def test_no_archive_section_is_noop(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"root": str(tmp_path)}), encoding="utf-8")
    assert archive.main(["--config", str(config)]) == 0


def test_parse_frontmatter():
    fm = archive.parse_frontmatter(RECORD)
    assert fm["topic"] == "tcp"
    assert fm["concept"] == "congestion-window"
    assert fm["state"] == "demonstrated"


def test_obsidian_copy_update(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    _, config = make_store(tmp_path, {"obsidian": {"vault_path": str(vault)}})
    assert archive.main(["--config", str(config)]) == 0
    dest = vault / "teach-me" / "tcp" / "congestion-window.md"
    assert dest.read_text(encoding="utf-8") == RECORD


def test_obsidian_missing_vault_degrades_to_exit_0(tmp_path):
    _, config = make_store(
        tmp_path, {"obsidian": {"vault_path": str(tmp_path / "nowhere")}}
    )
    assert archive.main(["--config", str(config)]) == 0


def test_dry_run_writes_nothing(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    _, config = make_store(tmp_path, {"obsidian": {"vault_path": str(vault)}})
    assert archive.main(["--config", str(config), "--dry-run"]) == 0
    assert not (vault / "teach-me").exists()


def test_bad_root_type_degrades_to_exit_0(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    root_file = tmp_path / "not-a-directory"
    root_file.write_text("not a directory", encoding="utf-8")
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"root": str(root_file), "archive": {"obsidian": {"vault_path": str(vault)}}}),
        encoding="utf-8",
    )
    assert archive.main(["--config", str(config)]) == 0


def test_unreadable_record_is_skipped(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    root, config = make_store(tmp_path, {"obsidian": {"vault_path": str(vault)}})
    bad = root / "records" / "tcp" / "bad.md"
    bad.write_bytes(b"\xff\xfe")
    assert archive.main(["--config", str(config)]) == 0
    assert (vault / "teach-me" / "tcp" / "congestion-window.md").is_file()
    assert not (vault / "teach-me" / "tcp" / "bad.md").exists()
