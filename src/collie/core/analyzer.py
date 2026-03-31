"""Collie bark analysis engine — T1/T2/T3 tiers + Issue analyzer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from collie.core.models import (
    HardRule,
    ItemType,
    Philosophy,
    Recommendation,
    RecommendationAction,
)
from collie.core.prompts import ISSUE_ANALYZE_PROMPT, T2_SUMMARIZE_PROMPT, T3_DEEP_REVIEW_PROMPT


class Tier(str, Enum):
    T1 = "t1"
    T2 = "t2"
    T3 = "t3"


@dataclass
class AnalysisResult:
    recommendation: Recommendation
    tier: Tier
    cost_usd: float = 0.0
    tokens_used: int = 0


class T1Scanner:
    """Rule-based scanner. No LLM calls. Zero cost."""

    def scan(self, item: dict, philosophy: Philosophy) -> AnalysisResult | None:
        """Apply hard rules. Returns result if decision made, None if escalation needed."""
        number = item["number"]
        item_type = ItemType.PR if "additions" in item else ItemType.ISSUE

        # Check CI status (PRs only)
        if item_type == ItemType.PR:
            ci_state = self._get_ci_state(item)
            if ci_state == "FAILURE":
                for rule in philosophy.hard_rules:
                    if rule.condition == "ci_failed" and rule.action == "reject":
                        return AnalysisResult(
                            recommendation=Recommendation(
                                number=number,
                                item_type=item_type,
                                action=RecommendationAction.CLOSE,
                                reason="CI failed — hard rule: ci_failed → reject",
                                title=item.get("title", ""),
                            ),
                            tier=Tier.T1,
                        )

            # Check for trivial docs-only PR
            if self._is_docs_only(item) and ci_state == "SUCCESS":
                reviews = self._get_review_count(item)
                if reviews >= 1:
                    return AnalysisResult(
                        recommendation=Recommendation(
                            number=number,
                            item_type=item_type,
                            action=RecommendationAction.MERGE,
                            reason="Documentation-only PR, CI passed, has reviews",
                            title=item.get("title", ""),
                            analysis_coverage="100% (docs only)",
                        ),
                        tier=Tier.T1,
                    )

        # Check each hard rule
        for rule in philosophy.hard_rules:
            if self._check_hard_rule(rule, item):
                return AnalysisResult(
                    recommendation=Recommendation(
                        number=number,
                        item_type=item_type,
                        action=RecommendationAction.CLOSE if rule.action == "reject" else RecommendationAction.HOLD,
                        reason=f"Hard rule: {rule.condition} → {rule.action}. {rule.description}",
                        title=item.get("title", ""),
                    ),
                    tier=Tier.T1,
                )

        # Cannot decide at T1
        return None

    def _get_ci_state(self, item: dict) -> str:
        """Extract CI status from PR data."""
        commits = item.get("commits", {}).get("nodes", [])
        if commits:
            rollup = commits[0].get("commit", {}).get("statusCheckRollup", {})
            return rollup.get("state", "UNKNOWN")
        return "UNKNOWN"

    def _get_review_count(self, item: dict) -> int:
        """Count approved reviews."""
        reviews = item.get("reviews", {}).get("nodes", [])
        return sum(1 for r in reviews if r.get("state") == "APPROVED")

    def _is_docs_only(self, item: dict) -> bool:
        """Check if PR only changes documentation files."""
        title = item.get("title", "").lower()
        changed_files = item.get("changedFiles", 0)
        if changed_files <= 3 and any(word in title for word in ["doc", "readme", "typo", "comment", "changelog"]):
            return True
        return False

    def _check_hard_rule(self, rule: HardRule, item: dict) -> bool:
        """Check if a hard rule is violated."""
        if rule.condition == "ci_failed":
            return self._get_ci_state(item) == "FAILURE"
        if rule.condition == "no_tests":
            # Heuristic: can't determine without file list at T1
            return False
        if rule.condition == "no_description":
            body = item.get("body", "") or ""
            return len(body.strip()) < 20
        return False


class T2Summarizer:
    """Smart summary tier. One LLM call per item."""

    def __init__(self, llm_client=None):
        """llm_client should have a method: async chat(system, user) -> str"""
        self.llm = llm_client

    async def summarize(self, item: dict, philosophy: Philosophy) -> AnalysisResult:
        """Summarize PR/Issue and make initial judgment."""
        number = item["number"]
        item_type = ItemType.PR if "additions" in item else ItemType.ISSUE

        # Build context for LLM
        user_prompt = self._build_user_prompt(item, philosophy)

        if self.llm is None:
            # No LLM available — return hold
            return AnalysisResult(
                recommendation=Recommendation(
                    number=number,
                    item_type=item_type,
                    action=RecommendationAction.HOLD,
                    reason="T2 analysis unavailable (no LLM configured)",
                    title=item.get("title", ""),
                ),
                tier=Tier.T2,
            )

        # Call LLM
        response = await self.llm.chat(
            system=T2_SUMMARIZE_PROMPT,
            user=user_prompt,
        )

        # Parse response
        result = self._parse_response(response, number, item_type, item)
        return result

    def _build_user_prompt(self, item: dict, philosophy: Philosophy) -> str:
        """Build the user prompt with item details + philosophy context."""
        parts = [
            f"# {'Pull Request' if 'additions' in item else 'Issue'} #{item['number']}: {item.get('title', '')}",
            f"\n**Author:** {item.get('author', {}).get('login', 'unknown')}",
            f"**Labels:** {', '.join(n.get('name', '') for n in item.get('labels', {}).get('nodes', []))}",
        ]
        if "additions" in item:
            parts.append(
                f"**Changes:** +{item.get('additions', 0)} -{item.get('deletions', 0)}, "
                f"{item.get('changedFiles', 0)} files"
            )
            ci = self._get_ci_state(item)
            parts.append(f"**CI:** {ci}")
            reviews = item.get("reviews", {}).get("nodes", [])
            parts.append(f"**Reviews:** {len(reviews)} ({', '.join(r.get('state', '') for r in reviews)})")

        parts.append(f"\n**Description:**\n{item.get('body', 'No description provided.')[:2000]}")

        if philosophy.soft_text:
            parts.append(f"\n---\n**Repository Philosophy:**\n{philosophy.soft_text[:1000]}")

        return "\n".join(parts)

    def _get_ci_state(self, item: dict) -> str:
        commits = item.get("commits", {}).get("nodes", [])
        if commits:
            rollup = commits[0].get("commit", {}).get("statusCheckRollup", {})
            return rollup.get("state", "UNKNOWN")
        return "UNKNOWN"

    def _parse_response(self, response: str, number: int, item_type: ItemType, item: dict) -> AnalysisResult:
        """Parse LLM response into AnalysisResult."""
        response_lower = response.lower()

        # Determine action from response
        if "recommend: merge" in response_lower or "recommendation: merge" in response_lower:
            action = RecommendationAction.MERGE
        elif "recommend: close" in response_lower or "recommendation: close" in response_lower:
            action = RecommendationAction.CLOSE
        elif "recommend: escalate" in response_lower or "needs deep review" in response_lower:
            action = RecommendationAction.ESCALATE
        else:
            action = RecommendationAction.HOLD

        # Extract confidence if present
        confidence = 0.5
        if "confidence:" in response_lower:
            try:
                conf_str = response_lower.split("confidence:")[1].strip().split()[0].strip("%")
                confidence = float(conf_str) / 100 if float(conf_str) > 1 else float(conf_str)
            except (ValueError, IndexError):
                pass

        # If confidence is low, escalate to hold
        if action == RecommendationAction.MERGE and confidence < 0.8:
            action = RecommendationAction.HOLD
            response = f"[Low confidence ({confidence:.0%}), holding for review] " + response

        return AnalysisResult(
            recommendation=Recommendation(
                number=number,
                item_type=item_type,
                action=action,
                reason=response[:500],
                title=item.get("title", ""),
            ),
            tier=Tier.T2,
        )


class T3Reviewer:
    """Deep review tier. Full diff analysis. Multiple LLM calls for large PRs."""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def review(self, item: dict, files: list[dict], philosophy: Philosophy) -> AnalysisResult:
        """Full diff review. Only produces merge recommendation if 100% analyzed."""
        number = item["number"]
        item_type = ItemType.PR

        if self.llm is None:
            return AnalysisResult(
                recommendation=Recommendation(
                    number=number,
                    item_type=item_type,
                    action=RecommendationAction.HOLD,
                    reason="T3 review unavailable (no LLM configured)",
                    title=item.get("title", ""),
                ),
                tier=Tier.T3,
            )

        total_files = len(files)
        analyzed_files = 0
        issues_found = []
        unanalyzable = []

        for f in files:
            patch = f.get("patch", "")
            filename = f.get("filename", "unknown")

            if not patch or len(patch) > 50000:
                # Too large to analyze or binary
                unanalyzable.append(filename)
                continue

            # Analyze this file
            file_prompt = f"File: {filename}\nStatus: {f.get('status', 'modified')}\nDiff:\n```\n{patch[:10000]}\n```\n"

            review_response = await self.llm.chat(
                system=T3_DEEP_REVIEW_PROMPT,
                user=file_prompt,
            )
            analyzed_files += 1

            if "issue:" in review_response.lower() or "problem:" in review_response.lower():
                issues_found.append(f"{filename}: {review_response[:200]}")

        # Determine recommendation
        coverage = f"{analyzed_files}/{total_files} files analyzed"

        if unanalyzable:
            # Incomplete analysis → MUST hold (zero false merge policy)
            action = RecommendationAction.HOLD
            reason = (
                f"Partial analysis: {coverage}. "
                f"Unanalyzable files: {', '.join(unanalyzable[:5])}. "
                f"Issues found: {len(issues_found)}"
            )
        elif issues_found:
            action = RecommendationAction.HOLD
            reason = f"Full analysis ({coverage}). Issues found: " + "; ".join(issues_found[:3])
        else:
            action = RecommendationAction.MERGE
            reason = f"Full analysis ({coverage}). No issues found. Safe to merge."

        return AnalysisResult(
            recommendation=Recommendation(
                number=number,
                item_type=item_type,
                action=action,
                reason=reason[:500],
                title=item.get("title", ""),
                analysis_coverage=coverage,
            ),
            tier=Tier.T3,
        )


class IssueAnalyzer:
    """Issue-specific analyzer with dedicated action set."""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def analyze(self, issue: dict, philosophy: Philosophy, open_prs: list[dict] | None = None) -> AnalysisResult:
        """Analyze an issue and recommend action."""
        number = issue["number"]
        title = issue.get("title", "")
        body = issue.get("body", "") or ""
        labels = [n.get("name", "") for n in issue.get("labels", {}).get("nodes", [])]
        updated_at = issue.get("updatedAt", "")
        comments_count = issue.get("comments", {}).get("totalCount", 0)

        # Check for linked PR
        if open_prs:
            for pr in open_prs:
                pr_body = pr.get("body", "") or ""
                if (
                    f"#{number}" in pr_body
                    or f"fixes #{number}" in pr_body.lower()
                    or f"closes #{number}" in pr_body.lower()
                ):
                    return AnalysisResult(
                        recommendation=Recommendation(
                            number=number,
                            item_type=ItemType.ISSUE,
                            action=RecommendationAction.LINK_TO_PR,
                            reason=f"Related PR #{pr['number']} found: {pr.get('title', '')}",
                            title=title,
                            linked_pr=pr["number"],
                        ),
                        tier=Tier.T1,
                    )

        # Check stale
        try:
            updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - updated).days
        except (ValueError, TypeError):
            age_days = 0

        if age_days > 180 and comments_count <= 1:
            return AnalysisResult(
                recommendation=Recommendation(
                    number=number,
                    item_type=ItemType.ISSUE,
                    action=RecommendationAction.CLOSE,
                    reason=f"Stale issue: no activity for {age_days} days, {comments_count} comments",
                    title=title,
                    suggested_comment=(
                        "This issue has been inactive for over 6 months. "
                        "Closing as stale. Please reopen if still relevant."
                    ),
                ),
                tier=Tier.T1,
            )

        # Use LLM for classification if available
        if self.llm:
            user_prompt = (
                f"Issue #{number}: {title}\n"
                f"Labels: {', '.join(labels)}\n"
                f"Body: {body[:2000]}\n"
                f"Age: {age_days} days, {comments_count} comments\n"
            )
            response = await self.llm.chat(system=ISSUE_ANALYZE_PROMPT, user=user_prompt)
            return self._parse_issue_response(response, number, title, labels)

        # Default: hold for human review
        return AnalysisResult(
            recommendation=Recommendation(
                number=number,
                item_type=ItemType.ISSUE,
                action=RecommendationAction.HOLD,
                reason="Issue requires human review (no LLM available for classification)",
                title=title,
            ),
            tier=Tier.T1,
        )

    def _parse_issue_response(self, response: str, number: int, title: str, labels: list[str]) -> AnalysisResult:
        response_lower = response.lower()
        if "close" in response_lower and "recommend" in response_lower:
            action = RecommendationAction.CLOSE
        elif "label" in response_lower:
            action = RecommendationAction.LABEL
        elif "comment" in response_lower and "respond" in response_lower:
            action = RecommendationAction.COMMENT
        else:
            action = RecommendationAction.HOLD

        return AnalysisResult(
            recommendation=Recommendation(
                number=number,
                item_type=ItemType.ISSUE,
                action=action,
                reason=response[:500],
                title=title,
            ),
            tier=Tier.T2,
        )
