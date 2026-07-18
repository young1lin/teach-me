import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "evals"))
import seed  # noqa: E402
import store  # noqa: E402  (seed put skills/teach-me/scripts on sys.path)

STORE = REPO / "skills" / "teach-me" / "scripts" / "store.py"
SPEC = [{"topic": "python-async", "concept": "event-loop", "state": "demonstrated",
         "review_question": "Without looking, explain what the event loop does at await."}]


def _store(config, *args):
    return subprocess.run([sys.executable, str(STORE), "--config", str(config), *args],
                          capture_output=True, text=True, check=True)


def test_seeded_record_is_due_and_reviewable():
    with seed.seeded_home(SPEC) as home:
        cfg = home / "config.json"
        listed = _store(cfg, "due").stdout
        assert "event-loop" in listed and "python-async" in listed
        _store(cfg, "review", "--topic", "python-async", "--concept", "event-loop",
               "--result", "pass")
        rec = (home / "records" / "python-async" / "event-loop.md").read_text(encoding="utf-8")
        fm, _ = store.split_record(rec)
        assert fm["state"] == "retained" and fm["review_count"] == 1 and fm["box"] == 2


def test_seed_body_has_self_test_section():
    with seed.seeded_home(SPEC) as home:
        text = (home / "records" / "python-async" / "event-loop.md").read_text(encoding="utf-8")
        assert "## Review question (self-test prompt)" in text
        assert "event loop does at await" in text


def test_homes_are_isolated_and_cleaned_up():
    with seed.seeded_home(SPEC) as h1:
        with seed.seeded_home(SPEC) as h2:
            assert h1 != h2 and h1.is_dir() and h2.is_dir()
        assert not h2.exists()
        assert h1.is_dir()
    assert not h1.exists()
