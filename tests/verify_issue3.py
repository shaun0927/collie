"""
Real verification script for Issue #3: GitHub API Integration Layer.
Tests all 17 checklist items against live GitHub API.
Uses shaun0927/collie (owned repo) with cleanup after each write test.
"""

import asyncio
import base64
import os
import subprocess
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import httpx

from collie.auth.providers import AuthError, GitHubAuth, LLMAuth
from collie.github.graphql import GitHubGraphQL
from collie.github.rest import _RETRY_STATUSES, GitHubREST, _request_with_retry


def _has_token():
    if os.environ.get("GITHUB_TOKEN"):
        return True
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
        return bool(r.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not _has_token(), reason="No GitHub token — integration test")

OWNER = "shaun0927"
REPO = "collie"
LARGE_OWNER = "cli"
LARGE_REPO = "cli"

results = {}


def report(key: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    results[key] = passed
    print(f"  [{status}] {key}")
    if detail:
        print(f"         {detail}")


async def test_01():
    """GITHUB_TOKEN env auth."""
    try:
        auth = GitHubAuth.from_env()
        gql = GitHubGraphQL(auth.token)
        data = await gql._execute("query { viewer { login } }", {})
        login = data["viewer"]["login"]
        report("01_github_token_auth", True, f"Authenticated as: {login}")
        await gql.close()
    except Exception as e:
        report("01_github_token_auth", False, str(e))


async def test_02():
    """gh CLI fallback auth."""
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            token = result.stdout.strip()
            gql = GitHubGraphQL(token)
            data = await gql._execute("query { viewer { login } }", {})
            report("02_gh_cli_fallback", True, f"gh CLI token works: {data['viewer']['login']}")
            await gql.close()
        else:
            report("02_gh_cli_fallback", False, "gh auth token failed")
    except Exception as e:
        report("02_gh_cli_fallback", False, str(e))


async def test_03_04():
    """Bulk fetch 500+ AND pagination test (combined to save API calls)."""
    auth = GitHubAuth.from_env()
    gql = GitHubGraphQL(auth.token)
    try:
        data = await gql.fetch_issues_and_prs(LARGE_OWNER, LARGE_REPO)
        n_issues = len(data["issues"])
        n_prs = len(data["pull_requests"])
        total = n_issues + n_prs
        paginated = n_issues > 100 or n_prs > 100
        report(
            "03_bulk_fetch_500",
            total >= 500,
            f"{n_issues} issues + {n_prs} PRs = {total} from {LARGE_OWNER}/{LARGE_REPO}",
        )
        report("04_graphql_pagination", paginated, f"Issues: {n_issues}, PRs: {n_prs} — multi-page: {paginated}")
    except Exception as e:
        report("03_bulk_fetch_500", False, str(e))
        report("04_graphql_pagination", False, str(e))
    finally:
        await gql.close()


async def test_05():
    """PR diff fetch (small + large)."""
    auth = GitHubAuth.from_env()
    gql = GitHubGraphQL(auth.token)
    try:
        # Use existing merged PRs in collie repo (small)
        files_small = await gql.fetch_pr_files(OWNER, REPO, 22)
        # Use a known merged PR from cli/cli (larger)
        files_large = await gql.fetch_pr_files("cli", "cli", 13048)
        both_ok = len(files_small) > 0 and len(files_large) > 0
        report(
            "05_pr_diff_fetch",
            both_ok,
            f"Small ({OWNER}/{REPO}#22): {len(files_small)} files, Large (cli/cli#13048): {len(files_large)} files",
        )
    except Exception as e:
        report("05_pr_diff_fetch", False, str(e))
    finally:
        await gql.close()


async def test_06():
    """Discussion CRUD: create, read, update — then cleanup."""
    auth = GitHubAuth.from_env()
    gql = GitHubGraphQL(auth.token)
    try:
        categories = await gql.get_discussion_categories(OWNER, REPO)
        if not categories:
            report("06_discussion_crud", False, "No discussion categories found")
            return
        cat = categories[0]
        repo_id = await gql.get_repository_id(OWNER, REPO)
        title = f"[Test] Issue#3 CRUD {int(time.time())}"
        created = await gql.create_discussion(repo_id, cat["id"], title, "Test body.")
        found = await gql.fetch_discussion(OWNER, REPO, cat["id"], title)
        read_ok = found is not None and found["id"] == created["id"]
        updated = await gql.update_discussion(created["id"], "Updated body.")
        update_ok = updated.get("body") == "Updated body."
        # Cleanup: delete via gh CLI
        subprocess.run(
            ["gh", "api", "--method", "DELETE", f"/repos/{OWNER}/{REPO}/discussions/{created['number']}"],
            capture_output=True,
            timeout=10,
        )
        report(
            "06_discussion_crud",
            read_ok and update_ok,
            f"#{created['number']}: Read={'OK' if read_ok else 'FAIL'}, Update={'OK' if update_ok else 'FAIL'}",
        )
    except Exception as e:
        report("06_discussion_crud", False, str(e))
    finally:
        await gql.close()


async def test_07():
    """Enable discussions (admin)."""
    auth = GitHubAuth.from_env()
    rest = GitHubREST(auth.token)
    try:
        result = await rest.enable_discussions(OWNER, REPO)
        report("07_enable_discussions", result is True, f"returned {result}")
    except Exception as e:
        report("07_enable_discussions", False, str(e))
    finally:
        await rest.close()


async def test_08():
    """Non-admin discussions — graceful failure."""
    auth = GitHubAuth.from_env()
    rest = GitHubREST(auth.token)
    try:
        result = await rest.enable_discussions("torvalds", "linux")
        report("08_discussions_no_admin", result is False, f"torvalds/linux returned {result} (expected False)")
    except Exception as e:
        report("08_discussions_no_admin", False, str(e))
    finally:
        await rest.close()


async def test_09():
    """PR merge (create branch, commit, PR, merge, cleanup)."""
    auth = GitHubAuth.from_env()
    rest = GitHubREST(auth.token)
    try:
        resp = await rest.client.get(f"/repos/{OWNER}/{REPO}/git/ref/heads/main")
        resp.raise_for_status()
        sha = resp.json()["object"]["sha"]
        ts = int(time.time())
        branch = f"test-merge-{ts}"
        await rest.client.post(f"/repos/{OWNER}/{REPO}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": sha})
        content = base64.b64encode(f"# merge test {ts}\n".encode()).decode()
        await rest.client.put(
            f"/repos/{OWNER}/{REPO}/contents/_test_merge_{ts}.md",
            json={"message": "test: merge verify", "content": content, "branch": branch},
        )
        resp = await rest.client.post(
            f"/repos/{OWNER}/{REPO}/pulls",
            json={"title": f"[Test] Merge verify {ts}", "body": "Auto cleanup.", "head": branch, "base": "main"},
        )
        resp.raise_for_status()
        pr_num = resp.json()["number"]
        merge = await rest.merge_pr(OWNER, REPO, pr_num, method="squash")
        merged = merge.get("merged", False)
        # Cleanup: delete branch
        await rest.client.delete(f"/repos/{OWNER}/{REPO}/git/refs/heads/{branch}")
        # Delete the test file from main via PUT-style delete (httpx delete doesn't support json body)
        resp2 = await rest.client.get(f"/repos/{OWNER}/{REPO}/contents/_test_merge_{ts}.md")
        if resp2.status_code == 200:
            file_sha = resp2.json()["sha"]
            await rest.client.request(
                "DELETE",
                f"/repos/{OWNER}/{REPO}/contents/_test_merge_{ts}.md",
                json={"message": "cleanup: remove test file", "sha": file_sha},
            )
        report("09_pr_merge", merged, f"PR #{pr_num} merged: {merged}")
    except Exception as e:
        report("09_pr_merge", False, str(e))
    finally:
        await rest.close()


