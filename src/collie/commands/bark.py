"""collie bark — 3-tier analysis engine + recommendation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from collie.core.cost_tracker import CostTracker
from collie.core.incremental import IncrementalManager
from collie.core.models import (
    ItemType,
    Philosophy,
    Recommendation,
    RecommendationAction,
)


@dataclass
class BarkReport:
    """Summary of a bark run."""

    total_items: int = 0
    prs_analyzed: int = 0
    issues_analyzed: int = 0
    recommendations: list[Recommendation] = field(default_factory=list)
    cost_summary: str = ""
    full_scan: bool = False
    approved_executed: list[int] = field(default_factory=list)

    def summary(self) -> str:
        from collections import Counter

        actions = Counter(r.action.value for r in self.recommendations)
        mode = "full scan" if self.full_scan else "incremental"
        lines = [
            f"Bark complete ({mode})",
            f"  Items: {self.total_items} ({self.prs_analyzed} PRs, {self.issues_analyzed} issues)",
            f"  Recommendations: {dict(actions)}",
            f"  {self.cost_summary}",
        ]
        if self.approved_executed:
            lines.append(f"  Executed: {len(self.approved_executed)} approved items")
        return "\n".join(lines)


class BarkPipeline:
    """Full bark pipeline: fetch -> analyze -> queue -> approve-detect -> execute."""

    def __init__(self, graphql, rest, philosophy_store, queue_store, llm_client=None):
        self.gql = graphql
        self.rest = rest
        self.philosophy_store = philosophy_store
        self.queue_store = queue_store
        self.llm = llm_client
        self.incremental = IncrementalManager(graphql, queue_store, philosophy_store)

    async def run(self, owner: str, repo: str, cost_cap: float = 50.0) -> BarkReport:
        """Execute full bark pipeline."""
        from collie.core.analyzer import IssueAnalyzer, T1Scanner, T2Summarizer, T3Reviewer

        cost = CostTracker(cap_usd=cost_cap)
        t1 = T1Scanner()
        t2 = T2Summarizer(self.llm)
        t3 = T3Reviewer(self.llm)
        issue_analyzer = IssueAnalyzer(self.llm)

        # Load philosophy
        philosophy = await self.philosophy_store.load(owner, repo)
        if philosophy is None:
            raise ValueError("No philosophy found. Run 'collie sit' first.")

        # Determine scan mode
        full_scan = await self.incremental.should_full_scan(owner, repo)

        if full_scan:
            items = await self.incremental.get_all(owner, repo)
        else:
            items = await self.incremental.get_delta(owner, repo)

        # Separate PRs and Issues
        prs = [i for i in items if "additions" in i]
        issues = [i for i in items if "additions" not in i]

        recommendations: list[Recommendation] = []

        # Analyze PRs: T1 -> T2 -> T3
        for item in prs:
            rec = await self._analyze_pr(item, philosophy, t1, t2, t3, cost)
            recommendations.append(rec)

        # Analyze Issues
        for issue in issues:
            rec = await self._analyze_issue(issue, philosophy, issue_analyzer, cost, prs)
            recommendations.append(rec)

        # Update queue
        await self.queue_store.upsert_recommendations(owner, repo, recommendations)

        # Detect approvals and execute (cron mode)
        approved = await self.queue_store.read_approvals(owner, repo)
        executed: list[int] = []
        if approved and philosophy.mode.value == "active":
            executed = list(approved)

        # Record bark time and philosophy hash
        self.incremental.record_bark_time()
        self.incremental.record_philosophy_hash(philosophy)

        return BarkReport(
            total_items=len(items),
            prs_analyzed=len(prs),
            issues_analyzed=len(issues),
            recommendations=recommendations,
            cost_summary=cost.summary(),
            full_scan=full_scan,
            approved_executed=executed,
        )

    async def _analyze_pr(self, item, philosophy, t1, t2, t3, cost) -> Recommendation:
        """Analyze a single PR through T1 -> T2 -> T3 pipeline."""
        # T1: rule-based
        result = t1.scan(item, philosophy)
        if result:
            return result.recommendation

        needs_t3 = self._needs_t3(item, philosophy)

        # T2: LLM summary
        depth = philosophy.tuning.analysis_depth
        if cost.can_afford() and depth in ("t2", "t3"):
            result = await t2.summarize(item, philosophy)
            cost.record(1000, 500)

            if result.recommendation.action == RecommendationAction.MERGE:
                needs_t3 = True
            elif not needs_t3:
                return result.recommendation

        # T3: full diff review
        if needs_t3 and cost.can_afford(8000) and depth == "t3":
            files = await self.gql.fetch_pr_files(
                item.get("repository", {}).get("owner", ""),
                item.get("repository", {}).get("name", ""),
                item["number"],
            )
            result = await t3.review(item, files, philosophy)
            cost.record(5000, 2000)
            return result.recommendation

        # Can't proceed further
        return Recommendation(
            number=item["number"],
            item_type=ItemType.PR,
            action=RecommendationAction.HOLD,
            reason="Deferred: deeper review needed but not performed (cost/depth limit)",
            title=item.get("title", ""),
        )

    async def _analyze_issue(self, issue, philosophy, analyzer, cost, prs) -> Recommendation:
        """Analyze a single issue."""
        if cost.can_afford():
            result = await analyzer.analyze(issue, philosophy, open_prs=prs)
            if result.tier.value == "t2":
                cost.record(800, 400)
            return result.recommendation

        return Recommendation(
            number=issue["number"],
            item_type=ItemType.ISSUE,
            action=RecommendationAction.HOLD,
            reason="Deferred: analysis skipped (cost limit)",
            title=issue.get("title", ""),
        )

    def _needs_t3(self, item: dict, philosophy: Philosophy) -> bool:
        """Check if escalation rules require T3."""
        for rule in philosophy.escalation_rules:
            if rule.action == "t3_required":
                pattern = rule.pattern.replace("/*", "").replace("/", "")
                if pattern in item.get("title", "").lower():
                    return True
        return False
