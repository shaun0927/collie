"""Configuration loading from ~/.collie/config.yaml."""

from __future__ import annotations

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
    extra: dict = field(default_factory=dict)


def load_config(path: Path | None = None) -> CollieConfig:
    """Load config from YAML file. Returns empty config if file doesn't exist."""
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        return CollieConfig()

    try:
        data = yaml.safe_load(config_path.read_text()) or {}
    except (yaml.YAMLError, OSError):
        return CollieConfig()

    return CollieConfig(
        github_token=data.get("github_token"),
        anthropic_api_key=data.get("anthropic_api_key"),
        default_repo=data.get("default_repo"),
        extra={k: v for k, v in data.items() if k not in ("github_token", "anthropic_api_key", "default_repo")},
    )
