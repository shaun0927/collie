"""Tests for BarkPipeline."""

import pytest

from collie.commands.bark import BarkPipeline, BarkReport
from collie.core.models import HardRule, ItemType, Mode, Philosophy, Recommendation, RecommendationAction


class MockGQL:
    async def fetch_issues_and_prs(self, owner, repo, since=None):
        return {"issues": [], "pull_requests": []}

    async def fetch_pr_files(self, owner, repo, number):
        return []


class MockREST:
    pass


class MockPhilosophyStore:
    def __init__(self, philosophy=None):
        self._p = philosophy

    async def load(self, owner, repo):
        return self._p

    async def save(self, owner, repo, p):
        self._p = p


class MockQueueStore:
    def __init__(self):
        self.items = []

    async def upsert_recommendations(self, owner, repo, items):
        self.items = items

    async def read_approvals(self, owner, repo):
        return []

    async def invalidate_all(self, owner, repo):
        pass


@pytest.mark.asyncio
async def test_bark_no_philosophy_raises():
    pipeline = BarkPipeline(MockGQL(), MockREST(), MockPhilosophyStore(None), MockQueueStore())
    with pytest.raises(ValueError, match="No philosophy found"):
        await pipeline.run("owner", "repo")


@pytest.mark.asyncio
async def test_bark_empty_repo():
    p = Philosophy(hard_rules=[HardRule("ci_failed", "reject")], soft_text="test", mode=Mode.TRAINING)
    pipeline = BarkPipeline(MockGQL(), MockREST(), MockPhilosophyStore(p), MockQueueStore())
    report = await pipeline.run("owner", "repo")
    assert report.total_items == 0
    assert report.prs_analyzed == 0
    assert report.issues_analyzed == 0
    assert len(report.recommendations) == 0


def test_bark_report_summary_format():
    report = BarkReport(
        total_items=10,
        prs_analyzed=7,
        issues_analyzed=3,
        recommendations=[
            Recommendation(number=1, item_type=ItemType.PR, action=RecommendationAction.MERGE, reason="ok", title="A"),
            Recommendation(number=2, item_type=ItemType.PR, action=RecommendationAction.HOLD, reason="wait", title="B"),
        ],
        cost_summary="LLM Usage: 2 calls, 3,000 tokens, $0.01 / $50.00 budget",
        full_scan=True,
        approved_executed=[],
    )
    s = report.summary()
    assert "full scan" in s
    assert "10" in s
    assert "merge" in s


def test_bark_report_summary_incremental():
    report = BarkReport(total_items=5, full_scan=False)
    s = report.summary()
    assert "incremental" in s


@pytest.mark.asyncio
async def test_bark_with_pr_items():
    """Test bark pipeline with actual PR items going through T1."""
    p = Philosophy(
        hard_rules=[HardRule("ci_failed", "reject", "CI must pass")],
        soft_text="test",
        mode=Mode.TRAINING,
    )

    class GQLWithPRs:
        async def fetch_issues_and_prs(self, owner, repo, since=None):
            return {
                "issues": [],
                "pull_requests": [
                    {
                        "number": 42,
                        "title": "Fix readme typo",
                        "additions": 1,
                        "deletions": 1,
                        "changedFiles": 1,
                        "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "FAILURE"}}}]},
                        "reviews": {"nodes": []},
                        "labels": {"nodes": []},
                        "author": {"login": "user"},
                    }
                ],
            }

        async def fetch_pr_files(self, owner, repo, number):
            return []

    queue = MockQueueStore()
    pipeline = BarkPipeline(GQLWithPRs(), MockREST(), MockPhilosophyStore(p), queue)
    report = await pipeline.run("owner", "repo")

    assert report.prs_analyzed == 1
    assert len(report.recommendations) == 1
    assert report.recommendations[0].action == RecommendationAction.CLOSE  # CI failed → reject
