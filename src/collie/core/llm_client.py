"""LLM client wrapper — supports Anthropic, OpenAI-compatible APIs, and Codex CLI."""

from __future__ import annotations

import asyncio
import shutil
import subprocess

import httpx


class LLMClient:
    """Anthropic API client."""

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


class OpenAICompatibleClient:
    """Generic OpenAI-compatible API client.

    Works with: OpenAI, Google Gemini, Azure OpenAI, Ollama, Groq,
    Together, Mistral, DeepSeek, vLLM, LM Studio, and any provider
    that supports the /v1/chat/completions endpoint.
    """

    # Well-known provider base URLs (user can override via LLM_BASE_URL)
    KNOWN_PROVIDERS = {
        "openai": "https://api.openai.com/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
        "azure": None,  # requires custom base_url
        "groq": "https://api.groq.com/openai/v1",
        "together": "https://api.together.xyz/v1",
        "mistral": "https://api.mistral.ai/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "ollama": "http://localhost:11434/v1",
    }

    DEFAULT_MODELS = {
        "openai": "gpt-4o",
        "gemini": "gemini-2.5-flash",
        "groq": "llama-3.3-70b-versatile",
        "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "mistral": "mistral-large-latest",
        "deepseek": "deepseek-chat",
        "ollama": "llama3.1",
    }

    def __init__(self, api_key: str, base_url: str, model: str | None = None, provider: str | None = None):
        self.model = model or self.DEFAULT_MODELS.get(provider or "", "gpt-4o")
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=120.0,
        )

    async def chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        """Send a chat message via OpenAI-compatible /chat/completions."""
        response = await self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def close(self):
        await self._client.aclose()


class CodexLLMClient:
    """LLM client that uses Codex CLI (OAuth-based, no API key needed)."""

    def __init__(self, model: str = "o3"):
        self.model = model
        if not shutil.which("codex"):
            raise RuntimeError("Codex CLI not found. Install it or use an API key instead.")

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


def create_llm_client() -> LLMClient | OpenAICompatibleClient | CodexLLMClient | None:
    """Auto-detect and create the best available LLM client.

    Priority:
      1. LLM_PROVIDER + LLM_API_KEY  (explicit provider selection)
      2. ANTHROPIC_API_KEY            (Anthropic API)
      3. OPENAI_API_KEY               (OpenAI API)
      4. Codex CLI                    (OAuth, no key needed)
      5. None                         (T1 rule-based only)

    Environment variables:
      LLM_PROVIDER:  anthropic | openai | gemini | groq | together | mistral | deepseek | ollama
      LLM_API_KEY:   API key for the chosen provider
      LLM_BASE_URL:  Custom base URL (overrides provider default)
      LLM_MODEL:     Model name (overrides provider default)
    """
    import os

    provider = os.environ.get("LLM_PROVIDER", "").lower()
    llm_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "")
    model = os.environ.get("LLM_MODEL", "")

    # 1. Explicit provider selection
    if provider:
        if provider == "anthropic":
            key = llm_key or os.environ.get("ANTHROPIC_API_KEY", "")
            if key:
                return LLMClient(key, model=model or "claude-sonnet-4-6")
        elif provider == "codex":
            if shutil.which("codex"):
                return CodexLLMClient(model=model or "o3")
        else:
            key = llm_key or os.environ.get(f"{provider.upper()}_API_KEY", "")
            url = base_url or OpenAICompatibleClient.KNOWN_PROVIDERS.get(provider, "")
            if key and url:
                return OpenAICompatibleClient(api_key=key, base_url=url, model=model or None, provider=provider)

    # 2. Anthropic API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return LLMClient(api_key, model=model or "claude-sonnet-4-6")

    # 3. OpenAI API key
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        return OpenAICompatibleClient(
            api_key=openai_key,
            base_url="https://api.openai.com/v1",
            model=model or "gpt-4o",
            provider="openai",
        )

    # 4. Codex CLI
    if shutil.which("codex"):
        return CodexLLMClient(model=model or "o3")

    # 5. None
    return None
