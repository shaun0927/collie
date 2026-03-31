"""collie approve / reject — multi-channel approval + execution."""

from __future__ import annotations

from collie.core.dependency_resolver import DependencyResolver
from collie.core.executor import ExecutionReport, Executor
from collie.core.models import Mode, Recommendation, RecommendationAction


class ApproveCommand:
    """Handle approve and reject operations."""

    def __init__(self, rest_client, queue_store, philosophy_store):
        self.rest = rest_client
        self.queue = queue_store
        self.philosophy = philosophy_store
        self.executor = Executor(rest_client)
        self.resolver = DependencyResolver()

    async def approve(
        self, owner: str, repo: str, numbers: list[int] | None = None, approve_all: bool = False
    ) -> ExecutionReport:
        """Approve and execute items."""
        # Check mode
        phil = await self.philosophy.load(owner, repo)
        if phil and phil.mode == Mode.TRAINING:
            raise PermissionError("Cannot execute in training mode. Run 'collie unleash' to enable execution.")

        # Get recommendations to execute
        if approve_all:
            approved_numbers = await self.queue.read_approvals(owner, repo)
            if not approved_numbers:
                return ExecutionReport()
            numbers = list(approved_numbers)

        if not numbers:
            return ExecutionReport()

        # Build recommendation objects for execution
        # (In a full implementation, we'd load from queue. Simplified here.)
        recs = [
            Recommendation(
                number=n,
                item_type="pr",  # simplified
                action=RecommendationAction.MERGE,
                reason="Approved by user",
            )
            for n in numbers
        ]

        # Resolve dependencies and execute
        report = await self.executor.execute_batch(owner, repo, recs)

        # Update queue with results
        succeeded = [r.number for r in report.succeeded]

        if succeeded:
            await self.queue.mark_executed(owner, repo, succeeded)

        return report

    async def reject(self, owner: str, repo: str, number: int, reason: str = "") -> str:
        """Reject an item and trigger micro-update suggestion."""
        # Generate micro-update suggestion based on reason
        suggestion = self._generate_rule_suggestion(number, reason)
        return suggestion

    def _generate_rule_suggestion(self, number: int, reason: str) -> str:
        """Generate a rule suggestion from rejection reason."""
        if not reason:
            return ""

        # Simple heuristic to suggest a rule
        reason_lower = reason.lower()
        if "vendor" in reason_lower or "lock-in" in reason_lower:
            return f"Add hard rule: vendor_dependency → reject (from rejection of #{number}: {reason})"
        if "security" in reason_lower:
            return f"Add escalation: security/* → escalate (from rejection of #{number}: {reason})"
        if "test" in reason_lower:
            return f"Add hard rule: no_tests → hold (from rejection of #{number}: {reason})"
        if "breaking" in reason_lower:
            return f"Add hard rule: breaking_change → hold (from rejection of #{number}: {reason})"

        return f"Consider adding rule based on: {reason} (from rejection of #{number})"
