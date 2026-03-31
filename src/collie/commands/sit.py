"""collie sit — Repository philosophy interview + auto-generation."""

from __future__ import annotations

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


class RepoAnalyzer:
    """Pre-analyze a repository to enable confirmatory interview."""

    def __init__(self, github_rest):
        self.rest = github_rest

    async def analyze(self, owner: str, repo: str) -> RepoProfile:
        """Scan repo for CONTRIBUTING.md, PR templates, branch protection, labels, CI config."""
        profile = RepoProfile(owner=owner, repo=repo)

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
                break

        # Branch protection
        protection = await self.rest.get_branch_protection(owner, repo, "main")
        if protection is None:
            protection = await self.rest.get_branch_protection(owner, repo, "master")
        if protection:
            profile.branch_protection = protection

        # CI workflows - check .github/workflows/
        # (simplified: just check if directory exists)
        ci_content = await self.rest.get_repo_content(owner, repo, ".github/workflows")
        if ci_content:
            profile.ci_workflows = ["detected"]

        # CODEOWNERS
        for path in ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]:
            content = await self.rest.get_repo_content(owner, repo, path)
            if content:
                profile.has_codeowners = True
                break

        return profile


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
        return {
            "ci_tools": ", ".join(self.profile.ci_workflows) or "unknown",
            "labels": ", ".join(self.profile.labels[:10]) or "none found",
            "existing_labels": ", ".join(self.profile.labels[:10]) or "none found",
            "review_count": "unknown",
            "gfi_count": "unknown",
            "ownership_file": "CODEOWNERS" if self.profile.has_codeowners else "none",
            "release_labels": "unknown",
            "latest_version": "unknown",
            "stale_days": "90",
            "avg_merge_size": "unknown",
            "linters": "unknown",
            "test_path": "unknown",
            "default_branch": "main",
            "template_fields": "unknown",
            "min_lines": "unknown",
            "max_lines": "unknown",
            "org_members": "unknown",
            "docs_path": "docs/",
            "convention_hint": "unknown",
            "security_areas": "unknown",
            "max_files": "unknown",
            "perf_tools": "unknown",
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
            },
            "interview_guide": questions,
            "instructions": (
                "Use these questions to interview the maintainer about their repository philosophy. "
                "After the interview, compile the answers into a philosophy document and call collie_sit_save."
            ),
        }


__all__ = ["RepoProfile", "RepoAnalyzer", "SitInterviewer"]
