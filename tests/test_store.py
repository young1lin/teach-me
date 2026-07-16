"""Tests for the deterministic teach-me store script."""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
STORE_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills" / "teach-me" / "scripts" / "store.py"
)
_spec = importlib.util.spec_from_file_location("store", STORE_PATH)
store = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(store)


def test_slugify_handles_symbols_unicode_and_empty():
    assert store.slugify("C++ / RAII: 析构") == "c-plus-plus-raii-析构"
    assert store.slugify("  HTTP retries  ") == "http-retries"
    assert store.slugify("///").startswith("item-")


def test_init_uses_teach_me_home_and_preserves_existing_fields(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setenv("TEACH_ME_HOME", str(home))
    home.mkdir()
    (home / "config.json").write_text(
        json.dumps({"root": str(tmp_path / "old"), "archive": {"obsidian": {"vault_path": "vault"}}}),
        encoding="utf-8",
    )
    cfg = store.init_store(root=str(tmp_path / "new"))
    assert cfg["root"] == str(tmp_path / "new")
    assert cfg["archive"] == {"obsidian": {"vault_path": "vault"}}
    assert (home / "config.json").is_file()


def test_save_record_serializes_json_frontmatter(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")

    path = store.main([
        "--config", str(config),
        "save-record",
        "--topic", "C++ / RAII",
        "--concept", "destructor: scope #1",
        "--body", "## What was demonstrated\nValues with : and # stay safe.",
        "--project", "demo",
        "--date", "2026-07-16",
    ])
    assert path == 0

    record = root / "records" / "c-plus-plus-raii" / "destructor-scope-1.md"
    text = record.read_text(encoding="utf-8")
    assert 'schema_version: 1' in text
    assert 'state: "demonstrated"' in text
    assert 'concept: "destructor-scope-1"' in text
    assert "Values with : and # stay safe." in text


def test_save_checkpoint_and_resume_returns_checkpoint(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    assert store.main([
        "--config", str(config),
        "save-checkpoint",
        "--topic", "tcp",
        "--goal", "Explain cwnd",
        "--concepts-json", '[{"name":"cwnd","state":"unstable"}]',
        "--body", "## Learning checkpoint\nNext: transfer.",
    ]) == 0
    found = store.resume(type("Args", (), {"config": config, "topic": "tcp"})())
    assert found == [root / "checkpoints" / "tcp.md"]


def test_resume_returns_all_topic_records_when_checkpoint_missing(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    for concept in ["a", "b"]:
        assert store.main([
            "--config", str(config),
            "save-record",
            "--topic", "tcp",
            "--concept", concept,
            "--body", "body",
        ]) == 0
    found = store.resume(type("Args", (), {"config": config, "topic": "tcp"})())
    assert found == [root / "records" / "tcp" / "a.md", root / "records" / "tcp" / "b.md"]


def test_no_topic_debrief_checkpoint_uses_date_project_name(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    assert store.main([
        "--config", str(config),
        "save-checkpoint",
        "--topic", "-",
        "--project", "teach-me repo",
        "--date", "2026-07-16",
        "--goal", "Debrief session",
        "--body", "checkpoint",
    ]) == 0
    assert (root / "checkpoints" / "2026-07-16-teach-me-repo.md").is_file()


def test_migrate_uses_frontmatter_topic_for_dated_records_and_newer_collision(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    old = legacy / "2026-07-01-congestion-window.md"
    old.write_text('---\ndate: "2026-07-01"\ntopic: "tcp"\n---\nold\n', encoding="utf-8")
    dest = root / "records" / "tcp" / "congestion-window.md"
    dest.parent.mkdir(parents=True)
    dest.write_text('---\ndate: "2026-07-02"\ntopic: "tcp"\n---\nnewer\n', encoding="utf-8")
    assert store.main(["--config", str(config), "migrate", str(legacy)]) == 0
    assert dest.read_text(encoding="utf-8").endswith("newer\n")

    newer = legacy / "2026-07-03-congestion-window.md"
    newer.write_text('---\ndate: "2026-07-03"\ntopic: "tcp"\n---\nnewest\n', encoding="utf-8")
    assert store.main(["--config", str(config), "migrate", str(legacy)]) == 0
    assert dest.read_text(encoding="utf-8").endswith("newest\n")


def test_file_lock_removes_stale_lock(tmp_path):
    lock = tmp_path / "record.md.lock"
    lock.write_text(json.dumps({"pid": 999999, "created": time.time() - 100}), encoding="utf-8")
    with store.file_lock(lock, timeout=0.1, stale_after=1):
        assert lock.is_file()
    assert not lock.exists()
