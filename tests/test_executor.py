"""Tests for Executor."""

import pytest

from collie.core.executor import ExecutionReport, ExecutionStatus, Executor
from collie.core.models import GitHubItemMetadata, ItemType, Recommendation, RecommendationAction


def make_rec(number: int, action: RecommendationAction, **kwargs) -> Recommendation:
    return Recommendation(number=number, item_type=ItemType.PR, action=action, reason="test", **kwargs)


class MockREST:
    def __init__(self):
        self.merged = []
        self.closed = []
        self.comments = []
        self.labels = []
        self.auto_merge_enabled = []
        self.merge_queue = []

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

    async def enable_auto_merge(self, pull_request_id, merge_method="SQUASH"):
        self.auto_merge_enabled.append((pull_request_id, merge_method))
        return {"id": pull_request_id}

    async def enqueue_pull_request(self, pull_request_id):
        self.merge_queue.append(pull_request_id)
        return {"id": pull_request_id}


class FailingREST(MockREST):
    def __init__(self, error_msg: str = "500 server error"):
        super().__init__()
        self.error_msg = error_msg

    async def merge_pr(self, owner, repo, number):
        raise Exception(self.error_msg)


@pytest.mark.asyncio
async def test_successful_merge():
    rest = MockREST()
    executor = Executor(rest)
    rec = make_rec(42, RecommendationAction.MERGE)
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.succeeded) == 1
    assert report.succeeded[0].number == 42
    assert report.succeeded[0].message == "Merged"
    assert report.succeeded[0].execution_path == "direct_merge"
    assert 42 in rest.merged


@pytest.mark.asyncio
async def test_merge_conflict_returns_failed_result():
    rest = FailingREST("405 method not allowed conflict")
    executor = Executor(rest)
    rec = make_rec(42, RecommendationAction.MERGE)
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.failed) == 1
    assert report.failed[0].number == 42
    assert "conflict" in report.failed[0].message.lower()
    assert report.failed[0].execution_path == "blocked"


@pytest.mark.asyncio
async def test_merge_403_branch_protection():
    rest = FailingREST("403 forbidden")
    executor = Executor(rest)
    rec = make_rec(42, RecommendationAction.MERGE)
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.failed) == 1
    assert "protection" in report.failed[0].message.lower()
    assert report.failed[0].execution_path == "blocked"


@pytest.mark.asyncio
async def test_draft_pr_is_blocked_before_merge_attempt():
    rest = MockREST()
    executor = Executor(rest)
    metadata = GitHubItemMetadata(is_draft=True).to_dict()
    rec = make_rec(43, RecommendationAction.MERGE, github_metadata=metadata)
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.failed) == 1
    assert report.failed[0].message == "Blocked: draft PR"
    assert rest.merged == []


@pytest.mark.asyncio
async def test_required_checks_pending_enable_auto_merge():
    rest = MockREST()
    executor = Executor(rest)
    metadata = GitHubItemMetadata(
        pull_request_id="PR_kw123",
        required_check_state="PENDING",
        mergeable="MERGEABLE",
    ).to_dict()
    rec = make_rec(44, RecommendationAction.MERGE, github_metadata=metadata)
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.succeeded) == 1
    assert report.succeeded[0].message == "Auto-merge enabled"
    assert report.succeeded[0].execution_path == "auto_merge"
    assert rest.auto_merge_enabled == [("PR_kw123", "SQUASH")]
    assert rest.merged == []


@pytest.mark.asyncio
async def test_merge_queue_path_enqueues_pull_request():
    rest = MockREST()
    executor = Executor(rest)
    metadata = GitHubItemMetadata(
        pull_request_id="PR_kw456",
        merge_queue_required=True,
        mergeable="MERGEABLE",
        required_check_state="SUCCESS",
    ).to_dict()
    rec = make_rec(45, RecommendationAction.MERGE, github_metadata=metadata)
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.succeeded) == 1
    assert report.succeeded[0].message == "Enqueued in merge queue"
    assert report.succeeded[0].execution_path == "merge_queue"
    assert rest.merge_queue == ["PR_kw456"]
    assert rest.merged == []


