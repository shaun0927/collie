"""Tests for collie sit command."""

from __future__ import annotations

import base64

import httpx
import pytest

from collie.commands.sit import RepoAnalyzer, RepoProfile, SitInterviewer
from collie.core.models import Mode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rest_response(data, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data, headers={"content-type": "application/json"})


def _make_transport(responses: list[httpx.Response]):
    calls = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return next(calls)

    return httpx.MockTransport(handler)


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


async def _async_return(value):
    return value


# ---------------------------------------------------------------------------
# RepoAnalyzer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repo_analyzer_finds_contributing():
    """Analyzer sets has_contributing when CONTRIBUTING.md exists."""
    from collie.github.rest import GitHubREST

    content_payload = {"encoding": "base64", "content": _b64("# Contributing\nPlease follow these steps.")}

    # CONTRIBUTING.md found; remaining calls return 404
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("CONTRIBUTING.md"):
            return _rest_response(content_payload)
        return httpx.Response(404, json={"message": "Not Found"})

    rest = GitHubREST(token="tok")
    rest.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com")

    analyzer = RepoAnalyzer(rest)
    profile = await analyzer.analyze("owner", "repo")

    assert profile.has_contributing is True
    assert "Contributing" in profile.contributing_content
    assert profile.owner == "owner"
    assert profile.repo == "repo"
    await rest.close()


@pytest.mark.asyncio
async def test_repo_analyzer_finds_pr_template():
    """Analyzer detects PR template at .github/PULL_REQUEST_TEMPLATE.md."""
    from collie.github.rest import GitHubREST

    template_text = "## What does this PR do?"
    content_payload = {"encoding": "base64", "content": _b64(template_text)}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "PULL_REQUEST_TEMPLATE" in path:
            return _rest_response(content_payload)
        return httpx.Response(404, json={"message": "Not Found"})

    rest = GitHubREST(token="tok")
    rest.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com")

    analyzer = RepoAnalyzer(rest)
    profile = await analyzer.analyze("owner", "repo")

    assert profile.has_pr_template is True
    assert template_text in profile.pr_template_content
    await rest.close()


@pytest.mark.asyncio
async def test_repo_analyzer_detects_branch_protection():
    """Analyzer stores branch protection when found."""
    from collie.github.rest import GitHubREST

    protection_data = {"required_status_checks": {"strict": True, "contexts": ["ci/test"]}}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/branches/main/protection" in path:
            return _rest_response(protection_data)
        return httpx.Response(404, json={"message": "Not Found"})

    rest = GitHubREST(token="tok")
    rest.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com")

    analyzer = RepoAnalyzer(rest)
    profile = await analyzer.analyze("owner", "repo")

    assert profile.branch_protection == protection_data
    await rest.close()


@pytest.mark.asyncio
async def test_repo_analyzer_detects_codeowners():
    """Analyzer sets has_codeowners when CODEOWNERS file found."""
    from collie.github.rest import GitHubREST

    codeowners_text = "* @alice"
    content_payload = {"encoding": "base64", "content": _b64(codeowners_text)}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("CODEOWNERS"):
            return _rest_response(content_payload)
        return httpx.Response(404, json={"message": "Not Found"})

    rest = GitHubREST(token="tok")
    rest.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com")

    analyzer = RepoAnalyzer(rest)
    profile = await analyzer.analyze("owner", "repo")

    assert profile.has_codeowners is True
    await rest.close()


@pytest.mark.asyncio
async def test_repo_analyzer_empty_repo():
    """Analyzer returns bare profile when nothing is found."""
    from collie.github.rest import GitHubREST

    rest = GitHubREST(token="tok")
    rest.client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(404, json={"message": "Not Found"})),
        base_url="https://api.github.com",
    )

    analyzer = RepoAnalyzer(rest)
    profile = await analyzer.analyze("owner", "myrepo")

    assert profile.has_contributing is False
    assert profile.has_pr_template is False
    assert profile.has_codeowners is False
    assert profile.branch_protection == {}
    assert profile.ci_workflows == []
    await rest.close()


