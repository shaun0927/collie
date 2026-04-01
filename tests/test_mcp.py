"""Tests for the Collie MCP server."""

from __future__ import annotations


def test_list_tools_returns_eight():
    """list_tools returns exactly 8 tools."""
    import asyncio

    from collie.mcp.server import list_tools

    tools = asyncio.run(list_tools())
    assert len(tools) == 8


def test_tool_names():
    """All expected tool names are present."""
    import asyncio

    from collie.mcp.server import list_tools

    tools = asyncio.run(list_tools())
    names = {t.name for t in tools}
    expected = {
        "collie_sit_analyze",
        "collie_sit_save",
        "collie_bark",
        "collie_approve",
        "collie_reject",
        "collie_unleash",
        "collie_leash",
        "collie_status",
    }
    assert names == expected


def test_tools_have_required_input_schema_fields():
    """Each tool has an inputSchema with type, properties, and required."""
    import asyncio

    from collie.mcp.server import list_tools

    tools = asyncio.run(list_tools())
    for tool in tools:
        schema = tool.inputSchema
        assert schema.get("type") == "object", f"{tool.name}: missing type=object"
        assert "properties" in schema, f"{tool.name}: missing properties"
        assert "required" in schema, f"{tool.name}: missing required"
        # owner and repo are required for every tool
        assert "owner" in schema["required"], f"{tool.name}: owner not required"
        assert "repo" in schema["required"], f"{tool.name}: repo not required"


def test_get_github_token_from_env(monkeypatch):
    """_get_github_token reads GITHUB_TOKEN from environment."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-abc")

    import importlib

    from collie.mcp import server as srv

    importlib.reload(srv)
    from collie.mcp.server import _get_github_token

    token = _get_github_token()
    assert token == "test-token-abc"


def test_get_github_token_empty_when_unset(monkeypatch):
    """_get_github_token returns empty string when env var not set and gh not available."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    import unittest.mock as mock

    with mock.patch("subprocess.run", side_effect=FileNotFoundError):
        from collie.mcp.server import _get_github_token

        token = _get_github_token()
        assert token == ""


def test_create_llm_if_available_with_key(monkeypatch):
    """_create_llm_if_available returns LLMClient when ANTHROPIC_API_KEY is set."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    from collie.core.llm_client import LLMClient
    from collie.mcp.server import _create_llm_if_available

    client = _create_llm_if_available()
    assert isinstance(client, LLMClient)
    assert client.api_key == "sk-test-key"


def test_create_llm_if_available_without_key(monkeypatch):
    """_create_llm_if_available returns None when ANTHROPIC_API_KEY is not set."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from collie.mcp.server import _create_llm_if_available

    client = _create_llm_if_available()
    assert client is None
