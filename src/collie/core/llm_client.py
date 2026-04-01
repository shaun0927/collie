"""LLM client wrapper — supports Anthropic API and Codex CLI backends."""

from __future__ import annotations

import asyncio
import shutil
import subprocess


class LLMClient:
    """Wrapper around Anthropic API for Collie's LLM calls."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.api_key = api_key
        self.model = model
        self._client = None

    async def _get_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        """Send a chat message and return the response text."""
        client = await self._get_client()
        response = await client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None


class CodexLLMClient:
    """LLM client that uses Codex CLI (OAuth-based, no API key needed)."""

    def __init__(self, model: str = "o3"):
        self.model = model
        if not shutil.which("codex"):
            raise RuntimeError("Codex CLI not found. Install it or use ANTHROPIC_API_KEY instead.")

    async def chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        """Send a prompt via codex exec and return the response."""
        # Truncate to avoid oversized prompts
        system_short = system[:1000] if len(system) > 1000 else system
        user_short = user[:2000] if len(user) > 2000 else user
        prompt = f"{system_short}\n\n---\n\n{user_short}"

        result = await asyncio.to_thread(
            subprocess.run,
            ["codex", "exec", "--full-auto", prompt],
            capture_output=True,
            text=True,
            timeout=180,
        )

        if result.returncode != 0:
            error = result.stderr.strip() or "Unknown codex error"
            raise RuntimeError(f"Codex exec failed: {error}")

        return result.stdout.strip()

    async def close(self):
        pass


def create_llm_client() -> LLMClient | CodexLLMClient | None:
    """Auto-detect and create the best available LLM client.

    Priority: ANTHROPIC_API_KEY > Codex CLI > None
    """
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return LLMClient(api_key)

    if shutil.which("codex"):
        return CodexLLMClient()

    return None
