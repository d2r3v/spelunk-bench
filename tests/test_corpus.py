"""Tests for corpus.yaml loading (M2 slice; clone command lands in M3)."""

import pytest

from spelunk_bench.corpus import known_repo_names, load_corpus_config

SAMPLE = """
repos:
  - name: fastapi
    url: https://github.com/fastapi/fastapi
    sha: 0123456789abcdef0123456789abcdef01234567
    language: python
    size_class: medium
  - name: gin
    url: https://github.com/gin-gonic/gin
    sha: fedcba9876543210fedcba9876543210fedcba98
    language: go
    size_class: small
"""


def test_load_corpus_config(tmp_path):
    path = tmp_path / "corpus.yaml"
    path.write_text(SAMPLE, encoding="utf-8")
    specs = load_corpus_config(path)
    assert [s.name for s in specs] == ["fastapi", "gin"]
    assert specs[0].language == "python"


def test_known_repo_names(tmp_path):
    path = tmp_path / "corpus.yaml"
    path.write_text(SAMPLE, encoding="utf-8")
    assert known_repo_names(path) == frozenset({"fastapi", "gin"})


def test_missing_repos_key(tmp_path):
    path = tmp_path / "corpus.yaml"
    path.write_text("something: else\n", encoding="utf-8")
    with pytest.raises(ValueError, match="repos"):
        load_corpus_config(path)


def test_bad_size_class(tmp_path):
    path = tmp_path / "corpus.yaml"
    path.write_text(
        "repos:\n  - {name: x, url: u, sha: s, language: py, size_class: huge}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="size_class"):
        load_corpus_config(path)
