"""Collie MCP Server — exposes Collie tools for Claude Desktop / Claude Code."""

from __future__ import annotations

import os

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("collie")


def _get_github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        import subprocess

        try:
            result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                token = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return token


def _get_llm_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY")


def _create_llm_if_available():
    key = _get_llm_key()
    if key:
        from collie.core.llm_client import LLMClient

        return LLMClient(key)
    return None


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="collie_sit_analyze",
            description="Analyze a repository and return interview guide for philosophy creation",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner"},
                    "repo": {"type": "string", "description": "Repository name"},
                },
                "required": ["owner", "repo"],
            },
        ),
        Tool(
            name="collie_sit_save",
            description="Save philosophy text to repository Discussion",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "philosophy_text": {"type": "string", "description": "Philosophy in markdown format"},
                },
                "required": ["owner", "repo", "philosophy_text"],
            },
        ),
        Tool(
            name="collie_bark",
            description="Analyze open issues/PRs and generate triage recommendations",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "cost_cap": {"type": "number", "default": 50.0},
                },
                "required": ["owner", "repo"],
            },
        ),
        Tool(
            name="collie_approve",
            description="Approve and execute recommended actions",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "numbers": {"type": "array", "items": {"type": "integer"}},
                    "approve_all": {"type": "boolean", "default": False},
                },
                "required": ["owner", "repo"],
            },
        ),
        Tool(
            name="collie_reject",
            description="Reject a recommendation and suggest philosophy update",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "number": {"type": "integer"},
                    "reason": {"type": "string", "default": ""},
                },
                "required": ["owner", "repo", "number"],
            },
        ),
        Tool(
            name="collie_unleash",
            description="Switch from training to active mode",
            inputSchema={
                "type": "object",
                "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}},
                "required": ["owner", "repo"],
            },
        ),
        Tool(
            name="collie_leash",
            description="Switch from active to training mode",
            inputSchema={
                "type": "object",
                "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}},
                "required": ["owner", "repo"],
            },
        ),
        Tool(
            name="collie_status",
            description="Show triage status for the repository",
            inputSchema={
                "type": "object",
                "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}},
                "required": ["owner", "repo"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Route tool calls to implementations."""
    try:
        token = _get_github_token()
        if not token:
            return [TextContent(type="text", text="Error: GitHub token not found. Set GITHUB_TOKEN.")]

        from collie.core.stores.philosophy_store import PhilosophyStore
        from collie.core.stores.queue_store import QueueStore
        from collie.github.graphql import GitHubGraphQL
        from collie.github.rest import GitHubREST

        gql = GitHubGraphQL(token)
        rest = GitHubREST(token)
        phil_store = PhilosophyStore(gql, rest)
        queue_store = QueueStore(gql, rest)

        result = await _dispatch(name, arguments, gql, rest, phil_store, queue_store)

        await gql.close()
        await rest.close()

        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def _dispatch(name, args, gql, rest, phil_store, queue_store) -> str:
    """Dispatch to the appropriate handler."""
    import json

    owner = args.get("owner", "")
    repo = args.get("repo", "")

    if name == "collie_sit_analyze":
        from collie.commands.sit import RepoAnalyzer, SitInterviewer

        analyzer = RepoAnalyzer(rest)
        profile = await analyzer.analyze(owner, repo)
        interviewer = SitInterviewer(profile)
        guide = interviewer.generate_for_mcp()
        return json.dumps(guide, indent=2)

    elif name == "collie_sit_save":
        from collie.core.models import Philosophy

        text = args.get("philosophy_text", "")
        philosophy = Philosophy.from_markdown(text)
        url = await phil_store.save(owner, repo, philosophy)
        return f"Philosophy saved. URL: {url}"

    elif name == "collie_bark":
        from collie.commands.bark import BarkPipeline

        llm = _create_llm_if_available()
        pipeline = BarkPipeline(gql, rest, phil_store, queue_store, llm)
        report = await pipeline.run(owner, repo, cost_cap=args.get("cost_cap", 50.0))
        return report.summary()

    elif name == "collie_approve":
        from collie.commands.approve import ApproveCommand

        cmd = ApproveCommand(rest, queue_store, phil_store)
        report = await cmd.approve(
            owner,
            repo,
            numbers=args.get("numbers"),
            approve_all=args.get("approve_all", False),
        )
        return report.summary()

    elif name == "collie_reject":
        from collie.commands.shake_hands import ShakeHandsCommand

        cmd = ShakeHandsCommand(phil_store, queue_store)
        result = await cmd.micro_update(owner, repo, args.get("reason", ""), args["number"])
        return f"Rejected #{args['number']}. Suggestion: {result['suggestion']}"

    elif name == "collie_unleash":
        from collie.commands.mode import ModeCommand

        cmd = ModeCommand(phil_store)
        await cmd.unleash(owner, repo)
        return f"Unleashed! {owner}/{repo} is now in active mode."

    elif name == "collie_leash":
        from collie.commands.mode import ModeCommand

        cmd = ModeCommand(phil_store)
        await cmd.leash(owner, repo)
        return f"Leashed. {owner}/{repo} is now in training mode."

    elif name == "collie_status":
        from collie.commands.mode import ModeCommand

        cmd = ModeCommand(phil_store)
        report = await cmd.status(owner, repo)
        return report.summary()

    return f"Unknown tool: {name}"


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
