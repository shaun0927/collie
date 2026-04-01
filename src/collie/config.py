"""Configuration loading from ~/.collie/config.yaml."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_PATH = Path.home() / ".collie" / "config.yaml"


@dataclass
class CollieConfig:
    """User configuration loaded from ~/.collie/config.yaml."""

    github_token: str | None = None
    anthropic_api_key: str | None = None
    default_repo: str | None = None
    llm_provider: str | None = None  # anthropic, openai, gemini, groq, together, mistral, deepseek, ollama, codex
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    extra: dict = field(default_factory=dict)


def load_config(path: Path | None = None) -> CollieConfig:
    """Load config from YAML file. Returns empty config if file doesn't exist."""
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        return CollieConfig()

    mode = config_path.stat().st_mode
    if mode & 0o077:
        warnings.warn(
            f"{config_path} is world- or group-readable (mode {oct(mode & 0o777)}). "
            "Consider running: chmod 600 ~/.collie/config.yaml",
            UserWarning,
            stacklevel=2,
        )

    try:
        data = yaml.safe_load(config_path.read_text()) or {}
    except (yaml.YAMLError, OSError):
        return CollieConfig()

    known_keys = {
        "github_token",
        "anthropic_api_key",
        "default_repo",
        "llm_provider",
        "llm_api_key",
        "llm_base_url",
        "llm_model",
    }
    return CollieConfig(
        github_token=data.get("github_token"),
        anthropic_api_key=data.get("anthropic_api_key"),
        default_repo=data.get("default_repo"),
        llm_provider=data.get("llm_provider"),
        llm_api_key=data.get("llm_api_key"),
        llm_base_url=data.get("llm_base_url"),
        llm_model=data.get("llm_model"),
        extra={k: v for k, v in data.items() if k not in known_keys},
    )
