import pytest
from click.testing import CliRunner

from collie.cli.main import main, parse_repo


def test_help_exits_zero():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0


def test_help_contains_all_subcommands():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    output = result.output
    subcommands = [
        "sit",
        "bark",
        "approve",
        "reject",
        "shake-hands",
        "unleash",
        "leash",
        "status",
    ]
    for cmd in subcommands:
        assert cmd in output, f"Subcommand '{cmd}' not found in --help output"


def test_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "collie" in result.output.lower() or "0." in result.output


def test_parse_repo_valid():
    owner, name = parse_repo("octocat/hello-world")
    assert owner == "octocat"
    assert name == "hello-world"


def test_parse_repo_invalid():
    import click

    with pytest.raises(click.BadParameter):
        parse_repo("not-a-valid-repo")


def test_parse_repo_invalid_extra_slash():
    import click

    with pytest.raises(click.BadParameter):
        parse_repo("owner/repo/extra")