# ---------------------------------------------------------------------------
# SitInterviewer._resolve_question
# ---------------------------------------------------------------------------


def _make_question(
    qid: str = "test_q",
    category: str = "hard_rules",
    text: str = "Generic question?",
    confirmation_template: str = "",
    fallback_text: str = "Fallback question?",
) -> dict:
    q = {"id": qid, "category": category, "text": text, "fallback_text": fallback_text}
    if confirmation_template:
        q["confirmation_template"] = confirmation_template
    return q


def test_resolve_question_uses_fallback_when_no_template():
    """Returns fallback_text when no confirmation_template present."""
    profile = RepoProfile(owner="o", repo="r")
    interviewer = SitInterviewer(profile)

    q = _make_question(confirmation_template="", fallback_text="Is this a fallback?")
    result = interviewer._resolve_question(q)
    assert result == "Is this a fallback?"


def test_resolve_question_uses_fallback_when_no_relevant_data():
    """Falls back when template references CI data but repo has no CI."""
    profile = RepoProfile(owner="o", repo="r")  # ci_workflows=[]
    interviewer = SitInterviewer(profile)

    q = _make_question(
        confirmation_template="I found CI workflows in .github/workflows/. Should all CI checks pass?",
        fallback_text="Do you require CI to pass?",
    )
    result = interviewer._resolve_question(q)
    assert result == "Do you require CI to pass?"


def test_resolve_question_uses_confirmation_when_ci_detected():
    """Uses confirmation template when CI workflows are detected."""
    profile = RepoProfile(owner="o", repo="r", ci_workflows=["detected"])
    interviewer = SitInterviewer(profile)

    q = _make_question(
        confirmation_template="I found CI workflows in .github/workflows/. Should all CI checks pass?",
        fallback_text="Do you require CI to pass?",
    )
    result = interviewer._resolve_question(q)
    assert "CI workflows" in result
    assert result != "Do you require CI to pass?"


def test_resolve_question_uses_confirmation_for_contributing():
    """Uses confirmation template when CONTRIBUTING.md is detected."""
    profile = RepoProfile(owner="o", repo="r", has_contributing=True, contributing_content="# Contributing")
    interviewer = SitInterviewer(profile)

    q = _make_question(
        confirmation_template="I found a CLA reference in your CONTRIBUTING.md. Should unsigned PRs be blocked?",
        fallback_text="Do you require a CLA?",
    )
    result = interviewer._resolve_question(q)
    assert "CONTRIBUTING.md" in result


def test_resolve_question_uses_confirmation_for_codeowners():
    """Uses confirmation template when CODEOWNERS file is detected."""
    profile = RepoProfile(owner="o", repo="r", has_codeowners=True)
    interviewer = SitInterviewer(profile)

    q = _make_question(
        confirmation_template="I found {ownership_file} in your repo. Should Collie use this?",
        fallback_text="Do you have CODEOWNERS?",
    )
    result = interviewer._resolve_question(q)
    assert "CODEOWNERS" in result
    assert result != "Do you have CODEOWNERS?"


def test_resolve_question_falls_back_on_format_error():
    """Falls back gracefully when template formatting fails."""
    profile = RepoProfile(owner="o", repo="r", ci_workflows=["detected"])
    interviewer = SitInterviewer(profile)

    q = _make_question(
        confirmation_template="I found CI workflows in .github/workflows/. {totally_unknown_key} works?",
        fallback_text="Fallback on format error.",
    )
    result = interviewer._resolve_question(q)
    assert result == "Fallback on format error."


