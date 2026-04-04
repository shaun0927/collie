"""Tests for GitHub GraphQL and REST clients."""

import httpx
import pytest  # noqa: F401

from collie.github.graphql import GitHubGraphQL, GitHubGraphQLError
from collie.github.rest import GitHubREST

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_transport(responses: list[httpx.Response]):
    """Return an httpx MockTransport that yields responses in order."""
    calls = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return next(calls)

    return httpx.MockTransport(handler)


def _gql_response(data: dict, status: int = 200, headers: dict | None = None) -> httpx.Response:
    h = {"content-type": "application/json"}
    if headers:
        h.update(headers)
    return httpx.Response(status, json={"data": data}, headers=h)


def _rest_response(data, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data, headers={"content-type": "application/json"})


# ---------------------------------------------------------------------------
# GitHubGraphQL — fetch_issues_and_prs pagination
# ---------------------------------------------------------------------------


def _issues_prs_page(
    issues_nodes: list,
    prs_nodes: list,
    issues_has_next: bool = False,
    prs_has_next: bool = False,
    issues_cursor: str | None = None,
    prs_cursor: str | None = None,
) -> dict:
    return {
        "repository": {
            "issues": {
                "pageInfo": {"hasNextPage": issues_has_next, "endCursor": issues_cursor},
                "nodes": issues_nodes,
            },
            "pullRequests": {
                "pageInfo": {"hasNextPage": prs_has_next, "endCursor": prs_cursor},
                "nodes": prs_nodes,
            },
        }
    }


@pytest.mark.asyncio
async def test_fetch_issues_and_prs_single_page():
    issue = {"number": 1, "title": "Bug", "body": "Issue body", "authorAssociation": "NONE", "state": "OPEN"}
    pr = {
        "number": 2,
        "title": "Fix",
        "body": "Fixes #1",
        "authorAssociation": "MEMBER",
        "isDraft": False,
        "reviewDecision": "APPROVED",
        "mergeable": "MERGEABLE",
        "baseRefName": "main",
        "headRefName": "feature",
        "autoMergeRequest": {"enabledAt": "2026-01-01T00:00:00Z"},
        "closingIssuesReferences": {"nodes": [{"number": 1, "title": "Bug"}]},
        "repository": {"name": "repo", "owner": {"login": "owner"}},
        "commits": {"nodes": [{"commit": {"oid": "abc123", "statusCheckRollup": {"state": "SUCCESS"}}}]},
        "state": "OPEN",
    }
    page = _issues_prs_page([issue], [pr])

    transport = _make_transport([_gql_response(page, headers={"x-ratelimit-remaining": "4999"})])
    gql = GitHubGraphQL(token="tok")
    gql.client = httpx.AsyncClient(transport=transport, base_url="https://api.github.com/graphql")

    result = await gql.fetch_issues_and_prs("owner", "repo")
    assert result["issues"] == [issue]
    assert result["pull_requests"] == [pr]
    assert result["pull_requests"][0]["reviewDecision"] == "APPROVED"
    assert result["pull_requests"][0]["closingIssuesReferences"]["nodes"][0]["number"] == 1
    assert gql.rate_limit_remaining == 4999
    await gql.close()


@pytest.mark.asyncio
async def test_fetch_issues_and_prs_pagination():
    """Two pages: issues paginate, PRs done on first page."""
    issue1 = {"number": 1, "title": "First"}
    issue2 = {"number": 3, "title": "Second"}
    pr = {"number": 2, "title": "PR"}

    page1 = _issues_prs_page([issue1], [pr], issues_has_next=True, issues_cursor="cur1")
    page2 = _issues_prs_page([issue2], [], issues_has_next=False)

    transport = _make_transport([_gql_response(page1), _gql_response(page2)])
    gql = GitHubGraphQL(token="tok")
    gql.client = httpx.AsyncClient(transport=transport, base_url="https://api.github.com/graphql")

    result = await gql.fetch_issues_and_prs("owner", "repo")
    assert len(result["issues"]) == 2
    assert result["issues"][0] == issue1
    assert result["issues"][1] == issue2
    assert result["pull_requests"] == [pr]
    await gql.close()


@pytest.mark.asyncio
async def test_graphql_error_raises():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"errors": [{"message": "Not found"}]}))
    gql = GitHubGraphQL(token="tok")
    gql.client = httpx.AsyncClient(transport=transport, base_url="https://api.github.com/graphql")

    with pytest.raises(GitHubGraphQLError, match="GraphQL errors"):
        await gql.fetch_issues_and_prs("owner", "repo")
    await gql.close()


# ---------------------------------------------------------------------------
# GitHubREST — basic operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_pr():
    rest = GitHubREST(token="tok")
    transport = _make_transport([_rest_response({"merged": True, "message": "Pull Request successfully merged"})])
    rest.client = httpx.AsyncClient(transport=transport, base_url="https://api.github.com")

    result = await rest.merge_pr("owner", "repo", 42, method="squash")
    assert result["merged"] is True
    await rest.close()


