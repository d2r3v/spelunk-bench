"""Command-line entry point for spelunk-bench.

This is the M1 skeleton: every subcommand named in docs/DESIGN.md is registered
so ``spelunk-bench --help`` documents the full surface, but the implementations
land in later milestones. Each stub exits non-zero with a clear pointer to the
milestone that fills it in, so an accidental early call fails loudly rather than
silently doing nothing.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__

# Subcommand -> milestone that implements it, surfaced in the stub message.
_MILESTONES = {
    "corpus": "M3",
    "validate": "M2",
    "consistency": "M2",
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
    return _stub("validate")


def _cmd_consistency(args: argparse.Namespace) -> int:
    return _stub("consistency")


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
    p_validate.set_defaults(func=_cmd_validate)

    p_consistency = subparsers.add_parser(
        "consistency", help="Diff the two labeling passes and report disagreements."
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
