"""Tests for ApproveCommand."""

import pytest

from collie.commands.approve import ApproveCommand
from collie.core.models import ApprovalRecord, ItemType, Mode, Philosophy, Recommendation, RecommendationAction


class MockREST:
    def __init__(self):
        self.merged = []
        self.closed = []
        self.comments = []
        self.labels = []

    async def merge_pr(self, owner, repo, number):
        self.merged.append(number)
        return {"merged": True}

    async def close_issue(self, owner, repo, number):
        self.closed.append(number)
        return {"state": "closed"}

    async def add_comment(self, owner, repo, number, body):
        self.comments.append((number, body))
        return {"id": 1}

    async def add_labels(self, owner, repo, number, labels):
        self.labels.append((number, labels))
        return {}


class MockQueueStore:
    def __init__(self, approvals=None, recommendations=None, actor=("maintainer", "WRITE")):
        self._approvals = approvals or []
        self._recommendations = recommendations or []
        self._verified_approvals: dict[int, ApprovalRecord] = {}
        self.executed = []
        self.results = None
        self.actor = actor

    async def read_approvals(self, owner, repo):
        return self._approvals

    async def read_verified_approvals(self, owner, repo):
        return sorted(self._verified_approvals)

    async def get_recommendations(self, owner, repo, numbers=None):
        if numbers is None:
            return list(self._recommendations)
        wanted = set(numbers)
        ordered = {n: idx for idx, n in enumerate(numbers)}
        recs = [r for r in self._recommendations if r.number in wanted]
        recs.sort(key=lambda item: ordered[item.number])
        return recs

    async def record_approvals(self, owner, repo, numbers, approver, source="cli"):
        created = []
        recs = await self.get_recommendations(owner, repo, numbers)
        for rec in recs:
            record = ApprovalRecord(
                number=rec.number,
                approver=approver,
                approved_payload_hash=rec.payload_hash(),
                approved_at="2026-04-03 00:00 UTC",
                source=source,
            )
            self._verified_approvals[rec.number] = record
            created.append(record)
        return created

    async def get_actor_permission(self, owner, repo):
        return self.actor

    async def mark_executed(self, owner, repo, numbers, results=None, execution_paths=None):
        self.executed.extend(numbers)
        self.results = results or {}


class MockPhilosophyStore:
    def __init__(self, philosophy=None):
        self._p = philosophy

    async def load(self, owner, repo):
        return self._p


def make_training_store():
    return MockPhilosophyStore(Philosophy(mode=Mode.TRAINING))


def make_active_store():
    return MockPhilosophyStore(Philosophy(mode=Mode.ACTIVE))


def make_rec(number: int, action: RecommendationAction, item_type: ItemType = ItemType.PR, **kwargs) -> Recommendation:
    return Recommendation(number=number, item_type=item_type, action=action, reason="Approved", **kwargs)


@pytest.mark.asyncio
async def test_training_mode_blocks_execution():
    cmd = ApproveCommand(MockREST(), MockQueueStore(), make_training_store())
    with pytest.raises(PermissionError, match="training mode"):
        await cmd.approve("owner", "repo", numbers=[42])


@pytest.mark.asyncio
async def test_unauthorized_actor_cannot_approve():
    rest = MockREST()
    queue = MockQueueStore(recommendations=[make_rec(10, RecommendationAction.MERGE)], actor=("viewer", "READ"))
    cmd = ApproveCommand(rest, queue, make_active_store())

    with pytest.raises(PermissionError, match="lacks approval permissions"):
        await cmd.approve("owner", "repo", numbers=[10])


@pytest.mark.asyncio
async def test_approve_specific_numbers_records_verified_approval_and_executes():
    rest = MockREST()
    queue = MockQueueStore(
        recommendations=[
            make_rec(10, RecommendationAction.MERGE),
            make_rec(20, RecommendationAction.CLOSE, item_type=ItemType.ISSUE),
            make_rec(30, RecommendationAction.LABEL, suggested_labels=["bug"]),
        ]
    )
    cmd = ApproveCommand(rest, queue, make_active_store())
    report = await cmd.approve("owner", "repo", numbers=[20, 30])

    assert len(report.succeeded) == 2
    assert rest.merged == []
    assert rest.closed == [20]
    assert rest.labels == [(30, ["bug"])]
    assert queue.executed == [20, 30]
    assert set(queue._verified_approvals) == {20, 30}
    assert queue._verified_approvals[20].approver == "maintainer"


@pytest.mark.asyncio
async def test_approve_all_consumes_verified_approvals_only():
    rest = MockREST()
    rec5 = make_rec(5, RecommendationAction.MERGE)
    rec6 = make_rec(6, RecommendationAction.COMMENT, item_type=ItemType.ISSUE, suggested_comment="Needs repro")
    queue = MockQueueStore(
        approvals=[5, 6, 7],
        recommendations=[
            rec5,
            rec6,
            make_rec(7, RecommendationAction.LINK_TO_PR, item_type=ItemType.ISSUE, linked_pr=11),
        ],
    )
    queue._verified_approvals = {
        5: ApprovalRecord(5, "maintainer", rec5.payload_hash(), "2026-04-03 00:00 UTC"),
        6: ApprovalRecord(6, "maintainer", rec6.payload_hash(), "2026-04-03 00:00 UTC"),
    }
    cmd = ApproveCommand(rest, queue, make_active_store())
    report = await cmd.approve("owner", "repo", approve_all=True)

    assert len(report.succeeded) == 2
    assert rest.merged == [5]
    assert (6, "Needs repro") in rest.comments
    assert 7 not in queue.executed


@pytest.mark.asyncio
async def test_approve_all_empty_verified_queue_returns_empty_report():
    rest = MockREST()
    queue = MockQueueStore(approvals=[5, 6], recommendations=[])
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
async def test_non_executable_actions_are_skipped_and_not_marked_executed():
    rest = MockREST()
    queue = MockQueueStore(
        recommendations=[
            make_rec(70, RecommendationAction.HOLD),
            make_rec(71, RecommendationAction.ESCALATE),
        ]
    )
    cmd = ApproveCommand(rest, queue, make_active_store())
    report = await cmd.approve("owner", "repo", numbers=[70, 71])

    assert len(report.skipped) == 2
    assert queue.executed == []
    assert set(queue._verified_approvals) == {70, 71}


@pytest.mark.asyncio
async def test_failed_execution_is_recorded_back_to_queue_with_reason():
    class FailingREST(MockREST):
        async def merge_pr(self, owner, repo, number):
            raise Exception("405 conflict")

    rest = FailingREST()
    queue = MockQueueStore(recommendations=[make_rec(42, RecommendationAction.MERGE)])
    cmd = ApproveCommand(rest, queue, make_active_store())
    report = await cmd.approve("owner", "repo", numbers=[42])

    assert len(report.failed) == 1
    assert queue.executed == [42]
    assert queue.results == {42: "error: Merge conflict"}
    assert queue._verified_approvals[42].approver == "maintainer"


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
