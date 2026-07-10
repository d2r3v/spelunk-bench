"""Smoke tests for the CLI skeleton (M1).

These assert the command surface exists and behaves, not that any subcommand
does real work yet — the stubs are expected to fail with a clear message.
"""

import argparse

import pytest

from spelunk_bench import __version__
from spelunk_bench.cli import build_parser, main

SUBCOMMANDS = ["corpus", "validate", "consistency", "bench", "report"]


def test_all_subcommands_registered():
    parser = build_parser()
    # The subparsers action holds the registered command names.
    subactions = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    assert len(subactions) == 1
    assert set(SUBCOMMANDS) == set(subactions[0].choices)


def test_no_args_prints_help_and_succeeds(capsys):
    rc = main([])
    assert rc == 0
    out = capsys.readouterr().out.lower()
    assert "usage" in out
    for name in SUBCOMMANDS:
        assert name in out


@pytest.mark.parametrize("name", SUBCOMMANDS)
def test_stub_subcommands_fail_loudly(name, capsys):
    rc = main([name])
    assert rc == 1
    err = capsys.readouterr().err
    assert name in err
    assert "not implemented" in err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert __version__ in out


def test_unknown_command_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["nonexistent"])
    assert excinfo.value.code == 2
