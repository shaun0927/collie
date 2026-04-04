"""Incremental processing — delta detection, stale checking, philosophy change detection."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


class IncrementalManager:
    """Manages incremental bark processing."""

    def __init__(self, graphql_client, queue_store, philosophy_store):
        self.gql = graphql_client
        self.queue = queue_store
        self.philosophy = philosophy_store
        self._last_bark_time: str | None = None
        self._last_philosophy_hash: str | None = None
        self._item_fingerprints: dict[str, str] = {}

    async def _hydrate_state(self, owner: str, repo: str):
        """Load persisted incremental state from the queue store when available."""
        if not hasattr(self.queue, "read_incremental_state"):
            return

        state = await self.queue.read_incremental_state(owner, repo)
        if "last_bark_time" in state:
            self._last_bark_time = state.get("last_bark_time")
        if "last_philosophy_hash" in state:
            self._last_philosophy_hash = state.get("last_philosophy_hash")
        if "item_fingerprints" in state:
            self._item_fingerprints = dict(state.get("item_fingerprints", {}))

    async def should_full_scan(self, owner: str, repo: str) -> bool:
        """Determine if a full scan is needed (first run or philosophy changed)."""
        await self._hydrate_state(owner, repo)

        # First run: no last_bark_time
        if self._last_bark_time is None:
            return True

        # Philosophy changed since last bark
        current_philosophy = await self.philosophy.load(owner, repo)
        if current_philosophy is None:
            return True

        current_hash = self._hash_philosophy(current_philosophy)
        if self._last_philosophy_hash and current_hash != self._last_philosophy_hash:
            # Philosophy changed → invalidate all pending + full scan
            await self.queue.invalidate_all(owner, repo)
            return True

        return False

    async def get_delta(self, owner: str, repo: str) -> list[dict]:
        """Fetch items updated since last bark."""
        await self._hydrate_state(owner, repo)
        all_items = await self.gql.fetch_issues_and_prs(owner, repo, since=self._last_bark_time)
        issues = all_items.get("issues", [])
        prs = all_items.get("pull_requests", [])
        return issues + prs

    async def get_all(self, owner: str, repo: str) -> list[dict]:
        """Fetch all open items (for full scan)."""
        all_items = await self.gql.fetch_issues_and_prs(owner, repo)
        issues = all_items.get("issues", [])
        prs = all_items.get("pull_requests", [])
        return issues + prs

    async def detect_stale_in_queue(self, owner: str, repo: str, current_items: list[dict]) -> list[int]:
        """Find queue items that are stale (already merged/closed, new commits, CI changed)."""
        if not hasattr(self.queue, "get_recommendations"):
            return []

        await self._hydrate_state(owner, repo)

        queue_items = await self.queue.get_recommendations(owner, repo)
        current_fingerprints = {str(item["number"]): self._fingerprint_item(item) for item in current_items}

        stale: list[int] = []
        for queue_item in queue_items:
            number_key = str(queue_item.number)
            old_fingerprint = self._item_fingerprints.get(number_key)
            new_fingerprint = current_fingerprints.get(number_key)

            if new_fingerprint is None:
                stale.append(queue_item.number)
                continue

            if old_fingerprint and old_fingerprint != new_fingerprint:
                stale.append(queue_item.number)

        return stale

    async def apply_stale_queue_updates(self, owner: str, repo: str, current_items: list[dict]):
        """Remove closed items and expire changed items that need re-analysis."""
        if not hasattr(self.queue, "remove_stale"):
            return

        stale_numbers = await self.detect_stale_in_queue(owner, repo, current_items)
        if not stale_numbers:
            return

        current_numbers = {item["number"] for item in current_items}
        removed = [number for number in stale_numbers if number not in current_numbers]
        changed = [number for number in stale_numbers if number in current_numbers]

        if removed:
            await self.queue.remove_stale(owner, repo, removed)
        if changed and hasattr(self.queue, "invalidate_numbers"):
            await self.queue.invalidate_numbers(owner, repo, changed)

    def record_bark_time(self):
        """Record current time as last bark time."""
        self._last_bark_time = datetime.now(timezone.utc).isoformat()

    def record_philosophy_hash(self, philosophy):
        """Record philosophy hash for change detection."""
        self._last_philosophy_hash = self._hash_philosophy(philosophy)

    async def persist_state(self, owner: str, repo: str, philosophy, current_items: list[dict]):
        """Persist bark watermark, philosophy hash, and item fingerprints."""
        fingerprints = {str(item["number"]): self._fingerprint_item(item) for item in current_items}
        self._item_fingerprints = fingerprints
        if hasattr(self.queue, "write_incremental_state"):
            await self.queue.write_incremental_state(
                owner,
                repo,
                {
                    "last_bark_time": self._last_bark_time,
                    "last_philosophy_hash": self._last_philosophy_hash,
                    "item_fingerprints": fingerprints,
                },
            )

    @staticmethod
    def _hash_philosophy(philosophy) -> str:
        """Simple hash of philosophy for change detection."""
        import hashlib

        md = philosophy.to_markdown()
        return hashlib.sha256(md.encode()).hexdigest()[:16]

    @staticmethod
    def _fingerprint_item(item: dict) -> str:
        """Create a stable fingerprint for an open item's queue-relevant state."""
        payload = {
            "number": item.get("number"),
            "state": item.get("state"),
            "updatedAt": item.get("updatedAt"),
            "closedAt": item.get("closedAt"),
            "mergedAt": item.get("mergedAt"),
            "changedFiles": item.get("changedFiles"),
            "additions": item.get("additions"),
            "deletions": item.get("deletions"),
            "ci_state": (
                item.get("commits", {})
                .get("nodes", [{}])[0]
                .get("commit", {})
                .get("statusCheckRollup", {})
                .get("state")
            ),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
