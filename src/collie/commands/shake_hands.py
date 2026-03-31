"""collie shake-hands — Philosophy revision + micro-update on rejection."""

from __future__ import annotations

from collie.core.models import EscalationRule, HardRule, Philosophy


class ShakeHandsCommand:
    """Handle philosophy modifications and micro-updates."""

    def __init__(self, philosophy_store, queue_store, llm_client=None):
        self.philosophy = philosophy_store
        self.queue = queue_store
        self.llm = llm_client

    async def micro_update(self, owner: str, repo: str, rejection_reason: str, number: int) -> dict:
        """Generate and optionally apply a micro-update from a rejection.

        Returns dict with 'suggestion' (str) and 'applied' (bool).
        """
        # Load current philosophy
        phil = await self.philosophy.load(owner, repo)
        if phil is None:
            raise ValueError("No philosophy found. Run 'collie sit' first.")

        # Generate rule suggestion
        suggestion = self._suggest_rule(rejection_reason, number)

        return {
            "suggestion": suggestion["description"],
            "rule": suggestion,
            "applied": False,
        }

    async def apply_micro_update(self, owner: str, repo: str, rule_type: str, rule: dict) -> Philosophy:
        """Apply a micro-update to the philosophy and invalidate pending queue."""
        phil = await self.philosophy.load(owner, repo)
        if phil is None:
            raise ValueError("No philosophy found. Run 'collie sit' first.")

        if rule_type == "hard_rule":
            phil.hard_rules.append(
                HardRule(
                    condition=rule.get("condition", "custom"),
                    action=rule.get("action", "hold"),
                    description=rule.get("description", ""),
                )
            )
        elif rule_type == "escalation":
            phil.escalation_rules.append(
                EscalationRule(
                    pattern=rule.get("pattern", "*"),
                    action=rule.get("action", "escalate"),
                    description=rule.get("description", ""),
                )
            )

        # Save updated philosophy
        await self.philosophy.save(owner, repo, phil)

        # Invalidate all pending recommendations (philosophy changed)
        await self.queue.invalidate_all(owner, repo)

        return phil

    async def full_revision(self, owner: str, repo: str) -> Philosophy:
        """Load current philosophy for full revision (shake-hands session).

        Returns current philosophy for display. The CLI/MCP layer handles
        the interactive revision and calls save directly.
        """
        phil = await self.philosophy.load(owner, repo)
        if phil is None:
            raise ValueError("No philosophy found. Run 'collie sit' first.")
        return phil

    def _suggest_rule(self, reason: str, number: int) -> dict:
        """Generate a rule suggestion from rejection reason."""
        reason_lower = reason.lower()

        if any(w in reason_lower for w in ["vendor", "lock-in", "dependency"]):
            return {
                "type": "hard_rule",
                "condition": "vendor_dependency",
                "action": "reject",
                "description": f"Vendor lock-in dependency changes (from #{number}: {reason})",
            }
        if any(w in reason_lower for w in ["security", "vuln", "cve"]):
            return {
                "type": "escalation",
                "pattern": "security/*",
                "action": "escalate",
                "description": f"Security-related changes need manual review (from #{number}: {reason})",
            }
        if any(w in reason_lower for w in ["test", "coverage", "untested"]):
            return {
                "type": "hard_rule",
                "condition": "no_tests",
                "action": "hold",
                "description": f"PRs should include tests (from #{number}: {reason})",
            }
        if any(w in reason_lower for w in ["breaking", "backward", "compat"]):
            return {
                "type": "hard_rule",
                "condition": "breaking_change",
                "action": "hold",
                "description": f"Breaking changes need careful review (from #{number}: {reason})",
            }

        return {
            "type": "hard_rule",
            "condition": "custom",
            "action": "hold",
            "description": f"Custom rule from rejection of #{number}: {reason}",
        }
