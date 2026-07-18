# teach-me Review & Retention Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add spaced-repetition review, a simple Leitner decay model, and prerequisite (`deps`) persistence to teach-me by activating schema fields the design already anticipates, with a small deterministic engine in `store.py`.

**Architecture:** All schedule math lives in `skills/teach-me/scripts/store.py` as pure helpers plus three CLI surfaces (`save-record --deps`, `due`, `review`). Records under `<root>/records/<topic>/<concept>.md` gain `deps`/`box`/`last_reviewed`/`review_count` frontmatter. The skill's markdown (SKILL.md + references) drives the review *conversation* and the passive due-surfacing; it never computes dates. Testing is the offline deterministic unit suite only.

**Tech Stack:** Python 3.8+ standard library only (`argparse`, `datetime`, `json`, `pathlib`, `tempfile`). Tests run via `uv run --with pytest --with pyyaml python -m pytest -q tests/`.

## Global Constraints

- **Commit author:** every commit authored as `young1lin <2550110827@qq.com>`. Claude credited **only** via trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` — never as author.
- **`store.py` stays standard-library only and Python 3.8+ compatible** (skill script; runs wherever the agent runs, not just the `uv` eval project). No third-party imports.
- **Offline unit suite stays green at every commit:** `uv run --with pytest --with pyyaml python -m pytest -q tests/`.
- **No secrets/PII in tracked files.** Tests use `tmp_path` and `monkeypatch.setenv("TEACH_ME_HOME", ...)`; no usernames, emails, or home paths in tracked content.
- **Leitner ladder is fixed:** `LADDER = [1, 3, 7, 21, 60]` days, `box` is 1-based indexing `LADDER[box - 1]`, capped at `len(LADDER)`.
- **No new CI cost**; the review engine is covered by deterministic offline tests only.
- **Reference spec:** `docs/superpowers/specs/2026-07-16-teach-me-review-retention-design.md`.

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `skills/teach-me/scripts/store.py` | Modify | Schedule primitives + `save-record --deps` + `due` + `review` commands |
| `tests/test_store.py` | Modify | Unit tests for all schedule logic |
| `skills/teach-me/SKILL.md` | Modify | `/teach-me review` command row, `argument-hint`, two Red Flags |
| `skills/teach-me/references/state.md` | Modify | Schedule fields, ladder, `due` computation, `deps`, required review-question section |
| `skills/teach-me/references/flows.md` | Modify | Branch C (review procedure) + passive due-surfacing |
| `skills/teach-me/references/review.md` | Create | Review loop detail (batch cap, fatigue, verdict→pass/fail, fail→relearn, prereq hint) |

---

## Task 1: Leitner schedule primitives

**Files:**
- Modify: `skills/teach-me/scripts/store.py` (add constants + pure helpers near the other module-level helpers, after `record_path`)
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `import datetime as dt` (already imported in store.py).
- Produces:
  - `LADDER: list[int]` — `[1, 3, 7, 21, 60]`.
  - `due_on(last_reviewed: str, box: int) -> str` — ISO date a concept at 1-based `box` last reviewed on ISO `last_reviewed` falls due (`last_reviewed + LADDER[box-1]` days, box clamped to `[1, len(LADDER)]`).
  - `next_box(box: int, result: str) -> int` — `min(box+1, len(LADDER))` for `"pass"`, else `1`.
  - `review_state(result: str) -> str` — `"retained"` for `"pass"`, else `"stale"`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --with pytest --with pyyaml python -m pytest -q tests/test_store.py -k "due_on or next_box or review_state"`
Expected: FAIL with `AttributeError: module 'store' has no attribute 'due_on'`

- [ ] **Step 3: Implement the primitives**

In `skills/teach-me/scripts/store.py`, immediately after the `record_path` function, add:

