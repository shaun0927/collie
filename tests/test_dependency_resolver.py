"""Tests for DependencyResolver."""

from collie.core.dependency_resolver import DependencyResolver


def make_pr(number: int, body: str = "") -> dict:
    return {"number": number, "additions": 1, "body": body}


def make_issue(number: int, body: str = "") -> dict:
    return {"number": number, "body": body}


def test_empty_list_returns_empty():
    resolver = DependencyResolver()
    assert resolver.resolve_order([]) == []


def test_prs_without_links_maintain_relative_order():
    resolver = DependencyResolver()
    items = [make_pr(10), make_pr(20), make_pr(30)]
    result = resolver.resolve_order(items)
    assert [i["number"] for i in result] == [10, 20, 30]


def test_pr_with_fixes_comes_before_issue():
    resolver = DependencyResolver()
    issue = make_issue(50)
    pr = make_pr(101, body="This fixes #50")
    result = resolver.resolve_order([issue, pr])
    numbers = [i["number"] for i in result]
    assert numbers.index(101) < numbers.index(50)


def test_closes_pattern():
    resolver = DependencyResolver()
    issue = make_issue(50)
    pr = make_pr(101, body="closes #50")
    result = resolver.resolve_order([issue, pr])
    numbers = [i["number"] for i in result]
    assert numbers.index(101) < numbers.index(50)


def test_resolves_pattern():
    resolver = DependencyResolver()
    issue = make_issue(50)
    pr = make_pr(101, body="resolves #50")
    result = resolver.resolve_order([issue, pr])
    numbers = [i["number"] for i in result]
    assert numbers.index(101) < numbers.index(50)


def test_closed_pattern():
    resolver = DependencyResolver()
    issue = make_issue(50)
    pr = make_pr(101, body="closed #50")
    result = resolver.resolve_order([issue, pr])
    numbers = [i["number"] for i in result]
    assert numbers.index(101) < numbers.index(50)


def test_mixed_prs_and_issues_sorted_correctly():
    resolver = DependencyResolver()
    # linked PR, other PR, linked issue, other issue
    linked_pr = make_pr(101, body="fixes #50")
    other_pr = make_pr(102)
    linked_issue = make_issue(50)
    other_issue = make_issue(99)

    result = resolver.resolve_order([other_issue, linked_issue, other_pr, linked_pr])
    numbers = [i["number"] for i in result]

    # linked PR before other PR
    assert numbers.index(101) < numbers.index(102)
    # PRs before issues
    assert numbers.index(101) < numbers.index(50)
    assert numbers.index(102) < numbers.index(99)
    # linked issue before other issue
    assert numbers.index(50) < numbers.index(99)


def test_issues_without_linked_pr_are_other_issues():
    resolver = DependencyResolver()
    issue = make_issue(77)
    pr = make_pr(200)
    result = resolver.resolve_order([issue, pr])
    numbers = [i["number"] for i in result]
    # PR comes before issue
    assert numbers.index(200) < numbers.index(77)


def test_multiple_linked_issues_in_one_pr():
    resolver = DependencyResolver()
    pr = make_pr(101, body="fixes #10, fixes #20")
    issue_10 = make_issue(10)
    issue_20 = make_issue(20)
    result = resolver.resolve_order([issue_10, issue_20, pr])
    numbers = [i["number"] for i in result]
    assert numbers.index(101) < numbers.index(10)
    assert numbers.index(101) < numbers.index(20)