@pytest.mark.asyncio
async def test_merge_queue_required_without_enqueue_support_blocks():
    class NoQueueREST(MockREST):
        async def enqueue_pull_request(self, pull_request_id):
            raise AttributeError

    rest = NoQueueREST()
    del rest.merge_queue
    executor = Executor(rest)
    metadata = GitHubItemMetadata(
        pull_request_id="PR_kw789",
        merge_queue_required=True,
        mergeable="MERGEABLE",
        required_check_state="SUCCESS",
    ).to_dict()
    rec = make_rec(46, RecommendationAction.MERGE, github_metadata=metadata)
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.failed) == 1
    assert report.failed[0].message == "Blocked: merge queue required"
    assert report.failed[0].execution_path == "blocked"


@pytest.mark.asyncio
async def test_close_and_comment():
    rest = MockREST()
    executor = Executor(rest)
    rec = make_rec(50, RecommendationAction.CLOSE, suggested_comment="Closing as stale.")
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.succeeded) == 1
    assert 50 in rest.closed
    assert (50, "Closing as stale.") in rest.comments


@pytest.mark.asyncio
async def test_close_without_comment():
    rest = MockREST()
    executor = Executor(rest)
    rec = make_rec(50, RecommendationAction.CLOSE)
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.succeeded) == 1
    assert 50 in rest.closed
    assert len(rest.comments) == 0


@pytest.mark.asyncio
async def test_label_action():
    rest = MockREST()
    executor = Executor(rest)
    rec = make_rec(60, RecommendationAction.LABEL, suggested_labels=["bug", "help wanted"])
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.succeeded) == 1
    assert (60, ["bug", "help wanted"]) in rest.labels


@pytest.mark.asyncio
async def test_hold_is_skipped():
    rest = MockREST()
    executor = Executor(rest)
    rec = make_rec(70, RecommendationAction.HOLD)
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.skipped) == 1
    assert report.skipped[0].number == 70
    assert report.skipped[0].message == "Not executable"


@pytest.mark.asyncio
async def test_escalate_is_skipped():
    rest = MockREST()
    executor = Executor(rest)
    rec = make_rec(71, RecommendationAction.ESCALATE)
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.skipped) == 1
    assert report.skipped[0].number == 71


@pytest.mark.asyncio
async def test_partial_execution_continues_on_failure():
    class BrokenREST(MockREST):
        async def merge_pr(self, owner, repo, number):
            if number == 2:
                raise Exception("405 conflict")
            self.merged.append(number)
            return {"merged": True}

    broken = BrokenREST()
    executor2 = Executor(broken)
    recs = [
        make_rec(1, RecommendationAction.MERGE),
        make_rec(2, RecommendationAction.MERGE),
        make_rec(3, RecommendationAction.MERGE),
    ]
    report = await executor2.execute_batch("owner", "repo", recs)

    assert len(report.succeeded) == 2
    assert len(report.failed) == 1
    assert report.failed[0].number == 2
    assert 1 in broken.merged
    assert 3 in broken.merged


def test_execution_report_summary_format():
    from collie.core.executor import ExecutionResult

    report = ExecutionReport(
        results=[
            ExecutionResult(1, ExecutionStatus.SUCCESS, RecommendationAction.MERGE, "Merged"),
            ExecutionResult(2, ExecutionStatus.FAILED, RecommendationAction.MERGE, "conflict"),
            ExecutionResult(3, ExecutionStatus.SKIPPED, RecommendationAction.HOLD, "Not executable"),
        ]
    )
    summary = report.summary()
    assert "1 succeeded" in summary
    assert "1 failed" in summary
    assert "1 skipped" in summary


def test_execution_report_empty():
    report = ExecutionReport()
    assert report.succeeded == []
    assert report.failed == []
    assert report.skipped == []
    summary = report.summary()
    assert "0 succeeded" in summary


@pytest.mark.asyncio
async def test_comment_action():
    rest = MockREST()
    executor = Executor(rest)
    rec = make_rec(80, RecommendationAction.COMMENT, suggested_comment="Please add tests.")
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.succeeded) == 1
    assert (80, "Please add tests.") in rest.comments


@pytest.mark.asyncio
async def test_link_to_pr_action():
    rest = MockREST()
    executor = Executor(rest)
    rec = make_rec(90, RecommendationAction.LINK_TO_PR, linked_pr=101)
    report = await executor.execute_batch("owner", "repo", [rec])

    assert len(report.succeeded) == 1
    assert (90, "Related PR: #101") in rest.comments
