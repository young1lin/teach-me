# Review Behavioral Eval — Store Seeding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the eval harness an isolated, seeded `TEACH_ME_HOME` so it can behaviorally test the `/teach-me review` flow, and add the pass/fail review scenarios.

**Architecture:** A new `evals/seed.py` writes teach-me records into a throwaway temp home, reusing `store.py`'s own serializer (same repo) so the seed can never drift from what the skill reads. `AgentSDKCoach.run` gains an `env_extra` argument that merges `{TEACH_ME_HOME: …}` into the CLI env for one run. `run_evals.py` seeds a fresh home per sample when a scenario declares `setup.seed`. Two new scenarios exercise the pass and fail paths.

**Tech Stack:** Python 3.11+ (evals uv project), pytest, PyYAML, the Claude Agent SDK (real coach), `store.py` (stdlib-only, imported for its record serializer). Coach + judge run on the existing DeepSeek `evals/.env`.

## Global Constraints

- **`store.py` is NOT modified** by this work. `seed.py` imports it read-only.
- **Offline unit suite stays green at every commit** (`uv run --project evals python -m pytest -q tests/`). All new tests are offline; the seed round-trip shells out to `store.py` locally (no network).
- **No secrets/PII in tracked files.** Seeds use `tempfile.mkdtemp` + `TEACH_ME_HOME`; never the operator's real `~/.teach-me`. `evals/.env` stays gitignored.
- **Never weaken an assert or rubric to turn a genuine teach-me miss green.** The review rubrics mirror teach-me's Red Flags (SKILL.md / references/review.md).
- **Paid run is gated:** the live `run_evals.py` on `r1`/`r2` costs real tokens — get an explicit go-ahead before running it. It is never part of the unit suite or CI.
- **Commit author** is always `young1lin <2550110827@qq.com>`; AI credited only via a `Co-Authored-By:` trailer naming the actual model. Commit messages in English.
- **Canonical self-test heading** the review flow reads: `## Review question (self-test prompt)` (exact).
- **`store.py --config <path>` is a GLOBAL flag** — it precedes the subcommand: `store.py --config H/config.json due`.

---

## File Structure

- `evals/seed.py` (new) — `seeded_home(seed_spec)` context manager + `write_record`. Reuses `store.frontmatter/slugify/record_path/init_store/SCHEMA_VERSION`.
- `evals/providers.py` (modify) — `CoachSession.run` / `AgentSDKCoach.run` gain `env_extra`.
- `evals/run_evals.py` (modify) — per-sample seeding via `_run_once`.
- `evals/scenarios/r1-review-recall.yaml`, `evals/scenarios/r2-review-fail-relearn.yaml` (new).
- `tests/test_seed.py` (new) — seed round-trips through `store.py`; isolation + cleanup.
- `tests/test_providers.py` (modify) — factory takes the merged env; new env-merge test.
- `tests/test_run_evals.py` (modify) — `_FakeCoach.run` accepts `env_extra`; seeding test; scenario count 6 → 8.

---

## Task 1: Seeding facility (`evals/seed.py`)

**Files:**
- Create: `evals/seed.py`
- Test: `tests/test_seed.py`

**Interfaces:**
- Consumes: `store.frontmatter(dict)->str`, `store.slugify(str)->str`, `store.record_path(root, topic, concept)->Path`, `store.init_store(root=str, path=Path)->dict`, `store.SCHEMA_VERSION` (int).
- Produces: `seeded_home(seed_spec: list[dict]) -> ContextManager[Path]` yielding an isolated `TEACH_ME_HOME`; `write_record(root: Path, rec: dict) -> Path`. A `rec` is `{topic, concept, review_question, state?="demonstrated", deps?=[], project?="-", date?=today, body?=""}`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_seed.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --project evals python -m pytest -q tests/test_seed.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'seed'`.

- [ ] **Step 3: Write the implementation**

Create `evals/seed.py`:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --project evals python -m pytest -q tests/test_seed.py`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add evals/seed.py tests/test_seed.py
git commit -m "feat(evals): store seeding for isolated review fixtures

