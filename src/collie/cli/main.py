"""Collie CLI — AI-powered GitHub repository triage."""

import asyncio
import sys

import click
from rich.console import Console
from rich.table import Table

import collie
from collie.auth import AuthError


def parse_repo(repo: str) -> tuple[str, str]:
    """Parse 'owner/repo' string."""
    parts = repo.split("/")
    if len(parts) != 2:
        raise click.BadParameter(f"Expected 'owner/repo', got '{repo}'")
    return parts[0], parts[1]


def handle_error(console: Console, e: Exception) -> None:
    """Display user-friendly error message."""
    if isinstance(e, AuthError):
        console.print(f"[red]Authentication error:[/red] {e}")
    elif isinstance(e, ValueError):
        console.print(f"[red]Error:[/red] {e}")
    elif isinstance(e, PermissionError):
        console.print(f"[yellow]Permission denied:[/yellow] {e}")
    else:
        console.print(f"[red]Unexpected error:[/red] {e}")
    sys.exit(1)


async def _create_clients(need_llm: bool = False):
    """Create authenticated GitHub + optional LLM clients."""
    from collie.auth import GitHubAuth, LLMAuth
    from collie.core.llm_client import LLMClient
    from collie.github import GitHubGraphQL, GitHubREST

    gh_auth = GitHubAuth.from_env()
    gql = GitHubGraphQL(gh_auth.token)
    rest = GitHubREST(gh_auth.token)

    llm = None
    if need_llm:
        try:
            llm_auth = LLMAuth.from_env()
            llm = LLMClient(llm_auth.api_key)
        except Exception:
            pass  # LLM is optional

    return gql, rest, llm


@click.group()
@click.version_option(version=collie.__version__, prog_name="collie")
def main() -> None:
    """Collie — AI-powered GitHub repository triage for solo maintainers."""
    pass


@main.command()
@click.argument("repo")
def sit(repo: str) -> None:
    """Analyze repository and create merge philosophy via interview."""
    console = Console()
    try:
        owner, name = parse_repo(repo)
        asyncio.run(_sit(owner, name, console))
    except Exception as e:
        handle_error(console, e)


async def _sit(owner: str, name: str, console: Console) -> None:
    gql, rest, llm = await _create_clients()
    from collie.commands.sit import RepoAnalyzer, SitInterviewer
    from collie.core.stores.philosophy_store import PhilosophyStore

    analyzer = RepoAnalyzer(rest)
    console.print(f"[cyan]Analyzing {owner}/{name}...[/cyan]")
    profile = await analyzer.analyze(owner, name)

    interviewer = SitInterviewer(profile)
    philosophy = interviewer.run_interactive()

    store = PhilosophyStore(gql, rest)
    url = await store.save(owner, name, philosophy)
    console.print(f"\n[green]Philosophy saved![/green] {url}")

    await gql.close()
    await rest.close()


@main.command()
@click.argument("repo")
@click.option("--cost-cap", default=50.0, help="Max LLM cost in USD per run")
def bark(repo: str, cost_cap: float) -> None:
    """Analyze open issues/PRs and generate triage recommendations."""
    console = Console()
    try:
        owner, name = parse_repo(repo)
        asyncio.run(_bark(owner, name, cost_cap, console))
    except Exception as e:
        handle_error(console, e)


