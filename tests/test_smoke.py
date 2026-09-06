"""Sanity check: package imports + CLI --help works."""
from agentsblog import __version__


def test_version_is_string():
    assert isinstance(__version__, str)
    assert __version__.count(".") >= 1


def test_cli_help_exits_zero():
    from agentsblog.cli import build_parser
    parser = build_parser()
    # argparse exits via SystemExit(0) on --help
    try:
        parser.parse_args(["--help"])
    except SystemExit as e:
        assert e.code == 0


def test_cli_version_exits_zero():
    from agentsblog.cli import build_parser
    parser = build_parser()
    try:
        parser.parse_args(["--version"])
    except SystemExit as e:
        assert e.code == 0


def test_cli_subcommands_registered():
    from agentsblog.cli import build_parser
    parser = build_parser()
    # All expected commands are listed in the subparsers action
    choices = parser._subparsers._group_actions[0].choices  # type: ignore[attr-defined]
    expected = {"init-db", "migrate", "scan", "publish", "publish-article",
                "add-manual", "build-site", "status", "health", "serve", "sources"}
    assert expected.issubset(set(choices.keys()))