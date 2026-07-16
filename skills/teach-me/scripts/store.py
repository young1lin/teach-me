#!/usr/bin/env python3
"""Deterministic teach-me learning-store operations.

This script owns low-freedom persistence details that agents should not hand-write:
configuration discovery, slugging, frontmatter serialization, atomic writes, and
coarse file locking.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1
DEFAULT_HOME = Path("~/.teach-me").expanduser()
CONFIG_NAME = "config.json"
SLUG_KEEP_RE = re.compile(r"[^\w.-]+", re.UNICODE)
EDGE_RE = re.compile(r"^[._-]+|[._-]+$")
DATED_RECORD_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(?P<concept>.+)$")
DEFAULT_LOCK_TIMEOUT_S = 10.0
DEFAULT_STALE_LOCK_S = 30 * 60


def teach_home() -> Path:
    """Return the discovery home, honoring TEACH_ME_HOME when set."""
    raw = os.environ.get("TEACH_ME_HOME") or str(DEFAULT_HOME)
    return Path(raw).expanduser()


def config_path() -> Path:
    return teach_home() / CONFIG_NAME


def load_config(path: Path | None = None) -> dict:
    path = path or config_path()
    if not path.exists():
        return {"root": str(teach_home())}
    with path.open(encoding="utf-8") as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"config must be an object: {path}")
    cfg.setdefault("root", str(teach_home()))
    return cfg


def root_from_config(cfg: dict) -> Path:
    return Path(str(cfg.get("root") or teach_home())).expanduser()


def init_store(root: str | None = None, path: Path | None = None) -> dict:
    """Initialize or update config without dropping existing archive/custom fields."""
    path = path or config_path()
    cfg: dict = {}
    if path.exists():
        with path.open(encoding="utf-8") as f:
            existing = json.load(f)
        if not isinstance(existing, dict):
            raise ValueError(f"config must be an object: {path}")
        cfg.update(existing)
    if root is not None or "root" not in cfg:
        selected = Path(root).expanduser() if root else teach_home()
        cfg["root"] = str(selected)
    cfg["schema_version"] = SCHEMA_VERSION
    atomic_write_json(path, cfg)
    return cfg


def slugify(value: str) -> str:
    """Make a portable, deterministic slug while preserving Unicode words."""
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    normalized = normalized.replace("+", " plus ").replace("&", " and ")
    normalized = SLUG_KEEP_RE.sub("-", normalized)
    normalized = re.sub(r"[-_]{2,}", "-", normalized)
    normalized = EDGE_RE.sub("", normalized)
    if normalized in {"", ".", ".."}:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
        return f"item-{digest}"
    return normalized[:120]


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(text)
        Path(tmp_name).replace(path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, data: dict) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _lock_is_stale(path: Path, stale_after: float) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        created = float(payload.get("created", 0))
    except Exception:
        try:
            created = path.stat().st_mtime
        except OSError:
            return False
    return time.time() - created > stale_after


@contextlib.contextmanager
def file_lock(
    path: Path,
    timeout: float = DEFAULT_LOCK_TIMEOUT_S,
    stale_after: float = DEFAULT_STALE_LOCK_S,
) -> Iterator[None]:
    """Coarse cross-process lock using exclusive lock-file creation.

    Stale lock files are removed after `stale_after` seconds so a crashed writer
    does not permanently prevent future saves.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    fd: int | None = None
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            payload = json.dumps({"pid": os.getpid(), "created": time.time()})
            os.write(fd, payload.encode("utf-8"))
            break
        except FileExistsError:
            if _lock_is_stale(path, stale_after):
                path.unlink(missing_ok=True)
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for lock: {path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        path.unlink(missing_ok=True)


def frontmatter(data: dict) -> str:
    """Serialize frontmatter as JSON values to avoid YAML quoting pitfalls."""
    lines = ["---"]
    for key in sorted(data):
        lines.append(f"{key}: {json.dumps(data[key], ensure_ascii=False, sort_keys=True)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    fm: dict = {}
    for line in text.split("\n")[1:]:
        if line.strip() == "---":
            break
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, _, value = line.partition(":")
        raw = value.strip()
        try:
            fm[key.strip()] = json.loads(raw)
        except json.JSONDecodeError:
            fm[key.strip()] = raw.split("#", 1)[0].strip().strip('"')
    return fm


def frontmatter_from_file(path: Path) -> dict:
    try:
        return parse_frontmatter(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, OSError):
        return {}


def frontmatter_date(path: Path) -> str:
    return str(frontmatter_from_file(path).get("date", ""))


def read_body_arg(value: str) -> str:
    if value == "-":
        return sys.stdin.read()
    p = Path(value)
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return value


def record_path(root: Path, topic: str, concept: str) -> Path:
    return root / "records" / slugify(topic) / f"{slugify(concept)}.md"


def checkpoint_path(root: Path, topic: str, date: str | None = None, project: str | None = None) -> Path:
    if topic == "-":
        checkpoint_date = date or dt.date.today().isoformat()
        project_slug = slugify(project or "session")
        return root / "checkpoints" / f"{checkpoint_date}-{project_slug}.md"
    return root / "checkpoints" / f"{slugify(topic)}.md"


def save_record(args: argparse.Namespace) -> Path:
    cfg = load_config(args.config)
    root = root_from_config(cfg)
    topic_slug = slugify(args.topic)
    concept_slug = slugify(args.concept)
    path = record_path(root, args.topic, args.concept)
    fm = {
        "schema_version": SCHEMA_VERSION,
        "date": args.date or dt.date.today().isoformat(),
        "kind": args.kind,
        "project": args.project,
        "topic": topic_slug,
        "concept": concept_slug,
        "state": args.state,
        "evidence": {"E1": args.e1, "E2": args.e2, "E3": args.e3},
    }
    text = frontmatter(fm) + read_body_arg(args.body).rstrip() + "\n"
    with file_lock(path.with_suffix(path.suffix + ".lock")):
        atomic_write_text(path, text)
    return path


def save_checkpoint(args: argparse.Namespace) -> Path:
    cfg = load_config(args.config)
    root = root_from_config(cfg)
    date = args.date or dt.date.today().isoformat()
    path = checkpoint_path(root, args.topic, date=date, project=args.project)
    fm = {
        "schema_version": SCHEMA_VERSION,
        "kind": "checkpoint",
        "date": date,
        "topic": slugify(args.topic) if args.topic != "-" else "-",
        "project": args.project,
        "mode": args.mode,
        "goal": args.goal,
        "concepts": json.loads(args.concepts_json),
        "misconception": args.misconception,
        "next_step": args.next_step,
    }
    text = frontmatter(fm) + read_body_arg(args.body).rstrip() + "\n"
    with file_lock(path.with_suffix(path.suffix + ".lock")):
        atomic_write_text(path, text)
    return path


def list_topics(args: argparse.Namespace) -> list[str]:
    cfg = load_config(args.config)
    records = root_from_config(cfg) / "records"
    if not records.is_dir():
        return []
    return sorted(p.name for p in records.iterdir() if p.is_dir())


def resume(args: argparse.Namespace) -> list[Path]:
    cfg = load_config(args.config)
    root = root_from_config(cfg)
    if args.topic == "-":
        # No-topic debrief checkpoints are saved as <date>-<project>.md; their
        # date/project are not known at resume time, so pick the most recent
        # dated checkpoint rather than reconstructing a name from today's date.
        checkpoints = root / "checkpoints"
        if checkpoints.is_dir():
            debriefs = sorted(p for p in checkpoints.glob("*.md")
                              if DATED_RECORD_RE.match(p.stem))
            if debriefs:
                return [debriefs[-1]]
        return []
    cp = checkpoint_path(root, args.topic)
    if cp.is_file():
        return [cp]
    rec_dir = root / "records" / slugify(args.topic)
    if rec_dir.is_dir():
        return sorted(rec_dir.glob("*.md"))
    return []


def destination_for_legacy(root: Path, old: Path) -> Path:
    name = old.stem
    if old.name.endswith("--checkpoint.md"):
        return root / "checkpoints" / old.name.replace("--checkpoint", "")

    fm = frontmatter_from_file(old)
    topic = str(fm.get("topic") or "").strip()
    concept = str(fm.get("concept") or "").strip()

    if "--" in name:
        topic_from_name, _, concept_from_name = name.partition("--")
        topic = topic or topic_from_name
        concept = concept or concept_from_name
    else:
        m = DATED_RECORD_RE.match(name)
        if m:
            concept = concept or m.group("concept")
        else:
            concept = concept or name
        topic = topic or "legacy"

    return root / "records" / slugify(topic) / f"{slugify(concept)}.md"


def copy_if_newer(src: Path, dest: Path) -> bool:
    if dest.exists() and frontmatter_date(dest) >= frontmatter_date(src):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def migrate(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    root = root_from_config(cfg)
    moved = 0
    for src_root in args.legacy_root:
        src = Path(src_root).expanduser()
        if not src.is_dir():
            continue
        for old in sorted(src.rglob("*.md")):
            dest = destination_for_legacy(root, old)
            if copy_if_newer(old, dest):
                moved += 1
    return moved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", type=Path, help="config path; defaults to ${TEACH_ME_HOME:-~/.teach-me}/config.json")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--root")

    sub.add_parser("list-topics")

    p = sub.add_parser("save-record")
    p.add_argument("--topic", required=True)
    p.add_argument("--concept", required=True)
    p.add_argument("--body", required=True, help="literal body, file path, or '-' for stdin")
    p.add_argument("--state", default="demonstrated", choices=["learning", "unstable", "demonstrated", "retained", "stale"])
    p.add_argument("--kind", default="topic", choices=["topic", "debrief"])
    p.add_argument("--project", default="-")
    p.add_argument("--date")
    p.add_argument("--e1", default="passed")
    p.add_argument("--e2", default="passed")
    p.add_argument("--e3", default="passed")

    p = sub.add_parser("save-checkpoint")
    p.add_argument("--topic", required=True)
    p.add_argument("--goal", required=True)
    p.add_argument("--body", required=True, help="literal body, file path, or '-' for stdin")
    p.add_argument("--mode", default="socratic", choices=["socratic", "feynman", "drill"])
    p.add_argument("--concepts-json", default="[]")
    p.add_argument("--misconception", default="")
    p.add_argument("--next-step", default="")
    p.add_argument("--project", default="-")
    p.add_argument("--date")

    p = sub.add_parser("resume")
    p.add_argument("--topic", default="-", help="topic to resume; omit for the latest no-topic debrief")

    p = sub.add_parser("migrate")
    p.add_argument("legacy_root", nargs="*")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.cmd == "init":
            cfg = init_store(args.root, args.config)
            print(json.dumps(cfg, ensure_ascii=False, sort_keys=True))
        elif args.cmd == "list-topics":
            print("\n".join(list_topics(args)))
        elif args.cmd == "save-record":
            print(save_record(args))
        elif args.cmd == "save-checkpoint":
            print(save_checkpoint(args))
        elif args.cmd == "resume":
            found = resume(args)
            if not found:
                print("not found")
                return 1
            print("\n".join(str(path) for path in found))
        elif args.cmd == "migrate":
            print(migrate(args))
    except Exception as err:
        print(f"store: failed ({err})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
