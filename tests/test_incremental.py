"""Tests for IncrementalManager."""

import pytest

from collie.core.incremental import IncrementalManager
from collie.core.models import HardRule, Mode, Philosophy


class MockGQL:
    async def fetch_issues_and_prs(self, owner, repo, since=None):
        return {"issues": [{"number": 1}], "pull_requests": [{"number": 2, "additions": 10}]}


class MockQueue:
    async def invalidate_all(self, owner, repo):
        self.invalidated = True

    async def read_approvals(self, owner, repo):
        return []


class MockPhilosophy:
    def __init__(self, philosophy=None):
        self._p = philosophy

    async def load(self, owner, repo):
        return self._p


def _make_philosophy(**kwargs):
    return Philosophy(
        hard_rules=[HardRule("ci_failed", "reject")],
        soft_text="test",
        mode=Mode.TRAINING,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_first_run_full_scan():
    mgr = IncrementalManager(MockGQL(), MockQueue(), MockPhilosophy(_make_philosophy()))
    assert await mgr.should_full_scan("o", "r") is True


@pytest.mark.asyncio
async def test_no_philosophy_full_scan():
    mgr = IncrementalManager(MockGQL(), MockQueue(), MockPhilosophy(None))
    assert await mgr.should_full_scan("o", "r") is True


@pytest.mark.asyncio
async def test_philosophy_change_triggers_full_scan():
    p = _make_philosophy()
    queue = MockQueue()
    mgr = IncrementalManager(MockGQL(), queue, MockPhilosophy(p))

    # First run records hash
    mgr.record_bark_time()
    mgr.record_philosophy_hash(p)

    # Change philosophy
    p2 = Philosophy(
        hard_rules=[HardRule("ci_failed", "reject")],
        soft_text="changed philosophy",
        mode=Mode.TRAINING,
    )
    mgr.philosophy = MockPhilosophy(p2)

    assert await mgr.should_full_scan("o", "r") is True


@pytest.mark.asyncio
async def test_no_change_incremental():
    p = _make_philosophy()
    mgr = IncrementalManager(MockGQL(), MockQueue(), MockPhilosophy(p))
    mgr.record_bark_time()
    mgr.record_philosophy_hash(p)

    assert await mgr.should_full_scan("o", "r") is False


def test_record_bark_time():
    mgr = IncrementalManager(MockGQL(), MockQueue(), MockPhilosophy(None))
    assert mgr._last_bark_time is None
    mgr.record_bark_time()
    assert mgr._last_bark_time is not None


def test_hash_philosophy_deterministic():
    p = _make_philosophy()
    h1 = IncrementalManager._hash_philosophy(p)
    h2 = IncrementalManager._hash_philosophy(p)
    assert h1 == h2
    assert len(h1) == 16


@pytest.mark.asyncio
async def test_get_all():
    mgr = IncrementalManager(MockGQL(), MockQueue(), MockPhilosophy(None))
    items = await mgr.get_all("o", "r")
    assert len(items) == 2


@pytest.mark.asyncio
async def test_get_delta():
    mgr = IncrementalManager(MockGQL(), MockQueue(), MockPhilosophy(None))
    mgr._last_bark_time = "2026-01-01T00:00:00Z"
    items = await mgr.get_delta("o", "r")
    assert len(items) == 2
