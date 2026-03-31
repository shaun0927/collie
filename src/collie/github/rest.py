"""GitHub REST client for write operations."""

import asyncio
import base64

import httpx

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 4
_BASE_BACKOFF = 1.0


async def _request_with_retry(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> httpx.Response:
    """Make an HTTP request with exponential backoff on 429/5xx."""
    for attempt in range(_MAX_RETRIES):
        response = await client.request(method, url, **kwargs)
        if response.status_code not in _RETRY_STATUSES:
            response.raise_for_status()
            return response
        if attempt == _MAX_RETRIES - 1:
            response.raise_for_status()
        retry_after = response.headers.get("retry-after")
        wait = float(retry_after) if retry_after else _BASE_BACKOFF * (2**attempt)
        await asyncio.sleep(wait)
    # unreachable, but satisfies type checker
    raise httpx.HTTPStatusError("Max retries exceeded", request=response.request, response=response)


_CREATE_DISCUSSION_MUTATION = """
mutation($repositoryId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
  createDiscussion(input: {repositoryId: $repositoryId, categoryId: $categoryId, title: $title, body: $body}) {
    discussion { id number title }
  }
}
"""

_UPDATE_DISCUSSION_MUTATION = """
mutation($discussionId: ID!, $body: String!) {
  updateDiscussion(input: {discussionId: $discussionId, body: $body}) {
    discussion { id number title body }
  }
}
"""

_REPO_ID_QUERY = """
query($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) { id }
}
"""

_DISCUSSION_CATEGORIES_QUERY = """
query($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) {
    discussionCategories(first: 25) { nodes { id name slug } }
  }
}
"""


class GitHubREST:
    def __init__(self, token: str):
        self.token = token
        self.client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            timeout=30.0,
        )
        self._graphql_client = httpx.AsyncClient(
            base_url="https://api.github.com/graphql",
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
            timeout=30.0,
        )

    async def _graphql(self, query: str, variables: dict) -> dict:
        response = await _request_with_retry(
            self._graphql_client, "POST", "", json={"query": query, "variables": variables}
        )
        payload = response.json()
        if "errors" in payload:
            raise RuntimeError(f"GraphQL errors: {payload['errors']}")
        return payload["data"]

    async def merge_pr(self, owner: str, repo: str, number: int, method: str = "squash") -> dict:
        """Merge a pull request."""
        response = await _request_with_retry(
            self.client,
            "PUT",
            f"/repos/{owner}/{repo}/pulls/{number}/merge",
            json={"merge_method": method},
        )
        return response.json()

    async def close_issue(self, owner: str, repo: str, number: int) -> dict:
        """Close an issue."""
        response = await _request_with_retry(
            self.client,
            "PATCH",
            f"/repos/{owner}/{repo}/issues/{number}",
            json={"state": "closed"},
        )
        return response.json()

    async def close_pr(self, owner: str, repo: str, number: int) -> dict:
        """Close a pull request without merging."""
        response = await _request_with_retry(
            self.client,
            "PATCH",
            f"/repos/{owner}/{repo}/pulls/{number}",
            json={"state": "closed"},
        )
        return response.json()

    async def add_comment(self, owner: str, repo: str, number: int, body: str) -> dict:
        """Add a comment to an issue or PR."""
        response = await _request_with_retry(
            self.client,
            "POST",
            f"/repos/{owner}/{repo}/issues/{number}/comments",
            json={"body": body},
        )
        return response.json()

    async def add_labels(self, owner: str, repo: str, number: int, labels: list[str]) -> dict:
        """Add labels to an issue or PR."""
        response = await _request_with_retry(
            self.client,
            "POST",
            f"/repos/{owner}/{repo}/issues/{number}/labels",
            json={"labels": labels},
        )
        return response.json()

    async def get_repo_content(self, owner: str, repo: str, path: str) -> str | None:
        """Get file content from repo (for CONTRIBUTING.md etc)."""
        try:
            response = await _request_with_retry(
                self.client,
                "GET",
                f"/repos/{owner}/{repo}/contents/{path}",
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        data = response.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8")
        return data.get("content")

    async def get_branch_protection(self, owner: str, repo: str, branch: str = "main") -> dict | None:
        """Get branch protection rules."""
        try:
            response = await _request_with_retry(
                self.client,
                "GET",
                f"/repos/{owner}/{repo}/branches/{branch}/protection",
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 403):
                return None
            raise
        return response.json()

    async def create_discussion(self, owner: str, repo: str, category_id: str, title: str, body: str) -> dict:
        """Create a new discussion via GraphQL mutation."""
        # First get repository node ID
        repo_data = await self._graphql(_REPO_ID_QUERY, {"owner": owner, "repo": repo})
        repository_id = repo_data["repository"]["id"]
        data = await self._graphql(
            _CREATE_DISCUSSION_MUTATION,
            {"repositoryId": repository_id, "categoryId": category_id, "title": title, "body": body},
        )
        return data["createDiscussion"]["discussion"]

    async def update_discussion(self, owner: str, repo: str, discussion_id: str, body: str) -> dict:
        """Update a discussion body via GraphQL mutation."""
        data = await self._graphql(_UPDATE_DISCUSSION_MUTATION, {"discussionId": discussion_id, "body": body})
        return data["updateDiscussion"]["discussion"]

    async def enable_discussions(self, owner: str, repo: str) -> bool:
        """Enable discussions on a repo (requires admin)."""
        try:
            await _request_with_retry(
                self.client,
                "PATCH",
                f"/repos/{owner}/{repo}",
                json={"has_discussions": True},
            )
            return True
        except httpx.HTTPStatusError:
            return False

    async def get_discussion_categories(self, owner: str, repo: str) -> list[dict]:
        """List discussion categories."""
        data = await self._graphql(_DISCUSSION_CATEGORIES_QUERY, {"owner": owner, "repo": repo})
        return data["repository"]["discussionCategories"]["nodes"]

    async def create_discussion_category(self, owner: str, repo: str, name: str) -> dict:
        """Create a discussion category (uses REST endpoint if available, otherwise raises)."""
        # The GitHub REST API does not support creating discussion categories programmatically.
        # This requires the GitHub web UI or GraphQL with admin scope.
        raise NotImplementedError(
            "GitHub does not support creating discussion categories via API. "
            "Please create the category manually in the repository settings."
        )

    async def close(self):
        await self.client.aclose()
        await self._graphql_client.aclose()
