"""Tests for BarkPipeline."""

import pytest

from collie.commands.bark import BarkPipeline, BarkReport
from collie.core.models import (
    GitHubItemMetadata,
    HardRule,
    ItemType,
    Mode,
    Philosophy,
    Recommendation,
    RecommendationAction,
)


class MockGQL:
    async def fetch_issues_and_prs(self, owner, repo, since=None):
        return {"issues": [], "pull_requests": []}

    async def fetch_pr_files(self, owner, repo, number):
        return []


class MockREST:
    async def get_repository(self, owner, repo):
        return {"default_branch": "main", "description": "Test repo"}

    async def get_repo_content(self, owner, repo, path):
        mapping = {
            ".github/workflows": "ci.yml",
            "docs": "guide.md",
            "tests": "test_api.py",
        }
        return mapping.get(path)

    async def get_branch_protection(self, owner, repo, branch="main"):
        return {}

    async def list_labels(self, owner, repo, limit=100):
        return ["bug", "security"]

    async def list_recent_merged_pulls(self, owner, repo, limit=5):
        return []

    async def get_rulesets(self, owner, repo):
        return [
            {
                "target": "branch",
                "enforcement": "active",
                "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                "rules": [{"type": "merge_queue"}],
            }
        ]


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


@pytest.mark.asyncio
async def test_bark_enriches_items_with_repo_profile_context():
    """Bark attaches repo profile context so downstream prompts can reuse richer repo metadata."""
    p = Philosophy(hard_rules=[], soft_text="test", mode=Mode.TRAINING)

    class CapturingGQL:
        async def fetch_issues_and_prs(self, owner, repo, since=None):
            return {
                "issues": [
                    {
                        "number": 10,
                        "title": "Issue",
                        "body": "Body",
                        "author": {"login": "user"},
                        "labels": {"nodes": []},
                        "updatedAt": "2026-04-01T00:00:00Z",
                        "comments": {"totalCount": 1},
                    }
                ],
                "pull_requests": [],
            }

        async def fetch_pr_files(self, owner, repo, number):
            return []

    pipeline = BarkPipeline(CapturingGQL(), MockREST(), MockPhilosophyStore(p), MockQueueStore())
    issue = {
        "number": 10,
        "title": "Issue",
        "body": "Body",
        "author": {"login": "user"},
        "labels": {"nodes": []},
        "updatedAt": "2026-04-01T00:00:00Z",
        "comments": {"totalCount": 1},
    }
    from collie.commands.sit import RepoAnalyzer

    profile = await pipeline._load_repo_profile("owner", "repo", RepoAnalyzer)
    enriched = pipeline._attach_profile_context(issue, profile, "owner", "repo")
    assert enriched["repositoryName"] == "owner/repo"
    assert enriched["repositoryDescription"] == "Test repo"
    assert enriched["testFramework"] == "tests"
    assert enriched["styleTools"] == "unknown"
    assert "github_metadata" in enriched


def test_attach_profile_context_includes_github_native_metadata():
    pipeline = BarkPipeline(MockGQL(), MockREST(), MockPhilosophyStore(Philosophy()), MockQueueStore())
    pr = {
        "number": 11,
        "title": "Draft PR",
        "body": "Fixes #5",
        "additions": 3,
        "deletions": 1,
        "changedFiles": 1,
        "author": {"login": "user"},
        "authorAssociation": "FIRST_TIME_CONTRIBUTOR",
        "labels": {"nodes": []},
        "isDraft": True,
        "reviewDecision": "REVIEW_REQUIRED",
        "mergeable": "MERGEABLE",
        "baseRefName": "main",
        "headRefName": "feature/pr",
        "autoMergeRequest": {"enabledAt": "2026-04-01T00:00:00Z"},
        "closingIssuesReferences": {"nodes": [{"number": 5, "title": "Issue"}]},
        "commits": {"nodes": [{"commit": {"oid": "abc123", "statusCheckRollup": {"state": "SUCCESS"}}}]},
        "repository": {"name": "repo", "owner": {"login": "owner"}},
    }
    enriched = pipeline._attach_profile_context(pr, None, "owner", "repo")
    metadata = GitHubItemMetadata.from_dict(enriched["github_metadata"])
    assert metadata.is_draft is True
    assert metadata.review_decision == "REVIEW_REQUIRED"
    assert metadata.mergeable == "MERGEABLE"
    assert metadata.linked_issue_numbers == [5]
    assert metadata.required_check_state == "SUCCESS"


@pytest.mark.asyncio
async def test_attach_profile_context_marks_merge_queue_required_from_profile():
    pipeline = BarkPipeline(MockGQL(), MockREST(), MockPhilosophyStore(Philosophy()), MockQueueStore())
    from collie.commands.sit import RepoAnalyzer

    profile = await pipeline._load_repo_profile("owner", "repo", RepoAnalyzer)
    pr = {
        "number": 12,
        "title": "Queue path",
        "body": "Body",
        "additions": 1,
        "deletions": 0,
        "changedFiles": 1,
        "author": {"login": "user"},
        "labels": {"nodes": []},
        "commits": {"nodes": [{"commit": {"oid": "abc", "statusCheckRollup": {"state": "SUCCESS"}}}]},
        "repository": {"name": "repo", "owner": {"login": "owner"}},
    }
    enriched = pipeline._attach_profile_context(pr, profile, "owner", "repo")
    metadata = GitHubItemMetadata.from_dict(enriched["github_metadata"])
    assert metadata.merge_queue_required is True


def test_bark_report_summary_includes_metadata_summary():
    report = BarkReport(total_items=1, metadata_summary="drafts=1; reviewDecision={'REVIEW_REQUIRED': 1}")
    summary = report.summary()
    assert "Metadata:" in summary
    assert "drafts=1" in summary
