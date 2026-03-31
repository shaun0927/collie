"""Tests for ModeCommand."""

from __future__ import annotations

import pytest

from collie.commands.mode import ModeCommand, StatusReport
from collie.core.models import EscalationRule, HardRule, Mode, Philosophy, TuningParams


class MockPhilosophyStore:
    def __init__(self, phil=None):
        self._p = phil

    async def load(self, owner, repo):
        return self._p

    async def set_mode(self, owner, repo, mode):
        self._p.mode = mode
        return self._p


def _phil(mode=Mode.TRAINING):
    return Philosophy(
        hard_rules=[HardRule("ci_failed", "reject")],
        escalation_rules=[EscalationRule("security/*", "escalate")],
        trusted_contributors=["alice"],
        soft_text="test",
        mode=mode,
        tuning=TuningParams(confidence_threshold=0.85, analysis_depth="t3", cost_cap_per_bark=100.0),
    )


# ---------------------------------------------------------------------------
# unleash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unleash_changes_mode_to_active():
    """unleash transitions mode from TRAINING to ACTIVE."""
    store = MockPhilosophyStore(_phil(Mode.TRAINING))
    cmd = ModeCommand(store)

    result = await cmd.unleash("owner", "repo")

    assert result.mode == Mode.ACTIVE


@pytest.mark.asyncio
async def test_unleash_when_already_active_raises():
    """unleash raises ValueError when already in ACTIVE mode."""
    cmd = ModeCommand(MockPhilosophyStore(_phil(Mode.ACTIVE)))

    with pytest.raises(ValueError, match="Already in active mode"):
        await cmd.unleash("owner", "repo")


@pytest.mark.asyncio
async def test_unleash_no_philosophy_raises():
    """unleash raises ValueError when no philosophy exists."""
    cmd = ModeCommand(MockPhilosophyStore(None))

    with pytest.raises(ValueError, match="No philosophy found"):
        await cmd.unleash("owner", "repo")


# ---------------------------------------------------------------------------
# leash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_leash_changes_mode_to_training():
    """leash transitions mode from ACTIVE to TRAINING."""
    store = MockPhilosophyStore(_phil(Mode.ACTIVE))
    cmd = ModeCommand(store)

    result = await cmd.leash("owner", "repo")

    assert result.mode == Mode.TRAINING


@pytest.mark.asyncio
async def test_leash_when_already_training_raises():
    """leash raises ValueError when already in TRAINING mode."""
    cmd = ModeCommand(MockPhilosophyStore(_phil(Mode.TRAINING)))

    with pytest.raises(ValueError, match="Already in training mode"):
        await cmd.leash("owner", "repo")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_returns_correct_fields():
    """status returns StatusReport populated from the philosophy."""
    cmd = ModeCommand(MockPhilosophyStore(_phil(Mode.TRAINING)))

    report = await cmd.status("owner", "repo")

    assert report.owner == "owner"
    assert report.repo == "repo"
    assert report.mode == Mode.TRAINING
    assert report.hard_rules_count == 1
    assert report.escalation_rules_count == 1
    assert report.trusted_contributors_count == 1
    assert report.confidence_threshold == 0.85
    assert report.analysis_depth == "t3"
    assert report.cost_cap == 100.0
    assert report.has_philosophy is True


@pytest.mark.asyncio
async def test_status_no_philosophy_returns_defaults():
    """status returns a default StatusReport with has_philosophy=False when none exists."""
    cmd = ModeCommand(MockPhilosophyStore(None))

    report = await cmd.status("owner", "repo")

    assert report.has_philosophy is False
    assert report.mode == Mode.TRAINING
    assert report.hard_rules_count == 0
    assert report.escalation_rules_count == 0
    assert report.trusted_contributors_count == 0
    assert report.confidence_threshold == 0.9
    assert report.analysis_depth == "t2"
    assert report.cost_cap == 50.0


# ---------------------------------------------------------------------------
# StatusReport.summary
# ---------------------------------------------------------------------------


def test_status_report_summary_contains_mode():
    """summary includes the current mode value."""
    report = StatusReport(
        owner="o",
        repo="r",
        mode=Mode.ACTIVE,
        hard_rules_count=2,
        escalation_rules_count=1,
        trusted_contributors_count=3,
        confidence_threshold=0.9,
        analysis_depth="t2",
        cost_cap=50.0,
    )

    text = report.summary()

    assert "active" in text


def test_status_report_summary_contains_cost_cap():
    """summary includes the cost cap formatted as currency."""
    report = StatusReport(
        owner="o",
        repo="r",
        mode=Mode.TRAINING,
        hard_rules_count=0,
        escalation_rules_count=0,
        trusted_contributors_count=0,
        confidence_threshold=0.9,
        analysis_depth="t2",
        cost_cap=75.50,
    )

    text = report.summary()

    assert "75.50" in text
