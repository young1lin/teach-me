"""Store seeding for behavioral evals.

Materializes teach-me records into an isolated temp TEACH_ME_HOME so a review
scenario has an already-due concept to quiz on. Reuses store.py's own record
serializer (same repo) so the seeded record can never drift from what the skill
reads; the subprocess round-trip test guards the contract end to end.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Iterator

# Reuse the skill's own record helpers so the seed format matches byte-for-byte.
_STORE_DIR = Path(__file__).resolve().parent.parent / "skills" / "teach-me" / "scripts"
if str(_STORE_DIR) not in sys.path:
    sys.path.insert(0, str(_STORE_DIR))
import store  # noqa: E402


def _record_body(rec: dict) -> str:
    """Body carrying the required self-test section the review flow quizzes with."""
    question = rec["review_question"]
    body = (f"# {rec['concept']}\n\n"
            f"## Review question (self-test prompt)\n\n{question}\n")
    extra = rec.get("body", "").rstrip()
    if extra:
        body += f"\n{extra}\n"
    return body


def write_record(root: Path, rec: dict) -> Path:
    """Write one schedule-less `demonstrated` record -> due now via migration."""
    fm = {
        "schema_version": store.SCHEMA_VERSION,
        "date": rec.get("date", dt.date.today().isoformat()),
        "kind": "topic",
        "project": rec.get("project", "-"),
        "topic": store.slugify(rec["topic"]),
        "concept": store.slugify(rec["concept"]),
        "state": rec.get("state", "demonstrated"),
        "evidence": {"E1": "passed", "E2": "passed", "E3": "passed"},
        "deps": list(rec.get("deps", [])),
        # No box/last_reviewed/review_count: a schedule-less demonstrated record
        # is treated as due now by store.py `due`.
    }
    path = store.record_path(root, rec["topic"], rec["concept"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(store.frontmatter(fm) + _record_body(rec), encoding="utf-8")
    return path


@contextlib.contextmanager
def seeded_home(seed_spec: list[dict]) -> Iterator[Path]:
    """Yield an isolated TEACH_ME_HOME seeded with the given records; clean up after."""
    home = Path(tempfile.mkdtemp(prefix="teachme-eval-"))
    try:
        store.init_store(root=str(home), path=home / "config.json")
        for rec in seed_spec or []:
            write_record(home, rec)
        yield home
    finally:
        shutil.rmtree(home, ignore_errors=True)
