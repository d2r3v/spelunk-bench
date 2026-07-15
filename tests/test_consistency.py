"""Tests for the two-pass consistency checker (M2)."""

from spelunk_bench.consistency import (
    compare_passes,
    counts_by_repo,
    render_report,
)
from spelunk_bench.queries import Answer, Query


def q(
    qid="fastapi-0001",
    repo="fastapi",
    answers=None,
    answer_type="single",
    difficulty="medium",
):
    if answers is None:
        answers = [Answer("a.py", 10, 20)]
    return Query(qid, repo, "where is x?", answers, answer_type, difficulty)


def _kinds(flags):
    return {f.kind for f in flags}


def test_identical_passes_no_flags():
    assert compare_passes([q()], [q()]) == []


def test_answer_type_mismatch():
    p1 = [q(answer_type="single", answers=[Answer("a.py", 10, 20)])]
    p2 = [
        q(
            answer_type="multi",
            answers=[Answer("a.py", 10, 20), Answer("b.py", 1, 5)],
        )
    ]
    flags = compare_passes(p1, p2)
    # both answer_type and answer_set differ here
    assert "answer_type" in _kinds(flags)
    assert "answer_set" in _kinds(flags)


def test_difficulty_mismatch():
    flags = compare_passes([q(difficulty="easy")], [q(difficulty="hard")])
    assert _kinds(flags) == {"difficulty"}
    assert "easy vs hard" in flags[0].detail


def test_answer_set_mismatch():
    p1 = [q(answers=[Answer("a.py", 10, 20)])]
    p2 = [q(answers=[Answer("b.py", 10, 20)])]
    flags = compare_passes(p1, p2)
    assert _kinds(flags) == {"answer_set"}


def test_span_drift_flagged_when_over_threshold():
    p1 = [q(answers=[Answer("a.py", 10, 20)])]
    p2 = [q(answers=[Answer("a.py", 10, 40)])]  # end differs by 20 > 10
    flags = compare_passes(p1, p2)
    assert _kinds(flags) == {"span_drift"}


def test_span_drift_not_flagged_within_threshold():
    p1 = [q(answers=[Answer("a.py", 10, 20)])]
    p2 = [q(answers=[Answer("a.py", 12, 28)])]  # both within 10
    assert compare_passes(p1, p2) == []


def test_only_in_pass1():
    flags = compare_passes([q(qid="fastapi-0001")], [])
    assert _kinds(flags) == {"only_in_pass1"}


def test_only_in_pass2():
    flags = compare_passes([], [q(qid="fastapi-0002")])
    assert _kinds(flags) == {"only_in_pass2"}


def test_counts_by_repo():
    p1 = [
        q(qid="fastapi-0001", difficulty="easy"),
        q(qid="gin-0001", repo="gin", difficulty="easy"),
    ]
    p2 = [
        q(qid="fastapi-0001", difficulty="hard"),
        q(qid="gin-0001", repo="gin", difficulty="hard"),
    ]
    counts = counts_by_repo(compare_passes(p1, p2))
    assert counts["fastapi"]["difficulty"] == 1
    assert counts["gin"]["difficulty"] == 1


def test_render_report_clean():
    out = render_report([])
    assert "No disagreements" in out


def test_render_report_with_flags():
    flags = compare_passes([q(difficulty="easy")], [q(difficulty="hard")])
    out = render_report(flags)
    assert "# Consistency report" in out
    assert "fastapi" in out
    assert "difficulty" in out
