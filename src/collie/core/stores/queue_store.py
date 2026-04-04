"""Recommendation queue storage backed by GitHub Discussions (Living Document)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from collie.core.models import ApprovalRecord, Recommendation, RecommendationStatus

STATE_BLOCK_START = "<!-- collie:queue-state"
STATE_BLOCK_END = "-->"


class QueueStore:
    """Manages the recommendation queue as a single living Discussion document."""

    DISCUSSION_TITLE = "🐕 Collie Queue"
    CATEGORY_NAME = "Collie"

    def __init__(self, graphql_client, rest_client):
        self.gql = graphql_client
        self.rest = rest_client

    async def upsert_recommendations(self, owner: str, repo: str, items: list[Recommendation]) -> str:
        """Add or update recommendations in the queue Discussion."""
        state = await self._load_state(owner, repo)
        existing_items = state["items"]
        approvals_by_number = state["approvals_by_number"]
        meta = state["meta"]

        # Merge: update existing by number, add new ones
        existing_by_number = {item.number: item for item in existing_items}
        for item in items:
            existing_by_number[item.number] = item
        merged = list(existing_by_number.values())

        valid_approvals = []
        for item in merged:
            approval = approvals_by_number.get(item.number)
            if approval and approval.approved_payload_hash == item.payload_hash():
                item.status = RecommendationStatus.APPROVED
                valid_approvals.append(approval)
            elif item.status == RecommendationStatus.APPROVED:
                item.status = RecommendationStatus.PENDING

        body = self._render_queue_markdown(merged, approvals=valid_approvals, meta=meta)
        discussion = await self._find_discussion(owner, repo)

        if discussion:
            await self.gql.update_discussion_body(discussion["id"], body)
            return discussion.get("url", "")
        else:
            category_id = await self._ensure_category(owner, repo)
            repo_id = await self.gql.get_repository_id(owner, repo)
            new_discussion = await self.gql.create_discussion(
                repository_id=repo_id,
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

    async def read_verified_approvals(self, owner: str, repo: str) -> list[int]:
        """Return approval numbers backed by a verified approval record and matching payload hash."""
        state = await self._load_state(owner, repo)
        valid_numbers = []
        for item in state["items"]:
            approval = state["approvals_by_number"].get(item.number)
            if approval and approval.approved_payload_hash == item.payload_hash():
                valid_numbers.append(item.number)
        return valid_numbers

    async def record_approvals(
        self, owner: str, repo: str, numbers: list[int], approver: str, source: str = "cli"
    ) -> list[ApprovalRecord]:
        """Persist verified approvals for the current canonical payload."""
        state = await self._load_state(owner, repo)
        approvals_by_number = state["approvals_by_number"]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        created: list[ApprovalRecord] = []

        for item in state["items"]:
            if item.number in numbers:
                record = ApprovalRecord(
                    number=item.number,
                    approver=approver,
                    approved_payload_hash=item.payload_hash(),
                    approved_at=now,
                    source=source,
                )
                approvals_by_number[item.number] = record
                item.status = RecommendationStatus.APPROVED
                created.append(record)

        await self._save_state(owner, repo, state["items"], list(approvals_by_number.values()), meta=state["meta"])
        return created

    async def get_actor_permission(self, owner: str, repo: str) -> tuple[str, str]:
        """Return the current viewer identity and repository permission."""
        return await self.gql.get_viewer_repository_permission(owner, repo)

    async def read_incremental_state(self, owner: str, repo: str) -> dict:
        """Load persisted incremental bark metadata."""
        state = await self._load_state(owner, repo)
        return dict(state["meta"])

    async def write_incremental_state(self, owner: str, repo: str, meta: dict):
        """Persist incremental bark metadata while preserving queue items and approvals."""
        state = await self._load_state(owner, repo)
        merged_meta = dict(state["meta"])
        merged_meta.update(meta)
        await self._save_state(owner, repo, state["items"], state["approvals"], meta=merged_meta)

    async def get_recommendations(
        self, owner: str, repo: str, numbers: list[int] | None = None
    ) -> list[Recommendation]:
        """Load canonical recommendations, optionally filtered by item number."""
        items = await self._load_items(owner, repo)
        if numbers is None:
            return items

        wanted = set(numbers)
        ordered = {n: idx for idx, n in enumerate(numbers)}
        filtered = [item for item in items if item.number in wanted]
        filtered.sort(key=lambda item: ordered.get(item.number, len(ordered)))
        return filtered

    async def mark_executed(
        self,
        owner: str,
        repo: str,
        numbers: list[int],
        results: dict[int, str] | None = None,
        execution_paths: dict[int, str] | None = None,
    ):
        """Move items from pending to executed (or failed with reason)."""
        state = await self._load_state(owner, repo)
        items = state["items"]
        approvals_by_number = state["approvals_by_number"]
        results = results or {}
        execution_paths = execution_paths or {}
        executed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        for item in items:
            if item.number in numbers:
                if item.number in execution_paths:
                    item.execution_path = execution_paths[item.number]
                if item.number in results and results[item.number].startswith("error:"):
                    item.status = RecommendationStatus.FAILED
                    item.failure_reason = results[item.number][len("error:") :].strip()
                else:
                    item.status = RecommendationStatus.EXECUTED
                    item.executed_at = executed_at

        await self._save_state(owner, repo, items, list(approvals_by_number.values()), meta=state["meta"])

    async def invalidate_all(self, owner: str, repo: str):
        """Mark all pending items as expired (on philosophy change)."""
        state = await self._load_state(owner, repo)
        items = state["items"]
        approvals_by_number = state["approvals_by_number"]
        for item in items:
            if item.status == RecommendationStatus.PENDING:
                item.status = RecommendationStatus.EXPIRED
        await self._save_state(owner, repo, items, list(approvals_by_number.values()), meta=state["meta"])

    async def invalidate_numbers(self, owner: str, repo: str, numbers: list[int]):
        """Expire specific queue items whose source state has drifted."""
        state = await self._load_state(owner, repo)
        items = state["items"]
        approvals_by_number = state["approvals_by_number"]
        stale = set(numbers)
        for item in items:
            if item.number in stale and item.status in (RecommendationStatus.PENDING, RecommendationStatus.APPROVED):
                item.status = RecommendationStatus.EXPIRED
        await self._save_state(owner, repo, items, list(approvals_by_number.values()), meta=state["meta"])

    async def remove_stale(self, owner: str, repo: str, numbers: list[int]):
        """Remove items that no longer exist (already merged/closed externally)."""
        state = await self._load_state(owner, repo)
        items = [item for item in state["items"] if item.number not in numbers]
        approvals = [approval for approval in state["approvals"] if approval.number not in numbers]
        await self._save_state(owner, repo, items, approvals, meta=state["meta"])

    @staticmethod
    def _render_queue_markdown(
        items: list[Recommendation],
        approvals: list[ApprovalRecord] | None = None,
        meta: dict | None = None,
        mode: str = "training",
        last_bark: str = "",
    ) -> str:
        """Render the full queue as markdown with a canonical structured state block."""
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
                path_part = f" via {item.execution_path}" if item.execution_path else ""
                lines.append(f"- [x] ~~{item_label} — {action_str}{path_part}~~ ✅")
        else:
            lines.append("_No executed items._")
        lines.append("")

        # Failed section
        lines.append(f"## Failed ({len(failed)})")
        if failed:
            for item in failed:
                item_label = _item_label(item)
                path_part = f" [{item.execution_path}]" if item.execution_path else ""
                reason_part = f" — {item.failure_reason}" if item.failure_reason else ""
                lines.append(f"- ❌ {item_label}{path_part}{reason_part}")
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

        lines.append("")
        lines.append(STATE_BLOCK_START)
        lines.append(
            json.dumps(
                {
                    "version": 2,
                    "items": [item.to_dict() for item in items],
                    "approvals": [approval.to_dict() for approval in (approvals or [])],
                    "meta": meta or {},
                },
                indent=2,
                sort_keys=True,
            )
        )
        lines.append(STATE_BLOCK_END)

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
        discussions = await self.gql.list_discussions(owner, repo)
        for d in discussions:
            if d.get("title") == self.DISCUSSION_TITLE:
                return d
        return None

    async def _load_items(self, owner: str, repo: str) -> list[Recommendation]:
        """Load existing items from the queue Discussion."""
        state = await self._load_state(owner, repo)
        return state["items"]

    async def _load_state(self, owner: str, repo: str) -> dict:
        """Load canonical queue state including items and verified approvals."""
        discussion = await self._find_discussion(owner, repo)
        if discussion is None:
            return {"items": [], "approvals": [], "approvals_by_number": {}, "meta": {}}
        body = discussion.get("body", "")
        payload = _parse_state_block(body)
        items = payload["items"] if payload is not None else _parse_queue_markdown(body)
        approvals = payload["approvals"] if payload is not None else []
        meta = payload["meta"] if payload is not None else {}
        approvals_by_number = {approval.number: approval for approval in approvals}
        return {"items": items, "approvals": approvals, "approvals_by_number": approvals_by_number, "meta": meta}

    async def _save_items(self, owner: str, repo: str, items: list[Recommendation]):
        """Save items back to the queue Discussion."""
        state = await self._load_state(owner, repo)
        await self._save_state(owner, repo, items, state["approvals"], meta=state["meta"])

    async def _save_state(
        self,
        owner: str,
        repo: str,
        items: list[Recommendation],
        approvals: list[ApprovalRecord],
        meta: dict | None = None,
    ):
        """Save items and approvals back to the queue Discussion."""
        body = self._render_queue_markdown(items, approvals=approvals, meta=meta or {})
        discussion = await self._find_discussion(owner, repo)
        if discussion:
            await self.gql.update_discussion_body(discussion["id"], body)

    async def _ensure_category(self, owner: str, repo: str) -> str:
        """Return category ID. Falls back to 'General' if 'Collie' doesn't exist."""
        categories = await self.gql.list_discussion_categories(owner, repo)
        for cat in categories:
            if cat.get("name") == self.CATEGORY_NAME:
                return cat["id"]
        for cat in categories:
            if cat.get("name") == "General":
                return cat["id"]
        if categories:
            return categories[0]["id"]
        raise ValueError(
            f"No discussion categories found for {owner}/{repo}. Enable Discussions in repository settings."
        )


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

    structured_state = _parse_state_block(markdown)
    if structured_state is not None:
        structured_items = structured_state["items"]
        checkboxes = QueueStore._parse_checkboxes(markdown)
        for item in structured_items:
            if (
                item.status in (RecommendationStatus.PENDING, RecommendationStatus.APPROVED)
                and item.number in checkboxes
            ):
                item.status = RecommendationStatus.APPROVED if checkboxes[item.number] else RecommendationStatus.PENDING
        return structured_items

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


def _parse_state_block(markdown: str) -> dict | None:
    """Parse the canonical structured queue state block if present."""
    match = re.search(r"<!--\s*collie:queue-state\s*\n(.*?)\n-->", markdown, re.DOTALL)
    if not match:
        return None

    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return None

    raw_approvals = payload.get("approvals", [])
    if not isinstance(raw_approvals, list):
        return None

    try:
        return {
            "items": [Recommendation.from_dict(item) for item in raw_items],
            "approvals": [ApprovalRecord.from_dict(item) for item in raw_approvals],
            "meta": payload.get("meta", {}),
        }
    except (KeyError, TypeError, ValueError):
        return None