async def test_10():
    """Issue close + comment."""
    auth = GitHubAuth.from_env()
    rest = GitHubREST(auth.token)
    try:
        resp = await rest.client.post(
            f"/repos/{OWNER}/{REPO}/issues", json={"title": "[Test] close+comment verify", "body": "Auto cleanup."}
        )
        resp.raise_for_status()
        num = resp.json()["number"]
        comment = await rest.add_comment(OWNER, REPO, num, "Verification comment.")
        comment_ok = "id" in comment
        closed = await rest.close_issue(OWNER, REPO, num)
        close_ok = closed.get("state") == "closed"
        report(
            "10_issue_close_comment",
            comment_ok and close_ok,
            f"#{num}: comment={'OK' if comment_ok else 'FAIL'}, close={'OK' if close_ok else 'FAIL'}",
        )
    except Exception as e:
        report("10_issue_close_comment", False, str(e))
    finally:
        await rest.close()


async def test_11():
    """Label addition."""
    auth = GitHubAuth.from_env()
    rest = GitHubREST(auth.token)
    try:
        resp = await rest.client.post(
            f"/repos/{OWNER}/{REPO}/issues", json={"title": "[Test] label verify", "body": "Auto cleanup."}
        )
        resp.raise_for_status()
        num = resp.json()["number"]
        try:
            await rest.client.post(
                f"/repos/{OWNER}/{REPO}/labels", json={"name": "verification-test", "color": "0e8a16"}
            )
        except Exception:
            pass
        result = await rest.add_labels(OWNER, REPO, num, ["verification-test"])
        labels = [lb["name"] for lb in result] if isinstance(result, list) else []
        ok = "verification-test" in labels
        await rest.close_issue(OWNER, REPO, num)
        report("11_label_addition", ok, f"#{num}: labels={labels}")
    except Exception as e:
        report("11_label_addition", False, str(e))
    finally:
        await rest.close()


