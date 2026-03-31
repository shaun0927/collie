"""Recommendation queue storage backed by GitHub Discussions (Living Document)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from collie.core.models import Recommendation, RecommendationStatus


class QueueStore:
    """Manages the recommendation queue as a single living Discussion document."""

    DISCUSSION_TITLE = "🐕 Collie Queue"
    CATEGORY_NAME = "Collie"

    def __init__(self, graphql_client, rest_client):
        self.gql = graphql_client
        self.rest = rest_client

    async def upsert_recommendations(self, owner: str, repo: str, items: list[Recommendation]) -> str:
        """Add or update recommendations in the queue Discussion."""
        existing_items = await self._load_items(owner, repo)

        # Merge: update existing by number, add new ones
        existing_by_number = {item.number: item for item in existing_items}
        for item in items:
            existing_by_number[item.number] = item
        merged = list(existing_by_number.values())

        body = self._render_queue_markdown(merged)
        discussion = await self._find_discussion(owner, repo)

        if discussion:
            await self.gql.update_discussion_body(discussion["id"], body)
            return discussion.get("url", "")
        else:
            category_id = await self._ensure_category(owner, repo)
            repo_id = await self.gql.get_repository_id(owner, repo)
            new_discussion = await self.gql.create_discussion(
                repo_id=repo_id,
                category_id=category_id,
                title=self.DISCUSSION_TITLE,
                body=body,
            )
            return new_discussion.get("url", "")

    async def read_approvals(self, owner: str, repo: str) -> list[int]:
        """Parse checkbox state to find approved items (checked = approved)."""
        discussion = await self._find_discussion(owner, repo)
        if discussion is None:
            return []
        body = discussion.get("body", "")
        checkboxes = self._parse_checkboxes(body)
        return [number for number, checked in checkboxes.items() if checked]

    async def mark_executed(self, owner: str, repo: str, numbers: list[int], results: dict[int, str] | None = None):
        """Move items from pending to executed (or failed with reason)."""
        items = await self._load_items(owner, repo)
        results = results or {}
        executed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        for item in items:
            if item.number in numbers:
                if item.number in results and results[item.number].startswith("error:"):
                    item.status = RecommendationStatus.FAILED
                    item.failure_reason = results[item.number][len("error:") :].strip()
                else:
                    item.status = RecommendationStatus.EXECUTED
                    item.executed_at = executed_at

        await self._save_items(owner, repo, items)

    async def invalidate_all(self, owner: str, repo: str):
        """Mark all pending items as expired (on philosophy change)."""
        items = await self._load_items(owner, repo)
        for item in items:
            if item.status == RecommendationStatus.PENDING:
                item.status = RecommendationStatus.EXPIRED
        await self._save_items(owner, repo, items)

    async def remove_stale(self, owner: str, repo: str, numbers: list[int]):
        """Remove items that no longer exist (already merged/closed externally)."""
        items = await self._load_items(owner, repo)
        items = [item for item in items if item.number not in numbers]
        await self._save_items(owner, repo, items)

    @staticmethod
    def _render_queue_markdown(items: list[Recommendation], mode: str = "training", last_bark: str = "") -> str:
        """Render the full queue as markdown."""
        pending = [i for i in items if i.status in (RecommendationStatus.PENDING, RecommendationStatus.APPROVED)]
        executed = [i for i in items if i.status == RecommendationStatus.EXECUTED]
        failed = [i for i in items if i.status == RecommendationStatus.FAILED]
        expired = [i for i in items if i.status == RecommendationStatus.EXPIRED]

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        timestamp = last_bark or now

        lines = [
            "# 🐕 Collie Queue",
            f"> Last updated: {timestamp} | Mode: {mode}",
            "",
        ]

        # Pending section
        lines.append(f"## Pending ({len(pending)})")
        if pending:
            for item in pending:
                item_label = _item_label(item)
                action_str = item.action.value if hasattr(item.action, "value") else str(item.action)
                checkbox = "[x]" if item.status == RecommendationStatus.APPROVED else "[ ]"
                title_part = f" | {item.title}" if item.title else ""
                coverage_part = f" | {item.analysis_coverage}" if item.analysis_coverage else ""
                lines.append(f"- {checkbox} **{item_label}** — `{action_str}`{title_part}{coverage_part}")
                if item.reason:
                    lines.append(f"  > {item.reason}")
        else:
            lines.append("_No pending items._")
        lines.append("")

        # Executed section
        lines.append(f"## Executed ({len(executed)})")
        if executed:
            for item in executed:
                item_label = _item_label(item)
                action_str = item.action.value if hasattr(item.action, "value") else str(item.action)
                lines.append(f"- [x] ~~{item_label} — {action_str}~~ ✅")
        else:
            lines.append("_No executed items._")
        lines.append("")

        # Failed section
        lines.append(f"## Failed ({len(failed)})")
        if failed:
            for item in failed:
                item_label = _item_label(item)
                reason_part = f" — {item.failure_reason}" if item.failure_reason else ""
                lines.append(f"- ❌ {item_label}{reason_part}")
        else:
            lines.append("_No failed items._")
        lines.append("")

        # Expired section
        lines.append(f"## Expired ({len(expired)})")
        if expired:
            for item in expired:
                item_label = _item_label(item)
                lines.append(f"- ⏰ {item_label} — expired (philosophy changed)")
        else:
            lines.append("_No expired items._")

        return "\n".join(lines)

    @staticmethod
    def _parse_checkboxes(markdown: str) -> dict[int, bool]:
        """Parse markdown checkboxes to determine which items are checked."""
        result: dict[int, bool] = {}
        # Match: - [x] **PR #N** or - [ ] **Issue #N**
        pattern = re.compile(r"^-\s+\[( |x)\]\s+\*\*(?:PR|Issue)\s+#(\d+)\*\*", re.MULTILINE | re.IGNORECASE)
        for match in pattern.finditer(markdown):
            checked = match.group(1) == "x"
            number = int(match.group(2))
            result[number] = checked
        return result

    async def _find_discussion(self, owner: str, repo: str) -> dict | None:
        """Find the queue discussion for the given repo."""
        discussions = await self.gql.list_discussions(owner, repo, category=self.CATEGORY_NAME)
        for d in discussions:
            if d.get("title") == self.DISCUSSION_TITLE:
                return d
        return None

    async def _load_items(self, owner: str, repo: str) -> list[Recommendation]:
        """Load existing items from the queue Discussion."""
        discussion = await self._find_discussion(owner, repo)
        if discussion is None:
            return []
        body = discussion.get("body", "")
        return _parse_queue_markdown(body)

    async def _save_items(self, owner: str, repo: str, items: list[Recommendation]):
        """Save items back to the queue Discussion."""
        body = self._render_queue_markdown(items)
        discussion = await self._find_discussion(owner, repo)
        if discussion:
            await self.gql.update_discussion_body(discussion["id"], body)

    async def _ensure_category(self, owner: str, repo: str) -> str:
        """Return category ID, creating it if it doesn't exist."""
        categories = await self.gql.list_discussion_categories(owner, repo)
        for cat in categories:
            if cat.get("name") == self.CATEGORY_NAME:
                return cat["id"]
        category = await self.rest.create_discussion_category(owner, repo, self.CATEGORY_NAME)
        return category["id"]


