# teach-me eval harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `evals/` — a repeatable harness that runs 6 teach-me behavioral scenarios against a real `claude -p` session (DeepSeek endpoint from `.env`) and scores each with deterministic assertions + a DeepSeek LLM judge.

**Architecture:** Five small single-purpose Python modules under `evals/` (`session.py` drives `claude -p`; `transcript.py` parses the transcript; `asserts.py` holds pure deterministic checks; `judge.py` calls DeepSeek; `run_evals.py` orchestrates) plus `evals/scenarios/*.yaml`. Pure modules get CI-safe pytest unit tests under `tests/`; the live layer is run deliberately via `uv`, never in CI.

**Tech Stack:** Python 3.11+ (run on 3.14 via `uv`), PEP 723 inline metadata, `pyyaml` (only third-party dep), stdlib `subprocess`/`json`/`urllib`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-15-teach-me-eval-harness-design.md`

## Global Constraints

- Every eval script is run via `uv run --python 3.14 evals/<script>.py` and carries PEP 723 inline metadata (`# /// script` … `requires-python = ">=3.11"`). Matches `tests/skill_live_check.py`.
- Only third-party dependency allowed: `pyyaml>=6,<7` (pinned in `run_evals.py`'s PEP 723 block). `session.py`/`judge.py`/`transcript.py`/`asserts.py` use stdlib only.
- The harness is **NOT** in CI and **NOT** collected by pytest: every file under `evals/` is named so it never matches `test_*.py`. Only the pure-logic tests under `tests/` (which make no network/subprocess calls) run in CI.
- No secret **values** in any tracked file — reference env var **names** only (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_MODEL`, `DEEPSEEK_API_KEY`). `.env` is already gitignored and is read only at runtime.
- No personal information (usernames, emails, home paths) in any tracked file. Code uses `Path.home()` / `Path(__file__)`, never literal user paths.
- Commits follow the repo git author policy in `CLAUDE.md` (author is fixed; the Co-Authored-By trailer names the actual model, never bare "Claude").
- A judge response that cannot be parsed is recorded as a **failed** sample, never a silent pass.
- Default sampling: `samples: 3`, `pass_threshold: 2` (majority) unless a scenario overrides.

## File Structure

| File | Responsibility |
|---|---|
| `evals/session.py` | Load `.env`; build the `claude -p` command; drive 1–2 turns via `--resume`; return transcript text. |
| `evals/transcript.py` | Pure: parse transcript JSONL → ordered coach (assistant) text turns. |
| `evals/asserts.py` | Pure: deterministic assertion functions + a `name → callable` registry. |
| `evals/judge.py` | DeepSeek judge over the `.env` endpoint; pure `parse_verdict` + live `judge`. |
| `evals/run_evals.py` | CLI orchestrator: load scenarios, run samples, aggregate, report, exit code. |
| `evals/scenarios/*.yaml` | The 6 scenario definitions. |
| `evals/README.md` | How to run, cost note, how to add a scenario. |
| `tests/test_transcript.py` | CI-safe unit tests for `transcript.coach_turns`. |
| `tests/test_asserts.py` | CI-safe unit tests for the assertion library. |
| `tests/test_run_evals.py` | CI-safe unit tests for `load_scenarios`/`run_asserts`/`aggregate` + judge `parse_verdict`. |

**Test import convention** (used by all three test files): `evals/` is not a package, so tests put it on `sys.path` and disable bytecode caching:

```python
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
```

---

### Task 1: `session.py` — env loader + command builder (pure core)

**Files:**
- Create: `evals/session.py`
- Test: `tests/test_session.py`

**Interfaces:**
- Produces: `SetupError(RuntimeError)`; `load_env(dotenv: Path | None = None) -> dict[str, str]`; `transcript_path(session_id: str) -> Path`; `build_claude_cmd(prompt: str, session_id: str | None = None) -> list[str]`. (Task 2 adds the subprocess parts.)

- [ ] **Step 1: Write the failing test**

Create `tests/test_session.py`:

```python
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
import session  # noqa: E402


def test_build_cmd_single_turn_has_no_resume():
    cmd = session.build_claude_cmd("hello")
    assert cmd[:3] == ["claude", "-p", "hello"]
    assert "--resume" not in cmd


def test_build_cmd_with_session_adds_resume():
    cmd = session.build_claude_cmd("next", session_id="abc123")
    assert "--resume" in cmd
    assert "abc123" in cmd


def test_load_env_reads_key_values(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("# comment\nANTHROPIC_MODEL=deepseek-x\nEMPTY\n", encoding="utf-8")
    env = session.load_env(dotenv)
    assert env["ANTHROPIC_MODEL"] == "deepseek-x"


def test_load_env_missing_raises_setup_error(tmp_path):
    import pytest
    with pytest.raises(session.SetupError):
        session.load_env(tmp_path / "absent.env")


def test_transcript_path_has_no_colon_or_slash_in_project_segment():
    p = session.transcript_path("SID")
    assert p.name == "SID.jsonl"
    assert ":" not in p.parent.name  # repo path munged
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --python 3.14 -m pytest tests/test_session.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'session'`.

- [ ] **Step 3: Write minimal implementation**

Create `evals/session.py`:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""Drive claude -p (1-2 turns via --resume) and return the on-disk transcript text.

Reuses the mechanism proven in tests/skill_live_check.py: load .env into the
subprocess env, capture the session_id from stream-json, then read the transcript
Claude Code writes to ~/.claude/projects/<munged-repo>/<session_id>.jsonl.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PER_CALL_TIMEOUT_S = 600


class SetupError(RuntimeError):
    """A precondition (env, CLI, transcript) is missing; the runner exits 2."""


def load_env(dotenv: Path | None = None) -> dict[str, str]:
    dotenv = dotenv or (REPO / ".env")
    if not dotenv.is_file():
        raise SetupError(f"missing {dotenv} (ANTHROPIC_BASE_URL/AUTH_TOKEN/MODEL)")
    env = os.environ.copy()
    for raw in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def transcript_path(session_id: str) -> Path:
    munged = re.sub(r"[:\\/]", "-", str(REPO))
    return Path.home() / ".claude" / "projects" / munged / f"{session_id}.jsonl"


def build_claude_cmd(prompt: str, session_id: str | None = None) -> list[str]:
    cmd = ["claude", "-p", prompt,
           "--output-format", "stream-json", "--verbose",
           "--max-turns", "6", "--allowedTools", "Skill"]
    if session_id:
        cmd += ["--resume", session_id]
    return cmd
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --python 3.14 -m pytest tests/test_session.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add evals/session.py tests/test_session.py
git commit -m "feat(evals): session.py env loader + claude command builder"
```

---

### Task 2: Walking-skeleton live check — prove headless multi-turn `--resume`

This de-risks spec §9.1 before any scenario is built. It costs a small amount of real API. If `--resume` does not accumulate both turns into one transcript, STOP and adjust (try `-c/--continue`, or fall back to single-turn scenarios) before continuing.

**Files:**
- Modify: `evals/session.py` (add `_run_turn`, `run_session`)
- Create: `evals/scenarios/` (empty dir placeholder is fine)

**Interfaces:**
- Consumes: `build_claude_cmd`, `transcript_path`, `SetupError` from Task 1.
- Produces: `run_session(turns: list[str], env: dict) -> str` (transcript text).

- [ ] **Step 1: Add the subprocess driver to `evals/session.py`**

Append to `evals/session.py`:

```python
def _run_turn(prompt: str, env: dict, session_id: str | None) -> str:
    """Run one claude -p turn; return the session_id it reports."""
    exe = shutil.which("claude")
    if not exe:
        raise SetupError("claude CLI not on PATH")
    cmd = build_claude_cmd(prompt, session_id)
    cmd[0] = exe
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=REPO, env=env, timeout=PER_CALL_TIMEOUT_S,
    )
    sid = session_id or ""
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = event.get("session_id") or sid
    if not sid:
        tail = "\n".join(proc.stderr.splitlines()[-5:])
        raise SetupError(f"no session_id in claude output; stderr tail:\n{tail}")
    return sid


def run_session(turns: list[str], env: dict) -> str:
    """Run turns in order (chaining via --resume); return the transcript text."""
    session_id = None
    for prompt in turns:
        session_id = _run_turn(prompt, env, session_id)
    path = transcript_path(session_id)
    if not path.is_file():
        raise SetupError(f"transcript not found: {path}")
    return path.read_text(encoding="utf-8", errors="replace")
```

- [ ] **Step 2: Run the live two-turn skeleton**

Run:

```bash
uv run --python 3.14 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path("evals").resolve()))
import session
env = session.load_env()
text = session.run_session(["say the word ALPHA and nothing else",
                            "now say the word BRAVO and nothing else"], env)
print("ALPHA present:", "ALPHA" in text)
print("BRAVO present:", "BRAVO" in text)
print("transcript chars:", len(text))
PY
```

Expected: `ALPHA present: True` AND `BRAVO present: True` — proving both turns landed in one transcript.

- [ ] **Step 3: Decide the gate**

- If both are `True`: `--resume` works headlessly. Proceed.
- If only BRAVO is present (resume started a fresh transcript): change `run_session` to read the **first** turn's `session_id` transcript, or switch to `-c/--continue`. Re-run Step 2 until both are present.
- If resume is unusable at all: mark f3/m5/f5 as single-turn-only for a later iteration and proceed with the three single-turn scenarios. Record the decision in `evals/README.md`.

- [ ] **Step 4: Save a real transcript as a fixture for Task 3**

Run:

```bash
uv run --python 3.14 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path("evals").resolve()))
import session
env = session.load_env()
text = session.run_session(["/teach-me --socratic recursion"], env)
Path("tests/fixtures").mkdir(parents=True, exist_ok=True)
Path("tests/fixtures/sample_transcript.jsonl").write_text(text, encoding="utf-8")
print("saved", len(text), "chars")
PY
```

Expected: a non-empty `tests/fixtures/sample_transcript.jsonl` written. Open it and confirm assistant messages look like `{"type":"assistant","message":{"content":[{"type":"text","text":...}]}}`; if the shape differs, note the real shape for Task 3.

- [ ] **Step 5: Commit**

```bash
git add evals/session.py tests/fixtures/sample_transcript.jsonl
git commit -m "feat(evals): multi-turn run_session + real transcript fixture (resume verified)"
```

---

### Task 3: `transcript.py` — coach-turn parser

**Files:**
- Create: `evals/transcript.py`
- Test: `tests/test_transcript.py`

**Interfaces:**
- Produces: `coach_turns(transcript_text: str) -> list[str]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_transcript.py`:

```python
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
import transcript  # noqa: E402


def test_extracts_assistant_text_in_order():
    jsonl = "\n".join([
        json.dumps({"type": "user", "message": {"content": "hi"}}),
        json.dumps({"type": "assistant",
                    "message": {"content": [{"type": "text", "text": "first"}]}}),
        json.dumps({"type": "assistant",
                    "message": {"content": [{"type": "text", "text": "second?"}]}}),
    ])
    assert transcript.coach_turns(jsonl) == ["first", "second?"]


def test_skips_tool_only_and_malformed_lines():
    jsonl = "\n".join([
        "not json",
        json.dumps({"type": "assistant",
                    "message": {"content": [{"type": "tool_use", "id": "x"}]}}),
        json.dumps({"type": "assistant",
                    "message": {"content": [{"type": "text", "text": "  kept  "}]}}),
    ])
    assert transcript.coach_turns(jsonl) == ["kept"]


def test_real_fixture_has_at_least_one_turn():
    fixture = Path(__file__).resolve().parent / "fixtures" / "sample_transcript.jsonl"
    if not fixture.is_file():
        return  # fixture only exists after Task 2 Step 4
    turns = transcript.coach_turns(fixture.read_text(encoding="utf-8"))
    assert len(turns) >= 1
    assert all(isinstance(t, str) and t for t in turns)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --python 3.14 -m pytest tests/test_transcript.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcript'`.

- [ ] **Step 3: Write minimal implementation**

Create `evals/transcript.py`. If Task 2 Step 4 revealed a different assistant-message shape, adjust the block extraction accordingly.

```python
"""Parse a Claude Code transcript JSONL into ordered coach (assistant) text turns."""
from __future__ import annotations

import json


def coach_turns(transcript_text: str) -> list[str]:
    """Assistant text turns in order; one joined string per assistant message.

    Skips non-assistant events, tool-only turns, and malformed lines.
    """
    turns: list[str] = []
    for line in transcript_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "assistant":
            continue
        content = (event.get("message") or {}).get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            text = ""
        text = text.strip()
        if text:
            turns.append(text)
    return turns
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --python 3.14 -m pytest tests/test_transcript.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add evals/transcript.py tests/test_transcript.py
git commit -m "feat(evals): transcript.py coach-turn parser"
```

---

### Task 4: `asserts.py` — deterministic assertion library + registry

**Files:**
- Create: `evals/asserts.py`
- Test: `tests/test_asserts.py`

**Interfaces:**
- Produces: `last_coach_turn_has_no_question(turns)`, `first_coach_turn_is_question(turns)`, `transcript_matches(turns, pattern)`, `transcript_not_matches(turns, pattern)`, `first_turn_heading_count_below(turns, n)`, and `REGISTRY: dict[str, Callable]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_asserts.py`:

```python
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
import asserts  # noqa: E402


def test_last_turn_no_question():
    assert asserts.last_coach_turn_has_no_question(["q?", "done. checkpoint saved."])
    assert not asserts.last_coach_turn_has_no_question(["x", "what is recursion?"])
    assert not asserts.last_coach_turn_has_no_question(["x", "再来一道：算一下"])
    assert not asserts.last_coach_turn_has_no_question([])


def test_first_turn_is_question():
    assert asserts.first_coach_turn_is_question(["what do you think?"])
    assert asserts.first_coach_turn_is_question(["你觉得呢？"])
    assert not asserts.first_coach_turn_is_question(["Recursion is a function that calls itself."])


def test_transcript_matches_and_not():
    turns = ["modes: socratic, feynman, drill"]
    assert asserts.transcript_matches(turns, "feynman")
    assert asserts.transcript_not_matches(turns, "leitner")


def test_first_turn_heading_count_below():
    dump = "## A\n## B\n## C\ntext"
    assert not asserts.first_turn_heading_count_below([dump], 3)
    assert asserts.first_turn_heading_count_below(["just one line"], 3)


def test_registry_exposes_all_by_name():
    for name in ["last_coach_turn_has_no_question", "first_coach_turn_is_question",
                 "transcript_matches", "transcript_not_matches",
                 "first_turn_heading_count_below"]:
        assert name in asserts.REGISTRY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --python 3.14 -m pytest tests/test_asserts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'asserts'`.

- [ ] **Step 3: Write minimal implementation**

Create `evals/asserts.py`:

```python
"""Deterministic assertions over coach turns. Pure: (turns, *args) -> bool."""
from __future__ import annotations

import re

_QUESTION_CHARS = ("?", "？")
_MORE = re.compile(r"(再来(一|道|个)|下一(题|道|个)|one more|another one)", re.I)


def last_coach_turn_has_no_question(turns: list[str]) -> bool:
    if not turns:
        return False
    last = turns[-1].rstrip()
    if last.endswith(_QUESTION_CHARS):
        return False
    return _MORE.search(last) is None


def first_coach_turn_is_question(turns: list[str]) -> bool:
    if not turns:
        return False
    return any(ch in turns[0] for ch in _QUESTION_CHARS)


def transcript_matches(turns: list[str], pattern: str) -> bool:
    rx = re.compile(pattern, re.I)
    return any(rx.search(t) for t in turns)


def transcript_not_matches(turns: list[str], pattern: str) -> bool:
    return not transcript_matches(turns, pattern)


def first_turn_heading_count_below(turns: list[str], n: int) -> bool:
    if not turns:
        return False
    headings = len(re.findall(r"(?m)^#{1,6}\s", turns[0]))
    return headings < n


REGISTRY = {
    "last_coach_turn_has_no_question": last_coach_turn_has_no_question,
    "first_coach_turn_is_question": first_coach_turn_is_question,
    "transcript_matches": transcript_matches,
    "transcript_not_matches": transcript_not_matches,
    "first_turn_heading_count_below": first_turn_heading_count_below,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --python 3.14 -m pytest tests/test_asserts.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add evals/asserts.py tests/test_asserts.py
git commit -m "feat(evals): asserts.py deterministic assertion library + registry"
```

---

### Task 5: `judge.py` — DeepSeek judge (pure parse + live smoke)

**Files:**
- Create: `evals/judge.py`
- Test: `tests/test_run_evals.py` (starts here with the pure `parse_verdict` tests; extended in Task 6)

**Interfaces:**
- Consumes: `load_env` (for the live smoke) from `session.py`.
- Produces: `parse_verdict(text: str) -> dict` (keys `pass`/`evidence`/`reasoning`); `judge(rubric: str, excerpt: str, env: dict) -> dict`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_run_evals.py`:

```python
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
import judge  # noqa: E402


def test_parse_verdict_valid_json():
    v = judge.parse_verdict('sure: {"pass": true, "evidence": "q?", "reasoning": "asked"}')
    assert v["pass"] is True
    assert v["evidence"] == "q?"


def test_parse_verdict_false():
    v = judge.parse_verdict('{"pass": false, "evidence": "", "reasoning": "dumped"}')
    assert v["pass"] is False


def test_parse_verdict_unparseable_is_flagged_failure():
    v = judge.parse_verdict("no json at all")
    assert v["pass"] is False
    assert "unparseable" in v["reasoning"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --python 3.14 -m pytest tests/test_run_evals.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'judge'`.

- [ ] **Step 3: Write minimal implementation**

Create `evals/judge.py`:

```python
"""DeepSeek LLM judge over the Anthropic-compatible endpoint from .env."""
from __future__ import annotations

import json
import urllib.request

SYSTEM = (
    "You are a strict grader. Given a RUBRIC and a transcript EXCERPT, decide "
    "whether the excerpt satisfies EVERY clause of the rubric. Output ONLY a JSON "
    'object: {"pass": true|false, "evidence": "<short quote>", "reasoning": "<one line>"}. '
    "Do not be lenient; a missed clause is a fail."
)


def parse_verdict(text: str) -> dict:
    """Extract the JSON verdict from model text. Unparseable => flagged failure."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {"pass": False, "evidence": "",
                "reasoning": f"unparseable judge output: {text[:120]!r}"}
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError as err:
        return {"pass": False, "evidence": "",
                "reasoning": f"invalid judge JSON: {err}"}
    return {"pass": bool(obj.get("pass", False)),
            "evidence": str(obj.get("evidence", "")),
            "reasoning": str(obj.get("reasoning", ""))}


def judge(rubric: str, excerpt: str, env: dict) -> dict:
    base = env["ANTHROPIC_BASE_URL"].rstrip("/")
    body = json.dumps({
        "model": env["ANTHROPIC_MODEL"],
        "max_tokens": 512,
        "temperature": 0,
        "system": SYSTEM,
        "messages": [{"role": "user",
                      "content": f"RUBRIC:\n{rubric}\n\nEXCERPT:\n{excerpt}"}],
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/v1/messages", data=body, method="POST",
        headers={"content-type": "application/json",
                 "x-api-key": env["ANTHROPIC_AUTH_TOKEN"],
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    text = "".join(b.get("text", "") for b in payload.get("content", [])
                   if isinstance(b, dict))
    return parse_verdict(text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --python 3.14 -m pytest tests/test_run_evals.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Live smoke — lock the judge auth header (spec §9.2)**

Run:

```bash
uv run --python 3.14 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path("evals").resolve()))
import session, judge
env = session.load_env()
v = judge.judge("The excerpt must contain a question.",
                "What is recursion?", env)
print(v)
PY
```

Expected: a dict like `{'pass': True, 'evidence': '...', 'reasoning': '...'}`.
- If it raises HTTP 401/403: the proxy wants a different header. Change `x-api-key` to `Authorization: Bearer` (keep both if needed), or switch to DeepSeek's native OpenAI endpoint using `env["DEEPSEEK_API_KEY"]` (POST `https://api.deepseek.com/chat/completions`, `{"model": "deepseek-chat", "messages": [...], "response_format": {"type": "json_object"}}`, header `Authorization: Bearer <key>`), and reshape `judge()` to read `choices[0].message.content`. Re-run until it returns a verdict.

- [ ] **Step 6: Commit**

```bash
git add evals/judge.py tests/test_run_evals.py
git commit -m "feat(evals): judge.py DeepSeek judge + verdict parser (auth header verified)"
```

---

### Task 6: `run_evals.py` — orchestrator, scenario loader, report, CLI

**Files:**
- Create: `evals/run_evals.py`
- Modify: `tests/test_run_evals.py` (add loader/assert-dispatch/aggregate tests)

**Interfaces:**
- Consumes: `load_env`, `run_session`, `SetupError` (session.py); `coach_turns` (transcript.py); `REGISTRY` (asserts.py); `judge` (judge.py).
- Produces: `load_scenarios(directory: Path) -> list[dict]`; `run_asserts(turns, assert_specs) -> list[tuple[str, bool]]`; `aggregate(sample_passes: list[bool], threshold: int) -> bool`; `main(argv=None) -> int`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_run_evals.py`:

```python
import run_evals  # noqa: E402


def test_run_asserts_bare_and_parameterized():
    turns = ["modes: socratic feynman drill"]
    specs = ["first_coach_turn_is_question", {"transcript_matches": "feynman"}]
    results = run_evals.run_asserts(turns, specs)
    assert results == [("first_coach_turn_is_question", False),
                       ("transcript_matches", True)]


def test_aggregate_majority():
    assert run_evals.aggregate([True, True, False], 2) is True
    assert run_evals.aggregate([True, False, False], 2) is False


def test_load_scenarios_reads_yaml(tmp_path):
    (tmp_path / "s1.yaml").write_text(
        "id: s1\nturns: ['/teach-me x']\nasserts: []\nsamples: 1\n", encoding="utf-8")
    scenarios = run_evals.load_scenarios(tmp_path)
    assert scenarios[0]["id"] == "s1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --python 3.14 -m pytest tests/test_run_evals.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'run_evals'`.

- [ ] **Step 3: Write minimal implementation**

Create `evals/run_evals.py`:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6,<7"]
# ///
"""Run teach-me behavioral evals: real claude -p sessions scored by asserts + judge.

Deliberate, paid, non-CI. Usage:
    uv run --python 3.14 evals/run_evals.py                # all scenarios
    uv run --python 3.14 evals/run_evals.py --scenario m1-socratic-first
    uv run --python 3.14 evals/run_evals.py --samples 1 --no-judge   # cheap smoke
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from session import load_env, run_session, SetupError
from transcript import coach_turns
from asserts import REGISTRY
from judge import judge as run_judge

EVALS_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = EVALS_DIR / "scenarios"


def load_scenarios(directory: Path) -> list[dict]:
    return [yaml.safe_load(p.read_text(encoding="utf-8"))
            for p in sorted(directory.glob("*.yaml"))]


def run_asserts(turns, assert_specs) -> list[tuple[str, bool]]:
    results = []
    for spec in assert_specs or []:
        if isinstance(spec, str):
            name, arg = spec, None
        else:  # single-key map {name: arg}
            (name, arg), = spec.items()
        fn = REGISTRY[name]
        ok = fn(turns, arg) if arg is not None else fn(turns)
        results.append((name, bool(ok)))
    return results


def aggregate(sample_passes: list[bool], threshold: int) -> bool:
    return sum(sample_passes) >= threshold


def run_scenario(scenario: dict, env: dict, samples_override, judge_on) -> dict:
    samples = samples_override or scenario.get("samples", 3)
    threshold = scenario.get("pass_threshold", 2)
    per_sample = []
    for _ in range(samples):
        turns = coach_turns(run_session(scenario["turns"], env))
        assert_results = run_asserts(turns, scenario.get("asserts"))
        asserts_ok = all(ok for _, ok in assert_results)
        verdict = {"pass": True, "evidence": "", "reasoning": "judge skipped"}
        if judge_on and scenario.get("judge"):
            excerpt = "\n\n".join(turns[-2:]) if turns else ""
            verdict = run_judge(scenario["judge"]["rubric"], excerpt, env)
        per_sample.append({"asserts": assert_results, "judge": verdict,
                           "ok": asserts_ok and verdict["pass"]})
    n_pass = sum(s["ok"] for s in per_sample)
    return {"id": scenario["id"], "n": samples, "n_pass": n_pass,
            "passed": aggregate([s["ok"] for s in per_sample], threshold),
            "samples": per_sample}


def _print_report(results: list[dict], verbose: bool) -> None:
    for r in results:
        flag = "PASS" if r["passed"] else "FAIL"
        print(f"[{flag}] {r['id']}  {r['n_pass']}/{r['n']}")
        if not r["passed"] or verbose:
            for i, s in enumerate(r["samples"]):
                if s["ok"] and not verbose:
                    continue
                fails = [n for n, ok in s["asserts"] if not ok]
                print(f"    sample {i}: asserts_failed={fails} "
                      f"judge={s['judge']['pass']} :: {s['judge']['reasoning']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--scenario", help="run only this scenario id")
    parser.add_argument("--samples", type=int, default=None)
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    try:
        env = load_env()
    except SetupError as err:
        print(f"SETUP FAIL - {err}")
        return 2

    scenarios = load_scenarios(SCENARIOS_DIR)
    if args.scenario:
        scenarios = [s for s in scenarios if s["id"] == args.scenario]
        if not scenarios:
            print(f"SETUP FAIL - no scenario id {args.scenario!r}")
            return 2

    try:
        results = [run_scenario(s, env, args.samples, not args.no_judge)
                   for s in scenarios]
    except SetupError as err:
        print(f"SETUP FAIL - {err}")
        return 2

    _print_report(results, args.verbose)
    ok = all(r["passed"] for r in results)
    print("ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --python 3.14 -m pytest tests/test_run_evals.py -v`
Expected: PASS (all tests in the file pass).

- [ ] **Step 5: Commit**

```bash
git add evals/run_evals.py tests/test_run_evals.py
git commit -m "feat(evals): run_evals.py orchestrator, scenario loader, report, CLI"
```

---

### Task 7: The 6 scenario YAMLs + README + scenario-integrity test

**Files:**
- Create: `evals/scenarios/f1-no-dump.yaml`, `m1-socratic-first.yaml`, `m10-unknown-flag.yaml`, `f3-mastery-gate.yaml`, `m5-just-tell-me.yaml`, `f5-fatigue-terminal.yaml`
- Create: `evals/README.md`
- Modify: `tests/test_run_evals.py` (add the integrity test)

**Interfaces:**
- Consumes: `load_scenarios`, `REGISTRY` (registry keys the scenarios must reference).

- [ ] **Step 1: Write the failing integrity test**

Append to `tests/test_run_evals.py`:

```python
from asserts import REGISTRY  # noqa: E402


def test_all_shipped_scenarios_load_and_reference_known_asserts():
    scenarios_dir = Path(__file__).resolve().parent.parent / "evals" / "scenarios"
    scenarios = run_evals.load_scenarios(scenarios_dir)
    assert len(scenarios) == 6
    ids = {s["id"] for s in scenarios}
    assert ids == {"f1-no-dump", "m1-socratic-first", "m10-unknown-flag",
                   "f3-mastery-gate", "m5-just-tell-me", "f5-fatigue-terminal"}
    for s in scenarios:
        assert s["turns"] and isinstance(s["turns"], list)
        for spec in s.get("asserts") or []:
            name = spec if isinstance(spec, str) else next(iter(spec))
            assert name in REGISTRY, f"{s['id']} references unknown assert {name}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --python 3.14 -m pytest tests/test_run_evals.py::test_all_shipped_scenarios_load_and_reference_known_asserts -v`
Expected: FAIL (`load_scenarios` returns 0 scenarios; `assert len == 6`).

- [ ] **Step 3: Create the six scenario files**

`evals/scenarios/f1-no-dump.yaml`:
```yaml
id: f1-no-dump
source: teach-me-scenarios.md#F1
description: zero-base topic -> diagnose + one minimal step, not an encyclopedia dump
setup: { platform: claude-code }
turns:
  - "/teach-me quantum mechanics（我完全零基础）"
asserts:
  - { first_turn_heading_count_below: 3 }
judge:
  rubric: |
    The first coach turn must diagnose the learner or take ONE minimal teaching step.
    It must NOT dump a multi-unit curriculum, several concepts, or multiple equations
    in the first turn. Fail if it delivers an encyclopedia-style outline.
samples: 3
pass_threshold: 2
```

`evals/scenarios/m1-socratic-first.yaml`:
```yaml
id: m1-socratic-first
source: teach-me-scenarios.md#M1
description: socratic first teaching turn opens with a probing question
setup: { platform: claude-code }
turns:
  - "/teach-me --socratic recursion"
asserts:
  - first_coach_turn_is_question
judge:
  rubric: |
    The opening coach turn must be built around ONE probing question that invites the
    learner to think, not a lecture or a multi-point explanation.
samples: 3
pass_threshold: 2
```

`evals/scenarios/m10-unknown-flag.yaml`:
```yaml
id: m10-unknown-flag
source: teach-me-scenarios.md#M10
description: unknown mode flag -> report it, list the three modes, ask (no silent fallback)
setup: { platform: claude-code }
turns:
  - "/teach-me --sacratic recursion"
asserts:
  - { transcript_matches: "socratic" }
  - { transcript_matches: "feynman" }
  - { transcript_matches: "drill" }
judge:
  rubric: |
    The coach must flag that "--sacratic" is an unknown flag, list the three modes
    (socratic, feynman, drill), and ask the learner what they meant. Fail if it
    silently guesses a mode or ignores the flag.
samples: 3
pass_threshold: 2
```

`evals/scenarios/f3-mastery-gate.yaml`:
```yaml
id: f3-mastery-gate
source: teach-me-scenarios.md#F3
description: "我懂了" without application evidence -> do not mark mastered; elicit E2/E3
setup: { platform: claude-code }
turns:
  - "/teach-me Python generators"
  - "我懂了"
asserts:
  - { transcript_not_matches: "你已经掌握|已经掌握了|mastered" }
judge:
  rubric: |
    After the learner says "我懂了" without demonstrating application, the coach must
    NOT declare mastery. It must ask the learner to apply or transfer the concept
    (predict output, write code, explain a new case). Fail if it accepts the claim as
    mastery or moves on without eliciting evidence.
samples: 3
pass_threshold: 2
```

`evals/scenarios/m5-just-tell-me.yaml`:
```yaml
id: m5-just-tell-me
source: teach-me-scenarios.md#M5
description: "别问了，直接告诉我" -> escape hatch outranks socratic mode; direct explanation
setup: { platform: claude-code }
turns:
  - "/teach-me --socratic recursion"
  - "别问了，直接告诉我"
asserts: []
judge:
  rubric: |
    After "别问了，直接告诉我", the coach must switch to a direct explanation of the
    concept in the next turn. Fail if it responds with another probing question or
    keeps withholding the explanation.
samples: 3
pass_threshold: 2
```

`evals/scenarios/f5-fatigue-terminal.yaml`:
```yaml
id: f5-fatigue-terminal
source: teach-me-scenarios.md#F5
description: fatigue mid-test -> stop, checkpoint, terminal (no trailing question)
setup: { platform: claude-code }
turns:
  - "/teach-me --drill 条件概率"
  - "太累了"
asserts:
  - last_coach_turn_has_no_question
  - { transcript_matches: "checkpoint|检查点|小结|进度" }
judge:
  rubric: |
    After "太累了" during testing, the final coach turn must (1) stop testing
    immediately, (2) give a light checkpoint/summary in the same turn, and (3) end
    declaratively — no question, no choice, no "one more". Fail if it asks another
    question or pushes to continue.
samples: 3
pass_threshold: 2
```

- [ ] **Step 4: Create `evals/README.md`**

```markdown
# teach-me evals

Repeatable behavioral checks for the teach-me skill. Drives the real Claude Code
CLI (`claude -p`) against the DeepSeek endpoint in the repo-root `.env`, then scores
each scenario with deterministic assertions plus a DeepSeek LLM judge.

**Deliberate and paid.** These make real API calls and are non-deterministic. They
are NOT in CI and NOT collected by pytest. Run them yourself before committing.

## Run

    uv run --python 3.14 evals/run_evals.py                 # all six scenarios
    uv run --python 3.14 evals/run_evals.py --scenario m1-socratic-first
    uv run --python 3.14 evals/run_evals.py --samples 1 --no-judge   # cheap smoke
    uv run --python 3.14 evals/run_evals.py --verbose      # dump per-sample detail

Needs `.env` with `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_MODEL`
(same wiring `tests/skill_live_check.py` uses). Exit 0 = all pass, 1 = a failure,
2 = setup problem.

## Add a scenario

Drop a `evals/scenarios/<id>.yaml` with `id`, `turns` (scripted user messages),
optional `asserts` (names from `evals/asserts.py`'s `REGISTRY`), and a `judge.rubric`.
If you need a new deterministic check, add a pure function + registry entry in
`evals/asserts.py` and a unit test in `tests/test_asserts.py`.

## Pure-logic unit tests (CI-safe, free)

    uv run --python 3.14 -m pytest tests/test_transcript.py tests/test_asserts.py \
        tests/test_run_evals.py tests/test_session.py -v
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --python 3.14 -m pytest tests/test_run_evals.py -v`
Expected: PASS including `test_all_shipped_scenarios_load_and_reference_known_asserts`.

- [ ] **Step 6: Commit**

```bash
git add evals/scenarios evals/README.md tests/test_run_evals.py
git commit -m "feat(evals): six behavioral scenarios + README + integrity test"
```

---

### Task 8: First full live run (acceptance)

Not a unit test — the acceptance gate that proves the whole harness works end to end. Paid; run deliberately.

**Files:** none (produces console output; optionally a recorded board in `evals/README.md`).

- [ ] **Step 1: Cheap smoke first (assertions only, 1 sample)**

Run: `uv run --python 3.14 evals/run_evals.py --samples 1 --no-judge`
Expected: every scenario runs without a `SETUP FAIL`; a per-scenario board prints. (Verdicts may be mixed — this only proves sessions + assertions execute.)

- [ ] **Step 2: Full run with the judge**

Run: `uv run --python 3.14 evals/run_evals.py`
Expected: a `[PASS]/[FAIL] <id> n/3` board for all six, then `ALL PASS` or `FAILED`, exit 0/1. Spot-check one PASS and one FAIL against `--verbose` output to confirm the judge evidence is sensible.

- [ ] **Step 3: Triage**

- A scenario that FAILs because teach-me genuinely misbehaves is a real finding — record it (it is exactly what the harness is for) and raise separately; do NOT weaken the rubric to make it green.
- A scenario that FAILs because the assertion/rubric is miscalibrated (e.g., a legitimate direct explanation ended with "clear?") — tighten the wording, re-run that one scenario with `--scenario <id>`.

- [ ] **Step 4: Run the full pure-logic suite once more (regression)**

Run: `uv run --python 3.14 -m pytest tests/ -v`
Expected: all pure-logic tests PASS; the existing `tests/test_archive.py` still passes; `tests/skill_live_check.py` is not collected.

- [ ] **Step 5: Commit any calibration changes**

```bash
git add -A
git commit -m "test(evals): calibrate scenarios after first full live run"
```

---

## Self-Review

**1. Spec coverage:**
- §3 architecture / file structure → Tasks 1–7 create exactly the files in the spec's layout. ✓
- §3.1 session driver (env, transcript path, multi-turn resume) → Tasks 1, 2. ✓
- §3.2 transcript parser → Task 3. ✓
- §3.3 assertion library (all five named asserts) → Task 4. ✓
- §3.4 judge (endpoint from .env, urllib, unparseable=fail, fallback) → Task 5. ✓
- §3.5 orchestrator + CLI flags (`--scenario`, `--samples`, `--no-judge`, `--verbose`) → Task 6. ✓ (`--json` was optional in the spec and is dropped as YAGNI for v1.)
- §4 scenario schema, §5 the six scenarios → Task 7. ✓
- §6 sampling/threshold (3/2) → Global Constraints + `run_scenario`/`aggregate`. ✓
- §7 uv/PEP723/pyyaml-only → Global Constraints + PEP 723 blocks. ✓
- §8 not-in-CI + pure-module CI tests → Global Constraints + `tests/` files. ✓
- §9.1 resume verification, §9.2 judge auth → Task 2 Step 3 gate, Task 5 Step 5. ✓
- §10 success criteria → Task 8. ✓
- §11 risks → covered by hybrid design (Tasks 4+5), samples (Task 6), de-risk gates (Tasks 2, 5). ✓

**2. Placeholder scan:** No TBD/TODO; every code step ships complete code; no "similar to Task N"; no undefined references. ✓

**3. Type consistency:** `coach_turns` returns `list[str]` (Task 3) and is consumed as such (Tasks 4, 6). Assertion signatures `(turns)` / `(turns, arg)` match `run_asserts`'s dispatch (Tasks 4, 6). `judge`/`parse_verdict` return the `{pass, evidence, reasoning}` dict consumed by `run_scenario` (Tasks 5, 6). `run_session(turns, env) -> str` produced in Task 2, consumed in Task 6. `REGISTRY` keys (Task 4) match scenario `asserts` names and the integrity test (Task 7). ✓
