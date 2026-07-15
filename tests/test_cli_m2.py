"""Integration tests for the `validate` and `consistency` CLI commands (M2)."""

import json

from spelunk_bench.cli import main

VALID = {
    "id": "fastapi-0001",
    "repo": "fastapi",
    "query": "where is the token extracted?",
    "answers": [{"path": "fastapi/security/oauth2.py", "start_line": 120, "end_line": 168}],
    "answer_type": "single",
    "difficulty": "medium",
    "notes": "",
}


def _write(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def test_validate_ok(tmp_path, capsys):
    _write(tmp_path / "fastapi.jsonl", [VALID])
    rc = main(["validate", str(tmp_path), "--corpus-yaml", "nope.yaml", "--corpus-root", "nope"])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_validate_reports_errors(tmp_path, capsys):
    bad = dict(VALID, difficulty="trivial")
    _write(tmp_path / "fastapi.jsonl", [bad])
    rc = main(["validate", str(tmp_path), "--corpus-yaml", "nope.yaml", "--corpus-root", "nope"])
    assert rc == 1
    assert "difficulty must be one of" in capsys.readouterr().err


def test_validate_no_files(tmp_path, capsys):
    rc = main(["validate", str(tmp_path), "--corpus-yaml", "nope.yaml", "--corpus-root", "nope"])
    assert rc == 0
    assert "no .jsonl files" in capsys.readouterr().out


def test_validate_with_corpus_yaml(tmp_path, capsys):
    corpus_yaml = tmp_path / "corpus.yaml"
    corpus_yaml.write_text(
        "repos:\n  - {name: fastapi, url: u, sha: s, language: python, size_class: small}\n",
        encoding="utf-8",
    )
    _write(tmp_path / "fastapi.jsonl", [VALID])
    rc = main(
        [
            "validate",
            str(tmp_path / "fastapi.jsonl"),
            "--corpus-yaml",
            str(corpus_yaml),
            "--corpus-root",
            "nope",
        ]
    )
    assert rc == 0
    assert "schema+repo" in capsys.readouterr().out


def test_consistency_clean(tmp_path, capsys):
    p1, p2 = tmp_path / "pass1", tmp_path / "pass2"
    p1.mkdir()
    p2.mkdir()
    _write(p1 / "fastapi.jsonl", [VALID])
    _write(p2 / "fastapi.jsonl", [VALID])
    rc = main(["consistency", "--pass1", str(p1), "--pass2", str(p2)])
    assert rc == 0
    assert "No disagreements" in capsys.readouterr().out


def test_consistency_flags_difference(tmp_path, capsys):
    p1, p2 = tmp_path / "pass1", tmp_path / "pass2"
    p1.mkdir()
    p2.mkdir()
    _write(p1 / "fastapi.jsonl", [VALID])
    _write(p2 / "fastapi.jsonl", [dict(VALID, difficulty="hard")])
    rc = main(["consistency", "--pass1", str(p1), "--pass2", str(p2)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Consistency report" in out
    assert "difficulty" in out


def test_consistency_output_file(tmp_path, capsys):
    p1, p2 = tmp_path / "pass1", tmp_path / "pass2"
    p1.mkdir()
    p2.mkdir()
    _write(p1 / "fastapi.jsonl", [VALID])
    _write(p2 / "fastapi.jsonl", [VALID])
    out_file = tmp_path / "report.md"
    rc = main(["consistency", "--pass1", str(p1), "--pass2", str(p2), "-o", str(out_file)])
    assert rc == 0
    assert out_file.is_file()
    assert "Consistency report" in out_file.read_text(encoding="utf-8")
