"""Env/config bootstrap for the eval harness.

Loads evals/.env as an overlay on the current environment so nested SDK clients
(coach + judge) reach DeepSeek. No subprocess/transport code lives here anymore
— that moved to providers.py.
"""
from __future__ import annotations

import os
from pathlib import Path

EVALS = Path(__file__).resolve().parent
REPO = EVALS.parent

REQUIRED = ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL")


class SetupError(RuntimeError):
    """Raised when the harness is misconfigured."""


def load_env(dotenv=None) -> dict:
    """Overlay a dotenv file onto a copy of os.environ; validate required keys."""
    path = Path(dotenv) if dotenv else EVALS / ".env"
    if not path.exists():
        raise SetupError(f"missing env file: {path} (copy .env.example to evals/.env)")
    env = os.environ.copy()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    missing = [k for k in REQUIRED if not env.get(k)]
    if missing:
        raise SetupError(f"missing required env keys: {', '.join(missing)}")
    return env
