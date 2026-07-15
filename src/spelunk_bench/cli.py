"""Command-line entry point for spelunk-bench.

Every subcommand named in docs/DESIGN.md is registered so ``spelunk-bench
--help`` documents the full surface. ``validate`` and ``consistency`` are
implemented (M2); the rest are stubs that exit non-zero with a pointer to the
milestone that fills them in, so an accidental early call fails loudly rather
than silently doing nothing.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__, consistency, corpus, queries

# Subcommand -> milestone that implements it, surfaced in the stub message.
_MILESTONES = {
    "corpus": "M3",
    "bench": "M6",
    "report": "M6",
}


def _stub(name: str) -> int:
    """Report that ``name`` is not implemented yet and return a failing code."""
    milestone = _MILESTONES[name]
    print(
        f"spelunk-bench {name}: not implemented yet (planned for {milestone}).",
        file=sys.stderr,
    )
    return 1


def _cmd_corpus(args: argparse.Namespace) -> int:
    return _stub("corpus")


def _cmd_validate(args: argparse.Namespace) -> int:
    known_repos = None
    corpus_yaml = Path(args.corpus_yaml)
    if corpus_yaml.is_file():
        try:
            known_repos = corpus.known_repo_names(corpus_yaml)
        except ValueError as exc:
            print(f"spelunk-bench validate: {exc}", file=sys.stderr)
            return 2

    corpus_root = Path(args.corpus_root)
    corpus_root = corpus_root if corpus_root.is_dir() else None

    report = queries.validate_paths(
        [Path(p) for p in args.paths],
        known_repos=known_repos,
        corpus_root=corpus_root,
    )

    for issue in report.issues:
        print(str(issue), file=sys.stderr)

    scope = "schema" if known_repos is None else "schema+repo"
    scope += "+corpus" if corpus_root is not None else ""
    if report.files == 0:
        print("validate: no .jsonl files found (nothing to check).")
        return 0
    if report.ok:
        print(f"validate: {report.queries} queries in {report.files} files OK ({scope}).")
        return 0
    print(
        f"validate: {len(report.issues)} issue(s) across "
        f"{report.queries} queries in {report.files} files ({scope}).",
        file=sys.stderr,
    )
    return 1


def _cmd_consistency(args: argparse.Namespace) -> int:
    pass1 = queries.iter_dataset_files([Path(args.pass1)])
    pass2 = queries.iter_dataset_files([Path(args.pass2)])
    try:
        q1 = [q for f in pass1 for q in queries.load_queries(f)]
        q2 = [q for f in pass2 for q in queries.load_queries(f)]
    except ValueError as exc:
        print(f"spelunk-bench consistency: {exc}", file=sys.stderr)
        print("run `spelunk-bench validate` first.", file=sys.stderr)
        return 2

    flags = consistency.compare_passes(q1, q2)
    output = consistency.render_report(flags)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"consistency: {len(flags)} flag(s) written to {args.output}", file=sys.stderr)
    else:
        print(output, end="")
    return 0


def _cmd_bench(args: argparse.Namespace) -> int:
    return _stub("bench")


def _cmd_report(args: argparse.Namespace) -> int:
    return _stub("report")


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser with all subcommands registered."""
    parser = argparse.ArgumentParser(
        prog="spelunk-bench",
        description="Benchmark code-retrieval tools against hand-labeled ground truth.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"spelunk-bench {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    p_corpus = subparsers.add_parser(
        "corpus", help="Clone corpus repositories at their pinned SHAs."
    )
    p_corpus.set_defaults(func=_cmd_corpus)

    p_validate = subparsers.add_parser(
        "validate", help="Validate query JSONL files against the schema and corpus."
    )
    p_validate.add_argument(
        "paths",
        nargs="*",
        default=["queries"],
        help="JSONL files or directories to validate (default: queries/).",
    )
    p_validate.add_argument(
        "--corpus-yaml",
        default="corpus.yaml",
        help="corpus.yaml providing known repo names (default: corpus.yaml).",
    )
    p_validate.add_argument(
        "--corpus-root",
        default="corpus",
        help="Root of cloned corpus checkouts for path/span checks (default: corpus/).",
    )
    p_validate.set_defaults(func=_cmd_validate)

    p_consistency = subparsers.add_parser(
        "consistency", help="Diff the two labeling passes and report disagreements."
    )
    p_consistency.add_argument(
        "--pass1", default="queries/pass1", help="Pass-1 directory (default: queries/pass1)."
    )
    p_consistency.add_argument(
        "--pass2", default="queries/pass2", help="Pass-2 directory (default: queries/pass2)."
    )
    p_consistency.add_argument(
        "-o", "--output", help="Write the report to this file instead of stdout."
    )
    p_consistency.set_defaults(func=_cmd_consistency)

    p_bench = subparsers.add_parser(
        "bench", help="Run adapters over the query set and write results.json."
    )
    p_bench.set_defaults(func=_cmd_bench)

    p_report = subparsers.add_parser("report", help="Render report.md from a results.json run.")
    p_report.set_defaults(func=_cmd_report)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse ``argv`` and dispatch to the selected subcommand.

    Returns a process exit code. With no subcommand, prints help and returns 0.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
