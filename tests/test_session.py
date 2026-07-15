import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
import session  # noqa: E402
import pytest  # noqa: E402


def test_load_env_overlays_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    f = tmp_path / ".env"
    f.write_text(
        "# comment\n"
        "ANTHROPIC_BASE_URL=https://x/anthropic\n"
        "ANTHROPIC_AUTH_TOKEN=tok\n"
        "ANTHROPIC_MODEL=m\n"
        "\n",
        encoding="utf-8",
    )
    env = session.load_env(dotenv=f)
    assert env["ANTHROPIC_BASE_URL"] == "https://x/anthropic"
    assert env["ANTHROPIC_MODEL"] == "m"


def test_load_env_missing_file_raises(tmp_path):
    with pytest.raises(session.SetupError):
        session.load_env(dotenv=tmp_path / "nope.env")


def test_load_env_missing_required_key_raises(tmp_path):
    f = tmp_path / ".env"
    f.write_text("ANTHROPIC_BASE_URL=https://x\n", encoding="utf-8")
    with pytest.raises(session.SetupError):
        session.load_env(dotenv=f)


def test_repo_is_parent_of_evals():
    assert session.EVALS.name == "evals"
    assert session.REPO == session.EVALS.parent