```python
LADDER = [1, 3, 7, 21, 60]  # spaced-repetition intervals in days (Leitner boxes)


def due_on(last_reviewed: str, box: int) -> str:
    """ISO date a concept at 1-based `box`, last reviewed on `last_reviewed`, falls due."""
    interval = LADDER[max(1, min(box, len(LADDER))) - 1]
    return (dt.date.fromisoformat(last_reviewed) + dt.timedelta(days=interval)).isoformat()


def next_box(box: int, result: str) -> int:
    """Promote one box on a pass (capped at the top), reset to box 1 on a fail."""
    return min(box + 1, len(LADDER)) if result == "pass" else 1


def review_state(result: str) -> str:
    return "retained" if result == "pass" else "stale"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --with pytest --with pyyaml python -m pytest -q tests/test_store.py -k "due_on or next_box or review_state"`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add skills/teach-me/scripts/store.py tests/test_store.py
git commit -m "feat(store): Leitner schedule primitives (ladder, due_on, next_box)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 2: `save-record --deps` and schedule-field initialization

**Files:**
- Modify: `skills/teach-me/scripts/store.py` — `save_record` (currently ~line 214) and its subparser in `build_parser` (currently ~line 336)
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `LADDER` (Task 1); existing `slugify`, `record_path`, `frontmatter`, `read_body_arg`, `file_lock`, `atomic_write_text`.
- Produces: a record whose frontmatter carries `deps` (list), `box` (int, `1`), `last_reviewed` (ISO date = record date), `review_count` (int, `0`). `--deps` accepts a comma-separated list of concept slugs; absent → `[]`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --with pytest --with pyyaml python -m pytest -q tests/test_store.py -k "persists_deps or defaults_deps"`
Expected: FAIL with `KeyError: 'deps'`

- [ ] **Step 3: Add `--deps` to the parser and initialize schedule fields**

In `build_parser`, in the `save-record` subparser block, add after the `--e3` line:

```python
    p.add_argument("--deps", default="", help="comma-separated prerequisite concept slugs")