Co-Authored-By: Claude <MODEL> <noreply@anthropic.com>"
```

---

## Task 2: Coach `env_extra` seam (`evals/providers.py`)

**Files:**
- Modify: `evals/providers.py` (the `CoachSession` protocol and `AgentSDKCoach`)
- Test: `tests/test_providers.py`

**Interfaces:**
- Produces: `CoachSession.run(turns: list[str], env_extra: dict | None = None) -> list[str]`. `AgentSDKCoach` merges `{**self._env, **env_extra}` and passes the merged env to `self._client_factory(env)`; `_default_client(env)` builds `ClaudeAgentOptions(env=env, …)`.
- Consumes (later tasks): `run_evals._run_once` calls `coach.run(turns, env_extra={"TEACH_ME_HOME": str(home)})`.

- [ ] **Step 1: Update the existing factory test + add the merge test (failing)**

In `tests/test_providers.py`, change the existing factory lambda (line ~120) from no-arg to one-arg:

```python
    coach = providers.AgentSDKCoach(env={}, repo="/repo", client_factory=lambda env: fake)
```

Then add:

```python
def test_env_extra_merges_over_base_env_for_client():
    captured = {}
    def factory(env):
        captured.update(env)
        return _FakeSDKClient([[_Assistant2([_Text2("ok")])]])
    coach = providers.AgentSDKCoach(env={"ANTHROPIC_MODEL": "deepseek"}, repo="/repo",
                                    client_factory=factory)
    out = coach.run(["/teach-me review"], env_extra={"TEACH_ME_HOME": "/tmp/h"})
    assert out == ["ok"]
    assert captured == {"ANTHROPIC_MODEL": "deepseek", "TEACH_ME_HOME": "/tmp/h"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --project evals python -m pytest -q tests/test_providers.py`
Expected: FAIL — old test now passes a 1-arg lambda into code that calls it with 0 args (or the new test errors because `run` has no `env_extra`).

- [ ] **Step 3: Implement the seam**

In `evals/providers.py`, update the protocol:

```python
class CoachSession(Protocol):
    """An agentic skill run over scripted turns. The coach sits on this."""

    def run(self, turns: list[str], env_extra: dict | None = None) -> list[str]: ...
```

And `AgentSDKCoach` — replace `_default_client`, `run`, `_run_async`:

```python
    def _default_client(self, env: dict):
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
        options = ClaudeAgentOptions(
            env=env,                       # forwarded to the CLI → routes to DeepSeek
            cwd=self._repo,
            plugins=[{"type": "local", "path": self._repo}],
            setting_sources=["project"],   # load this repo's teach-me skill
            permission_mode="bypassPermissions",
        )
        return ClaudeSDKClient(options=options)

    def run(self, turns: list[str], env_extra: dict | None = None) -> list[str]:
        import asyncio
        return asyncio.run(self._run_async(turns, env_extra or {}))

    async def _run_async(self, turns: list[str], env_extra: dict) -> list[str]:
        messages = []
        client = self._client_factory({**self._env, **env_extra})
        async with client:
            for turn in turns:
                await client.query(turn)
                async for msg in client.receive_response():
                    messages.append(msg)
        return coach_turns(messages)
```

(The default `client_factory` is `self._default_client`, which now takes the merged env.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --project evals python -m pytest -q tests/test_providers.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add evals/providers.py tests/test_providers.py
git commit -m "feat(evals): thread per-run env_extra into the coach (TEACH_ME_HOME)

Co-Authored-By: Claude <MODEL> <noreply@anthropic.com>"
```

---

## Task 3: Per-sample seeding wiring (`evals/run_evals.py`)

**Files:**
- Modify: `evals/run_evals.py`
- Test: `tests/test_run_evals.py`

**Interfaces:**
- Consumes: `seed.seeded_home` (Task 1), `coach.run(turns, env_extra=…)` (Task 2).
- Produces: `run_scenario` reads `scenario["setup"]["seed"]`; for each sample it seeds a fresh home and passes `env_extra={"TEACH_ME_HOME": str(home)}`; scenarios without `seed` are unchanged.

- [ ] **Step 1: Update `_FakeCoach` + add the seeding test (failing)**

In `tests/test_run_evals.py`, update `_FakeCoach.run` to accept `env_extra`:

```python
class _FakeCoach:
    def __init__(self, turns): self._turns = turns
    def run(self, turns, env_extra=None): return list(self._turns)
```

Add:

```python
def test_run_scenario_seeds_home_and_passes_teach_me_home():
    captured = []
    class _SeedCoach:
        def run(self, turns, env_extra=None):
            captured.append(env_extra)
            return ["preamble", "the event loop question?"]
    scenario = {"id": "r", "turns": ["/teach-me review"],
                "setup": {"seed": [{"topic": "t", "concept": "c",
                                    "review_question": "explain the event loop"}]},
                "asserts": [], "samples": 1}
    r = run_evals.run_scenario(scenario, coach=_SeedCoach(), judge_chat=None,
                               samples_override=1, judge_on=False)
    assert r["passed"] is True
    assert captured and "TEACH_ME_HOME" in (captured[0] or {})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --project evals python -m pytest -q tests/test_run_evals.py`
Expected: FAIL — `run_scenario` does not seed, so `captured[0]` is `None` (no `TEACH_ME_HOME`).

- [ ] **Step 3: Implement per-sample seeding**

In `evals/run_evals.py`, add the import near the top (with the other local imports):

```python
from seed import seeded_home
```

Add a helper above `run_scenario`:

```python
def _run_once(coach, turns, seed_spec):
    """One coach run; seeded into an isolated TEACH_ME_HOME when seed_spec is given."""
    if not seed_spec:
        return coach.run(turns)
    with seeded_home(seed_spec) as home:
        return coach.run(turns, env_extra={"TEACH_ME_HOME": str(home)})
```

In `run_scenario`, replace the sampling loop's coach call:

```python
def run_scenario(scenario: dict, *, coach, judge_chat, samples_override, judge_on) -> dict:
    samples = samples_override or scenario.get("samples", 3)
    threshold = effective_threshold(scenario.get("pass_threshold", 2), samples)
    seed_spec = (scenario.get("setup") or {}).get("seed")
    per_sample = []
    for _ in range(samples):
        turns = _run_once(coach, scenario["turns"], seed_spec)
        assert_results = run_asserts(turns, scenario.get("asserts"))
        asserts_ok = all(ok for _, ok in assert_results)
        verdict = {"pass": True, "evidence": "", "reasoning": "judge skipped"}
        if judge_on and judge_chat is not None and scenario.get("judge"):
            ji = _judge_input(scenario["turns"], turns)
            verdict = run_judge(judge_chat, scenario["judge"]["rubric"], ji)
        per_sample.append({"asserts": assert_results, "judge": verdict,
                           "ok": asserts_ok and verdict["pass"]})
    n_pass = sum(s["ok"] for s in per_sample)
    return {"id": scenario["id"], "n": samples, "n_pass": n_pass,
            "passed": aggregate([s["ok"] for s in per_sample], threshold),
            "samples": per_sample}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --project evals python -m pytest -q tests/test_run_evals.py`
Expected: PASS (existing tests still green; new seeding test passes).

- [ ] **Step 5: Commit**

```bash
git add evals/run_evals.py tests/test_run_evals.py
git commit -m "feat(evals): seed a fresh isolated home per sample for seeded scenarios

Co-Authored-By: Claude <MODEL> <noreply@anthropic.com>"
```

---

## Task 4: Review scenarios `r1` + `r2`

**Files:**
- Create: `evals/scenarios/r1-review-recall.yaml`
- Create: `evals/scenarios/r2-review-fail-relearn.yaml`
- Test: `tests/test_run_evals.py` (integrity: count 6 → 8, id set, seed well-formedness)

**Interfaces:**
- Consumes: the `setup.seed` seeding wiring (Task 3) and the `transcript_matches` assert (existing `REGISTRY`).

- [ ] **Step 1: Update the integrity test (failing)**

In `tests/test_run_evals.py`, in `test_all_shipped_scenarios_load_and_reference_known_asserts`, change the count and id set and add a seed check:

```python
    assert len(scenarios) == 8
    ids = {s["id"] for s in scenarios}
    assert ids == {"f1-no-dump", "m1-socratic-first", "m10-unknown-flag",
                   "f3-mastery-gate", "m5-just-tell-me", "f5-fatigue-terminal",
                   "r1-review-recall", "r2-review-fail-relearn"}
    for s in scenarios:
        assert s["turns"] and isinstance(s["turns"], list)
        assert s.get("judge", {}).get("rubric")
        for spec in s.get("asserts") or []:
            name = spec if isinstance(spec, str) else next(iter(spec))
            assert name in REGISTRY, f"{s['id']} references unknown assert {name}"
        for rec in (s.get("setup") or {}).get("seed") or []:
            assert rec.get("topic") and rec.get("concept") and rec.get("review_question")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --project evals python -m pytest -q tests/test_run_evals.py::test_all_shipped_scenarios_load_and_reference_known_asserts`
Expected: FAIL — `assert len(scenarios) == 8` fails (only 6 exist).

- [ ] **Step 3: Create the two scenarios**

Create `evals/scenarios/r1-review-recall.yaml`:

```yaml
id: r1-review-recall
source: docs/superpowers/specs/2026-07-19-review-eval-seeding-design.md#7
description: /teach-me review quizzes a due concept with its stored self-test question
setup:
  platform: claude-code
  seed:
    - topic: python-async
      concept: event-loop
      state: demonstrated
      review_question: "Without looking anything up, explain what the event loop does the moment a coroutine hits await."
turns:
  - "/teach-me review"
asserts:
  - { transcript_matches: "event.?loop|事件循环|await" }
judge:
  rubric: |
    The learner ran /teach-me review with exactly one concept due. The coach must
    pose that concept's stored self-test question (about what the event loop does
    when a coroutine hits await) as a retrieval check and let the learner attempt
    it. It must NOT dump the answer, deliver a lecture, or auto-advance without
    asking. Pass only if the coach presents a retrieval question and waits for the
    learner.
samples: 3
pass_threshold: 2
```

Create `evals/scenarios/r2-review-fail-relearn.yaml`:

```yaml
id: r2-review-fail-relearn
source: docs/superpowers/specs/2026-07-19-review-eval-seeding-design.md#7
description: a failed review marks the concept stale and offers to relearn it now
setup:
  platform: claude-code
  seed:
    - topic: python-async
      concept: event-loop
      state: demonstrated
      review_question: "Without looking anything up, explain what the event loop does the moment a coroutine hits await."
turns:
  - "/teach-me review"
  - "不会，忘了"
judge:
  rubric: |
    The learner ran /teach-me review, was quizzed on the due concept, and answered
    that they cannot recall it ("不会，忘了"). The coach must treat the concept as no
    longer solid (stale) and ASK whether to relearn it now — offering the choice,
    not forcing a relearn and not silently moving on as if it passed. Pass only if
    the coach acknowledges the miss and offers to relearn/review it now.
samples: 3
pass_threshold: 2
```

- [ ] **Step 4: Run the offline suite to verify integrity passes**

Run: `uv run --project evals python -m pytest -q tests/`
Expected: PASS (all offline tests, including the 8-scenario integrity check).

- [ ] **Step 5: Commit**

```bash
git add evals/scenarios/r1-review-recall.yaml evals/scenarios/r2-review-fail-relearn.yaml tests/test_run_evals.py
git commit -m "test(evals): review-flow scenarios r1 (recall) and r2 (fail->relearn)

Co-Authored-By: Claude <MODEL> <noreply@anthropic.com>"
```

---

## After all tasks

- Full offline suite green: `uv run --project evals python -m pytest -q tests/`.
- Validators green: `python scripts/validate.py` and `python scripts/validate_skill.py`.
- The **paid** run of `r1`/`r2` on DeepSeek is a separate, explicitly-gated step (Global Constraints) — do NOT run it as part of implementation. Present it to the human for go-ahead:
  `uv run --project evals evals/run_evals.py --scenario r1-review-recall` and
  `--scenario r2-review-fail-relearn` (add `--samples 1` for a cheaper first look).

## Self-Review

- **Spec coverage:** seeding facility (§5,§6 → Task 1), `env_extra` seam (§6 → Task 2), per-sample seeding (§4.4,§6 → Task 3), r1/r2 scenarios (§7 → Task 4), offline tests (§8 → all tasks). DeepSeek-only and no store.py change (§3) honored. ✔
- **Placeholder scan:** the only `<MODEL>` tokens are in commit trailers, filled at execution with the actual model. No TBD/TODO; all code is complete. ✔
- **Type consistency:** `seeded_home(list[dict]) -> ContextManager[Path]`, `write_record(Path, dict) -> Path`, `run(turns, env_extra=None)`, `_run_once(coach, turns, seed_spec)` are used identically across tasks. `store` symbols (`frontmatter`, `slugify`, `record_path`, `init_store`, `split_record`, `SCHEMA_VERSION`) match `store.py`. ✔
