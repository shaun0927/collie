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
        """Auto-detect GitHub token: GITHUB_TOKEN > gh CLI."""
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            return cls(token)
        # Try gh CLI
        try:
            result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return cls(result.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        raise AuthError(
            "GitHub token not found.\n"
            "Set GITHUB_TOKEN environment variable or install gh CLI and run 'gh auth login'.\n"
            "  export GITHUB_TOKEN=ghp_your_token_here"
        )


class LLMAuth:
    def __init__(self, api_key: str, provider: str = "anthropic"):
        self.api_key = api_key
        self.provider = provider

    @classmethod
    def from_env(cls) -> "LLMAuth":
        """Auto-detect LLM API key: ANTHROPIC_API_KEY."""
        key = os.environ.get("ANTHROPIC_API_KEY")
        if key:
            return cls(key, "anthropic")
        raise AuthError(
            "Anthropic API key not found.\n"
            "Set ANTHROPIC_API_KEY environment variable.\n"
            "  export ANTHROPIC_API_KEY=sk-ant-your_key_here\n"
            "Get your key at: https://console.anthropic.com/settings/keys"
        )
