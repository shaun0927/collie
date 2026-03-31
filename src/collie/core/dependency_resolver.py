"""Resolve execution order based on PR↔Issue dependencies."""

from __future__ import annotations

import re


class DependencyResolver:
    """Analyze 'fixes #N' / 'closes #N' keywords to determine execution order."""

    LINK_PATTERNS = [
        re.compile(r"(?:fix(?:es)?|close[sd]?|resolve[sd]?)\s+#(\d+)", re.IGNORECASE),
    ]

    def resolve_order(self, items: list[dict]) -> list[dict]:
        """Sort items so PRs that fix issues come before those issues.

        Logic: If PR #101 has 'fixes #50', PR #101 should be merged before
        Issue #50 is closed (because merging the PR auto-closes the issue).

        Items that aren't referenced come after linked ones.
        PRs come before Issues in general.
        """
        # Build dependency graph
        pr_fixes_issue: dict[int, list[int]] = {}  # pr_number -> [issue_numbers]
        issue_fixed_by: dict[int, int] = {}  # issue_number -> pr_number

        for item in items:
            body = item.get("body", "") or ""
            number = item.get("number", 0)
            if "additions" in item:  # It's a PR
                for pattern in self.LINK_PATTERNS:
                    for match in pattern.finditer(body):
                        issue_num = int(match.group(1))
                        pr_fixes_issue.setdefault(number, []).append(issue_num)
                        issue_fixed_by[issue_num] = number

        # Sort: linked PRs first, then other PRs, then linked issues, then other issues
        linked_prs = []
        other_prs = []
        linked_issues = []
        other_issues = []

        for item in items:
            num = item.get("number", 0)
            is_pr = "additions" in item
            if is_pr:
                if num in pr_fixes_issue:
                    linked_prs.append(item)
                else:
                    other_prs.append(item)
            else:
                if num in issue_fixed_by:
                    linked_issues.append(item)
                else:
                    other_issues.append(item)

        return linked_prs + other_prs + linked_issues + other_issues
