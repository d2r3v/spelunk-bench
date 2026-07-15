"""Tests for the query schema validator (M2)."""

import json
from pathlib import Path

from spelunk_bench.queries import (
    Answer,
    Query,
    load_queries,
    validate_paths,
    validate_query_dict,
)

VALID = {
    "id": "fastapi-0001",
    "repo": "fastapi",
    "query": "where is the OAuth2 password flow token extracted from the request?",
    "answers": [{"path": "fastapi/security/oauth2.py", "start_line": 120, "end_line": 168}],
    "answer_type": "single",
    "difficulty": "medium",
    "notes": "",
}


def _check(obj, *, known_repos=None, corpus_root=None, seen_ids=None):
    return validate_query_dict(
        obj,
        file="q.jsonl",
        line=1,
        known_repos=known_repos,
        corpus_root=corpus_root,
        seen_ids={} if seen_ids is None else seen_ids,
    )


def _messages(issues):
    return " | ".join(i.message for i in issues)


def test_valid_query_has_no_issues():
    assert _check(dict(VALID)) == []


def test_valid_query_with_known_repo():
    assert _check(dict(VALID), known_repos=frozenset({"fastapi"})) == []


def test_missing_required_key():
    obj = dict(VALID)
    del obj["difficulty"]
    assert "missing required keys" in _messages(_check(obj))


def test_unknown_key_flagged():
    obj = dict(VALID)
    obj["answr"] = []  # typo
    assert "unknown keys" in _messages(_check(obj))


def test_bad_id_format():
    obj = dict(VALID, id="fastapi-1")
    assert "must match" in _messages(_check(obj))


def test_id_repo_prefix_mismatch():
    obj = dict(VALID, id="wagtail-0001")
    assert "does not match repo" in _messages(_check(obj))


def test_unknown_repo():
    obj = dict(VALID, repo="unknownrepo", id="unknownrepo-0001")
    issues = _check(obj, known_repos=frozenset({"fastapi"}))
    assert "unknown repo" in _messages(issues)


def test_bad_difficulty():
    obj = dict(VALID, difficulty="trivial")
    assert "difficulty must be one of" in _messages(_check(obj))


def test_single_with_two_answers():
    obj = dict(
        VALID,
        answer_type="single",
        answers=[
            {"path": "a.py", "start_line": 1, "end_line": 2},
            {"path": "b.py", "start_line": 1, "end_line": 2},
        ],
    )
    assert "requires exactly 1 answer" in _messages(_check(obj))


def test_multi_with_one_answer():
    obj = dict(VALID, answer_type="multi")
    assert "requires >= 2 answers" in _messages(_check(obj))


def test_multi_with_two_answers_ok():
    obj = dict(
        VALID,
        answer_type="multi",
        answers=[
            {"path": "a.py", "start_line": 1, "end_line": 2},
            {"path": "b.py", "start_line": 3, "end_line": 4},
        ],
    )
    assert _check(obj) == []


def test_empty_answers():
    obj = dict(VALID, answers=[])
    assert "non-empty list" in _messages(_check(obj))


def test_start_after_end():
    obj = dict(VALID, answers=[{"path": "a.py", "start_line": 50, "end_line": 10}])
    assert "must be >= start_line" in _messages(_check(obj))


def test_start_line_below_one():
    obj = dict(VALID, answers=[{"path": "a.py", "start_line": 0, "end_line": 10}])
    assert "must be >= 1" in _messages(_check(obj))


def test_backslash_path_flagged():
    obj = dict(VALID, answers=[{"path": "a\\b.py", "start_line": 1, "end_line": 2}])
    assert "forward slashes" in _messages(_check(obj))


def test_absolute_path_flagged():
    obj = dict(VALID, answers=[{"path": "/etc/passwd", "start_line": 1, "end_line": 2}])
    assert "repo-relative" in _messages(_check(obj))


def test_non_integer_line_flagged():
    obj = dict(VALID, answers=[{"path": "a.py", "start_line": "1", "end_line": 2}])
    assert "must be an integer" in _messages(_check(obj))


def test_boolean_line_flagged():
    # bool is an int subclass in Python; make sure we reject it explicitly.
    obj = dict(VALID, answers=[{"path": "a.py", "start_line": True, "end_line": 2}])
    assert "must be an integer" in _messages(_check(obj))


def test_duplicate_id_across_records():
    seen: dict[str, str] = {}
    first = _check(dict(VALID), seen_ids=seen)
    second = _check(dict(VALID), seen_ids=seen)
    assert first == []
    assert "duplicate id" in _messages(second)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def test_validate_paths_clean_file(tmp_path):
    _write_jsonl(tmp_path / "fastapi.jsonl", [VALID])
    report = validate_paths([tmp_path])
    assert report.ok
    assert report.files == 1
    assert report.queries == 1


def test_validate_paths_reports_invalid_json(tmp_path):
    (tmp_path / "bad.jsonl").write_text("{not json}\n", encoding="utf-8")
    report = validate_paths([tmp_path])
    assert not report.ok
    assert "invalid JSON" in _messages(report.issues)


def test_validate_paths_no_files(tmp_path):
    report = validate_paths([tmp_path])
    assert report.ok
    assert report.files == 0


def test_corpus_check_missing_path(tmp_path):
    corpus_root = tmp_path / "corpus"
    (corpus_root / "fastapi").mkdir(parents=True)
    issues = _check(dict(VALID), corpus_root=corpus_root)
    assert "not found in corpus" in _messages(issues)


def test_corpus_check_span_beyond_eof(tmp_path):
    corpus_root = tmp_path / "corpus"
    repo = corpus_root / "fastapi"
    (repo / "fastapi" / "security").mkdir(parents=True)
    (repo / "fastapi" / "security" / "oauth2.py").write_text("line1\nline2\n", encoding="utf-8")
    obj = dict(
        VALID,
        answers=[{"path": "fastapi/security/oauth2.py", "start_line": 1, "end_line": 999}],
    )
    assert "exceeds file length 2" in _messages(_check(obj, corpus_root=corpus_root))


def test_corpus_check_valid_span(tmp_path):
    corpus_root = tmp_path / "corpus"
    repo = corpus_root / "fastapi"
    (repo / "fastapi" / "security").mkdir(parents=True)
    (repo / "fastapi" / "security" / "oauth2.py").write_text(
        "\n".join(f"line{i}" for i in range(1, 201)) + "\n", encoding="utf-8"
    )
    assert _check(dict(VALID), corpus_root=corpus_root) == []


def test_corpus_check_skipped_when_repo_absent(tmp_path):
    # corpus_root exists but this repo isn't cloned -> corpus checks skipped.
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    assert _check(dict(VALID), corpus_root=corpus_root) == []


def test_load_queries_roundtrip(tmp_path):
    path = tmp_path / "fastapi.jsonl"
    _write_jsonl(path, [VALID])
    (q,) = load_queries(path)
    assert q == Query(
        id="fastapi-0001",
        repo="fastapi",
        query=VALID["query"],
        answers=[Answer("fastapi/security/oauth2.py", 120, 168)],
        answer_type="single",
        difficulty="medium",
        notes="",
    )
