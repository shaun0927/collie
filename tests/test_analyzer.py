"""Tests for collie.core.analyzer — T1/T2/T3 tiers + Issue analyzer."""

from __future__ import annotations

import json

import pytest

from collie.core.analyzer import AnalysisResult, IssueAnalyzer, T1Scanner, T2Summarizer, T3Reviewer, Tier
from collie.core.models import HardRule, ItemType, Philosophy, RecommendationAction

# ─── Fixtures ────────────────────────────────────────────────────────────────


def make_pr(
    number: int = 1,
    title: str = "Add feature X",
    body: str = "This PR adds feature X to fix issue #42.",
    additions: int = 50,
    deletions: int = 10,
    changed_files: int = 5,
    ci_state: str = "SUCCESS",
    reviews: list[dict] | None = None,
) -> dict:
    return {
        "number": number,
        "title": title,
        "body": body,
        "additions": additions,
        "deletions": deletions,
        "changedFiles": changed_files,
        "author": {"login": "contributor"},
        "labels": {"nodes": []},
        "commits": {
            "nodes": [
                {
                    "commit": {
                        "statusCheckRollup": {"state": ci_state},
                    }
                }
            ]
        },
        "reviews": {"nodes": reviews or []},
    }


def make_issue(
    number: int = 10,
    title: str = "Bug: something is broken",
    body: str = "Steps to reproduce: ...",
    updated_at: str = "2025-01-01T00:00:00Z",
    comments_count: int = 3,
    labels: list[str] | None = None,
) -> dict:
    return {
        "number": number,
        "title": title,
        "body": body,
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": updated_at,
        "author": {"login": "reporter"},
        "labels": {"nodes": [{"name": lbl} for lbl in (labels or [])]},
        "comments": {"totalCount": comments_count},
    }


def make_philosophy(hard_rules: list[HardRule] | None = None, soft_text: str = "") -> Philosophy:
    return Philosophy(hard_rules=hard_rules or [], soft_text=soft_text)


def make_t2_response(
    action: str = "hold", confidence: float = 0.5, summary: str = "Summary", reasoning: str = "Reason"
):
    return json.dumps(
        {
            "action": action,
            "confidence": confidence,
            "summary": summary,
            "reasoning": reasoning,
            "hard_rule_checks": {},
            "soft_signals": {},
            "questions_for_author": [],
        }
    )


def make_t3_response(has_issue: bool = False, details: str = "No issues found.", merge_blocker: bool | None = None):
    return json.dumps(
        {
            "has_issue": has_issue,
            "summary": details,
            "issue_category": "quality" if has_issue else "none",
            "merge_blocker": has_issue if merge_blocker is None else merge_blocker,
            "details": details,
            "suggested_fix": "",
        }
    )


def make_issue_response(action: str = "hold", reason: str = "Needs review", labels: list[str] | None = None):
    return json.dumps(
        {
            "classification": "BUG",
            "confidence": "HIGH",
            "quality": {
                "reproduction": "YES",
                "version_specified": "YES",
                "expected_vs_actual": "CLEAR",
                "minimal_example": "YES",
                "overall": "COMPLETE",
            },
            "duplicate_assessment": "NO_DUPLICATE_FOUND",
            "component": "core",
            "priority": "MEDIUM",
            "action": action,
            "reason": reason,
            "suggested_labels": labels or [],
            "response_template": "Thanks for the report.",
        }
    )


# ─── T1 Scanner tests ────────────────────────────────────────────────────────