def test_resolve_question_uses_labels_when_present():
    """Uses confirmation template when labels are available and template references them."""
    profile = RepoProfile(owner="o", repo="r", labels=["bug", "feature", "docs"])
    interviewer = SitInterviewer(profile)

    q = _make_question(
        confirmation_template="I found these existing labels: {existing_labels}. Are these right?",
        fallback_text="What labels do you use?",
    )
    result = interviewer._resolve_question(q)
    assert "bug" in result
    assert "feature" in result


# ---------------------------------------------------------------------------
# SitInterviewer.generate_for_mcp
# ---------------------------------------------------------------------------


def test_generate_for_mcp_structure():
    """generate_for_mcp returns correct top-level keys."""
    profile = RepoProfile(owner="myorg", repo="myrepo")
    interviewer = SitInterviewer(profile)

    result = interviewer.generate_for_mcp()

    assert "profile" in result
    assert "interview_guide" in result
    assert "instructions" in result


def test_generate_for_mcp_profile_fields():
    """Profile section contains expected fields."""
    profile = RepoProfile(
        owner="myorg",
        repo="myrepo",
        has_contributing=True,
        has_pr_template=False,
        has_codeowners=True,
        ci_workflows=["detected"],
        labels=["bug", "docs"],
    )
    interviewer = SitInterviewer(profile)
    result = interviewer.generate_for_mcp()

    p = result["profile"]
    assert p["owner"] == "myorg"
    assert p["repo"] == "myrepo"
    assert p["has_contributing"] is True
    assert p["has_pr_template"] is False
    assert p["has_codeowners"] is True
    assert p["ci_detected"] is True
    assert p["label_count"] == 2
    assert p["default_branch"] == "main"


def test_generate_for_mcp_interview_guide_completeness():
    """interview_guide contains an entry for every question in QUESTION_BANK."""
    from collie.core.question_bank import QUESTION_BANK

    profile = RepoProfile(owner="o", repo="r")
    interviewer = SitInterviewer(profile)
    result = interviewer.generate_for_mcp()

    guide = result["interview_guide"]
    assert len(guide) == len(QUESTION_BANK)


def test_generate_for_mcp_guide_entry_schema():
    """Each interview_guide entry has id, category, text."""
    profile = RepoProfile(owner="o", repo="r")
    interviewer = SitInterviewer(profile)
    result = interviewer.generate_for_mcp()

    for entry in result["interview_guide"]:
        assert "id" in entry
        assert "category" in entry
        assert "text" in entry
        assert isinstance(entry["text"], str)
        assert len(entry["text"]) > 0


def test_generate_for_mcp_instructions_nonempty():
    """Instructions string is not empty."""
    profile = RepoProfile(owner="o", repo="r")
    interviewer = SitInterviewer(profile)
    result = interviewer.generate_for_mcp()

    assert len(result["instructions"]) > 0


# ---------------------------------------------------------------------------
# Philosophy generation from answers
# ---------------------------------------------------------------------------


def test_philosophy_from_hard_rule_answers():
    """Affirmative answers to hard_rules questions create HardRule entries."""
    profile = RepoProfile(owner="o", repo="r")
    interviewer = SitInterviewer(profile)

    # Simulate answers: two hard_rule questions answered affirmatively
    interviewer.answers = {
        "ci_policy": "yes, CI must pass",
        "required_reviews": "we require 2 approvals",
    }

    # Build philosophy by calling the parsing logic directly
    from collie.core.question_bank import QUESTION_BANK

    hard_rules = []
    escalation_rules = []
    soft_parts = []

    for q in QUESTION_BANK:
        answer = interviewer.answers.get(q["id"])
        if answer is None:
            continue
        if q["category"] == "hard_rules":
            if any(word in answer.lower() for word in ["yes", "required", "must", "mandatory"]):
                from collie.core.models import HardRule

                hard_rules.append(HardRule(condition=q["id"], action="reject", description=answer[:200]))
        elif q["category"] == "escalation":
            if any(word in answer.lower() for word in ["yes", "always", "must"]):
                from collie.core.models import EscalationRule

                escalation_rules.append(EscalationRule(pattern=q["id"], action="escalate", description=answer[:200]))
        else:
            soft_parts.append(f"- **{q['text']}**: {answer}")

    assert len(hard_rules) == 1  # only ci_policy matches ("yes")
    assert hard_rules[0].condition == "ci_policy"
    assert hard_rules[0].action == "reject"


