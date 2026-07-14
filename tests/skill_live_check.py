#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""Live functional check for the teach-me skill — drives the real Claude Code CLI.

Loads the API endpoint from the repo-root `.env` (gitignored; e.g. DeepSeek's
Anthropic-compatible endpoint) into the environment via Python, then runs
`claude -p` headless and verifies the skill's core contract end to end:

  T1  an explicit `/teach-me` invocation loads the skill into the session
  T2  a "teach me ..." request WITHOUT the token does NOT load it (no auto-invoke)

Detection: injected SKILL.md content is not echoed in stream-json output, so
each check inspects the session transcript Claude Code writes to
`~/.claude/projects/<project>/<session_id>.jsonl` for a phrase that exists
only in SKILL.md.

Usage:
    uv run --python 3.14 tests/skill_live_check.py   # default: uv, latest Python
    python tests/skill_live_check.py                 # fallback: global Python 3.11+

Exit codes: 0 = all checks pass, 1 = a check failed, 2 = setup problem.
(Named *_check.py, not test_*.py, so pytest never collects it — it costs real
API calls and is run deliberately, not as part of the unit-test suite.)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    print("SETUP FAIL - Python 3.11+ required")
    sys.exit(2)

REPO = Path(__file__).resolve().parent.parent
# Exists only in skills/teach-me/SKILL.md (the "When to Use" heading) — its
# presence in a session transcript proves the skill entered that session.
MARKER = "trigger is explicit and manual"
PER_CALL_TIMEOUT_S = 600


def load_env() -> dict[str, str]:
    dotenv = REPO / ".env"
    if not dotenv.is_file():
        print(f"SETUP FAIL - missing {dotenv} (ANTHROPIC_BASE_URL/AUTH_TOKEN/...)")
        sys.exit(2)
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


def run_claude(prompt: str, env: dict[str, str]) -> str:
    """Run one headless claude session; return its on-disk transcript text."""
    exe = shutil.which("claude")
    if not exe:
        print("SETUP FAIL - claude CLI not on PATH")
        sys.exit(2)
    proc = subprocess.run(
        [exe, "-p", prompt,
         "--output-format", "stream-json", "--verbose",
         "--max-turns", "4",
         "--allowedTools", "Skill"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO, env=env, timeout=PER_CALL_TIMEOUT_S,
    )
    session_id = ""
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        session_id = event.get("session_id") or session_id
    if not session_id:
        print("SETUP FAIL - no session_id in claude output; stderr tail:")
        print("\n".join(proc.stderr.splitlines()[-5:]))
        sys.exit(2)
    path = transcript_path(session_id)
    if not path.is_file():
        print(f"SETUP FAIL - transcript not found: {path}")
        sys.exit(2)
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    env = load_env()
    ok = True

    print("T1: claude -p '/teach-me git rebase'")
    transcript = run_claude("/teach-me git rebase", env)
    if MARKER in transcript:
        print("T1 PASS - explicit invocation loaded SKILL.md into the session")
    else:
        ok = False
        print("T1 FAIL - SKILL.md content not in the session transcript")

    print("T2: claude -p 'teach me how git rebase works, briefly'")
    transcript = run_claude("teach me how git rebase works, briefly", env)
    if MARKER not in transcript and not re.search(r'"skill"\s*:\s*"teach-me"',
                                                  transcript):
        print("T2 PASS - skill was not auto-invoked without the explicit token")
    else:
        ok = False
        print("T2 FAIL - skill loaded without an explicit /teach-me token")

    print("ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
