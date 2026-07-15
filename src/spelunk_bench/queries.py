"""Query dataset schema, loading, and validation.

A query is one JSON object per line (JSONL) with the shape documented in
docs/DESIGN.md §4 and constrained by docs/LABELING.md §6. This module owns the
data model (:class:`Query`, :class:`Answer`), a strict loader, and the schema +
corpus validator behind ``spelunk-bench validate``.

Validation is split in two, matching the sequencing note in docs/PLAN.md:

* **schema checks** — pure, run whenever; no corpus needed.
* **corpus checks** — a gold path exists at the pinned SHA and its span lies
  within the file; these activate only for repos whose checkout is present
  under the corpus root, and are silently skipped otherwise.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

DIFFICULTIES = frozenset({"easy", "medium", "hard"})
ANSWER_TYPES = frozenset({"single", "multi"})

# id is "<repo>-NNNN"; the repo portion must equal the record's own repo field.
_ID_RE = re.compile(r"^(?P<repo>.+)-(?P<num>\d{4})$")

_QUERY_KEYS = frozenset({"id", "repo", "query", "answers", "answer_type", "difficulty", "notes"})
_REQUIRED_QUERY_KEYS = frozenset({"id", "repo", "query", "answers", "answer_type", "difficulty"})
_ANSWER_KEYS = frozenset({"path", "start_line", "end_line"})


@dataclass(frozen=True)
class Answer:
    """A single gold location: a repo-relative path and an inclusive line span."""

    path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class Query:
    """One labeled query with its gold answer set."""

    id: str
    repo: str
    query: str
    answers: list[Answer]
    answer_type: str
    difficulty: str
    notes: str = ""


@dataclass(frozen=True)
class ValidationIssue:
    """A single problem found while validating a dataset file.

    ``line`` is 1-indexed into the source JSONL file; 0 marks a file-level
    problem with no single offending line (e.g. a file that cannot be read).
    """

    file: str
    line: int
    query_id: str | None
    message: str

    def __str__(self) -> str:
        where = f"{self.file}:{self.line}"
        who = f" [{self.query_id}]" if self.query_id else ""
        return f"{where}:{who} {self.message}"


@dataclass
class ValidationReport:
    """Outcome of validating one or more dataset files."""

    files: int = 0
    queries: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def read_jsonl_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Yield ``(line_no, raw_line)`` for each non-blank line in ``path``."""
    with path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            if raw.strip():
                yield line_no, raw


