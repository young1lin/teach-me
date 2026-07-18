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


def test_resume_no_topic_finds_latest_debrief_checkpoint(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    for date, proj in [("2026-07-15", "teach-me"), ("2026-07-16", "other repo")]:
        assert store.main([
            "--config", str(config), "save-checkpoint",
            "--topic", "-", "--project", proj, "--date", date,
            "--goal", "Debrief", "--body", f"checkpoint {date}",
        ]) == 0
    # topic "-" must find the saved debrief (not reconstruct today's date/"session")
    found = store.resume(type("Args", (), {"config": config, "topic": "-"})())
    assert found == [root / "checkpoints" / "2026-07-16-other-repo.md"]


def test_resume_subcommand_does_not_require_topic(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    assert store.main([
        "--config", str(config), "save-checkpoint",
        "--topic", "-", "--project", "p", "--date", "2026-07-16",
        "--goal", "g", "--body", "b",
    ]) == 0
    # `resume` with no --topic must succeed (default "-"), not argparse-error
    assert store.main(["--config", str(config), "resume"]) == 0


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


def test_due_on_uses_ladder_intervals():
    assert store.due_on("2026-07-16", 1) == "2026-07-17"   # +1
    assert store.due_on("2026-07-16", 2) == "2026-07-19"   # +3
    assert store.due_on("2026-07-16", 5) == "2026-09-14"   # +60
    # box past the top clamps to the last interval (60), never raises
    assert store.due_on("2026-07-16", 9) == "2026-09-14"


def test_next_box_promotes_on_pass_and_resets_on_fail():
    assert store.next_box(1, "pass") == 2
    assert store.next_box(4, "pass") == 5
    assert store.next_box(5, "pass") == 5      # capped at len(LADDER)
    assert store.next_box(3, "fail") == 1
    assert store.next_box(1, "fail") == 1


def test_review_state_maps_result():
    assert store.review_state("pass") == "retained"
    assert store.review_state("fail") == "stale"


def test_save_record_persists_deps_and_initializes_schedule(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    assert store.main([
        "--config", str(config), "save-record",
        "--topic", "tcp", "--concept", "cwnd",
        "--body", "b", "--date", "2026-07-16",
        "--deps", "slow-start, ack-clocking",
    ]) == 0
    text = (root / "records" / "tcp" / "cwnd.md").read_text(encoding="utf-8")
    fm = store.parse_frontmatter(text)
    assert fm["deps"] == ["slow-start", "ack-clocking"]
    assert fm["box"] == 1
    assert fm["last_reviewed"] == "2026-07-16"
    assert fm["review_count"] == 0


def test_save_record_defaults_deps_to_empty_list(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    assert store.main([
        "--config", str(config), "save-record",
        "--topic", "tcp", "--concept", "cwnd", "--body", "b",
    ]) == 0
    fm = store.parse_frontmatter((root / "records" / "tcp" / "cwnd.md").read_text(encoding="utf-8"))
    assert fm["deps"] == []


def _saved_record(tmp_path, deps=""):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    store.main([
        "--config", str(config), "save-record",
        "--topic", "tcp", "--concept", "cwnd",
        "--body", "## Review question (self-test prompt)\nWhy linear?",
        "--date", "2026-07-16", "--deps", deps,
    ])
    return config, root


def test_review_pass_promotes_box_and_marks_retained(tmp_path):
    config, root = _saved_record(tmp_path, deps="slow-start")
    assert store.main([
        "--config", str(config), "review",
        "--topic", "tcp", "--concept", "cwnd",
        "--result", "pass", "--date", "2026-07-18",
    ]) == 0
    fm = store.parse_frontmatter((root / "records" / "tcp" / "cwnd.md").read_text(encoding="utf-8"))
    assert fm["box"] == 2
    assert fm["state"] == "retained"
    assert fm["last_reviewed"] == "2026-07-18"
    assert fm["review_count"] == 1
    assert fm["deps"] == ["slow-start"]          # preserved
    text = (root / "records" / "tcp" / "cwnd.md").read_text(encoding="utf-8")
    assert "Why linear?" in text                  # body preserved


def test_review_fail_resets_box_and_marks_stale(tmp_path):
    config, root = _saved_record(tmp_path)
    assert store.main([
        "--config", str(config), "review",
        "--topic", "tcp", "--concept", "cwnd", "--result", "fail",
    ]) == 0
    fm = store.parse_frontmatter((root / "records" / "tcp" / "cwnd.md").read_text(encoding="utf-8"))
    assert fm["box"] == 1
    assert fm["state"] == "stale"
    assert fm["review_count"] == 1


def test_review_missing_record_exits_1(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"root": str(tmp_path / "learn")}), encoding="utf-8")
    assert store.main([
        "--config", str(config), "review",
        "--topic", "tcp", "--concept", "nope", "--result", "pass",
    ]) == 1


def _save(config, topic, concept, date, state="demonstrated", deps=""):
    store.main([
        "--config", str(config), "save-record",
        "--topic", topic, "--concept", concept, "--body", "b",
        "--date", date, "--state", state, "--deps", deps,
    ])


def _due_lines(config, on):
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        store.main(["--config", str(config), "due", "--on", on])
    return [ln for ln in buf.getvalue().splitlines() if ln]


def test_due_selects_only_records_past_their_interval(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    _save(config, "tcp", "cwnd", "2026-07-16")     # box 1 -> due 2026-07-17
    _save(config, "tcp", "nagle", "2026-07-20")    # box 1 -> due 2026-07-21
    lines = _due_lines(config, on="2026-07-18")
    concepts = [ln.split("\t")[1] for ln in lines]
    assert concepts == ["cwnd"]                    # nagle not yet due


def test_due_treats_schedule_less_demonstrated_record_as_due_now(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    rec = root / "records" / "tcp" / "legacy.md"
    rec.parent.mkdir(parents=True)
    rec.write_text('---\nstate: "demonstrated"\ntopic: "tcp"\nconcept: "legacy"\n---\nbody\n',
                   encoding="utf-8")
    lines = _due_lines(config, on="2020-01-01")
    assert [ln.split("\t")[1] for ln in lines] == ["legacy"]


def test_save_record_preserves_deps_and_review_count_on_resave(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    store.main(["--config", str(config), "save-record", "--topic", "tcp", "--concept", "cwnd",
                "--body", "b", "--date", "2026-07-16", "--deps", "slow-start"])
    store.main(["--config", str(config), "review", "--topic", "tcp", "--concept", "cwnd",
                "--result", "pass", "--date", "2026-07-17"])
    # re-save WITHOUT --deps: deps + review_count survive; box resets to 1
    store.main(["--config", str(config), "save-record", "--topic", "tcp", "--concept", "cwnd",
                "--body", "b2", "--date", "2026-07-18"])
    fm = store.parse_frontmatter((root / "records" / "tcp" / "cwnd.md").read_text(encoding="utf-8"))
    assert fm["deps"] == ["slow-start"]
    assert fm["review_count"] == 1
    assert fm["box"] == 1
    assert fm["last_reviewed"] == "2026-07-18"


def test_review_writes_schedule_fields_onto_schedule_less_record(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    rec = root / "records" / "tcp" / "legacy.md"
    rec.parent.mkdir(parents=True)
    rec.write_text('---\nstate: "demonstrated"\ntopic: "tcp"\nconcept: "legacy"\n---\n## body\nkeep me\n',
                   encoding="utf-8")
    assert store.main(["--config", str(config), "review", "--topic", "tcp",
                       "--concept", "legacy", "--result", "pass", "--date", "2026-07-17"]) == 0
    fm = store.parse_frontmatter(rec.read_text(encoding="utf-8"))
    assert fm["box"] == 2
    assert fm["state"] == "retained"
    assert fm["last_reviewed"] == "2026-07-17"
    assert fm["review_count"] == 1
    assert "keep me" in rec.read_text(encoding="utf-8")


def test_due_orders_prerequisite_before_dependent(tmp_path):
    config = tmp_path / "config.json"
    root = tmp_path / "learn"
    config.write_text(json.dumps({"root": str(root)}), encoding="utf-8")
    # cwnd depends on slow-start; both due. slow-start must come first even though
    # cwnd is more overdue.
    _save(config, "tcp", "cwnd", "2026-07-10", deps="slow-start")
    _save(config, "tcp", "slow-start", "2026-07-14")
    lines = _due_lines(config, on="2026-07-20")
    assert [ln.split("\t")[1] for ln in lines] == ["slow-start", "cwnd"]
