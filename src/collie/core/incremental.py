"""Incremental processing — delta detection, stale checking, philosophy change detection."""

from __future__ import annotations

from datetime import datetime, timezone


class IncrementalManager:
    """Manages incremental bark processing."""

    def __init__(self, graphql_client, queue_store, philosophy_store):
        self.gql = graphql_client
        self.queue = queue_store
        self.philosophy = philosophy_store
        self._last_bark_time: str | None = None
        self._last_philosophy_hash: str | None = None

    async def should_full_scan(self, owner: str, repo: str) -> bool:
        """Determine if a full scan is needed (first run or philosophy changed)."""
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
        await self.queue.read_approvals(owner, repo)
        # Items in queue but no longer open → stale (already merged/closed)
        stale: list[int] = []
        return stale

    def record_bark_time(self):
        """Record current time as last bark time."""
        self._last_bark_time = datetime.now(timezone.utc).isoformat()

    def record_philosophy_hash(self, philosophy):
        """Record philosophy hash for change detection."""
        self._last_philosophy_hash = self._hash_philosophy(philosophy)

    @staticmethod
    def _hash_philosophy(philosophy) -> str:
        """Simple hash of philosophy for change detection."""
        import hashlib

        md = philosophy.to_markdown()
        return hashlib.sha256(md.encode()).hexdigest()[:16]