def _item_label(item: Recommendation) -> str:
    """Format item as 'PR #N' or 'Issue #N'."""
    type_str = "PR" if item.item_type in (None, "pr") or str(item.item_type).endswith("pr") else "Issue"
    # Handle both enum and string
    if hasattr(item.item_type, "value"):
        type_str = "PR" if item.item_type.value == "pr" else "Issue"
    return f"{type_str} #{item.number}"


def _parse_queue_markdown(markdown: str) -> list[Recommendation]:
    """Parse queue markdown back into Recommendation objects (best-effort)."""
    from collie.core.models import ItemType, RecommendationAction

    items: list[Recommendation] = []

    # Pattern for pending/approved: - [ ] **PR #N** — `action` | title
    pending_pattern = re.compile(
        r"^-\s+\[( |x)\]\s+\*\*(PR|Issue)\s+#(\d+)\*\*\s+—\s+`([^`]+)`(?:\s+\|(.*))?$",
        re.MULTILINE | re.IGNORECASE,
    )
    for match in pending_pattern.finditer(markdown):
        checked = match.group(1) == "x"
        item_type_str = match.group(2).lower()
        number = int(match.group(3))
        action_str = match.group(4).strip()
        title = match.group(5).strip() if match.group(5) else ""

        try:
            action = RecommendationAction(action_str)
        except ValueError:
            action = RecommendationAction.HOLD

        item_type = ItemType.PR if item_type_str == "pr" else ItemType.ISSUE
        status = RecommendationStatus.APPROVED if checked else RecommendationStatus.PENDING
        items.append(
            Recommendation(number=number, item_type=item_type, action=action, reason="", title=title, status=status)
        )

    # Pattern for executed: - [x] ~~PR #N — action~~ ✅
    executed_pattern = re.compile(
        r"^-\s+\[x\]\s+~~(PR|Issue)\s+#(\d+)\s+—\s+([^~]+)~~\s*✅",
        re.MULTILINE | re.IGNORECASE,
    )
    for match in executed_pattern.finditer(markdown):
        item_type_str = match.group(1).lower()
        number = int(match.group(2))
        action_str = match.group(3).strip()
        try:
            action = RecommendationAction(action_str)
        except ValueError:
            action = RecommendationAction.HOLD
        item_type = ItemType.PR if item_type_str == "pr" else ItemType.ISSUE
        items.append(
            Recommendation(
                number=number, item_type=item_type, action=action, reason="", status=RecommendationStatus.EXECUTED
            )
        )

    # Pattern for failed: - ❌ PR #N — reason
    failed_pattern = re.compile(
        r"^-\s+❌\s+(PR|Issue)\s+#(\d+)(?:\s+—\s+(.+))?$",
        re.MULTILINE | re.IGNORECASE,
    )
    for match in failed_pattern.finditer(markdown):
        item_type_str = match.group(1).lower()
        number = int(match.group(2))
        failure_reason = match.group(3).strip() if match.group(3) else ""
        item_type = ItemType.PR if item_type_str == "pr" else ItemType.ISSUE
        items.append(
            Recommendation(
                number=number,
                item_type=item_type,
                action=RecommendationAction.HOLD,
                reason="",
                status=RecommendationStatus.FAILED,
                failure_reason=failure_reason,
            )
        )

    # Pattern for expired: - ⏰ PR #N — expired
    expired_pattern = re.compile(
        r"^-\s+⏰\s+(PR|Issue)\s+#(\d+)",
        re.MULTILINE | re.IGNORECASE,
    )
    for match in expired_pattern.finditer(markdown):
        item_type_str = match.group(1).lower()
        number = int(match.group(2))
        item_type = ItemType.PR if item_type_str == "pr" else ItemType.ISSUE
        items.append(
            Recommendation(
                number=number,
                item_type=item_type,
                action=RecommendationAction.HOLD,
                reason="",
                status=RecommendationStatus.EXPIRED,
            )
        )

    return items
