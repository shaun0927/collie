"""Tests for ApproveCommand."""

import pytest

from collie.commands.approve import ApproveCommand
from collie.core.models import Mode, Philosophy


class MockREST:
    def __init__(self):
        self.merged = []

    async def merge_pr(self, owner, repo, number):
        self.merged.append(number)
        return {"merged": True}

    async def close_issue(self, owner, repo, number):
        return {"state": "closed"}

    async def add_comment(self, owner, repo, number, body):
        return {"id": 1}

    async def add_labels(self, owner, repo, number, labels):
        return {}


class MockQueueStore:
    def __init__(self, approvals=None):
        self._approvals = approvals or []
        self.executed = []

    async def read_approvals(self, owner, repo):
        return self._approvals

    async def mark_executed(self, owner, repo, numbers, results=None):
        self.executed.extend(numbers)


class MockPhilosophyStore:
    def __init__(self, philosophy=None):
        self._p = philosophy

    async def load(self, owner, repo):
        return self._p


def make_training_store():
    return MockPhilosophyStore(Philosophy(mode=Mode.TRAINING))


def make_active_store():
    return MockPhilosophyStore(Philosophy(mode=Mode.ACTIVE))


@pytest.mark.asyncio
async def test_training_mode_blocks_execution():
    cmd = ApproveCommand(MockREST(), MockQueueStore(), make_training_store())
    with pytest.raises(PermissionError, match="training mode"):
        await cmd.approve("owner", "repo", numbers=[42])


@pytest.mark.asyncio
async def test_approve_specific_numbers():
    rest = MockREST()
    queue = MockQueueStore()
    cmd = ApproveCommand(rest, queue, make_active_store())
    report = await cmd.approve("owner", "repo", numbers=[10, 20])

    assert len(report.succeeded) == 2
    assert 10 in rest.merged
    assert 20 in rest.merged
    assert 10 in queue.executed
    assert 20 in queue.executed


@pytest.mark.asyncio
async def test_approve_all():
    rest = MockREST()
    queue = MockQueueStore(approvals=[5, 6, 7])
    cmd = ApproveCommand(rest, queue, make_active_store())
    report = await cmd.approve("owner", "repo", approve_all=True)

    assert len(report.succeeded) == 3
    assert set(rest.merged) == {5, 6, 7}


@pytest.mark.asyncio
async def test_approve_all_empty_queue_returns_empty_report():
    rest = MockREST()
    queue = MockQueueStore(approvals=[])
    cmd = ApproveCommand(rest, queue, make_active_store())
    report = await cmd.approve("owner", "repo", approve_all=True)

    assert report.results == []
    assert len(rest.merged) == 0


@pytest.mark.asyncio
async def test_approve_empty_numbers_returns_empty_report():
    rest = MockREST()
    queue = MockQueueStore()
    cmd = ApproveCommand(rest, queue, make_active_store())
    report = await cmd.approve("owner", "repo", numbers=[])

    assert report.results == []


@pytest.mark.asyncio
async def test_approve_none_numbers_returns_empty_report():
    rest = MockREST()
    queue = MockQueueStore()
    cmd = ApproveCommand(rest, queue, make_active_store())
    report = await cmd.approve("owner", "repo", numbers=None)

    assert report.results == []


@pytest.mark.asyncio
async def test_reject_vendor_generates_rule_suggestion():
    cmd = ApproveCommand(MockREST(), MockQueueStore(), make_active_store())
    suggestion = await cmd.reject("owner", "repo", number=42, reason="vendor lock-in concern")
    assert "vendor_dependency" in suggestion
    assert "42" in suggestion


@pytest.mark.asyncio
async def test_reject_security_generates_escalation():
    cmd = ApproveCommand(MockREST(), MockQueueStore(), make_active_store())
    suggestion = await cmd.reject("owner", "repo", number=10, reason="security vulnerability")
    assert "escalate" in suggestion
    assert "10" in suggestion


@pytest.mark.asyncio
async def test_reject_test_generates_hold_rule():
    cmd = ApproveCommand(MockREST(), MockQueueStore(), make_active_store())
    suggestion = await cmd.reject("owner", "repo", number=5, reason="no tests added")
    assert "no_tests" in suggestion
    assert "hold" in suggestion


@pytest.mark.asyncio
async def test_reject_breaking_change_generates_hold_rule():
    cmd = ApproveCommand(MockREST(), MockQueueStore(), make_active_store())
    suggestion = await cmd.reject("owner", "repo", number=3, reason="breaking change in API")
    assert "breaking_change" in suggestion
    assert "hold" in suggestion


@pytest.mark.asyncio
async def test_reject_empty_reason_returns_empty():
    cmd = ApproveCommand(MockREST(), MockQueueStore(), make_active_store())
    suggestion = await cmd.reject("owner", "repo", number=1, reason="")
    assert suggestion == ""


@pytest.mark.asyncio
async def test_reject_generic_reason_returns_suggestion():
    cmd = ApproveCommand(MockREST(), MockQueueStore(), make_active_store())
    suggestion = await cmd.reject("owner", "repo", number=99, reason="not aligned with roadmap")
    assert "99" in suggestion
    assert len(suggestion) > 0
