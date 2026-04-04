"""Tests for verified approval records in QueueStore."""

from __future__ import annotations

import pytest

from collie.core.models import ApprovalRecord, ItemType, Recommendation, RecommendationAction
from collie.core.stores.queue_store import QueueStore


class FakeGQL:
    def __init__(self):
        self.discussion = None

    async def list_discussions(self, owner, repo):
        return [self.discussion] if self.discussion else []

    async def update_discussion_body(self, discussion_id, body):
        assert self.discussion is not None
        self.discussion["body"] = body
        return self.discussion.get("url", "")

    async def list_discussion_categories(self, owner, repo):
        return [{"id": "cat1", "name": "General"}]

    async def get_repository_id(self, owner, repo):
        return "repo1"

    async def create_discussion(self, repository_id, category_id, title, body):
        self.discussion = {"id": "disc1", "title": title, "body": body, "url": "https://example.test/discussion"}
        return self.discussion

    async def get_viewer_repository_permission(self, owner, repo):
        return "maintainer", "WRITE"


class FakeREST:
    pass


@pytest.mark.asyncio
async def test_verified_approval_round_trip_and_lookup():
    gql = FakeGQL()
    store = QueueStore(gql, FakeREST())
    rec = Recommendation(number=1, item_type=ItemType.PR, action=RecommendationAction.MERGE, reason="ok")

    await store.upsert_recommendations("o", "r", [rec])
    created = await store.record_approvals("o", "r", [1], approver="maintainer", source="cli")

    assert len(created) == 1
    approvals = await store.read_verified_approvals("o", "r")
    assert approvals == [1]

    state = await store._load_state("o", "r")
    assert len(state["approvals"]) == 1
    assert state["approvals"][0].approver == "maintainer"
    assert state["approvals"][0].approved_payload_hash == rec.payload_hash()


@pytest.mark.asyncio
async def test_verified_approval_invalidated_after_payload_change():
    gql = FakeGQL()
    store = QueueStore(gql, FakeREST())
    original = Recommendation(number=2, item_type=ItemType.PR, action=RecommendationAction.MERGE, reason="ok")
    changed = Recommendation(number=2, item_type=ItemType.PR, action=RecommendationAction.CLOSE, reason="changed")

    await store.upsert_recommendations("o", "r", [original])
    await store.record_approvals("o", "r", [2], approver="maintainer", source="cli")
    assert await store.read_verified_approvals("o", "r") == [2]

    await store.upsert_recommendations("o", "r", [changed])
    assert await store.read_verified_approvals("o", "r") == []


@pytest.mark.asyncio
async def test_latest_approval_record_replaces_prior_for_same_item():
    gql = FakeGQL()
    store = QueueStore(gql, FakeREST())
    rec = Recommendation(number=3, item_type=ItemType.ISSUE, action=RecommendationAction.CLOSE, reason="stale")

    await store.upsert_recommendations("o", "r", [rec])
    await store.record_approvals("o", "r", [3], approver="alice", source="cli")
    await store.record_approvals("o", "r", [3], approver="bob", source="cli")

    state = await store._load_state("o", "r")
    assert len(state["approvals"]) == 1
    assert state["approvals"][0].approver == "bob"


def test_approval_record_serialization_round_trip():
    record = ApprovalRecord(
        number=9,
        approver="maintainer",
        approved_payload_hash="abcdef1234567890",
        approved_at="2026-04-03 00:00 UTC",
        source="cli",
    )

    restored = ApprovalRecord.from_dict(record.to_dict())
    assert restored == record