async def _bark(owner: str, name: str, cost_cap: float, console: Console) -> None:
    gql, rest, llm = await _create_clients(need_llm=True)
    from collie.commands.bark import BarkPipeline
    from collie.core.stores.philosophy_store import PhilosophyStore
    from collie.core.stores.queue_store import QueueStore

    phil_store = PhilosophyStore(gql, rest)
    queue_store = QueueStore(gql, rest)

    pipeline = BarkPipeline(gql, rest, phil_store, queue_store, llm)
    console.print(f"[cyan]Barking at {owner}/{name}...[/cyan]")

    report = await pipeline.run(owner, name, cost_cap=cost_cap)

    table = Table(title=f"Collie Bark — {owner}/{name}")
    table.add_column("#", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Action", style="bold")
    table.add_column("Title")
    table.add_column("Reason", style="dim")

    for rec in report.recommendations:
        action_style = {
            "merge": "green",
            "close": "red",
            "hold": "yellow",
            "escalate": "magenta",
            "label": "blue",
            "comment": "cyan",
        }.get(rec.action.value, "white")
        table.add_row(
            str(rec.number),
            rec.item_type.value,
            f"[{action_style}]{rec.action.value}[/{action_style}]",
            rec.title[:60],
            rec.reason[:80],
        )

    console.print(table)
    console.print(f"\n{report.summary()}")

    await gql.close()
    await rest.close()
    if llm:
        await llm.close()


@main.command()
@click.argument("repo")
@click.argument("numbers", nargs=-1, type=int)
@click.option("--all", "approve_all", is_flag=True, help="Approve all pending items")
def approve(repo: str, numbers: tuple[int, ...], approve_all: bool) -> None:
    """Approve and execute recommended actions."""
    console = Console()
    try:
        owner, name = parse_repo(repo)
        asyncio.run(_approve(owner, name, list(numbers), approve_all, console))
    except Exception as e:
        handle_error(console, e)


async def _approve(owner: str, name: str, numbers: list[int], approve_all: bool, console: Console) -> None:
    gql, rest, llm = await _create_clients()
    from collie.commands.approve import ApproveCommand
    from collie.core.stores.philosophy_store import PhilosophyStore
    from collie.core.stores.queue_store import QueueStore

    cmd = ApproveCommand(rest, QueueStore(gql, rest), PhilosophyStore(gql, rest))
    report = await cmd.approve(owner, name, numbers=numbers or None, approve_all=approve_all)

    for r in report.succeeded:
        console.print(f"  [green]\u2713[/green] #{r.number} \u2014 {r.action.value}: {r.message}")
    for r in report.failed:
        console.print(f"  [red]\u2717[/red] #{r.number} \u2014 {r.action.value}: {r.message}")
    for r in report.skipped:
        console.print(f"  [dim]\u2013[/dim] #{r.number} \u2014 {r.action.value}: {r.message}")

    console.print(f"\n{report.summary()}")
    await gql.close()
    await rest.close()


@main.command()
@click.argument("repo")
@click.argument("number", type=int)
@click.option("--reason", "-r", default="", help="Reason for rejection")
def reject(repo: str, number: int, reason: str) -> None:
    """Reject a recommendation and suggest philosophy update."""
    console = Console()
    try:
        owner, name = parse_repo(repo)
        asyncio.run(_reject(owner, name, number, reason, console))
    except Exception as e:
        handle_error(console, e)


async def _reject(owner: str, name: str, number: int, reason: str, console: Console) -> None:
    gql, rest, llm = await _create_clients()
    from collie.commands.shake_hands import ShakeHandsCommand
    from collie.core.stores.philosophy_store import PhilosophyStore
    from collie.core.stores.queue_store import QueueStore

    cmd = ShakeHandsCommand(PhilosophyStore(gql, rest), QueueStore(gql, rest))
    result = await cmd.micro_update(owner, name, reason, number)

    console.print(f"[yellow]Rejected #{number}[/yellow]")
    if result["suggestion"]:
        console.print(f"[cyan]Suggested rule:[/cyan] {result['suggestion']}")
        if click.confirm("Add this rule to your philosophy?"):
            rule = result["rule"]
            await cmd.apply_micro_update(owner, name, rule["type"], rule)
            console.print("[green]Philosophy updated! Pending recommendations invalidated.[/green]")

    await gql.close()
    await rest.close()


@main.command("shake-hands")
@click.argument("repo")
def shake_hands(repo: str) -> None:
    """Revise repository merge philosophy."""
    console = Console()
    try:
        owner, name = parse_repo(repo)
        asyncio.run(_shake_hands(owner, name, console))
    except Exception as e:
        handle_error(console, e)


async def _shake_hands(owner: str, name: str, console: Console) -> None:
    gql, rest, llm = await _create_clients()
    from collie.commands.shake_hands import ShakeHandsCommand
    from collie.core.stores.philosophy_store import PhilosophyStore
    from collie.core.stores.queue_store import QueueStore

    cmd = ShakeHandsCommand(PhilosophyStore(gql, rest), QueueStore(gql, rest))
    phil = await cmd.full_revision(owner, name)

    console.print("[bold]Current Philosophy:[/bold]")
    console.print(phil.to_markdown())
    console.print("\n[dim]Edit the philosophy Discussion directly, then run 'collie bark' to apply changes.[/dim]")

    await gql.close()
    await rest.close()


@main.command()
@click.argument("repo")
def unleash(repo: str) -> None:
    """Switch from training to active mode (enable execution)."""
    console = Console()
    try:
        owner, name = parse_repo(repo)
        asyncio.run(_unleash(owner, name, console))
    except Exception as e:
        handle_error(console, e)


async def _unleash(owner: str, name: str, console: Console) -> None:
    gql, rest, _ = await _create_clients()
    from collie.commands.mode import ModeCommand
    from collie.core.stores.philosophy_store import PhilosophyStore

    cmd = ModeCommand(PhilosophyStore(gql, rest))
    await cmd.unleash(owner, name)
    console.print(f"[green]Unleashed![/green] {owner}/{name} is now in active mode.")
    await gql.close()
    await rest.close()


@main.command()
@click.argument("repo")
def leash(repo: str) -> None:
    """Switch from active to training mode (disable execution)."""
    console = Console()
    try:
        owner, name = parse_repo(repo)
        asyncio.run(_leash(owner, name, console))
    except Exception as e:
        handle_error(console, e)


async def _leash(owner: str, name: str, console: Console) -> None:
    gql, rest, _ = await _create_clients()
    from collie.commands.mode import ModeCommand
    from collie.core.stores.philosophy_store import PhilosophyStore

    cmd = ModeCommand(PhilosophyStore(gql, rest))
    await cmd.leash(owner, name)
    console.print(f"[yellow]Leashed.[/yellow] {owner}/{name} is now in training mode.")
    await gql.close()
    await rest.close()


@main.command()
@click.argument("repo")
def status(repo: str) -> None:
    """Show triage status for the repository."""
    console = Console()
    try:
        owner, name = parse_repo(repo)
        asyncio.run(_status(owner, name, console))
    except Exception as e:
        handle_error(console, e)


async def _status(owner: str, name: str, console: Console) -> None:
    gql, rest, _ = await _create_clients()
    from collie.commands.mode import ModeCommand
    from collie.core.stores.philosophy_store import PhilosophyStore

    cmd = ModeCommand(PhilosophyStore(gql, rest))
    report = await cmd.status(owner, name)

    if not report.has_philosophy:
        console.print(f"[yellow]No philosophy found for {owner}/{name}.[/yellow]")
        console.print("Run 'collie sit' to create one.")
    else:
        console.print(report.summary())

    await gql.close()
    await rest.close()
