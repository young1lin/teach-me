"""Tests for the deterministic teach-me store script."""
import importlib.util
import json
import sys
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


def test_init_uses_teach_me_home(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setenv("TEACH_ME_HOME", str(home))
    cfg = store.init_store()
    assert cfg["root"] == str(home)
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


def test_save_checkpoint_and_resume(tmp_path):
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
    assert found == root / "checkpoints" / "tcp.md"
