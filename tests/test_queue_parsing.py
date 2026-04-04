"""Tests for queue markdown parsing."""

from __future__ import annotations

from collie.core.models import (
    ApprovalRecord,
    ItemType,
    Recommendation,
    RecommendationAction,
    RecommendationStatus,
)
from collie.core.stores.queue_store import QueueStore, _parse_queue_markdown


def test_parse_checkboxes_checked():
    md = "- [x] **PR #142** — `merge` | Title\n  > reason"
    result = QueueStore._parse_checkboxes(md)
    assert result == {142: True}


def test_parse_checkboxes_unchecked():
    md = "- [ ] **PR #142** — `merge` | Title\n  > reason"
    result = QueueStore._parse_checkboxes(md)
    assert result == {142: False}


def test_parse_checkboxes_mixed():
    md = (
        "- [x] **PR #100** — `merge` | Title A\n"
        "- [ ] **PR #200** — `close` | Title B\n"
        "- [x] **Issue #300** — `close` | Title C\n"
    )
    result = QueueStore._parse_checkboxes(md)
    assert result == {100: True, 200: False, 300: True}


def test_parse_checkboxes_empty():
    result = QueueStore._parse_checkboxes("")
    assert result == {}


def test_parse_checkboxes_no_matches():
    md = "Some text without checkboxes\n## Section\nContent"
    result = QueueStore._parse_checkboxes(md)
    assert result == {}


def test_render_queue_markdown_basic():
    items = [
        Recommendation(
            number=142,
            item_type=ItemType.PR,
            action=RecommendationAction.MERGE,
            reason="CI passed, 2 reviews",
            status=RecommendationStatus.PENDING,
            title="Add dark mode",
        ),
        Recommendation(
            number=100,
            item_type=ItemType.PR,
            action=RecommendationAction.MERGE,
            reason="",
            status=RecommendationStatus.EXECUTED,
            title="Fix bug",
        ),
    ]
    md = QueueStore._render_queue_markdown(items, mode="training")
    assert "## Pending" in md
    assert "- [ ] **PR #142**" in md
    assert "## Executed" in md
    assert "~~PR #100" in md


def test_render_queue_markdown_failed():
    items = [
        Recommendation(
            number=105,
            item_type=ItemType.PR,
            action=RecommendationAction.MERGE,
            reason="",
            status=RecommendationStatus.FAILED,
            failure_reason="merge conflict",
            execution_path="blocked",
        ),
    ]
    md = QueueStore._render_queue_markdown(items, mode="training")
    assert "## Failed" in md
    assert "❌ PR #105" in md
    assert "merge conflict" in md
    assert "blocked" in md


def test_render_queue_markdown_expired():
    items = [
        Recommendation(
            number=90,
            item_type=ItemType.PR,
            action=RecommendationAction.HOLD,
            reason="",
            status=RecommendationStatus.EXPIRED,
        ),
    ]
    md = QueueStore._render_queue_markdown(items, mode="training")
    assert "## Expired" in md
    assert "⏰ PR #90" in md
    assert "expired" in md


def test_render_queue_markdown_executed_includes_execution_path():
    items = [
        Recommendation(
            number=91,
            item_type=ItemType.PR,
            action=RecommendationAction.MERGE,
            reason="",
            status=RecommendationStatus.EXECUTED,
            execution_path="auto_merge",
        ),
    ]
    md = QueueStore._render_queue_markdown(items, mode="training")
    assert "via auto_merge" in md


def test_render_queue_markdown_empty():
    md = QueueStore._render_queue_markdown([], mode="training")
    assert "## Pending (0)" in md
    assert "## Executed (0)" in md
    assert "## Failed (0)" in md
    assert "## Expired (0)" in md
    assert "_No pending items._" in md


def test_render_queue_markdown_issue_type():
    items = [
        Recommendation(
            number=301,
            item_type=ItemType.ISSUE,
            action=RecommendationAction.CLOSE,
            reason="Resolved by PR #142",
            status=RecommendationStatus.PENDING,
            title="Feature request: dark mode",
        ),
    ]
    md = QueueStore._render_queue_markdown(items, mode="training")
    assert "**Issue #301**" in md
    assert "`close`" in md


