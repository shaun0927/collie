"""LLM client wrapper — supports Anthropic, OpenAI-compatible APIs, and Codex CLI.

Provider registry lives in PROVIDERS dict. To add a provider or update a model,
edit that single dict — no other code changes needed.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from dataclasses import dataclass

import httpx

# ── Provider Registry ────────────────────────────────────────────────────────
# Each entry maps a provider slug to its config. Use stable model aliases
# that auto-upgrade (e.g., "gpt-4o" not "gpt-4o-2024-08-06") so the code
# doesn't break when providers release new model versions.
#
# To add a new provider: add one entry here. That's it.


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    default_model: str
    env_key: str  # expected env var name for API key


PROVIDERS: dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o",
        env_key="OPENAI_API_KEY",
    ),
    "gemini": ProviderConfig(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        default_model="gemini-2.5-flash",
        env_key="GEMINI_API_KEY",
    ),
    "groq": ProviderConfig(
        base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        env_key="GROQ_API_KEY",
    ),
    "together": ProviderConfig(
        base_url="https://api.together.xyz/v1",
        default_model="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        env_key="TOGETHER_API_KEY",
    ),
    "mistral": ProviderConfig(
        base_url="https://api.mistral.ai/v1",
        default_model="mistral-large-latest",
        env_key="MISTRAL_API_KEY",
    ),
    "deepseek": ProviderConfig(
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        env_key="DEEPSEEK_API_KEY",
    ),
    "xai": ProviderConfig(
        base_url="https://api.x.ai/v1",
        default_model="grok-3",
        env_key="XAI_API_KEY",
    ),
    "perplexity": ProviderConfig(
        base_url="https://api.perplexity.ai",
        default_model="sonar-pro",
        env_key="PERPLEXITY_API_KEY",
    ),
    "fireworks": ProviderConfig(
        base_url="https://api.fireworks.ai/inference/v1",
        default_model="accounts/fireworks/models/llama-v3p1-8b-instruct",
        env_key="FIREWORKS_API_KEY",
    ),
    "ollama": ProviderConfig(
        base_url="http://localhost:11434/v1",
        default_model="llama3.1",
        env_key="",  # no key needed
    ),
}

# Anthropic defaults (uses native SDK, not OpenAI-compatible)
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-6"


# ── Clients ──────────────────────────────────────────────────────────────────


class LLMClient:
    """Anthropic API client (native SDK)."""

    def __init__(self, api_key: str, model: str = ANTHROPIC_DEFAULT_MODEL):
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

    Works with any provider that supports POST /chat/completions.
    See PROVIDERS dict for pre-configured providers.
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        self.model = model
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


# ── Factory ──────────────────────────────────────────────────────────────────


def create_llm_client() -> LLMClient | OpenAICompatibleClient | CodexLLMClient | None:
    """Auto-detect and create the best available LLM client.

    Priority:
      1. LLM_PROVIDER + LLM_API_KEY  (explicit provider selection)
      2. ANTHROPIC_API_KEY            (Anthropic native SDK)
      3. OPENAI_API_KEY               (OpenAI via compatible client)
      4. Codex CLI                    (OAuth, no key needed)
      5. None                         (T1 rule-based only)

    Environment variables:
      LLM_PROVIDER:  anthropic | openai | gemini | groq | together |
                     mistral | deepseek | xai | perplexity | fireworks |
                     ollama | codex
      LLM_API_KEY:   API key for the chosen provider
      LLM_BASE_URL:  Custom base URL (overrides provider default)
      LLM_MODEL:     Model name (overrides provider default)
    """
    import os

    provider = os.environ.get("LLM_PROVIDER", "").lower()
    llm_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "")
    model = os.environ.get("LLM_MODEL", "")

    # 1. Explicit provider
    if provider:
        if provider == "anthropic":
            key = llm_key or os.environ.get("ANTHROPIC_API_KEY", "")
            if key:
                return LLMClient(key, model=model or ANTHROPIC_DEFAULT_MODEL)
        elif provider == "codex":
            if shutil.which("codex"):
                return CodexLLMClient(model=model or "o3")
        elif provider in PROVIDERS:
            cfg = PROVIDERS[provider]
            key = llm_key or os.environ.get(cfg.env_key, "")
            url = base_url or cfg.base_url
            if key or not cfg.env_key:  # ollama needs no key
                return OpenAICompatibleClient(
                    api_key=key or "ollama",
                    base_url=url,
                    model=model or cfg.default_model,
                )
        else:
            # Unknown provider — use as custom OpenAI-compatible endpoint
            if llm_key and base_url:
                return OpenAICompatibleClient(
                    api_key=llm_key,
                    base_url=base_url,
                    model=model or "default",
                )

    # 2. Anthropic API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return LLMClient(api_key, model=model or ANTHROPIC_DEFAULT_MODEL)

    # 3. OpenAI API key
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        cfg = PROVIDERS["openai"]
        return OpenAICompatibleClient(
            api_key=openai_key,
            base_url=cfg.base_url,
            model=model or cfg.default_model,
        )

    # 4. Codex CLI
    if shutil.which("codex"):
        return CodexLLMClient(model=model or "o3")

    # 5. None
    return None