class TestT1Scanner:
    def setup_method(self):
        self.scanner = T1Scanner()

    def test_t1_ci_failed_rejects(self):
        """CI failure + ci_failed hard rule → close."""
        pr = make_pr(ci_state="FAILURE")
        philosophy = make_philosophy(
            hard_rules=[HardRule(condition="ci_failed", action="reject", description="CI must pass")]
        )
        result = self.scanner.scan(pr, philosophy)
        assert result is not None
        assert result.recommendation.action == RecommendationAction.CLOSE
        assert result.tier == Tier.T1
        assert "ci_failed" in result.recommendation.reason

    def test_t1_docs_only_merges(self):
        """Docs-only PR + CI pass + at least one approved review → merge."""
        pr = make_pr(
            title="Fix typo in README",
            changed_files=1,
            ci_state="SUCCESS",
            reviews=[{"state": "APPROVED"}],
        )
        philosophy = make_philosophy()
        result = self.scanner.scan(pr, philosophy)
        assert result is not None
        assert result.recommendation.action == RecommendationAction.MERGE
        assert result.tier == Tier.T1
        assert result.recommendation.analysis_coverage == "100% (docs only)"

    def test_t1_no_decision(self):
        """Complex PR with no matching hard rules → returns None (escalate to T2)."""
        pr = make_pr(
            title="Refactor core module",
            body="This is a large refactor with detailed explanation of changes.",
            changed_files=20,
            ci_state="SUCCESS",
        )
        philosophy = make_philosophy()
        result = self.scanner.scan(pr, philosophy)
        assert result is None

    def test_t1_no_description_rule(self):
        """Empty body + no_description hard rule → hold."""
        pr = make_pr(body="")
        philosophy = make_philosophy(
            hard_rules=[HardRule(condition="no_description", action="hold", description="PRs need a description")]
        )
        result = self.scanner.scan(pr, philosophy)
        assert result is not None
        assert result.recommendation.action == RecommendationAction.HOLD
        assert result.tier == Tier.T1

    def test_t1_no_hard_rules(self):
        """Empty philosophy → no decision (None) for a normal PR."""
        pr = make_pr(ci_state="FAILURE", body="some PR")
        philosophy = make_philosophy()
        result = self.scanner.scan(pr, philosophy)
        assert result is None

    def test_t1_docs_only_no_review_does_not_merge(self):
        """Docs PR + CI pass but zero reviews → no T1 decision."""
        pr = make_pr(title="Update changelog", changed_files=1, ci_state="SUCCESS", reviews=[])
        philosophy = make_philosophy()
        result = self.scanner.scan(pr, philosophy)
        assert result is None

    def test_t1_ci_failed_no_matching_rule_no_decision(self):
        """CI failed but no ci_failed rule defined → no T1 decision."""
        pr = make_pr(ci_state="FAILURE")
        philosophy = make_philosophy(
            hard_rules=[HardRule(condition="no_description", action="hold", description="needs desc")]
        )
        result = self.scanner.scan(pr, philosophy)
        assert result is None


# ─── T2 Summarizer tests ─────────────────────────────────────────────────────


