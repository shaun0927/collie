"""collie sit — Repository philosophy interview + auto-generation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from collie.core.models import EscalationRule, HardRule, Mode, Philosophy, TuningParams
from collie.core.question_bank import QUESTION_BANK


@dataclass
class RepoProfile:
    """Analysis results from scanning a repository."""

    owner: str
    repo: str
    has_contributing: bool = False
    contributing_content: str = ""
    has_pr_template: bool = False
    pr_template_content: str = ""
    branch_protection: dict = field(default_factory=dict)
    labels: list[str] = field(default_factory=list)
    ci_workflows: list[str] = field(default_factory=list)
    recent_merges: list[dict] = field(default_factory=list)
    has_codeowners: bool = False
    ownership_file: str = ""
    default_branch: str = "main"
    repo_description: str = ""
    issue_templates: list[str] = field(default_factory=list)
    discussion_templates: list[str] = field(default_factory=list)
    docs_paths: list[str] = field(default_factory=list)
    test_paths: list[str] = field(default_factory=list)
    lint_tools: list[str] = field(default_factory=list)
    perf_tools: list[str] = field(default_factory=list)
    release_labels: list[str] = field(default_factory=list)
    stale_labels: list[str] = field(default_factory=list)
    security_policy_paths: list[str] = field(default_factory=list)
    pr_template_fields: list[str] = field(default_factory=list)
    convention_hint: str = "unknown"
    security_areas: list[str] = field(default_factory=list)
    org_members: list[str] = field(default_factory=list)
    merge_queue_required: bool = False


class RepoAnalyzer:
    """Pre-analyze a repository to enable confirmatory interview."""

    def __init__(self, github_rest):
        self.rest = github_rest

    async def analyze(self, owner: str, repo: str) -> RepoProfile:
        """Scan repo for CONTRIBUTING.md, PR templates, branch protection, labels, CI config."""
        profile = RepoProfile(owner=owner, repo=repo)

        repo_meta = await self.rest.get_repository(owner, repo)
        if repo_meta:
            profile.default_branch = repo_meta.get("default_branch", "main")
            profile.repo_description = repo_meta.get("description", "") or ""

        # Fetch CONTRIBUTING.md
        content = await self.rest.get_repo_content(owner, repo, "CONTRIBUTING.md")
        if content:
            profile.has_contributing = True
            profile.contributing_content = content

        # Fetch PR template
        for path in [
            ".github/PULL_REQUEST_TEMPLATE.md",
            ".github/pull_request_template.md",
            "PULL_REQUEST_TEMPLATE.md",
        ]:
            content = await self.rest.get_repo_content(owner, repo, path)
            if content:
                profile.has_pr_template = True
                profile.pr_template_content = content
                profile.pr_template_fields = self._extract_template_fields(content)
                break

        # Branch protection
        protection = await self.rest.get_branch_protection(owner, repo, profile.default_branch)
        if protection is None:
            protection = await self.rest.get_branch_protection(owner, repo, "master")
        if protection:
            profile.branch_protection = protection

        # CI workflows - check .github/workflows/
        ci_content = await self.rest.get_repo_content(owner, repo, ".github/workflows")
        if ci_content:
            profile.ci_workflows = self._split_directory_listing(ci_content)

        # CODEOWNERS
        for path in ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]:
            content = await self.rest.get_repo_content(owner, repo, path)
            if content:
                profile.has_codeowners = True
                profile.ownership_file = path
                break

        profile.labels = await self.rest.list_labels(owner, repo)
        profile.release_labels = [
            label for label in profile.labels if any(token in label.lower() for token in ["release", "backport"])
        ]
        profile.stale_labels = [label for label in profile.labels if "stale" in label.lower()]
        profile.recent_merges = await self.rest.list_recent_merged_pulls(owner, repo, limit=5)
        profile.org_members = sorted(
            {merge.get("author", "") for merge in profile.recent_merges if merge.get("author")}
        )
        profile.convention_hint = self._infer_convention_hint(profile.recent_merges)

        issue_templates = await self.rest.get_repo_content(owner, repo, ".github/ISSUE_TEMPLATE")
        if issue_templates:
            profile.issue_templates = self._split_directory_listing(issue_templates)

        discussion_templates = await self.rest.get_repo_content(owner, repo, ".github/DISCUSSION_TEMPLATE")
        if discussion_templates:
            profile.discussion_templates = self._split_directory_listing(discussion_templates)

        for docs_path in ["docs", "README.md"]:
            content = await self.rest.get_repo_content(owner, repo, docs_path)
            if content:
                profile.docs_paths.append(docs_path)

        for test_path in ["tests", "test", "__tests__"]:
            content = await self.rest.get_repo_content(owner, repo, test_path)
            if content:
                profile.test_paths.append(test_path)

        detected_lint_tools = []
        lint_candidates = {
            "ruff": ["ruff.toml", ".ruff.toml", "pyproject.toml"],
            "eslint": [".eslintrc", ".eslintrc.json", "package.json"],
            "black": ["pyproject.toml"],
            "prettier": [".prettierrc", "package.json"],
        }
        for tool, candidates in lint_candidates.items():
            for candidate in candidates:
                content = await self.rest.get_repo_content(owner, repo, candidate)
                if content and self._content_suggests_tool(tool, candidate, content):
                    detected_lint_tools.append(tool)
                    break
        profile.lint_tools = sorted(set(detected_lint_tools))

        for perf_path in ["benchmarks", "benchmark", "perf", "performance"]:
            content = await self.rest.get_repo_content(owner, repo, perf_path)
            if content:
                profile.perf_tools.append(perf_path)

        security_markers = []
        for security_path in ["SECURITY.md", ".github/SECURITY.md"]:
            content = await self.rest.get_repo_content(owner, repo, security_path)
            if content:
                profile.security_policy_paths.append(security_path)
                security_markers.append(security_path)

        profile.security_areas = sorted(
            set(
                security_markers
                + [
                    label
                    for label in profile.labels
                    if any(token in label.lower() for token in ["security", "auth", "permission"])
                ]
            )
        )

        if hasattr(self.rest, "get_rulesets"):
            try:
                rulesets = await self.rest.get_rulesets(owner, repo)
            except Exception:
                rulesets = []
            profile.merge_queue_required = self._rulesets_require_merge_queue(rulesets, profile.default_branch)

        return profile

    @staticmethod
    def _split_directory_listing(content: str) -> list[str]:
        return [entry.strip() for entry in content.split(",") if entry.strip()]

    @staticmethod
    def _extract_template_fields(content: str) -> list[str]:
        fields = []
        for line in content.splitlines():
            stripped = line.strip()
            heading = re.match(r"^#+\s+(.+)$", stripped)
            if heading:
                fields.append(heading.group(1).strip())
                continue
            checkbox = re.match(r"^- \[[ xX]\]\s+(.+)$", stripped)
            if checkbox:
                fields.append(checkbox.group(1).strip())
        return fields[:10]

    @staticmethod
    def _infer_convention_hint(recent_merges: list[dict]) -> str:
        titles = [merge.get("title", "") for merge in recent_merges if merge.get("title")]
        if any(re.match(r"^(feat|fix|chore|docs|refactor)(\(.+\))?:", title, re.IGNORECASE) for title in titles):
            return "Conventional Commits-like titles detected"
        if any(re.match(r"^(Fixed|Refs)\s+#\d+\s+--", title) for title in titles):
            return "Django-style ticket title convention detected"
        return "unknown"

    @staticmethod
    def _content_suggests_tool(tool: str, candidate: str, content: str) -> bool:
        lowered = content.lower()
        if tool == "ruff":
            return "ruff" in candidate.lower() or "[tool.ruff]" in lowered
        if tool == "eslint":
            return "eslint" in lowered or "eslint" in candidate.lower()
        if tool == "black":
            return "[tool.black]" in lowered or "black" in lowered
        if tool == "prettier":
            return "prettier" in lowered or "prettier" in candidate.lower()
        return False

    @staticmethod
    def _rulesets_require_merge_queue(rulesets: list[dict], default_branch: str) -> bool:
        """Return whether any active branch ruleset requires merge queue on the default branch."""
        target_ref = f"refs/heads/{default_branch}"
        for ruleset in rulesets:
            if ruleset.get("target") != "branch":
                continue
            if ruleset.get("enforcement") != "active":
                continue
            ref_name = (ruleset.get("conditions") or {}).get("ref_name") or {}
            include = ref_name.get("include") or []
            exclude = ref_name.get("exclude") or []
            applies = not include or "~DEFAULT_BRANCH" in include or target_ref in include
            if target_ref in exclude:
                applies = False
            if not applies:
                continue
            for rule in ruleset.get("rules") or []:
                if rule.get("type") == "merge_queue":
                    return True
        return False


class SitInterviewer:
    """Confirmatory interview based on repo analysis + question bank."""

    def __init__(self, profile: RepoProfile):
        self.profile = profile
        self.answers: dict[str, str] = {}

    def run_interactive(self) -> Philosophy:
        """Run CLI interactive interview. Returns Philosophy."""
        from rich.console import Console
        from rich.prompt import Prompt

        console = Console()
        console.print(f"\n[bold]🐕 Collie Sit — {self.profile.owner}/{self.profile.repo}[/bold]\n")
        console.print(
            "I've analyzed your repository. Let me ask a few questions to understand your merge philosophy.\n"
        )

        hard_rules = []
        escalation_rules = []
        trusted: list[str] = []
        soft_parts = []

        for q in QUESTION_BANK:
            # Use confirmation template if we have data, else fallback
            question_text = self._resolve_question(q)

            console.print(f"[cyan]({q['category']})[/cyan] {question_text}")
            answer = Prompt.ask("Your answer", default="skip")

            if answer.lower() == "skip":
                continue

            self.answers[q["id"]] = answer

            # Parse answer into philosophy components based on category
            if q["category"] == "hard_rules":
                if any(word in answer.lower() for word in ["yes", "required", "must", "mandatory"]):
                    hard_rules.append(
                        HardRule(
                            condition=q["id"],
                            action="reject",
                            description=answer[:200],
                        )
                    )
            elif q["category"] == "escalation":
                if any(word in answer.lower() for word in ["yes", "always", "must"]):
                    escalation_rules.append(
                        EscalationRule(
                            pattern=q["id"],
                            action="escalate",
                            description=answer[:200],
                        )
                    )
            else:
                soft_parts.append(f"- **{q['text']}**: {answer}")

        soft_text = "\n".join(soft_parts) if soft_parts else "No specific soft preferences defined."

        philosophy = Philosophy(
            hard_rules=hard_rules,
            soft_text=soft_text,
            tuning=TuningParams(),
            trusted_contributors=trusted,
            escalation_rules=escalation_rules,
            mode=Mode.TRAINING,
        )

        console.print("\n[bold green]✅ Philosophy generated![/bold green]")
        return philosophy

    def _resolve_question(self, question: dict) -> str:
        """Use confirmation template if repo data supports it, else fallback."""
        p = self.profile
        template = question.get("confirmation_template", "")

        if not template:
            return question.get("fallback_text", question["text"])

        template_lower = template.lower()

        # Decide whether we have sufficient repo data to use the confirmation template
        has_ci = bool(p.ci_workflows)
        has_contributing = p.has_contributing
        has_pr_template = p.has_pr_template
        has_codeowners = p.has_codeowners
        has_labels = bool(p.labels)
        has_branch_protection = bool(p.branch_protection)

        # Check if the template references a placeholder we can fill
        needs_ci = "{ci" in template_lower or "ci workflows" in template_lower or ".github/workflows" in template
        needs_contributing = "{contributing" in template_lower or "contributing.md" in template_lower
        needs_pr_template = "{template" in template_lower or "pr template" in template_lower
        needs_codeowners = "{ownership" in template_lower
        needs_labels = "{existing_labels" in template_lower or "{labels" in template_lower

        # Use confirmation template when the relevant repo signal is present
        use_confirmation = (
            (needs_ci and has_ci)
            or (needs_contributing and has_contributing)
            or (needs_pr_template and has_pr_template)
            or (needs_codeowners and has_codeowners)
            or (needs_labels and has_labels)
            or (
                not needs_ci
                and not needs_contributing
                and not needs_pr_template
                and not needs_codeowners
                and not needs_labels
                and (has_ci or has_contributing or has_pr_template or has_codeowners or has_branch_protection)
            )
        )

        if not use_confirmation:
            return question.get("fallback_text", question["text"])

        # Try to fill the template with available vars; if it fails, use fallback
        try:
            filled = template.format(**self._get_template_vars())
            return filled
        except (KeyError, IndexError):
            return question.get("fallback_text", question["text"])

    def _get_template_vars(self) -> dict:
        """Generate template variables from profile."""
        merge_sizes = [merge.get("additions", 0) + merge.get("deletions", 0) for merge in self.profile.recent_merges]
        merge_files = [merge.get("changed_files", 0) for merge in self.profile.recent_merges]
        approval_counts = [merge.get("approval_count", 0) for merge in self.profile.recent_merges]
        review_count = approval_counts[0] if approval_counts else "unknown"
        min_lines = min(merge_sizes) if merge_sizes else "unknown"
        max_lines = max(merge_sizes) if merge_sizes else "unknown"
        max_files = max(merge_files) if merge_files else "unknown"

        return {
            "ci_tools": ", ".join(self.profile.ci_workflows) or "unknown",
            "labels": ", ".join(self.profile.labels[:10]) or "none found",
            "existing_labels": ", ".join(self.profile.labels[:10]) or "none found",
            "review_count": review_count,
            "gfi_count": sum(1 for label in self.profile.labels if "good first issue" in label.lower()),
            "ownership_file": self.profile.ownership_file or ("CODEOWNERS" if self.profile.has_codeowners else "none"),
            "release_labels": ", ".join(self.profile.release_labels) or "unknown",
            "latest_version": "unknown",
            "stale_days": "90" if self.profile.stale_labels else "unknown",
            "avg_merge_size": round(sum(merge_sizes) / len(merge_sizes)) if merge_sizes else "unknown",
            "linters": ", ".join(self.profile.lint_tools) or "unknown",
            "test_path": self.profile.test_paths[0] if self.profile.test_paths else "unknown",
            "default_branch": self.profile.default_branch,
            "template_fields": ", ".join(self.profile.pr_template_fields) or "unknown",
            "min_lines": min_lines,
            "max_lines": max_lines,
            "org_members": len(self.profile.org_members) or "unknown",
            "docs_path": self.profile.docs_paths[0] if self.profile.docs_paths else "docs/",
            "convention_hint": (
                self.profile.convention_hint
                if self.profile.convention_hint != "unknown"
                else RepoAnalyzer._infer_convention_hint(self.profile.recent_merges)
            ),
            "security_areas": ", ".join(self.profile.security_areas) or "unknown",
            "max_files": max_files,
            "perf_tools": ", ".join(self.profile.perf_tools) or "unknown",
        }

    def generate_for_mcp(self) -> dict:
        """Generate interview guide for MCP mode (host LLM conducts interview)."""
        questions = []
        for q in QUESTION_BANK:
            questions.append(
                {
                    "id": q["id"],
                    "category": q["category"],
                    "text": self._resolve_question(q),
                }
            )
        return {
            "profile": {
                "owner": self.profile.owner,
                "repo": self.profile.repo,
                "has_contributing": self.profile.has_contributing,
                "has_pr_template": self.profile.has_pr_template,
                "has_codeowners": self.profile.has_codeowners,
                "ci_detected": bool(self.profile.ci_workflows),
                "label_count": len(self.profile.labels),
                "default_branch": self.profile.default_branch,
                "repo_description": self.profile.repo_description,
                "docs_paths": list(self.profile.docs_paths),
                "test_paths": list(self.profile.test_paths),
                "lint_tools": list(self.profile.lint_tools),
                "issue_template_count": len(self.profile.issue_templates),
                "recent_merge_count": len(self.profile.recent_merges),
            },
            "interview_guide": questions,
            "instructions": (
                "Use these questions to interview the maintainer about their repository philosophy. "
                "After the interview, compile the answers into a philosophy document and call collie_sit_save."
            ),
        }


__all__ = ["RepoProfile", "RepoAnalyzer", "SitInterviewer"]