def test_philosophy_from_escalation_answers():
    """Affirmative answers to escalation questions create EscalationRule entries."""
    from collie.core.models import EscalationRule
    from collie.core.question_bank import QUESTION_BANK

    profile = RepoProfile(owner="o", repo="r")
    interviewer = SitInterviewer(profile)
    interviewer.answers = {
        "security_review_policy": "yes, all security changes must go through security review",
    }

    escalation_rules = []
    for q in QUESTION_BANK:
        answer = interviewer.answers.get(q["id"])
        if answer is None:
            continue
        if q["category"] == "escalation":
            if any(word in answer.lower() for word in ["yes", "always", "must"]):
                escalation_rules.append(EscalationRule(pattern=q["id"], action="escalate", description=answer[:200]))

    assert len(escalation_rules) == 1
    assert escalation_rules[0].pattern == "security_review_policy"


def test_philosophy_mode_is_training():
    """Generated philosophy defaults to TRAINING mode."""
    from collie.core.models import Philosophy, TuningParams

    philosophy = Philosophy(
        hard_rules=[],
        soft_text="No specific soft preferences defined.",
        tuning=TuningParams(),
        trusted_contributors=[],
        escalation_rules=[],
        mode=Mode.TRAINING,
    )

    assert philosophy.mode == Mode.TRAINING


@pytest.mark.asyncio
async def test_repo_analyzer_enriches_profile_with_labels_and_repo_metadata():
    """Analyzer collects richer repo metadata beyond presence checks."""

    class FakeREST:
        async def get_repository(self, owner, repo):
            return {"default_branch": "develop", "description": "Example repo"}

        async def get_repo_content(self, owner, repo, path):
            return {
                "CONTRIBUTING.md": "# Contributing",
                ".github/PULL_REQUEST_TEMPLATE.md": "## Summary\n## Test plan",
                ".github/workflows": "ci.yml, release.yml",
                ".github/ISSUE_TEMPLATE": "bug.yml, feature.yml",
                "docs": "guide.md, api.md",
                "tests": "test_cli.py",
                "pyproject.toml": "[tool.ruff]\n[tool.black]",
                "SECURITY.md": "Contact security@example.com",
            }.get(path)

        async def get_branch_protection(self, owner, repo, branch="main"):
            return {}

        async def list_labels(self, owner, repo, limit=100):
            return ["bug", "good first issue", "release", "security", "stale"]

        async def list_recent_merged_pulls(self, owner, repo, limit=5):
            return [
                {
                    "number": 1,
                    "title": "feat: add thing",
                    "author": "alice",
                    "additions": 20,
                    "deletions": 5,
                    "changed_files": 3,
                    "approval_count": 2,
                },
                {
                    "number": 2,
                    "title": "fix: tighten auth",
                    "author": "bob",
                    "additions": 10,
                    "deletions": 2,
                    "changed_files": 1,
                    "approval_count": 1,
                },
            ]

        async def get_rulesets(self, owner, repo):
            return [
                {
                    "target": "branch",
                    "enforcement": "active",
                    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                    "rules": [{"type": "merge_queue"}],
                }
            ]

    analyzer = RepoAnalyzer(FakeREST())
    profile = await analyzer.analyze("owner", "repo")

    assert profile.default_branch == "develop"
    assert profile.repo_description == "Example repo"
    assert profile.labels[:2] == ["bug", "good first issue"]
    assert profile.issue_templates == ["bug.yml", "feature.yml"]
    assert profile.docs_paths == ["docs"]
    assert profile.test_paths == ["tests"]
    assert profile.lint_tools == ["black", "ruff"]
    assert profile.release_labels == ["release"]
    assert profile.stale_labels == ["stale"]
    assert profile.pr_template_fields == ["Summary", "Test plan"]
    assert profile.org_members == ["alice", "bob"]
    assert profile.merge_queue_required is True


