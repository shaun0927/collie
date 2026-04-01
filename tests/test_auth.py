"""Tests for auth providers."""

import pytest

from collie.auth import AuthError, GitHubAuth, LLMAuth
from collie.config import CollieConfig


def test_github_auth_from_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test_token")
    auth = GitHubAuth.from_env()
    assert auth.token == "test_token"


def test_github_auth_missing(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr("collie.config.load_config", lambda: CollieConfig())
    # Patch subprocess.run to simulate gh CLI not being available
    import subprocess

    def mock_run(*args, **kwargs):
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr(subprocess, "run", mock_run)
    with pytest.raises(AuthError, match="GitHub token not found"):
        GitHubAuth.from_env()


def test_github_auth_from_gh_cli(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    import subprocess

    class MockResult:
        returncode = 0
        stdout = "ghp_cli_token\n"

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: MockResult())
    auth = GitHubAuth.from_env()
    assert auth.token == "ghp_cli_token"


def test_llm_auth_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    auth = LLMAuth.from_env()
    assert auth.api_key == "sk-ant-test"
    assert auth.provider == "anthropic"


def test_llm_auth_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("collie.config.load_config", lambda: CollieConfig())
    with pytest.raises(AuthError, match="Anthropic API key not found"):
        LLMAuth.from_env()


def test_auth_error_is_exception():
    err = AuthError("test message")
    assert isinstance(err, Exception)
    assert str(err) == "test message"
