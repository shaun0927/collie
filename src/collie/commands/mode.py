"""collie unleash / leash / status — Mode management."""

from __future__ import annotations

from dataclasses import dataclass

from collie.core.models import Mode, Philosophy


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

    def summary(self) -> str:
        mode_emoji = "🟢" if self.mode == Mode.ACTIVE else "🟡"
        return (
            f"{mode_emoji} {self.owner}/{self.repo} — Mode: {self.mode.value}\n"
            f"  Hard rules: {self.hard_rules_count}\n"
            f"  Escalation rules: {self.escalation_rules_count}\n"
            f"  Trusted contributors: {self.trusted_contributors_count}\n"
            f"  Confidence threshold: {self.confidence_threshold}\n"
            f"  Analysis depth: {self.analysis_depth}\n"
            f"  Cost cap: ${self.cost_cap:.2f}"
        )


class ModeCommand:
    """Handle mode transitions and status queries."""

    def __init__(self, philosophy_store):
        self.philosophy = philosophy_store

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
        )
