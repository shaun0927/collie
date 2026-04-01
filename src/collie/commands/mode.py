"""collie unleash / leash / status — Mode management."""

from __future__ import annotations

import re
from dataclasses import dataclass

from collie.core.models import Mode, Philosophy, RecommendationStatus


@dataclass
class StatusReport:
    """Current status of a Collie-managed repository."""

    owner: str
    repo: str
    mode: Mode
    hard_rules_count: int
    escalation_rules_count: int
    trusted_contributors_count: int
    confidence_threshold: float
    analysis_depth: str
    cost_cap: float
    has_philosophy: bool = True
    last_bark_time: str | None = None
    pending_count: int = 0

    def summary(self) -> str:
        mode_emoji = "🟢" if self.mode == Mode.ACTIVE else "🟡"
        bark_line = f"  Last bark: {self.last_bark_time}" if self.last_bark_time else "  Last bark: never"
        return (
            f"{mode_emoji} {self.owner}/{self.repo} — Mode: {self.mode.value}\n"
            f"{bark_line}\n"
            f"  Pending recommendations: {self.pending_count}\n"
            f"  Hard rules: {self.hard_rules_count}\n"
            f"  Escalation rules: {self.escalation_rules_count}\n"
            f"  Trusted contributors: {self.trusted_contributors_count}\n"
            f"  Confidence threshold: {self.confidence_threshold}\n"
            f"  Analysis depth: {self.analysis_depth}\n"
            f"  Cost cap: ${self.cost_cap:.2f}"
        )


class ModeCommand:
    """Handle mode transitions and status queries."""

    def __init__(self, philosophy_store, queue_store=None):
        self.philosophy = philosophy_store
        self.queue = queue_store

    async def unleash(self, owner: str, repo: str) -> Philosophy:
        """Switch from training to active mode."""
        phil = await self.philosophy.load(owner, repo)
        if phil is None:
            raise ValueError("No philosophy found. Run 'collie sit' first.")

        if phil.mode == Mode.ACTIVE:
            raise ValueError("Already in active mode.")

        phil = await self.philosophy.set_mode(owner, repo, Mode.ACTIVE)
        return phil

    async def leash(self, owner: str, repo: str) -> Philosophy:
        """Switch from active to training mode."""
        phil = await self.philosophy.load(owner, repo)
        if phil is None:
            raise ValueError("No philosophy found. Run 'collie sit' first.")

        if phil.mode == Mode.TRAINING:
            raise ValueError("Already in training mode.")

        phil = await self.philosophy.set_mode(owner, repo, Mode.TRAINING)
        return phil

    async def status(self, owner: str, repo: str) -> StatusReport:
        """Get current status of a Collie-managed repository."""
        phil = await self.philosophy.load(owner, repo)
        last_bark_time, pending_count = await self._get_queue_stats(owner, repo)

        if phil is None:
            return StatusReport(
                owner=owner,
                repo=repo,
                mode=Mode.TRAINING,
                hard_rules_count=0,
                escalation_rules_count=0,
                trusted_contributors_count=0,
                confidence_threshold=0.9,
                analysis_depth="t2",
                cost_cap=50.0,
                has_philosophy=False,
                last_bark_time=last_bark_time,
                pending_count=pending_count,
            )

        return StatusReport(
            owner=owner,
            repo=repo,
            mode=phil.mode,
            hard_rules_count=len(phil.hard_rules),
            escalation_rules_count=len(phil.escalation_rules),
            trusted_contributors_count=len(phil.trusted_contributors),
            confidence_threshold=phil.tuning.confidence_threshold,
            analysis_depth=phil.tuning.analysis_depth,
            cost_cap=phil.tuning.cost_cap_per_bark,
            last_bark_time=last_bark_time,
            pending_count=pending_count,
        )

    async def _get_queue_stats(self, owner: str, repo: str) -> tuple[str | None, int]:
        """Fetch last bark time and pending count from the queue Discussion."""
        if self.queue is None:
            return None, 0

        from collie.core.stores.queue_store import _parse_queue_markdown

        discussion = await self.queue._find_discussion(owner, repo)
        if discussion is None:
            return None, 0

        body = discussion.get("body", "")

        # Parse last updated timestamp from "> Last updated: ... | Mode: ..."
        last_bark_time = None
        meta_match = re.search(r"Last updated:\s*([^|]+)", body)
        if meta_match:
            last_bark_time = meta_match.group(1).strip()

        # Count pending items
        items = _parse_queue_markdown(body)
        pending_statuses = (RecommendationStatus.PENDING, RecommendationStatus.APPROVED)
        pending_count = sum(1 for i in items if i.status in pending_statuses)

        return last_bark_time, pending_count