```

In `save_record`, change the `fm` dict construction. Replace:

```python
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
```

with:

```python
    record_date = args.date or dt.date.today().isoformat()
    deps = [d.strip() for d in args.deps.split(",") if d.strip()]
    fm = {
        "schema_version": SCHEMA_VERSION,
        "date": record_date,
        "kind": args.kind,
        "project": args.project,
        "topic": topic_slug,
        "concept": concept_slug,
        "state": args.state,
        "evidence": {"E1": args.e1, "E2": args.e2, "E3": args.e3},
        "deps": deps,
        "box": 1,
        "last_reviewed": record_date,
        "review_count": 0,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --with pytest --with pyyaml python -m pytest -q tests/test_store.py -k "persists_deps or defaults_deps"`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `uv run --with pytest --with pyyaml python -m pytest -q tests/`
Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add skills/teach-me/scripts/store.py tests/test_store.py
git commit -m "feat(store): save-record --deps and schedule-field initialization

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 3: `store.py review` command

**Files:**
- Modify: `skills/teach-me/scripts/store.py` — add `split_record` helper + `review` function + subparser + `main` dispatch
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `next_box`, `review_state` (Task 1); existing `record_path`, `parse_frontmatter`, `frontmatter`, `atomic_write_text`, `file_lock`.
- Produces:
  - `split_record(text: str) -> tuple[dict, str]` — parsed frontmatter dict + the body text following the closing `---`.
  - CLI `review --topic T --concept C --result {pass|fail} [--date D]` — read the record, update `box`/`state`/`last_reviewed`/`review_count`, preserve `deps`/`evidence`/body, rewrite atomically. Missing record → stderr message, exit 1.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --with pytest --with pyyaml python -m pytest -q tests/test_store.py -k review`
Expected: FAIL (`argument cmd: invalid choice: 'review'` / SystemExit)

- [ ] **Step 3: Add `split_record`, `review`, parser, and dispatch**

In `store.py`, after `parse_frontmatter` (or near the other frontmatter helpers), add:

```python
def split_record(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body after the closing '---')."""
    fm = parse_frontmatter(text)
    lines = text.split("\n")
    seen = 0
    body_start = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == "---":
            seen += 1
            if seen == 2:
                body_start = i + 1
                break
    return fm, "\n".join(lines[body_start:])
```

After `save_checkpoint`, add:

```python
def review(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    root = root_from_config(cfg)
    path = record_path(root, args.topic, args.concept)
    if not path.is_file():
        print(f"store: no record for {slugify(args.topic)}/{slugify(args.concept)}", file=sys.stderr)
        return 1
    fm, body = split_record(path.read_text(encoding="utf-8"))
    box = int(fm.get("box", 1) or 1)
    fm["box"] = next_box(box, args.result)
    fm["state"] = review_state(args.result)
    fm["last_reviewed"] = args.date or dt.date.today().isoformat()
    fm["review_count"] = int(fm.get("review_count", 0) or 0) + 1
    fm.setdefault("deps", [])
    text = frontmatter(fm) + body
    with file_lock(path.with_suffix(path.suffix + ".lock")):
        atomic_write_text(path, text)
    return 0
```

In `build_parser`, after the `resume` subparser, add:

```python
    p = sub.add_parser("review")
    p.add_argument("--topic", required=True)
    p.add_argument("--concept", required=True)
    p.add_argument("--result", required=True, choices=["pass", "fail"])
    p.add_argument("--date")
```

In `main`, add a dispatch branch after the `resume` branch:

```python
        elif args.cmd == "review":
            return review(args)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --with pytest --with pyyaml python -m pytest -q tests/test_store.py -k review`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full suite**

Run: `uv run --with pytest --with pyyaml python -m pytest -q tests/`
Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add skills/teach-me/scripts/store.py tests/test_store.py
git commit -m "feat(store): review command updates Leitner schedule and state

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 4: `store.py due` command (selection, ordering, migration)

**Files:**
- Modify: `skills/teach-me/scripts/store.py` — add `_due_items`, `_order_due`, `due` + subparser + dispatch
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `due_on` (Task 1); existing `frontmatter_from_file`, `load_config`, `root_from_config`.
- Produces: CLI `due [--on DATE] [--limit N]` printing one tab-separated line per due concept: `topic\tconcept\tstate\tbox\tdays_overdue\tpath`. A record with `state` in `{demonstrated, retained, stale}` is due when its computed `due_on(last_reviewed, box) <= on_date`; a record with that state but **no** `last_reviewed` is due now. Ordering: a due prerequisite (matched by `concept` slug) prints before its dependents; ties break by most-overdue, then concept slug.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --with pytest --with pyyaml python -m pytest -q tests/test_store.py -k due`
Expected: FAIL (`argument cmd: invalid choice: 'due'` / SystemExit)

- [ ] **Step 3: Implement selection, ordering, and the command**

In `store.py`, after `resume` (and near `review`), add:

```python
def _due_items(root: Path, on_date: str) -> list[dict]:
    records = root / "records"
    items: list[dict] = []
    if not records.is_dir():
        return items
    for path in sorted(records.glob("*/*.md")):
        fm = frontmatter_from_file(path)
        state = str(fm.get("state", ""))
        if state not in ("demonstrated", "retained", "stale"):
            continue
        last = str(fm.get("last_reviewed", "")).strip()
        box = int(fm.get("box", 1) or 1)
        due = due_on(last, box) if last else on_date
        if due > on_date:
            continue
        overdue = (dt.date.fromisoformat(on_date) - dt.date.fromisoformat(due)).days
        items.append({
            "path": path, "topic": path.parent.name, "concept": path.stem,
            "state": state, "box": box,
            "deps": [str(d) for d in (fm.get("deps") or [])],
            "days_overdue": overdue,
        })
    return items


def _order_due(items: list[dict]) -> list[dict]:
    """Prerequisites (by concept slug) before dependents; ties by most-overdue then slug."""
    by_concept = {it["concept"]: it for it in items}
    ordered: list[dict] = []
    seen: set[str] = set()

    def visit(it: dict) -> None:
        if it["concept"] in seen:
            return
        seen.add(it["concept"])
        for dep in it["deps"]:
            if dep in by_concept:
                visit(by_concept[dep])
        ordered.append(it)

    for it in sorted(items, key=lambda x: (-x["days_overdue"], x["concept"])):
        visit(it)
    return ordered


def due(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    root = root_from_config(cfg)
    on_date = args.on or dt.date.today().isoformat()
    items = _order_due(_due_items(root, on_date))
    if args.limit is not None:
        items = items[: args.limit]
    for it in items:
        print(f"{it['topic']}\t{it['concept']}\t{it['state']}\t{it['box']}\t{it['days_overdue']}\t{it['path']}")
    return 0
```

In `build_parser`, after the `review` subparser, add:

```python
    p = sub.add_parser("due")
    p.add_argument("--on", help="reference date (ISO); defaults to today")
    p.add_argument("--limit", type=int, help="cap the number of due concepts printed")
```

In `main`, add a dispatch branch after the `review` branch:

```python
        elif args.cmd == "due":
            return due(args)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --with pytest --with pyyaml python -m pytest -q tests/test_store.py -k due`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full suite + skill validator**

Run: `uv run --with pytest --with pyyaml python -m pytest -q tests/ && python scripts/validate.py && python scripts/validate_skill.py`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add skills/teach-me/scripts/store.py tests/test_store.py
git commit -m "feat(store): due command with dep-ordered spaced-repetition selection

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 5: Skill documentation — review flow, surfacing, schedule model

**Files:**
- Create: `skills/teach-me/references/review.md`
- Modify: `skills/teach-me/SKILL.md`, `skills/teach-me/references/state.md`, `skills/teach-me/references/flows.md`
- Test: `python scripts/validate_skill.py` (SKILL.md must still conform)

**Interfaces:**
- Consumes: the CLI surfaces from Tasks 2–4 (`save-record --deps`, `review --topic --concept --result`, `due --on --limit`). Command strings in the docs must match those exactly.
- Produces: user-facing docs; no code consumers.

- [ ] **Step 1: Create `references/review.md`**

Create `skills/teach-me/references/review.md`:

```markdown
# teach-me review flow (Branch C)

Spaced-repetition retention checks for concepts already demonstrated in an earlier session.
Explicitly invoked only, via `/teach-me review` (`$teach-me review`). Never auto-started.

## Procedure

1. Get the due list deterministically: `python scripts/store.py due --limit 5`. Each line is
   `topic<TAB>concept<TAB>state<TAB>box<TAB>days_overdue<TAB>path`. Empty output → tell the
   user nothing is due and stop.
2. For each due concept, in the order printed (prerequisites come first), open its record and
   ask its stored **"Review question (self-test prompt)"** as a retrieval check. One question
   per turn. Obey every fatigue hard rule in `teaching.md` — stop immediately on any stop or
   fatigue signal, checkpoint, and do not add "one more".
3. Grade the answer with the normal feedback verdict:
   - `correct` → `python scripts/store.py review --topic T --concept C --result pass`
     (promotes the Leitner box, marks `retained`).
   - `partial` / `not yet` → `python scripts/store.py review --topic T --concept C --result fail`
     (resets to box 1, marks `stale`), then ask "review this now?" — yes runs the normal
     teaching loop on the concept; no moves to the next due item.
4. If a failed concept lists `deps` that are themselves `stale` or overdue, offer to check the
   prerequisite first: "this may be because prerequisite Y is shaky — review Y?"
5. Stop when the batch (5) is exhausted, the due list is empty, or a fatigue signal arrives.
   Always end with the standard copyable checkpoint.

## Invariants

- Batch cap: at most 5 due concepts per review session unless the user asks for more.
- Never compute due dates or box transitions by hand — `store.py` owns all schedule math.
- Review changes retention state only; it never fabricates prior learning. If `due` returns
  nothing, say so.
```

- [ ] **Step 2: Add the review command + argument-hint + Red Flags to `SKILL.md`**

In `skills/teach-me/SKILL.md`, update the `argument-hint` line (line 4) to:

```
argument-hint: "[no args = debrief this conversation] [topic] [resume] [review] [--socratic (default)|--feynman|--drill]"
```

In the `## Commands` table, add a row after the `resume` row:

```
| `/teach-me review` | Spaced-repetition review of due concepts → `references/review.md`; scheduling → `references/state.md` |
```

In `## Red Flags`, add two bullets at the end:

```
- Starting a review, or any teaching, without an explicit `/teach-me review` (or `$teach-me review`) token → STOP; review is explicit-invocation-only like every other branch.
- Surfacing "N concepts are due" anywhere other than the end of an already-invoked teach-me session or a `resume` → STOP; never nag outside an invoked session, never auto-start review.
```

- [ ] **Step 3: Document the schedule model in `references/state.md`**

In `skills/teach-me/references/state.md`, under `## Deterministic store script`, add `review` and
`due` to the "Supported operations" sentence so it reads:

```
Supported operations: `init`, `list-topics`, `save-record`, `save-checkpoint`, `resume`,
`review`, `due`, and `migrate`.
```

After the `## Learning-state vocabulary` section, add a new section:

```markdown
## Spaced-repetition schedule (records carry their own review clock)

Every concept record carries a Leitner schedule in frontmatter:

- `deps: [<concept-slug>, ...]` — prerequisites, used only to order reviews and to flag a
  shaky prerequisite behind a failed review.
- `box: <1..5>` — Leitner level; `last_reviewed: <ISO date>`; `review_count: <int>`.
- Intervals ladder: `[1, 3, 7, 21, 60]` days. A concept at `box` is **due** on
  `last_reviewed + LADDER[box - 1]` days; the date is computed, never stored.
- A concept enters the schedule when first written `demonstrated` (`box 1`,
  `last_reviewed` = write date, `review_count 0`), so its first check falls due one day later.
- Review outcomes (via `store.py review`): a pass promotes one box and sets `retained`; a fail
  resets to box 1 and sets `stale`. `store.py due` lists concepts whose due date has passed;
  a `demonstrated`/`retained`/`stale` record with no `last_reviewed` counts as due now.

The **"Review question (self-test prompt)"** section of each record is **required** — the
review flow uses it as the retrieval prompt.
```

- [ ] **Step 4: Add Branch C and surfacing to `references/flows.md`**

In `skills/teach-me/references/flows.md`, add a Branch C describing the review procedure with a
pointer to `references/review.md`, and a passive-surfacing rule. Append:

```markdown
## Branch C — review (spaced repetition)

`/teach-me review` runs retention checks on due concepts. The full procedure — due list, batch
cap of 5, fatigue rules, verdict→pass/fail, fail→relearn, prerequisite hint — lives in
`references/review.md`. Review is explicit-invocation-only and never auto-starts.

## Passive due-surfacing (only inside an invoked session)

At the end of an already-invoked teach-me session (any branch) and at the start of `resume`,
run `python scripts/store.py due --limit 1` to check whether anything is due. If so, print one
line and nothing more: "N concept(s) are due for review — run `/teach-me review` when you want."
Never surface due items outside an invoked teach-me session, and never start review on your own.
```

- [ ] **Step 5: Validate the skill still conforms**

Run: `python scripts/validate_skill.py && python scripts/validate.py`
Expected: both print `OK`

- [ ] **Step 6: Run the full offline suite once more**

Run: `uv run --with pytest --with pyyaml python -m pytest -q tests/`
Expected: PASS (all tests)

- [ ] **Step 7: Commit**

```bash
git add skills/teach-me/SKILL.md skills/teach-me/references/
git commit -m "docs(skill): review flow (Branch C), due-surfacing, and schedule model

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Data model (§5, spec): `deps`/`box`/`last_reviewed`/`review_count` + ladder → Task 2 (init) & Task 1 (ladder). ✓
- `store.py due` (§6) → Task 4. ✓ · `store.py review` (§6) → Task 3. ✓ · `save-record --deps` (§6) → Task 2. ✓
- Review flow & surfacing (§7) → Task 5 (`review.md`, `flows.md`). ✓
- `deps` ordering + prerequisite hint (§8) → Task 4 (`_order_due`) + Task 5 (hint in `review.md`). ✓
- Documentation (§9) → Task 5 (SKILL.md, state.md, flows.md, review.md). ✓
- Testing (§10) → Tasks 1–4 unit tests. ✓
- Migration/back-compat (§11): schedule-less demonstrated record due now → Task 4 test. ✓
- State lifecycle `retained`/`stale` (§5) → Task 3 (`review_state`). ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every doc step shows the exact text to insert.

**Type consistency:** `due_on(last_reviewed, box)`, `next_box(box, result)`, `review_state(result)`, `split_record(text)->(dict,str)`, `_due_items(root, on_date)`, `_order_due(items)` are defined in Tasks 1/3/4 and consumed with matching signatures. The `due` output columns (`topic\tconcept\tstate\tbox\tdays_overdue\tpath`) are asserted in Task 4 tests and documented identically in Task 5's `review.md`.