def test_render_queue_markdown_large():
    """Large queue (50+ items) renders without errors."""
    items = [
        Recommendation(
            number=i,
            item_type=ItemType.PR,
            action=RecommendationAction.MERGE,
            reason=f"Reason {i}",
            status=RecommendationStatus.PENDING,
            title=f"PR title {i}",
        )
        for i in range(1, 55)
    ]
    md = QueueStore._render_queue_markdown(items, mode="active")
    assert "## Pending (54)" in md
    assert "**PR #1**" in md
    assert "**PR #54**" in md


def test_render_queue_markdown_analysis_coverage():
    items = [
        Recommendation(
            number=237,
            item_type=ItemType.PR,
            action=RecommendationAction.HOLD,
            reason="crypto/ directory not analyzed",
            status=RecommendationStatus.PENDING,
            title="Refactor auth module",
            analysis_coverage="120/150 files analyzed",
        ),
    ]
    md = QueueStore._render_queue_markdown(items, mode="training")
    assert "120/150 files analyzed" in md
    assert "crypto/ directory not analyzed" in md


def test_render_includes_mode():
    md = QueueStore._render_queue_markdown([], mode="active")
    assert "Mode: active" in md


def test_parse_checkboxes_with_full_queue_markdown():
    """Checkboxes parsed correctly from a full rendered queue."""
    items = [
        Recommendation(
            number=10,
            item_type=ItemType.PR,
            action=RecommendationAction.MERGE,
            reason="",
            status=RecommendationStatus.PENDING,
            title="A",
        ),
        Recommendation(
            number=20,
            item_type=ItemType.ISSUE,
            action=RecommendationAction.CLOSE,
            reason="",
            status=RecommendationStatus.PENDING,
            title="B",
        ),
    ]
    md = QueueStore._render_queue_markdown(items, mode="training")
    result = QueueStore._parse_checkboxes(md)
    assert 10 in result
    assert 20 in result
    assert result[10] is False
    assert result[20] is False


def test_render_queue_markdown_embeds_structured_state():
    items = [
        Recommendation(
            number=401,
            item_type=ItemType.ISSUE,
            action=RecommendationAction.COMMENT,
            reason="Needs more context",
            status=RecommendationStatus.PENDING,
            title="Question",
            suggested_comment="Please share repro steps.",
        )
    ]
    md = QueueStore._render_queue_markdown(items, mode="training")
    assert "<!-- collie:queue-state" in md
    assert '"suggested_comment": "Please share repro steps."' in md


def test_parse_queue_markdown_prefers_structured_state_and_preserves_fields():
    original = Recommendation(
        number=402,
        item_type=ItemType.ISSUE,
        action=RecommendationAction.LABEL,
        reason="Classified as bug",
        status=RecommendationStatus.PENDING,
        title="Bug report",
        suggested_labels=["bug", "triaged"],
        suggested_comment="",
    )
    md = QueueStore._render_queue_markdown([original], mode="training")
    parsed = _parse_queue_markdown(md)

    assert len(parsed) == 1
    restored = parsed[0]
    assert restored.number == 402
    assert restored.item_type == ItemType.ISSUE
    assert restored.action == RecommendationAction.LABEL
    assert restored.reason == "Classified as bug"
    assert restored.suggested_labels == ["bug", "triaged"]


def test_parse_queue_markdown_overlays_checkbox_state_on_structured_state():
    item = Recommendation(
        number=403,
        item_type=ItemType.PR,
        action=RecommendationAction.MERGE,
        reason="Looks good",
        status=RecommendationStatus.PENDING,
        title="Feature",
    )
    md = QueueStore._render_queue_markdown([item], mode="training")
    md = md.replace("- [ ] **PR #403**", "- [x] **PR #403**")
    parsed = _parse_queue_markdown(md)

    assert parsed[0].status == RecommendationStatus.APPROVED


def test_render_queue_markdown_embeds_approvals_in_state_block():
    item = Recommendation(
        number=404,
        item_type=ItemType.PR,
        action=RecommendationAction.MERGE,
        reason="Looks good",
        status=RecommendationStatus.APPROVED,
        title="Feature",
    )
    approval = ApprovalRecord(
        number=404,
        approver="maintainer",
        approved_payload_hash=item.payload_hash(),
        approved_at="2026-04-03 00:00 UTC",
        source="cli",
    )
    md = QueueStore._render_queue_markdown([item], approvals=[approval], mode="active")
    assert '"approver": "maintainer"' in md
    assert '"approved_payload_hash":' in md
