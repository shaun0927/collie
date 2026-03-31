"""Tests for ShakeHandsCommand."""

from __future__ import annotations

import pytest

from collie.commands.shake_hands import ShakeHandsCommand
from collie.core.models import HardRule, Mode, Philosophy


class MockPhilosophyStore:
    def __init__(self, phil=None):
        self._p = phil

    async def load(self, owner, repo):
        return self._p

    async def save(self, owner, repo, phil):
        self._p = phil

    async def set_mode(self, owner, repo, mode):
        self._p.mode = mode
        return self._p

    async def update_rule(self, owner, repo, rule, action):
        pass


class MockQueueStore:
    def __init__(self):
        self.invalidated = False

    async def invalidate_all(self, owner, repo):
        self.invalidated = True


def _phil():
    return Philosophy(hard_rules=[HardRule("ci_failed", "reject")], soft_text="test", mode=Mode.TRAINING)


# ---------------------------------------------------------------------------
# micro_update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_micro_update_vendor_reason():
    """micro_update returns hard_rule suggestion for vendor lock-in reason."""
    cmd = ShakeHandsCommand(MockPhilosophyStore(_phil()), MockQueueStore())
    result = await cmd.micro_update("owner", "repo", "vendor lock-in detected", 42)

    assert "vendor" in result["suggestion"].lower() or "lock-in" in result["suggestion"].lower()
    assert result["applied"] is False
    assert result["rule"]["type"] == "hard_rule"
    assert result["rule"]["condition"] == "vendor_dependency"


@pytest.mark.asyncio
async def test_micro_update_security_reason():
    """micro_update returns escalation suggestion for security reason."""
    cmd = ShakeHandsCommand(MockPhilosophyStore(_phil()), MockQueueStore())
    result = await cmd.micro_update("owner", "repo", "security vulnerability CVE-2024-1234", 7)

    assert result["applied"] is False
    assert result["rule"]["type"] == "escalation"
    assert result["rule"]["action"] == "escalate"


@pytest.mark.asyncio
async def test_micro_update_test_reason():
    """micro_update returns hard_rule suggestion for missing test reason."""
    cmd = ShakeHandsCommand(MockPhilosophyStore(_phil()), MockQueueStore())
    result = await cmd.micro_update("owner", "repo", "no test coverage provided", 15)

    assert result["applied"] is False
    assert result["rule"]["type"] == "hard_rule"
    assert result["rule"]["condition"] == "no_tests"


@pytest.mark.asyncio
async def test_micro_update_generic_reason():
    """micro_update returns custom hard_rule for unrecognised rejection reason."""
    cmd = ShakeHandsCommand(MockPhilosophyStore(_phil()), MockQueueStore())
    result = await cmd.micro_update("owner", "repo", "style issues throughout", 99)

    assert result["applied"] is False
    assert result["rule"]["type"] == "hard_rule"
    assert result["rule"]["condition"] == "custom"
    assert "99" in result["suggestion"]


@pytest.mark.asyncio
async def test_micro_update_no_philosophy_raises():
    """micro_update raises ValueError when no philosophy exists."""
    cmd = ShakeHandsCommand(MockPhilosophyStore(None), MockQueueStore())

    with pytest.raises(ValueError, match="No philosophy found"):
        await cmd.micro_update("owner", "repo", "some reason", 1)


# ---------------------------------------------------------------------------
# apply_micro_update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_micro_update_adds_hard_rule():
    """apply_micro_update appends a HardRule to the philosophy."""
    store = MockPhilosophyStore(_phil())
    cmd = ShakeHandsCommand(store, MockQueueStore())

    rule = {"condition": "no_tests", "action": "hold", "description": "Tests required"}
    updated = await cmd.apply_micro_update("owner", "repo", "hard_rule", rule)

    conditions = [r.condition for r in updated.hard_rules]
    assert "no_tests" in conditions


@pytest.mark.asyncio
async def test_apply_micro_update_adds_escalation_rule():
    """apply_micro_update appends an EscalationRule to the philosophy."""
    store = MockPhilosophyStore(_phil())
    cmd = ShakeHandsCommand(store, MockQueueStore())

    rule = {"pattern": "security/*", "action": "escalate", "description": "Security review"}
    updated = await cmd.apply_micro_update("owner", "repo", "escalation", rule)

    patterns = [r.pattern for r in updated.escalation_rules]
    assert "security/*" in patterns


@pytest.mark.asyncio
async def test_apply_micro_update_invalidates_queue():
    """apply_micro_update calls invalidate_all on the queue store."""
    queue = MockQueueStore()
    cmd = ShakeHandsCommand(MockPhilosophyStore(_phil()), queue)

    rule = {"condition": "custom", "action": "hold", "description": "test"}
    await cmd.apply_micro_update("owner", "repo", "hard_rule", rule)

    assert queue.invalidated is True


# ---------------------------------------------------------------------------
# full_revision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_revision_returns_philosophy():
    """full_revision returns the current philosophy object."""
    phil = _phil()
    cmd = ShakeHandsCommand(MockPhilosophyStore(phil), MockQueueStore())

    result = await cmd.full_revision("owner", "repo")

    assert result is phil


@pytest.mark.asyncio
async def test_full_revision_no_philosophy_raises():
    """full_revision raises ValueError when no philosophy exists."""
    cmd = ShakeHandsCommand(MockPhilosophyStore(None), MockQueueStore())

    with pytest.raises(ValueError, match="No philosophy found"):
        await cmd.full_revision("owner", "repo")
