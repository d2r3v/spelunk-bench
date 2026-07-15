"""Two-pass labeling consistency check.

Implements docs/LABELING.md §5.4: compare pass-1 and pass-2 labels for the same
query ids and flag disagreements a human must reconcile into ``queries/final/``.
Flags are *expected*, not errors — the output is a labeling-quality report
committed alongside the dataset, so this never gates CI.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .queries import Query

# Same-path spans whose start or end differ by more than this many lines between
# passes are flagged as drift (docs/LABELING.md §5.4).
SPAN_DRIFT_LINES = 10

FLAG_KINDS = (
    "only_in_pass1",
    "only_in_pass2",
    "answer_set",
    "span_drift",
    "answer_type",
    "difficulty",
)


@dataclass(frozen=True)
class ConsistencyFlag:
    """One disagreement between the two passes for a given query id."""

    query_id: str
    repo: str
    kind: str
    detail: str


def _paths(query: Query) -> set[str]:
    return {a.path for a in query.answers}


def _span_by_path(query: Query) -> dict[str, tuple[int, int]]:
    # If a path appears more than once (unusual), the first span wins.
    spans: dict[str, tuple[int, int]] = {}
    for a in query.answers:
        spans.setdefault(a.path, (a.start_line, a.end_line))
    return spans


def compare_passes(pass1: list[Query], pass2: list[Query]) -> list[ConsistencyFlag]:
    """Return every disagreement between two passes, ordered by query id."""
    by_id1 = {q.id: q for q in pass1}
    by_id2 = {q.id: q for q in pass2}
    flags: list[ConsistencyFlag] = []

    for qid in sorted(set(by_id1) - set(by_id2)):
        q = by_id1[qid]
        flags.append(ConsistencyFlag(qid, q.repo, "only_in_pass1", "present only in pass 1"))
    for qid in sorted(set(by_id2) - set(by_id1)):
        q = by_id2[qid]
        flags.append(ConsistencyFlag(qid, q.repo, "only_in_pass2", "present only in pass 2"))

    for qid in sorted(set(by_id1) & set(by_id2)):
        q1, q2 = by_id1[qid], by_id2[qid]
        repo = q1.repo

        if q1.answer_type != q2.answer_type:
            flags.append(
                ConsistencyFlag(qid, repo, "answer_type", f"{q1.answer_type} vs {q2.answer_type}")
            )
        if q1.difficulty != q2.difficulty:
            flags.append(
                ConsistencyFlag(qid, repo, "difficulty", f"{q1.difficulty} vs {q2.difficulty}")
            )

        paths1, paths2 = _paths(q1), _paths(q2)
        if paths1 != paths2:
            only1 = sorted(paths1 - paths2)
            only2 = sorted(paths2 - paths1)
            flags.append(
                ConsistencyFlag(qid, repo, "answer_set", f"pass1 only={only1} pass2 only={only2}")
            )

        spans1, spans2 = _span_by_path(q1), _span_by_path(q2)
        for path in sorted(paths1 & paths2):
            s1, e1 = spans1[path]
            s2, e2 = spans2[path]
            if abs(s1 - s2) > SPAN_DRIFT_LINES or abs(e1 - e2) > SPAN_DRIFT_LINES:
                flags.append(
                    ConsistencyFlag(
                        qid,
                        repo,
                        "span_drift",
                        f"{path}: [{s1},{e1}] vs [{s2},{e2}]",
                    )
                )

    return flags


def counts_by_repo(flags: list[ConsistencyFlag]) -> dict[str, Counter[str]]:
    """Aggregate flags into per-repo counts of each flag kind."""
    result: dict[str, Counter[str]] = {}
    for flag in flags:
        result.setdefault(flag.repo, Counter())[flag.kind] += 1
    return result


def render_report(flags: list[ConsistencyFlag]) -> str:
    """Render a text report: a per-repo count table then the flag details."""
    lines: list[str] = ["# Consistency report", ""]

    if not flags:
        lines.append("No disagreements between passes.")
        return "\n".join(lines) + "\n"

    per_repo = counts_by_repo(flags)
    header = ["repo", *FLAG_KINDS, "total"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for repo in sorted(per_repo):
        counter = per_repo[repo]
        row = [repo] + [str(counter.get(k, 0)) for k in FLAG_KINDS] + [str(sum(counter.values()))]
        lines.append("| " + " | ".join(row) + " |")

    lines += ["", "## Details", ""]
    for flag in flags:
        lines.append(f"- {flag.query_id} ({flag.kind}): {flag.detail}")

    return "\n".join(lines) + "\n"
