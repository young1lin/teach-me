import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
import run_evals  # noqa: E402
from asserts import REGISTRY  # noqa: E402


def test_run_asserts_bare_and_parameterized():
    turns = ["intro", "final answer."]
    specs = ["last_coach_turn_has_no_question", {"transcript_matches": "final"}]
    results = run_evals.run_asserts(turns, specs)
    assert results == [("last_coach_turn_has_no_question", True),
                       ("transcript_matches", True)]


def test_aggregate_majority():
    assert run_evals.aggregate([True, True, False], 2) is True
    assert run_evals.aggregate([True, False, False], 2) is False


def test_effective_threshold_caps_at_samples():
    assert run_evals.effective_threshold(2, 1) == 1
    assert run_evals.effective_threshold(2, 3) == 2


def test_excerpt_preserves_both_ends_when_long():
    ex = run_evals._excerpt(["A" * 6000, "Z" * 6000], limit=1000)
    assert ex.startswith("A") and ex.endswith("Z") and "trimmed" in ex


def test_judge_input_includes_user_turns():
    framed = run_evals._judge_input(["/teach-me x", "我懂了"],
                                    ["Let me ask...", "Now apply it."])
    assert "我懂了" in framed and "/teach-me x" in framed and "Now apply it." in framed
    assert framed.index("我懂了") < framed.index("Now apply it.")


class _FakeCoach:
    def __init__(self, turns): self._turns = turns
    def run(self, turns, env_extra=None): return list(self._turns)


class _FakeChat:
    def __init__(self, reply): self._reply = reply
    def complete(self, *, system, user, max_tokens, temperature): return self._reply


def test_run_scenario_injects_coach_and_judge():
    scenario = {"id": "x", "turns": ["/teach-me x"], "asserts": [],
                "judge": {"rubric": "must ask a question"}, "samples": 1}
    coach = _FakeCoach(["preamble", "a question?"])
    chat = _FakeChat('{"pass": true, "evidence": "?", "reasoning": "ok"}')
    r = run_evals.run_scenario(scenario, coach=coach, judge_chat=chat,
                               samples_override=1, judge_on=True)
    assert r["passed"] is True and r["n_pass"] == 1


def test_run_scenario_no_judge_skips_chat():
    scenario = {"id": "x", "turns": ["/teach-me x"], "asserts": [], "samples": 1}
    coach = _FakeCoach(["preamble", "final."])
    r = run_evals.run_scenario(scenario, coach=coach, judge_chat=None,
                               samples_override=1, judge_on=False)
    assert r["passed"] is True


def test_all_shipped_scenarios_load_and_reference_known_asserts():
    scenarios_dir = Path(__file__).resolve().parent.parent / "evals" / "scenarios"
    scenarios = run_evals.load_scenarios(scenarios_dir)
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
