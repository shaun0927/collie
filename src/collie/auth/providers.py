"""Authentication providers for GitHub and LLM APIs."""

import os
import subprocess


class AuthError(Exception):
    """Raised when authentication credentials are missing or invalid."""

    pass


class GitHubAuth:
    def __init__(self, token: str):
        self.token = token

    @classmethod
    def from_env(cls) -> "GitHubAuth":
        """Auto-detect GitHub token: GITHUB_TOKEN > config.yaml > gh CLI."""
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            return cls(token)
        # Try config.yaml
        from collie.config import load_config

        cfg = load_config()
        if cfg.github_token:
            return cls(cfg.github_token)
        # Try gh CLI
        try:
            result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return cls(result.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        raise AuthError(
            "GitHub token not found.\n"
            "Set GITHUB_TOKEN environment variable, add it to ~/.collie/config.yaml,\n"
            "or install gh CLI and run 'gh auth login'.\n"
            "  export GITHUB_TOKEN=ghp_your_token_here"
        )


class LLMAuth:
    def __init__(self, api_key: str, provider: str = "anthropic"):
        self.api_key = api_key
        self.provider = provider

    @classmethod
    def from_env(cls) -> "LLMAuth":
        """Auto-detect LLM credentials: env vars > config.yaml > Codex CLI.

        Checks (in order):
          1. LLM_PROVIDER + LLM_API_KEY env vars
          2. ANTHROPIC_API_KEY env var
          3. OPENAI_API_KEY env var
          4. Config yaml (llm_provider or anthropic_api_key)
          5. Codex CLI availability
        """
        # Explicit provider env var
        provider = os.environ.get("LLM_PROVIDER", "").lower()
        llm_key = os.environ.get("LLM_API_KEY", "")
        if provider and llm_key:
            return cls(llm_key, provider)

        # Anthropic env var
        key = os.environ.get("ANTHROPIC_API_KEY")
        if key:
            return cls(key, "anthropic")

        # OpenAI env var
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            return cls(openai_key, "openai")

        # Config yaml
        from collie.config import load_config

        cfg = load_config()
        if cfg.llm_provider and cfg.llm_api_key:
            return cls(cfg.llm_api_key, cfg.llm_provider)
        if cfg.anthropic_api_key:
            return cls(cfg.anthropic_api_key, "anthropic")

        # Codex CLI (no API key needed)
        import shutil

        if shutil.which("codex"):
            return cls("", "codex")

        raise AuthError(
            "No LLM provider found.\n"
            "Options:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...    # Anthropic (Claude)\n"
            "  export OPENAI_API_KEY=sk-...           # OpenAI (GPT-4o)\n"
            "  export LLM_PROVIDER=gemini LLM_API_KEY=...  # Google, Groq, etc.\n"
            "  Install Codex CLI                      # OAuth, no key needed\n"
            "  Add credentials to ~/.collie/config.yaml"
        )
