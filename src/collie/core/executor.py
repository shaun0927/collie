"""Execute approved recommendations (merge, close, comment, label)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from collie.core.models import GitHubItemMetadata, Recommendation, RecommendationAction


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionResult:
    number: int
    status: ExecutionStatus
    action: RecommendationAction
    message: str = ""
    execution_path: str = ""


@dataclass
class ExecutionReport:
    results: list[ExecutionResult] = field(default_factory=list)

    @property
    def succeeded(self) -> list[ExecutionResult]:
        return [r for r in self.results if r.status == ExecutionStatus.SUCCESS]

    @property
    def failed(self) -> list[ExecutionResult]:
        return [r for r in self.results if r.status == ExecutionStatus.FAILED]

    @property
    def skipped(self) -> list[ExecutionResult]:
        return [r for r in self.results if r.status == ExecutionStatus.SKIPPED]

    def summary(self) -> str:
        return f"Execution: {len(self.succeeded)} succeeded, {len(self.failed)} failed, {len(self.skipped)} skipped"


class Executor:
    """Execute approved items via GitHub API. Partial execution on failure."""

    def __init__(self, rest_client):
        self.rest = rest_client

    async def execute_batch(self, owner: str, repo: str, recommendations: list[Recommendation]) -> ExecutionReport:
        """Execute a batch of approved recommendations. Continues on failure."""
        report = ExecutionReport()

        for rec in recommendations:
            try:
                result = await self._execute_one(owner, repo, rec)
                report.results.append(result)
            except Exception as e:
                report.results.append(
                    ExecutionResult(
                        number=rec.number,
                        status=ExecutionStatus.FAILED,
                        action=rec.action,
                        message=str(e),
                    )
                )

        return report

    async def _execute_one(self, owner: str, repo: str, rec: Recommendation) -> ExecutionResult:
        """Execute a single recommendation."""
        action = rec.action
        number = rec.number

        if action == RecommendationAction.MERGE:
            governance_result = await self._execute_merge_with_governance(owner, repo, rec)
            if governance_result is not None:
                return governance_result
            try:
                await self.rest.merge_pr(owner, repo, number)
                return ExecutionResult(number, ExecutionStatus.SUCCESS, action, "Merged", execution_path="direct_merge")
            except Exception as e:
                error_msg = str(e)
                if "conflict" in error_msg.lower() or "405" in error_msg:
                    return ExecutionResult(
                        number,
                        ExecutionStatus.FAILED,
                        action,
                        "Merge conflict",
                        execution_path="blocked",
                    )
                if "403" in error_msg:
                    return ExecutionResult(
                        number, ExecutionStatus.FAILED, action, "Branch protection blocked", execution_path="blocked"
                    )
                raise

        elif action == RecommendationAction.CLOSE:
            await self.rest.close_issue(owner, repo, number)
            if rec.suggested_comment:
                await self.rest.add_comment(owner, repo, number, rec.suggested_comment)
            return ExecutionResult(number, ExecutionStatus.SUCCESS, action, "Closed", execution_path="close")

        elif action == RecommendationAction.COMMENT:
            if rec.suggested_comment:
                await self.rest.add_comment(owner, repo, number, rec.suggested_comment)
            return ExecutionResult(number, ExecutionStatus.SUCCESS, action, "Commented", execution_path="comment")

        elif action == RecommendationAction.LABEL:
            if rec.suggested_labels:
                await self.rest.add_labels(owner, repo, number, rec.suggested_labels)
            return ExecutionResult(number, ExecutionStatus.SUCCESS, action, "Labeled", execution_path="label")

        elif action == RecommendationAction.LINK_TO_PR:
            if rec.linked_pr:
                comment = f"Related PR: #{rec.linked_pr}"
                await self.rest.add_comment(owner, repo, number, comment)
            return ExecutionResult(number, ExecutionStatus.SUCCESS, action, "Linked", execution_path="link")

        else:
            # HOLD, ESCALATE — should not be executed
            return ExecutionResult(number, ExecutionStatus.SKIPPED, action, "Not executable", execution_path="skip")

    async def _execute_merge_with_governance(
        self, owner: str, repo: str, rec: Recommendation
    ) -> ExecutionResult | None:
        """Honor GitHub-native governance metadata before attempting a direct merge."""
        metadata = GitHubItemMetadata.from_dict(rec.github_metadata) if rec.github_metadata else GitHubItemMetadata()

        if metadata.is_draft:
            rec.execution_path = "blocked"
            return ExecutionResult(
                rec.number,
                ExecutionStatus.FAILED,
                rec.action,
                "Blocked: draft PR",
                execution_path="blocked",
            )

        if metadata.review_decision == "CHANGES_REQUESTED":
            rec.execution_path = "blocked"
            return ExecutionResult(
                rec.number, ExecutionStatus.FAILED, rec.action, "Blocked: changes requested", execution_path="blocked"
            )

        if metadata.mergeable == "CONFLICTING":
            rec.execution_path = "blocked"
            return ExecutionResult(
                rec.number,
                ExecutionStatus.FAILED,
                rec.action,
                "Blocked: merge conflict",
                execution_path="blocked",
            )

        if metadata.merge_queue_required:
            if metadata.pull_request_id and hasattr(self.rest, "enqueue_pull_request"):
                try:
                    await self.rest.enqueue_pull_request(metadata.pull_request_id)
                except (AttributeError, NotImplementedError):
                    rec.execution_path = "blocked"
                    return ExecutionResult(
                        rec.number,
                        ExecutionStatus.FAILED,
                        rec.action,
                        "Blocked: merge queue required",
                        execution_path="blocked",
                    )
                rec.execution_path = "merge_queue"
                return ExecutionResult(
                    rec.number,
                    ExecutionStatus.SUCCESS,
                    rec.action,
                    "Enqueued in merge queue",
                    execution_path="merge_queue",
                )
            rec.execution_path = "blocked"
            return ExecutionResult(
                rec.number,
                ExecutionStatus.FAILED,
                rec.action,
                "Blocked: merge queue required",
                execution_path="blocked",
            )

        if metadata.required_check_state in {"PENDING", "EXPECTED"}:
            if metadata.pull_request_id and hasattr(self.rest, "enable_auto_merge"):
                try:
                    await self.rest.enable_auto_merge(metadata.pull_request_id)
                except (AttributeError, NotImplementedError):
                    rec.execution_path = "blocked"
                    return ExecutionResult(
                        rec.number,
                        ExecutionStatus.FAILED,
                        rec.action,
                        "Blocked: required checks pending",
                        execution_path="blocked",
                    )
                rec.execution_path = "auto_merge"
                return ExecutionResult(
                    rec.number, ExecutionStatus.SUCCESS, rec.action, "Auto-merge enabled", execution_path="auto_merge"
                )
            rec.execution_path = "blocked"
            return ExecutionResult(
                rec.number,
                ExecutionStatus.FAILED,
                rec.action,
                "Blocked: required checks pending",
                execution_path="blocked",
            )

        if metadata.required_check_state in {"FAILURE", "ERROR"}:
            rec.execution_path = "blocked"
            return ExecutionResult(
                rec.number,
                ExecutionStatus.FAILED,
                rec.action,
                "Blocked: required checks failing",
                execution_path="blocked",
            )

        rec.execution_path = "direct_merge"
        return None
