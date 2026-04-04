"""Tests for IncrementalManager."""

import pytest

from collie.core.incremental import IncrementalManager
from collie.core.models import HardRule, Mode, Philosophy


class MockGQL:
    def __init__(self):
        self.calls = []

    async def fetch_issues_and_prs(self, owner, repo, since=None):
        self.calls.append({"owner": owner, "repo": repo, "since": since})
        return {"issues": [{"number": 1}], "pull_requests": [{"number": 2, "additions": 10}]}


class MockQueue:
    def __init__(self):
        self.invalidated = False
        self.removed = []
        self.invalidated_numbers = []
        self.meta = {}
        self.items = []

    async def invalidate_all(self, owner, repo):
        self.invalidated = True

    async def read_approvals(self, owner, repo):
        return []

    async def read_incremental_state(self, owner, repo):
        return dict(self.meta)

    async def write_incremental_state(self, owner, repo, meta):
        self.meta = dict(meta)

    async def get_recommendations(self, owner, repo):
        return list(self.items)

    async def remove_stale(self, owner, repo, numbers):
        self.removed.extend(numbers)

    async def invalidate_numbers(self, owner, repo, numbers):
        self.invalidated_numbers.extend(numbers)


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


@pytest.mark.asyncio
async def test_persisted_state_reused_by_new_manager():
    gql = MockGQL()
    queue = MockQueue()
    p = _make_philosophy()
    mgr1 = IncrementalManager(gql, queue, MockPhilosophy(p))
    mgr1.record_bark_time()
    mgr1.record_philosophy_hash(p)
    items = await mgr1.get_all("o", "r")
    await mgr1.persist_state("o", "r", p, items)

    mgr2 = IncrementalManager(gql, queue, MockPhilosophy(p))
    assert await mgr2.should_full_scan("o", "r") is False
    await mgr2.get_delta("o", "r")
    assert gql.calls[-1]["since"] == queue.meta["last_bark_time"]


@pytest.mark.asyncio
async def test_detect_stale_in_queue_for_removed_and_changed_items():
    gql = MockGQL()
    queue = MockQueue()
    p = _make_philosophy()
    mgr = IncrementalManager(gql, queue, MockPhilosophy(p))

    queue.items = [
        type("QueueRec", (), {"number": 1})(),
        type("QueueRec", (), {"number": 2})(),
    ]
    queue.meta = {
        "last_bark_time": "2026-01-01T00:00:00Z",
        "last_philosophy_hash": mgr._hash_philosophy(p),
        "item_fingerprints": {
            "1": "old-fingerprint",
            "2": "fingerprint-2",
        },
    }
    current_items = [
        {"number": 1, "updatedAt": "2026-02-01T00:00:00Z", "state": "OPEN", "additions": 1, "changedFiles": 1},
    ]
    stale = await mgr.detect_stale_in_queue("o", "r", current_items)
    assert set(stale) == {1, 2}


@pytest.mark.asyncio
async def test_apply_stale_queue_updates_removes_and_invalidates():
    gql = MockGQL()
    queue = MockQueue()
    p = _make_philosophy()
    mgr = IncrementalManager(gql, queue, MockPhilosophy(p))
    queue.items = [
        type("QueueRec", (), {"number": 1})(),
        type("QueueRec", (), {"number": 2})(),
    ]
    queue.meta = {
        "last_bark_time": "2026-01-01T00:00:00Z",
        "last_philosophy_hash": mgr._hash_philosophy(p),
        "item_fingerprints": {
            "1": "old-fingerprint",
            "2": "fingerprint-2",
        },
    }
    current_items = [
        {"number": 1, "updatedAt": "2026-02-01T00:00:00Z", "state": "OPEN", "additions": 1, "changedFiles": 1},
    ]
    await mgr.apply_stale_queue_updates("o", "r", current_items)
    assert queue.invalidated_numbers == [1]
    assert queue.removed == [2]