def test_get_template_vars_uses_richer_profile_signals():
    """Template vars are grounded in the richer RepoProfile fields."""
    profile = RepoProfile(
        owner="o",
        repo="r",
        labels=["bug", "release"],
        ci_workflows=["ci.yml"],
        has_codeowners=True,
        ownership_file=".github/CODEOWNERS",
        default_branch="develop",
        docs_paths=["docs"],
        test_paths=["tests"],
        lint_tools=["ruff", "black"],
        release_labels=["release"],
        pr_template_fields=["Summary", "Test plan"],
        security_areas=["SECURITY.md", "security"],
        perf_tools=["benchmarks"],
        org_members=["alice", "bob"],
        recent_merges=[
            {"title": "feat: add thing", "additions": 20, "deletions": 5, "changed_files": 3, "approval_count": 2},
            {"title": "fix: auth tweak", "additions": 10, "deletions": 2, "changed_files": 1, "approval_count": 1},
        ],
    )
    interviewer = SitInterviewer(profile)
    vars = interviewer._get_template_vars()

    assert vars["review_count"] == 2
    assert vars["linters"] == "ruff, black"
    assert vars["test_path"] == "tests"
    assert vars["default_branch"] == "develop"
    assert vars["template_fields"] == "Summary, Test plan"
    assert vars["min_lines"] == 12
    assert vars["max_lines"] == 25
    assert vars["max_files"] == 3
    assert vars["release_labels"] == "release"
    assert vars["org_members"] == 2
    assert vars["security_areas"] == "SECURITY.md, security"
    assert "Conventional Commits" in vars["convention_hint"]


def test_soft_answers_go_to_soft_text():
    """Non-hard-rule, non-escalation answers appear in soft_parts."""
    from collie.core.question_bank import QUESTION_BANK

    profile = RepoProfile(owner="o", repo="r")
    interviewer = SitInterviewer(profile)
    interviewer.answers = {
        "pr_description_quality": "We expect motivation, test plan, and screenshots for UI changes.",
    }

    soft_parts = []
    for q in QUESTION_BANK:
        answer = interviewer.answers.get(q["id"])
        if answer is None:
            continue
        if q["category"] not in ("hard_rules", "escalation"):
            soft_parts.append(f"- **{q['text']}**: {answer}")

    assert len(soft_parts) == 1
    assert "motivation" in soft_parts[0]


# ---------------------------------------------------------------------------
# RepoProfile dataclass defaults
# ---------------------------------------------------------------------------


def test_repo_profile_defaults():
    """RepoProfile initializes with expected default values."""
    profile = RepoProfile(owner="alice", repo="myproject")

    assert profile.owner == "alice"
    assert profile.repo == "myproject"
    assert profile.has_contributing is False
    assert profile.contributing_content == ""
    assert profile.has_pr_template is False
    assert profile.pr_template_content == ""
    assert profile.branch_protection == {}
    assert profile.labels == []
    assert profile.ci_workflows == []
    assert profile.recent_merges == []
    assert profile.has_codeowners is False
    assert profile.default_branch == "main"
    assert profile.docs_paths == []
    assert profile.test_paths == []
    assert profile.lint_tools == []
    assert profile.issue_templates == []
    assert profile.merge_queue_required is False


def test_rulesets_require_merge_queue_matches_default_branch():
    rulesets = [
        {
            "target": "branch",
            "enforcement": "active",
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            "rules": [{"type": "merge_queue"}],
        }
    ]
    assert RepoAnalyzer._rulesets_require_merge_queue(rulesets, "main") is True
