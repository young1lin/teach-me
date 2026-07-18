#!/usr/bin/env python3
"""Run teach-me behavioral evals: real teach-me sessions scored by asserts + judge.

Deliberate, paid, non-CI. Coach runs via the Claude Agent SDK; judge runs via
the Anthropic or OpenAI SDK. Both reach DeepSeek through evals/.env.

Usage (from repo root):
    uv run --project evals evals/run_evals.py
    uv run --project evals evals/run_evals.py --scenario m1-socratic-first
    uv run --project evals evals/run_evals.py --judge-backend openai
    uv run --project evals evals/run_evals.py --samples 1 --no-judge   # cheap smoke
    uv run --project evals evals/run_evals.py --verbose
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from session import load_env, SetupError
from providers import make_coach, make_chat
from asserts import REGISTRY
from judge import judge as run_judge
from seed import seeded_home

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
        else:
            (name, arg), = spec.items()
        fn = REGISTRY[name]
        ok = fn(turns, arg) if arg is not None else fn(turns)
        results.append((name, bool(ok)))
    return results


def aggregate(sample_passes: list[bool], threshold: int) -> bool:
    return sum(sample_passes) >= threshold


def effective_threshold(pass_threshold: int, samples: int) -> int:
    """Cap the pass threshold at the sample count (2-of-1 can never pass)."""
    return min(pass_threshold, samples)


def _excerpt(turns: list[str], limit: int = 8000) -> str:
    joined = "\n\n---\n\n".join(turns)
    if len(joined) <= limit:
        return joined
    half = limit // 2
    return joined[:half] + "\n\n…[trimmed]…\n\n" + joined[-half:]


def _judge_input(user_turns: list[str], turns: list[str], limit: int = 8000) -> str:
    """Frame BOTH sides so learner-keyed rubrics can see the scripted messages."""
    convo = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(user_turns))
    return (f"LEARNER MESSAGES (scripted, in order):\n{convo}\n\n"
            f"COACH RESPONSE(S):\n{_excerpt(turns, limit)}")


def _run_once(coach, turns, seed_spec):
    """One coach run; seeded into an isolated TEACH_ME_HOME when seed_spec is given."""
    if not seed_spec:
        return coach.run(turns)
    with seeded_home(seed_spec) as home:
        return coach.run(turns, env_extra={"TEACH_ME_HOME": str(home)})


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


def _print_report(results: list[dict], verbose: bool) -> None:
    for r in results:
        flag = "PASS" if r["passed"] else "FAIL"
        print(f"[{flag}] {r['id']}  {r['n_pass']}/{r['n']}")
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
    parser.add_argument("--judge-backend", choices=["anthropic", "openai"],
                        default="anthropic")
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
        coach = make_coach(env)
        judge_chat = None if args.no_judge else make_chat(args.judge_backend, env)
        results = [run_scenario(s, coach=coach, judge_chat=judge_chat,
                                samples_override=args.samples, judge_on=not args.no_judge)
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
