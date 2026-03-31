import click

from collie import __version__


@click.group()
@click.version_option(__version__, "--version")
def main() -> None:
    """Collie — AI-powered GitHub repository triage for solo maintainers."""


@main.command()
@click.argument("repo")
def sit(repo: str) -> None:
    """Analyze repository issues and PRs."""
    print("Not implemented yet")


@main.command()
@click.argument("repo")
def bark(repo: str) -> None:
    """Post triage comments on open issues and PRs."""
    print("Not implemented yet")


@main.command()
@click.argument("repo")
@click.argument("numbers", nargs=-1, type=int)
@click.option(
    "--all",
    "approve_all",
    is_flag=True,
    default=False,
    help="Approve all pending items.",
)
def approve(repo: str, numbers: tuple[int, ...], approve_all: bool) -> None:
    """Approve issues or PRs."""
    print("Not implemented yet")


@main.command()
@click.argument("repo")
@click.argument("number", type=int)
@click.option("--reason", default=None, help="Reason for rejection.")
def reject(repo: str, number: int, reason: str | None) -> None:
    """Reject an issue or PR."""
    print("Not implemented yet")


@main.command("shake-hands")
@click.argument("repo")
def shake_hands(repo: str) -> None:
    """Onboard a new contributor."""
    print("Not implemented yet")


@main.command()
@click.argument("repo")
def unleash(repo: str) -> None:
    """Enable automated triage on the repository."""
    print("Not implemented yet")


@main.command()
@click.argument("repo")
def leash(repo: str) -> None:
    """Disable automated triage on the repository."""
    print("Not implemented yet")


@main.command()
@click.argument("repo")
def status(repo: str) -> None:
    """Show triage status for the repository."""
    print("Not implemented yet")
