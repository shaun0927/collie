from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

app = Server("collie")

_EMPTY_SCHEMA = {"type": "object", "properties": {}}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="collie_sit_analyze",
            description="Analyze repository issues and PRs.",
            inputSchema=_EMPTY_SCHEMA,
        ),
        Tool(
            name="collie_sit_save",
            description="Save triage analysis results.",
            inputSchema=_EMPTY_SCHEMA,
        ),
        Tool(
            name="collie_bark",
            description="Post triage comments on open issues and PRs.",
            inputSchema=_EMPTY_SCHEMA,
        ),
        Tool(
            name="collie_approve",
            description="Approve issues or PRs.",
            inputSchema=_EMPTY_SCHEMA,
        ),
        Tool(
            name="collie_reject",
            description="Reject an issue or PR.",
            inputSchema=_EMPTY_SCHEMA,
        ),
        Tool(
            name="collie_unleash",
            description="Enable automated triage on the repository.",
            inputSchema=_EMPTY_SCHEMA,
        ),
        Tool(
            name="collie_leash",
            description="Disable automated triage on the repository.",
            inputSchema=_EMPTY_SCHEMA,
        ),
        Tool(
            name="collie_status",
            description="Show triage status for the repository.",
            inputSchema=_EMPTY_SCHEMA,
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    return [TextContent(type="text", text='{"status": "not_implemented"}')]


async def serve() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(serve())
