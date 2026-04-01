"""GitHub GraphQL client for bulk fetching issues, PRs, and discussions."""

import httpx

ISSUES_AND_PRS_QUERY = """
query($owner: String!, $repo: String!, $afterIssues: String, $afterPRs: String) {
  repository(owner: $owner, name: $repo) {
    issues(first: 100, after: $afterIssues, states: OPEN, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title state author { login }
        labels(first: 10) { nodes { name } }
        createdAt updatedAt closedAt
        comments { totalCount }
      }
    }
    pullRequests(first: 100, after: $afterPRs, states: OPEN, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title state author { login }
        labels(first: 10) { nodes { name } }
        additions deletions changedFiles
        reviews(first: 10) { nodes { state author { login } } }
        commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }
        createdAt updatedAt closedAt mergedAt
      }
    }
  }
}
"""

PR_DETAIL_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      number title state body author { login }
      labels(first: 10) { nodes { name } }
      additions deletions changedFiles
      baseRefName headRefName
      reviews(first: 20) { nodes { state author { login } submittedAt body } }
      commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }
      createdAt updatedAt closedAt mergedAt
    }
  }
}
"""

DISCUSSION_QUERY = """
query($owner: String!, $repo: String!, $category: String!, $after: String) {
  repository(owner: $owner, name: $repo) {
    discussions(first: 100, after: $after, categoryId: $category) {
      pageInfo { hasNextPage endCursor }
      nodes {
        id title body number
        category { id name }
        author { login }
        createdAt updatedAt
      }
    }
  }
}
"""

DISCUSSION_CATEGORIES_QUERY = """
query($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) {
    discussionCategories(first: 25) {
      nodes { id name slug }
    }
  }
}
"""

CREATE_DISCUSSION_MUTATION = """
mutation($repositoryId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
  createDiscussion(input: {repositoryId: $repositoryId, categoryId: $categoryId, title: $title, body: $body}) {
    discussion { id number title }
  }
}
"""

UPDATE_DISCUSSION_MUTATION = """
mutation($discussionId: ID!, $body: String!) {
  updateDiscussion(input: {discussionId: $discussionId, body: $body}) {
    discussion { id number title body }
  }
}
"""


class GitHubGraphQLError(Exception):
    """Raised when the GitHub GraphQL API returns errors."""

    pass


class GitHubGraphQL:
    def __init__(self, token: str):
        self.token = token
        self.client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
            timeout=30.0,
        )
        self.rate_limit_remaining: int | None = None

    async def _execute(self, query: str, variables: dict) -> dict:
        """Execute a GraphQL query and return the data, tracking rate limits."""
        response = await self.client.post("/graphql", json={"query": query, "variables": variables})
        response.raise_for_status()

        # Track rate limit from headers
        remaining = response.headers.get("x-ratelimit-remaining")
        if remaining is not None:
            self.rate_limit_remaining = int(remaining)

        payload = response.json()
        if "errors" in payload:
            raise GitHubGraphQLError(f"GraphQL errors: {payload['errors']}")
        return payload["data"]

    async def fetch_issues_and_prs(self, owner: str, repo: str, since: str | None = None) -> dict:
        """Bulk fetch all open issues and PRs with pagination."""
        issues: list[dict] = []
        pull_requests: list[dict] = []
        after_issues: str | None = None
        after_prs: str | None = None
        has_next_issues = True
        has_next_prs = True

        while has_next_issues or has_next_prs:
            variables: dict = {
                "owner": owner,
                "repo": repo,
                "afterIssues": after_issues,
                "afterPRs": after_prs,
            }
            data = await self._execute(ISSUES_AND_PRS_QUERY, variables)
            repo_data = data["repository"]

            issues_page = repo_data["issues"]
            issues.extend(issues_page["nodes"])
            has_next_issues = issues_page["pageInfo"]["hasNextPage"]
            after_issues = issues_page["pageInfo"]["endCursor"] if has_next_issues else after_issues

            prs_page = repo_data["pullRequests"]
            pull_requests.extend(prs_page["nodes"])
            has_next_prs = prs_page["pageInfo"]["hasNextPage"]
            after_prs = prs_page["pageInfo"]["endCursor"] if has_next_prs else after_prs

        return {"issues": issues, "pull_requests": pull_requests}

    async def fetch_pr_detail(self, owner: str, repo: str, number: int) -> dict:
        """Fetch detailed PR info including review state."""
        data = await self._execute(PR_DETAIL_QUERY, {"owner": owner, "repo": repo, "number": number})
        return data["repository"]["pullRequest"]

    async def fetch_pr_files(self, owner: str, repo: str, number: int) -> list[dict]:
        """Fetch changed files for a PR via REST fallback (GraphQL lacks diff content)."""
        files: list[dict] = []
        page = 1
        while True:
            response = await self.client.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/files",
                params={"per_page": 100, "page": page},
                headers={"Authorization": f"token {self.token}", "Accept": "application/vnd.github+json"},
            )
            response.raise_for_status()
            batch = response.json()
            if not batch:
                break
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return files

    async def fetch_discussion(self, owner: str, repo: str, category: str, title: str) -> dict | None:
        """Find a discussion by category ID and title."""
        after: str | None = None
        while True:
            variables: dict = {"owner": owner, "repo": repo, "category": category, "after": after}
            data = await self._execute(DISCUSSION_QUERY, variables)
            discussions = data["repository"]["discussions"]
            for node in discussions["nodes"]:
                if node["title"].lower() == title.lower():
                    return node
            if not discussions["pageInfo"]["hasNextPage"]:
                break
            after = discussions["pageInfo"]["endCursor"]
        return None

    async def get_discussion_categories(self, owner: str, repo: str) -> list[dict]:
        """List discussion categories for a repository."""
        data = await self._execute(DISCUSSION_CATEGORIES_QUERY, {"owner": owner, "repo": repo})
        return data["repository"]["discussionCategories"]["nodes"]

    async def create_discussion(self, repository_id: str, category_id: str, title: str, body: str) -> dict:
        """Create a new discussion via GraphQL mutation."""
        data = await self._execute(
            CREATE_DISCUSSION_MUTATION,
            {"repositoryId": repository_id, "categoryId": category_id, "title": title, "body": body},
        )
        return data["createDiscussion"]["discussion"]

    async def update_discussion(self, discussion_id: str, body: str) -> dict:
        """Update a discussion body via GraphQL mutation."""
        data = await self._execute(UPDATE_DISCUSSION_MUTATION, {"discussionId": discussion_id, "body": body})
        return data["updateDiscussion"]["discussion"]

    # Aliases used by stores
    async def list_discussions(self, owner: str, repo: str, category: str = "") -> list[dict]:
        """List discussions, optionally filtered by category name."""
        query = """
        query($owner: String!, $repo: String!, $after: String) {
          repository(owner: $owner, name: $repo) {
            discussions(first: 50, after: $after) {
              pageInfo { hasNextPage endCursor }
              nodes { id title body category { name } url }
            }
          }
        }
        """
        results = []
        after = None
        while True:
            data = await self._execute(query, {"owner": owner, "repo": repo, "after": after})
            nodes = data["repository"]["discussions"]["nodes"]
            for node in nodes:
                if not category or node.get("category", {}).get("name") == category:
                    results.append(node)
            page_info = data["repository"]["discussions"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            after = page_info["endCursor"]
        return results

    async def list_discussion_categories(self, owner: str, repo: str) -> list[dict]:
        """Alias for get_discussion_categories."""
        return await self.get_discussion_categories(owner, repo)

    async def update_discussion_body(self, discussion_id: str, body: str) -> str:
        """Update discussion body. Returns URL."""
        result = await self.update_discussion(discussion_id, body)
        return result.get("url", "")

    async def get_repository_id(self, owner: str, repo: str) -> str:
        """Get the node ID of a repository (needed for mutations)."""
        query = """
        query($owner: String!, $repo: String!) {
          repository(owner: $owner, name: $repo) { id }
        }
        """
        data = await self._execute(query, {"owner": owner, "repo": repo})
        return data["repository"]["id"]

    async def close(self):
        await self.client.aclose()