def load_queries(path: Path) -> list[Query]:
    """Strictly parse a JSONL file into :class:`Query` objects.

    Assumes the file has already passed :func:`validate_paths`; raises
    ``ValueError`` on the first structural problem. Used by the consistency
    checker, which runs on already-validated passes.
    """
    queries: list[Query] = []
    for line_no, raw in read_jsonl_lines(path):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        try:
            answers = [
                Answer(a["path"], int(a["start_line"]), int(a["end_line"])) for a in obj["answers"]
            ]
            queries.append(
                Query(
                    id=obj["id"],
                    repo=obj["repo"],
                    query=obj["query"],
                    answers=answers,
                    answer_type=obj["answer_type"],
                    difficulty=obj["difficulty"],
                    notes=obj.get("notes", ""),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{path}:{line_no}: malformed query record: {exc}") from exc
    return queries


def _file_line_count(path: Path) -> int:
    data = path.read_bytes()
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def _validate_answer(
    answer: object,
    *,
    file: str,
    line: int,
    query_id: str | None,
    repo: str,
    corpus_repo_root: Path | None,
) -> Iterator[ValidationIssue]:
    def issue(msg: str) -> ValidationIssue:
        return ValidationIssue(file, line, query_id, msg)

    if not isinstance(answer, dict):
        yield issue("each answer must be an object")
        return

    unknown = set(answer) - _ANSWER_KEYS
    if unknown:
        yield issue(f"answer has unknown keys: {sorted(unknown)}")
    missing = _ANSWER_KEYS - set(answer)
    if missing:
        yield issue(f"answer missing keys: {sorted(missing)}")
        return

    path = answer["path"]
    start = answer["start_line"]
    end = answer["end_line"]

    path_ok = isinstance(path, str) and path
    if not path_ok:
        yield issue("answer.path must be a non-empty string")
    else:
        if "\\" in path:
            yield issue(f"answer.path must use forward slashes: {path!r}")
        if path.startswith("/"):
            yield issue(f"answer.path must be repo-relative, not absolute: {path!r}")

    lines_ok = True
    for name, value in (("start_line", start), ("end_line", end)):
        if isinstance(value, bool) or not isinstance(value, int):
            yield issue(f"answer.{name} must be an integer")
            lines_ok = False
    if lines_ok:
        if start < 1:
            yield issue(f"answer.start_line must be >= 1 (got {start})")
        if end < start:
            yield issue(f"answer.end_line ({end}) must be >= start_line ({start})")

    # Corpus check: only when this repo's checkout is present.
    if path_ok and lines_ok and corpus_repo_root is not None and "\\" not in path:
        target = corpus_repo_root / path
        if not target.is_file():
            yield issue(f"gold path not found in corpus/{repo}: {path}")
        else:
            n = _file_line_count(target)
            if end > n:
                yield issue(f"span end_line {end} exceeds file length {n}: {path}")


def validate_query_dict(
    obj: object,
    *,
    file: str,
    line: int,
    known_repos: frozenset[str] | None,
    corpus_root: Path | None,
    seen_ids: dict[str, str],
) -> list[ValidationIssue]:
    """Validate one decoded record, appending its id to ``seen_ids`` if usable.

    ``seen_ids`` maps id -> "file:line" of its first sighting, so duplicates are
    reported against later occurrences.
    """
    issues: list[ValidationIssue] = []
    query_id = obj.get("id") if isinstance(obj, dict) else None
    if not isinstance(query_id, str):
        query_id = None

    def issue(msg: str, *, qid: str | None = query_id) -> None:
        issues.append(ValidationIssue(file, line, qid, msg))

    if not isinstance(obj, dict):
        issue("record must be a JSON object")
        return issues

    unknown = set(obj) - _QUERY_KEYS
    if unknown:
        issue(f"unknown keys: {sorted(unknown)}")
    missing = _REQUIRED_QUERY_KEYS - set(obj)
    if missing:
        issue(f"missing required keys: {sorted(missing)}")

    repo = obj.get("repo")
    repo_ok = isinstance(repo, str) and repo
    if not repo_ok:
        issue("repo must be a non-empty string")
    elif known_repos is not None and repo not in known_repos:
        issue(f"unknown repo {repo!r} (not in corpus.yaml)")

    raw_id = obj.get("id")
    if not isinstance(raw_id, str):
        issue("id must be a string")
    else:
        m = _ID_RE.match(raw_id)
        if not m:
            issue(f"id must match '<repo>-NNNN': {raw_id!r}")
        elif repo_ok and m.group("repo") != repo:
            issue(f"id prefix {m.group('repo')!r} does not match repo {repo!r}")
        if raw_id in seen_ids:
            issue(f"duplicate id (first seen at {seen_ids[raw_id]})")
        else:
            seen_ids[raw_id] = f"{file}:{line}"

    if not isinstance(obj.get("query"), str) or not obj.get("query", "").strip():
        issue("query must be a non-empty string")

    difficulty = obj.get("difficulty")
    if difficulty not in DIFFICULTIES:
        issue(f"difficulty must be one of {sorted(DIFFICULTIES)} (got {difficulty!r})")

    if "notes" in obj and not isinstance(obj["notes"], str):
        issue("notes must be a string")

    answer_type = obj.get("answer_type")
    if answer_type not in ANSWER_TYPES:
        issue(f"answer_type must be one of {sorted(ANSWER_TYPES)} (got {answer_type!r})")

    answers = obj.get("answers")
    if not isinstance(answers, list) or not answers:
        issue("answers must be a non-empty list")
    else:
        corpus_repo_root = corpus_root / repo if (corpus_root is not None and repo_ok) else None
        if corpus_repo_root is not None and not corpus_repo_root.is_dir():
            corpus_repo_root = None  # repo not cloned; skip corpus checks
        for answer in answers:
            issues.extend(
                _validate_answer(
                    answer,
                    file=file,
                    line=line,
                    query_id=query_id,
                    repo=repo if repo_ok else "?",
                    corpus_repo_root=corpus_repo_root,
                )
            )
        # answer_type must agree with cardinality: single => 1, multi => >= 2.
        if answer_type == "single" and len(answers) != 1:
            issue(f"answer_type 'single' requires exactly 1 answer (got {len(answers)})")
        elif answer_type == "multi" and len(answers) < 2:
            issue(f"answer_type 'multi' requires >= 2 answers (got {len(answers)})")

    return issues


def iter_dataset_files(paths: Iterable[Path]) -> list[Path]:
    """Expand paths (files or directories) into a sorted list of .jsonl files."""
    found: list[Path] = []
    for p in paths:
        if p.is_dir():
            found.extend(sorted(p.rglob("*.jsonl")))
        elif p.suffix == ".jsonl":
            found.append(p)
    # De-duplicate while preserving order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in found:
        rp = f.resolve()
        if rp not in seen:
            seen.add(rp)
            unique.append(f)
    return unique


def validate_paths(
    paths: Iterable[Path],
    *,
    known_repos: frozenset[str] | None = None,
    corpus_root: Path | None = None,
) -> ValidationReport:
    """Validate every .jsonl file reachable from ``paths``.

    ``known_repos`` enables the repo-name cross-check; ``corpus_root`` enables
    per-repo path/span checks. Either being ``None`` skips that class of check.
    """
    report = ValidationReport()
    seen_ids: dict[str, str] = {}
    for file in iter_dataset_files(paths):
        report.files += 1
        rel = str(file)
        try:
            lines = list(read_jsonl_lines(file))
        except OSError as exc:
            report.issues.append(ValidationIssue(rel, 0, None, f"cannot read file: {exc}"))
            continue
        for line_no, raw in lines:
            report.queries += 1
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                report.issues.append(ValidationIssue(rel, line_no, None, f"invalid JSON: {exc}"))
                continue
            report.issues.extend(
                validate_query_dict(
                    obj,
                    file=rel,
                    line=line_no,
                    known_repos=known_repos,
                    corpus_root=corpus_root,
                    seen_ids=seen_ids,
                )
            )
    report.issues.sort(key=lambda i: (i.file, i.line))
    return report
