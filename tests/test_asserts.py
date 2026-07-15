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


def test_transcript_matches_and_not():
    turns = ["modes: socratic, feynman, drill"]
    assert asserts.transcript_matches(turns, "feynman")
    assert asserts.transcript_matches(turns, r"\?|？") is False  # no question mark here
    assert asserts.transcript_not_matches(turns, "leitner")


def test_total_heading_count_below():
    dump = ["Using teach-me...", "## A\n## B\n## C\n## D\ntext"]
    assert not asserts.total_heading_count_below(dump, 4)   # 4 headings: not below 4
    lean = ["Using teach-me...", "Let me ask you one thing about recursion."]
    assert asserts.total_heading_count_below(lean, 4)       # 0 headings
    assert not asserts.total_heading_count_below([], 4)     # empty -> False


def test_registry_exposes_all_by_name():
    assert set(asserts.REGISTRY) == {
        "last_coach_turn_has_no_question", "transcript_matches",
        "transcript_not_matches", "total_heading_count_below"}
