"""LLM client wrapper for Anthropic API."""

from __future__ import annotations


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
