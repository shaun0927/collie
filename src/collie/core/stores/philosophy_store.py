"""Philosophy storage backed by GitHub Discussions."""

from __future__ import annotations

from collie.core.models import Mode, Philosophy


class PhilosophyStore:
    """Manages philosophy storage in GitHub Discussions."""

    DISCUSSION_TITLE = "🐕 Collie Philosophy"
    CATEGORY_NAME = "Collie"

    def __init__(self, graphql_client, rest_client):
        self.gql = graphql_client
        self.rest = rest_client

    async def save(self, owner: str, repo: str, philosophy: Philosophy) -> str:
        """Save philosophy to Discussion. Returns discussion URL."""
        existing = await self._find_discussion(owner, repo)
        body = philosophy.to_markdown()

        if existing:
            url = await self.gql.update_discussion_body(existing["id"], body)
            return url or existing.get("url", "")
        else:
            category_id = await self._ensure_category(owner, repo)
            repo_id = await self.gql.get_repository_id(owner, repo)
            discussion = await self.gql.create_discussion(
                repository_id=repo_id,
                category_id=category_id,
                title=self.DISCUSSION_TITLE,
                body=body,
            )
            return discussion.get("url", "")

    async def load(self, owner: str, repo: str) -> Philosophy | None:
        """Load philosophy from Discussion. Returns None if not found."""
        existing = await self._find_discussion(owner, repo)
        if existing is None:
            return None
        body = existing.get("body", "")
        if not body:
            return None
        return Philosophy.from_markdown(body)

    async def update_rule(self, owner: str, repo: str, rule_text: str, action: str = "add") -> Philosophy:
        """Micro-update: add or remove a hard rule."""
        philosophy = await self.load(owner, repo)
        if philosophy is None:
            raise ValueError("No philosophy found. Run 'collie sit' first.")

        from collie.core.models import HardRule

        if action == "add":
            # Parse rule_text as "condition:action[:description]"
            parts = rule_text.split(":", 2)
            condition = parts[0].strip()
            rule_action = parts[1].strip() if len(parts) > 1 else "hold"
            description = parts[2].strip() if len(parts) > 2 else ""
            philosophy.hard_rules.append(HardRule(condition=condition, action=rule_action, description=description))
        elif action == "remove":
            philosophy.hard_rules = [r for r in philosophy.hard_rules if r.condition != rule_text.strip()]

        await self.save(owner, repo, philosophy)
        return philosophy

    async def set_mode(self, owner: str, repo: str, mode: Mode) -> Philosophy:
        """Change mode (training/active)."""
        philosophy = await self.load(owner, repo)
        if philosophy is None:
            raise ValueError("No philosophy found. Run 'collie sit' first.")
        philosophy.mode = mode
        await self.save(owner, repo, philosophy)
        return philosophy

    async def _find_discussion(self, owner: str, repo: str) -> dict | None:
        """Find the philosophy discussion by title (any category)."""
        discussions = await self.gql.list_discussions(owner, repo)
        for d in discussions:
            if d.get("title") == self.DISCUSSION_TITLE:
                return d
        return None

    async def _ensure_category(self, owner: str, repo: str) -> str:
        """Return category ID. Falls back to 'General' if 'Collie' doesn't exist."""
        categories = await self.gql.list_discussion_categories(owner, repo)
        # Prefer "Collie" category
        for cat in categories:
            if cat.get("name") == self.CATEGORY_NAME:
                return cat["id"]
        # Fallback to "General" category
        for cat in categories:
            if cat.get("name") == "General":
                return cat["id"]
        # Use first available category
        if categories:
            return categories[0]["id"]
        raise ValueError(
            f"No discussion categories found for {owner}/{repo}. "
            "Enable Discussions in repository settings."
        )