class MockLLM:
    """Synchronous-style async mock LLM client."""

    def __init__(self, response: str):
        self._response = response
        self.calls = []

    async def chat(self, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        return self._response


class TestT2Summarizer:
    def setup_method(self):
        self.philosophy = make_philosophy(soft_text="We value correctness and test coverage.")

    @pytest.mark.asyncio
    async def test_t2_merge_recommendation(self):
        """LLM returns merge with high confidence → merge action."""
        llm = MockLLM(make_t2_response(action="merge", confidence=0.95, reasoning="This PR looks good."))
        summarizer = T2Summarizer(llm_client=llm)
        pr = make_pr()
        result = await summarizer.summarize(pr, self.philosophy)
        assert isinstance(result, AnalysisResult)
        assert result.recommendation.action == RecommendationAction.MERGE
        assert result.tier == Tier.T2

    @pytest.mark.asyncio
    async def test_t2_prompt_rendered_with_concrete_values(self):
        """T2 system prompt is rendered with concrete values before dispatch."""
        llm = MockLLM(make_t2_response())
        summarizer = T2Summarizer(llm_client=llm)
        pr = make_pr(title="Add feature X", body="Body content")
        await summarizer.summarize(pr, self.philosophy)
        assert "{repo_philosophy}" not in llm.calls[0]["system"]
        assert "Add feature X" in llm.calls[0]["system"]
        assert "Return only valid JSON" in llm.calls[0]["user"]

    @pytest.mark.asyncio
    async def test_t2_low_confidence_holds(self):
        """Merge recommendation but confidence < 80% → hold."""
        llm = MockLLM(make_t2_response(action="merge", confidence=0.60, reasoning="Not entirely sure about this one."))
        summarizer = T2Summarizer(llm_client=llm)
        pr = make_pr()
        result = await summarizer.summarize(pr, self.philosophy)
        assert result.recommendation.action == RecommendationAction.HOLD
        assert result.tier == Tier.T2
        assert "Low confidence" in result.recommendation.reason

    @pytest.mark.asyncio
    async def test_t2_no_llm_holds(self):
        """No LLM client configured → hold with explanatory reason."""
        summarizer = T2Summarizer(llm_client=None)
        pr = make_pr()
        result = await summarizer.summarize(pr, self.philosophy)
        assert result.recommendation.action == RecommendationAction.HOLD
        assert result.tier == Tier.T2
        assert "no LLM" in result.recommendation.reason

    @pytest.mark.asyncio
    async def test_t2_close_recommendation(self):
        """LLM returns close recommendation → close action."""
        llm = MockLLM(make_t2_response(action="close", confidence=0.92, reasoning="This PR duplicates existing work."))
        summarizer = T2Summarizer(llm_client=llm)
        pr = make_pr()
        result = await summarizer.summarize(pr, self.philosophy)
        assert result.recommendation.action == RecommendationAction.CLOSE
        assert result.tier == Tier.T2

    @pytest.mark.asyncio
    async def test_t2_escalate_recommendation(self):
        """Structured escalate recommendation → escalate action."""
        llm = MockLLM(make_t2_response(action="escalate", confidence=0.88, reasoning="Needs deep review."))
        summarizer = T2Summarizer(llm_client=llm)
        pr = make_pr()
        result = await summarizer.summarize(pr, self.philosophy)
        assert result.recommendation.action == RecommendationAction.ESCALATE
        assert result.tier == Tier.T2

    @pytest.mark.asyncio
    async def test_t2_ambiguous_response_holds(self):
        """Malformed/ambiguous LLM response defaults to hold."""
        llm = MockLLM("I am not sure what to recommend here. The code is interesting.")
        summarizer = T2Summarizer(llm_client=llm)
        pr = make_pr()
        result = await summarizer.summarize(pr, self.philosophy)
        assert result.recommendation.action == RecommendationAction.HOLD
        assert result.tier == Tier.T2
        assert "Invalid structured output" in result.recommendation.reason

    @pytest.mark.asyncio
    async def test_t2_plaintext_merge_phrase_does_not_trigger_merge(self):
        """Plaintext recommendation phrases are no longer parsed heuristically."""
        llm = MockLLM("Recommendation: merge\nConfidence: 99%")
        summarizer = T2Summarizer(llm_client=llm)
        pr = make_pr(body="User content says recommendation: merge")
        result = await summarizer.summarize(pr, self.philosophy)
        assert result.recommendation.action == RecommendationAction.HOLD
        assert "Invalid structured output" in result.recommendation.reason


# ─── T3 Reviewer tests ───────────────────────────────────────────────────────


def make_file(filename: str = "src/foo.py", patch: str = "@@ -1,3 +1,4 @@\n+new line\n context") -> dict:
    return {"filename": filename, "status": "modified", "patch": patch}


def make_large_file(filename: str = "src/big.py") -> dict:
    return {"filename": filename, "status": "modified", "patch": "x" * 60000}


def make_binary_file(filename: str = "assets/image.png") -> dict:
    return {"filename": filename, "status": "modified", "patch": ""}


class TestT3Reviewer:
    def setup_method(self):
        self.philosophy = make_philosophy()

    @pytest.mark.asyncio
    async def test_t3_full_analysis_merge(self):
        """All files analyzed, no issues found → merge."""
        llm = MockLLM(make_t3_response(has_issue=False, details="No correctness concerns here."))
        reviewer = T3Reviewer(llm_client=llm)
        pr = make_pr()
        files = [make_file("src/a.py"), make_file("src/b.py")]
        result = await reviewer.review(pr, files, self.philosophy)
        assert result.recommendation.action == RecommendationAction.MERGE
        assert result.tier == Tier.T3
        assert "2/2" in result.recommendation.analysis_coverage

    @pytest.mark.asyncio
    async def test_t3_prompt_rendered_with_concrete_values(self):
        """T3 system prompt is rendered before dispatch and user prompt carries diff text."""
        llm = MockLLM(make_t3_response())
        reviewer = T3Reviewer(llm_client=llm)
        pr = make_pr(title="Refactor auth", body="PR body")
        files = [make_file("src/auth.py", "@@ -1 +1 @@\n+auth change")]
        await reviewer.review(pr, files, self.philosophy)
        assert "{repo_philosophy}" not in llm.calls[0]["system"]
        assert "Refactor auth" in llm.calls[0]["system"]
        assert "src/auth.py" in llm.calls[0]["user"]
        assert "auth change" in llm.calls[0]["user"]

    @pytest.mark.asyncio
    async def test_t3_partial_analysis_holds(self):
        """Unanalyzable files (too large / binary) → hold. Zero false merge guarantee."""
        llm = MockLLM(make_t3_response(has_issue=False, details="Looks fine."))
        reviewer = T3Reviewer(llm_client=llm)
        pr = make_pr()
        files = [make_file("src/a.py"), make_large_file("src/huge.py")]
        result = await reviewer.review(pr, files, self.philosophy)
        assert result.recommendation.action == RecommendationAction.HOLD
        assert result.tier == Tier.T3
        assert "src/huge.py" in result.recommendation.reason

    @pytest.mark.asyncio
    async def test_t3_binary_file_holds(self):
        """Binary file with empty patch → hold (incomplete analysis)."""
        llm = MockLLM(make_t3_response(has_issue=False, details="Looks fine."))
        reviewer = T3Reviewer(llm_client=llm)
        pr = make_pr()
        files = [make_file("src/a.py"), make_binary_file("assets/logo.png")]
        result = await reviewer.review(pr, files, self.philosophy)
        assert result.recommendation.action == RecommendationAction.HOLD
        assert result.tier == Tier.T3

    @pytest.mark.asyncio
    async def test_t3_issues_found_holds(self):
        """LLM finds issues in analyzed files → hold."""
        llm = MockLLM(make_t3_response(has_issue=True, details="Potential null pointer dereference on line 42."))
        reviewer = T3Reviewer(llm_client=llm)
        pr = make_pr()
        files = [make_file("src/a.py")]
        result = await reviewer.review(pr, files, self.philosophy)
        assert result.recommendation.action == RecommendationAction.HOLD
        assert result.tier == Tier.T3
        assert "src/a.py" in result.recommendation.reason

    @pytest.mark.asyncio
    async def test_t3_no_llm_holds(self):
        """No LLM client → hold immediately."""
        reviewer = T3Reviewer(llm_client=None)
        pr = make_pr()
        files = [make_file()]
        result = await reviewer.review(pr, files, self.philosophy)
        assert result.recommendation.action == RecommendationAction.HOLD
        assert result.tier == Tier.T3
        assert "no LLM" in result.recommendation.reason

    @pytest.mark.asyncio
    async def test_t3_empty_file_list_merges(self):
        """Zero files to analyze → 0/0, no issues, merge (nothing to reject)."""
        llm = MockLLM(make_t3_response(has_issue=False, details="All good."))
        reviewer = T3Reviewer(llm_client=llm)
        pr = make_pr()
        result = await reviewer.review(pr, [], self.philosophy)
        assert result.recommendation.action == RecommendationAction.MERGE
        assert result.tier == Tier.T3


# ─── Issue Analyzer tests ────────────────────────────────────────────────────


class TestIssueAnalyzer:
    def setup_method(self):
        self.philosophy = make_philosophy()

    @pytest.mark.asyncio
    async def test_issue_stale_close(self):
        """Issue with 180+ days of inactivity and ≤1 comment → close as stale."""
        issue = make_issue(updated_at="2024-01-01T00:00:00Z", comments_count=0)
        analyzer = IssueAnalyzer(llm_client=None)
        result = await analyzer.analyze(issue, self.philosophy)
        assert result.recommendation.action == RecommendationAction.CLOSE
        assert result.tier == Tier.T1
        assert "Stale" in result.recommendation.reason
        assert result.recommendation.suggested_comment != ""

    @pytest.mark.asyncio
    async def test_issue_stale_with_comments_not_closed(self):
        """Issue with 180+ days but 5 comments → not auto-closed as stale."""
        issue = make_issue(updated_at="2024-01-01T00:00:00Z", comments_count=5)
        analyzer = IssueAnalyzer(llm_client=None)
        result = await analyzer.analyze(issue, self.philosophy)
        # Should not be stale-closed; with no LLM it should hold
        assert result.recommendation.action == RecommendationAction.HOLD

    @pytest.mark.asyncio
    async def test_issue_linked_pr(self):
        """Issue referenced in an open PR body → link_to_pr action."""
        issue = make_issue(number=55)
        open_prs = [
            {
                "number": 100,
                "title": "Fix issue",
                "body": "This PR fixes #55 as requested.",
            }
        ]
        analyzer = IssueAnalyzer(llm_client=None)
        result = await analyzer.analyze(issue, self.philosophy, open_prs=open_prs)
        assert result.recommendation.action == RecommendationAction.LINK_TO_PR
        assert result.recommendation.linked_pr == 100
        assert result.tier == Tier.T1

    @pytest.mark.asyncio
    async def test_issue_closes_keyword_links(self):
        """'closes #N' in PR body → link_to_pr."""
        issue = make_issue(number=77)
        open_prs = [{"number": 200, "title": "Fix", "body": "closes #77"}]
        analyzer = IssueAnalyzer(llm_client=None)
        result = await analyzer.analyze(issue, self.philosophy, open_prs=open_prs)
        assert result.recommendation.action == RecommendationAction.LINK_TO_PR
        assert result.recommendation.linked_pr == 200

    @pytest.mark.asyncio
    async def test_issue_no_llm_holds(self):
        """Recent issue, no LLM → hold for human review."""
        issue = make_issue(updated_at="2026-01-01T00:00:00Z", comments_count=3)
        analyzer = IssueAnalyzer(llm_client=None)
        result = await analyzer.analyze(issue, self.philosophy)
        assert result.recommendation.action == RecommendationAction.HOLD
        assert result.tier == Tier.T1
        assert "no LLM" in result.recommendation.reason

    @pytest.mark.asyncio
    async def test_issue_llm_close_recommendation(self):
        """LLM recommends closing the issue → close action."""
        llm = MockLLM(make_issue_response(action="close", reason="Duplicate issue."))
        analyzer = IssueAnalyzer(llm_client=llm)
        issue = make_issue(updated_at="2026-01-01T00:00:00Z", comments_count=1)
        result = await analyzer.analyze(issue, self.philosophy)
        assert result.recommendation.action == RecommendationAction.CLOSE
        assert result.tier == Tier.T2

    @pytest.mark.asyncio
    async def test_issue_llm_label_recommendation(self):
        """LLM mentions labeling → label action."""
        llm = MockLLM(make_issue_response(action="label", reason="Bug confirmed.", labels=["bug", "confirmed"]))
        analyzer = IssueAnalyzer(llm_client=llm)
        issue = make_issue(updated_at="2026-01-01T00:00:00Z", comments_count=2)
        result = await analyzer.analyze(issue, self.philosophy)
        assert result.recommendation.action == RecommendationAction.LABEL
        assert result.tier == Tier.T2
        assert result.recommendation.suggested_labels == ["bug", "confirmed"]

    @pytest.mark.asyncio
    async def test_issue_prompt_rendered_with_concrete_values(self):
        """Issue analyzer prompt is rendered with concrete values before dispatch."""
        llm = MockLLM(make_issue_response())
        analyzer = IssueAnalyzer(llm_client=llm)
        issue = make_issue(title="Bug report", body="Steps to reproduce")
        await analyzer.analyze(issue, self.philosophy)
        assert "{repo_name}" not in llm.calls[0]["system"]
        assert "Bug report" in llm.calls[0]["system"]
        assert "Return only valid JSON" in llm.calls[0]["user"]

    @pytest.mark.asyncio
    async def test_issue_plaintext_label_phrase_does_not_trigger_label(self):
        """Plaintext label instructions from the model fail closed to hold."""
        llm = MockLLM("This issue should be labeled bug/confirmed. Add label to the issue.")
        analyzer = IssueAnalyzer(llm_client=llm)
        issue = make_issue(updated_at="2026-01-01T00:00:00Z", comments_count=2)
        result = await analyzer.analyze(issue, self.philosophy)
        assert result.recommendation.action == RecommendationAction.HOLD
        assert "Invalid structured output" in result.recommendation.reason

    @pytest.mark.asyncio
    async def test_issue_item_type_is_issue(self):
        """Issue results always have ItemType.ISSUE."""
        issue = make_issue(updated_at="2026-03-01T00:00:00Z", comments_count=2)
        analyzer = IssueAnalyzer(llm_client=None)
        result = await analyzer.analyze(issue, self.philosophy)
        assert result.recommendation.item_type == ItemType.ISSUE
