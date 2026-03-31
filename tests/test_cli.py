from click.testing import CliRunner

from collie.cli.main import main


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