@pytest.mark.asyncio
async def test_close_issue():
    rest = GitHubREST(token="tok")
    transport = _make_transport([_rest_response({"number": 5, "state": "closed"})])
    rest.client = httpx.AsyncClient(transport=transport, base_url="https://api.github.com")

    result = await rest.close_issue("owner", "repo", 5)
    assert result["state"] == "closed"
    await rest.close()


@pytest.mark.asyncio
async def test_close_pr():
    rest = GitHubREST(token="tok")
    transport = _make_transport([_rest_response({"number": 7, "state": "closed"})])
    rest.client = httpx.AsyncClient(transport=transport, base_url="https://api.github.com")

    result = await rest.close_pr("owner", "repo", 7)
    assert result["state"] == "closed"
    await rest.close()


@pytest.mark.asyncio
async def test_add_comment():
    rest = GitHubREST(token="tok")
    transport = _make_transport([_rest_response({"id": 1, "body": "hello"})])
    rest.client = httpx.AsyncClient(transport=transport, base_url="https://api.github.com")

    result = await rest.add_comment("owner", "repo", 10, "hello")
    assert result["body"] == "hello"
    await rest.close()


@pytest.mark.asyncio
async def test_add_labels():
    rest = GitHubREST(token="tok")
    transport = _make_transport([_rest_response([{"name": "bug"}, {"name": "help wanted"}])])
    rest.client = httpx.AsyncClient(transport=transport, base_url="https://api.github.com")

    result = await rest.add_labels("owner", "repo", 3, ["bug", "help wanted"])
    assert len(result) == 2
    await rest.close()


@pytest.mark.asyncio
async def test_get_repo_content_base64():
    import base64

    encoded = base64.b64encode(b"# Contributing\nPlease read this.").decode()
    rest = GitHubREST(token="tok")
    transport = _make_transport([_rest_response({"encoding": "base64", "content": encoded})])
    rest.client = httpx.AsyncClient(transport=transport, base_url="https://api.github.com")

    result = await rest.get_repo_content("owner", "repo", "CONTRIBUTING.md")
    assert result == "# Contributing\nPlease read this."
    await rest.close()


@pytest.mark.asyncio
async def test_get_repo_content_not_found():
    rest = GitHubREST(token="tok")
    transport = _make_transport([httpx.Response(404, json={"message": "Not Found"})])
    rest.client = httpx.AsyncClient(transport=transport, base_url="https://api.github.com")

    result = await rest.get_repo_content("owner", "repo", "NONEXISTENT.md")
    assert result is None
    await rest.close()


# ---------------------------------------------------------------------------
# Retry on 429
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_on_429(monkeypatch):
    """REST client retries on 429 and succeeds on the second attempt."""
    # Patch asyncio.sleep to avoid real delay
    import collie.github.rest as rest_module

    async def _noop_sleep(_):
        pass

    monkeypatch.setattr(rest_module.asyncio, "sleep", _noop_sleep)

    calls = [
        httpx.Response(429, json={"message": "rate limited"}, headers={"retry-after": "0"}),
        _rest_response({"number": 1, "state": "closed"}),
    ]
    transport = _make_transport(calls)

    rest = GitHubREST(token="tok")
    rest.client = httpx.AsyncClient(transport=transport, base_url="https://api.github.com")

    result = await rest.close_issue("owner", "repo", 1)
    assert result["state"] == "closed"
    await rest.close()


# ---------------------------------------------------------------------------
# Headers verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graphql_auth_header():
    """GraphQL client sends bearer token."""
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.headers.get("authorization"))
        return _gql_response(_issues_prs_page([], []))

    gql = GitHubGraphQL(token="mytoken")
    gql.client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.github.com/graphql",
        headers={"Authorization": "bearer mytoken"},
    )

    await gql.fetch_issues_and_prs("owner", "repo")
    assert captured[0] == "bearer mytoken"
    await gql.close()


@pytest.mark.asyncio
async def test_get_viewer_repository_permission():
    payload = {"viewer": {"login": "maintainer"}, "repository": {"viewerPermission": "WRITE"}}
    transport = _make_transport([_gql_response(payload)])
    gql = GitHubGraphQL(token="tok")
    gql.client = httpx.AsyncClient(transport=transport, base_url="https://api.github.com/graphql")

    viewer, permission = await gql.get_viewer_repository_permission("owner", "repo")
    assert viewer == "maintainer"
    assert permission == "WRITE"
    await gql.close()


@pytest.mark.asyncio
async def test_rest_auth_header():
    """REST client sends token auth header."""
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.headers.get("authorization"))
        return _rest_response({"number": 1, "state": "closed"})

    rest = GitHubREST(token="mytoken")
    rest.client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.github.com",
        headers={"Authorization": "token mytoken"},
    )

    await rest.close_issue("owner", "repo", 1)
    assert captured[0] == "token mytoken"
    await rest.close()