async def test_12():
    """429 retry mechanism — functional mock test."""
    has_429 = 429 in _RETRY_STATUSES
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(429, headers={"retry-after": "0.05"}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        resp = await _request_with_retry(client, "GET", "https://api.github.com/test")
        retried = call_count == 3 and resp.status_code == 200
        report(
            "12_retry_on_429",
            has_429 and retried,
            f"429 in statuses: {has_429}, attempts: {call_count}, final status: {resp.status_code}",
        )
    except Exception as e:
        report("12_retry_on_429", False, str(e))
    finally:
        await client.aclose()


async def test_13():
    """Rate limit remaining tracking."""
    auth = GitHubAuth.from_env()
    gql = GitHubGraphQL(auth.token)
    try:
        before = gql.rate_limit_remaining
        await gql._execute("query { viewer { login } }", {})
        after = gql.rate_limit_remaining
        report("13_rate_limit_logging", before is None and after is not None, f"Before: {before}, After: {after}")
    except Exception as e:
        report("13_rate_limit_logging", False, str(e))
    finally:
        await gql.close()


async def test_14():
    """ANTHROPIC_API_KEY auth — verify code path works."""
    real_key = os.environ.get("ANTHROPIC_API_KEY")
    if real_key:
        auth = LLMAuth.from_env()
        report(
            "14_anthropic_api_key",
            auth.api_key == real_key and auth.provider == "anthropic",
            f"Provider: {auth.provider}, key: {auth.api_key[:12]}...",
        )
    else:
        # Key not in this shell — verify the code path with a test value
        test_key = "sk-ant-test-verification-key-12345"
        os.environ["ANTHROPIC_API_KEY"] = test_key
        try:
            auth = LLMAuth.from_env()
            ok = auth.api_key == test_key and auth.provider == "anthropic"
            report(
                "14_anthropic_api_key",
                ok,
                f"Code path verified with test key: provider={auth.provider}, key_match={ok}",
            )
        finally:
            del os.environ["ANTHROPIC_API_KEY"]


async def test_15():
    """Missing API key error message."""
    original = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        LLMAuth.from_env()
        report("15_api_key_error_msg", False, "No exception raised")
    except AuthError as e:
        msg = str(e)
        ok = "ANTHROPIC_API_KEY" in msg and "export" in msg
        report("15_api_key_error_msg", ok, f"Message: {msg[:120]}")
    except Exception as e:
        report("15_api_key_error_msg", False, f"{type(e).__name__}: {e}")
    finally:
        if original:
            os.environ["ANTHROPIC_API_KEY"] = original


async def test_16():
    """Timeout 30s on all clients."""
    auth = GitHubAuth.from_env()
    gql = GitHubGraphQL(auth.token)
    rest = GitHubREST(auth.token)
    try:
        t1 = gql.client.timeout
        t2 = rest.client.timeout
        t3 = rest._graphql_client.timeout
        ok = all(t.connect == 30.0 and t.read == 30.0 for t in [t1, t2, t3])
        report("16_timeout_30s", ok, f"GQL: {t1}, REST: {t2}, REST-GQL: {t3}")
    except Exception as e:
        report("16_timeout_30s", False, str(e))
    finally:
        await gql.close()
        await rest.close()


async def test_17():
    """Network error produces clean exception, not raw traceback."""
    gql = GitHubGraphQL("fake")
    gql.client = httpx.AsyncClient(
        base_url="https://localhost:1", headers={"Authorization": "bearer fake"}, timeout=2.0
    )
    try:
        await gql._execute("query { viewer { login } }", {})
        report("17_network_error", False, "No error raised")
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        report("17_network_error", True, f"{type(e).__name__}: {str(e)[:80]}")
    except Exception as e:
        report("17_network_error", len(str(e)) < 500, f"{type(e).__name__}: {str(e)[:80]}")
    finally:
        await gql.close()


async def main():
    print("=" * 70)
    print("Issue #3 Verification: GitHub API Integration Layer")
    print(f"Target: {OWNER}/{REPO} | Large repo: {LARGE_OWNER}/{LARGE_REPO}")
    print("=" * 70)

    tests = [
        ("01 GITHUB_TOKEN Auth", test_01),
        ("02 gh CLI Fallback", test_02),
        ("03+04 Bulk Fetch + Pagination", test_03_04),
        ("05 PR Diff Fetch", test_05),
        ("06 Discussion CRUD", test_06),
        ("07 Enable Discussions", test_07),
        ("08 No-Admin Error", test_08),
        ("09 PR Merge", test_09),
        ("10 Issue Close+Comment", test_10),
        ("11 Label Addition", test_11),
        ("12 Retry on 429", test_12),
        ("13 Rate Limit Tracking", test_13),
        ("14 ANTHROPIC_API_KEY", test_14),
        ("15 Missing Key Error", test_15),
        ("16 Timeout 30s", test_16),
        ("17 Network Error", test_17),
    ]

    for name, fn in tests:
        print(f"\n--- {name} ---")
        try:
            await fn()
        except Exception as e:
            print(f"  [FAIL] Unexpected: {e}")

    print("\n" + "=" * 70)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"RESULTS: {passed}/{total} passed")
    for key, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'} {key}")
    print("=" * 70)
    return passed, total


if __name__ == "__main__":
    p, t = asyncio.run(main())
    sys.exit(0 if p == t else 1)
