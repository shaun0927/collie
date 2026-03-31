"""Execute approved recommendations (merge, close, comment, label)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from collie.core.models import Recommendation, RecommendationAction


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
            try:
                await self.rest.merge_pr(owner, repo, number)
                return ExecutionResult(number, ExecutionStatus.SUCCESS, action, "Merged")
            except Exception as e:
                error_msg = str(e)
                if "conflict" in error_msg.lower() or "405" in error_msg:
                    return ExecutionResult(number, ExecutionStatus.FAILED, action, "Merge conflict")
                if "403" in error_msg:
                    return ExecutionResult(number, ExecutionStatus.FAILED, action, "Branch protection blocked")
                raise

        elif action == RecommendationAction.CLOSE:
            await self.rest.close_issue(owner, repo, number)
            if rec.suggested_comment:
                await self.rest.add_comment(owner, repo, number, rec.suggested_comment)
            return ExecutionResult(number, ExecutionStatus.SUCCESS, action, "Closed")

        elif action == RecommendationAction.COMMENT:
            if rec.suggested_comment:
                await self.rest.add_comment(owner, repo, number, rec.suggested_comment)
            return ExecutionResult(number, ExecutionStatus.SUCCESS, action, "Commented")

        elif action == RecommendationAction.LABEL:
            if rec.suggested_labels:
                await self.rest.add_labels(owner, repo, number, rec.suggested_labels)
            return ExecutionResult(number, ExecutionStatus.SUCCESS, action, "Labeled")

        elif action == RecommendationAction.LINK_TO_PR:
            if rec.linked_pr:
                comment = f"Related PR: #{rec.linked_pr}"
                await self.rest.add_comment(owner, repo, number, comment)
            return ExecutionResult(number, ExecutionStatus.SUCCESS, action, "Linked")

        else:
            # HOLD, ESCALATE — should not be executed
            return ExecutionResult(number, ExecutionStatus.SKIPPED, action, "Not executable")
