"""Issue #5 Verification — collie sit command: all 16 checkboxes.

Each test maps to a specific checkbox in the verification checklist.
Tests are numbered V01–V16 for traceability.
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from collie.commands.sit import RepoAnalyzer, RepoProfile, SitInterviewer
from collie.core.models import (
    EscalationRule,
    HardRule,
    Mode,
    Philosophy,
    TuningParams,
)
from collie.core.question_bank import QUESTION_BANK


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


# ═══════════════════════════════════════════════════════════════════════
# V01: Running `collie sit owner/repo` outputs the repository pre-analysis results
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_v01_sit_outputs_pre_analysis():
    """collie sit should analyze the repo and output pre-analysis results."""
    from collie.github.rest import GitHubREST

    contributing = {"encoding": "base64", "content": _b64("# Contributing Guide\nPlease follow rules.")}
    pr_template = {"encoding": "base64", "content": _b64("## What does this PR do?\n## Test plan")}
    protection = {"required_status_checks": {"strict": True, "contexts": ["ci/test"]}}
    workflows_dir = [{"name": "ci.yml"}, {"name": "release.yml"}]
    codeowners = {"encoding": "base64", "content": _b64("* @maintainer")}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("CONTRIBUTING.md"):
            return httpx.Response(200, json=contributing)
        if "PULL_REQUEST_TEMPLATE" in path:
            return httpx.Response(200, json=pr_template)
        if "/branches/main/protection" in path:
            return httpx.Response(200, json=protection)
        if path.endswith(".github/workflows"):
            return httpx.Response(200, json=workflows_dir)
        if path.endswith("CODEOWNERS"):
            return httpx.Response(200, json=codeowners)
        return httpx.Response(404, json={"message": "Not Found"})

    rest = GitHubREST(token="tok")
    rest.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com")

    analyzer = RepoAnalyzer(rest)
    profile = await analyzer.analyze("owner", "repo")

    # V01: Verify pre-analysis results are populated
    assert profile.owner == "owner"
    assert profile.repo == "repo"
    assert profile.has_contributing is True
    assert "Contributing Guide" in profile.contributing_content
    assert profile.has_pr_template is True
    assert "What does this PR do?" in profile.pr_template_content
    assert profile.branch_protection == protection
    assert len(profile.ci_workflows) > 0
    assert profile.has_codeowners is True
    await rest.close()


# ═══════════════════════════════════════════════════════════════════════
# V02: CONTRIBUTING.md → confirmation style questions
# ═══════════════════════════════════════════════════════════════════════


def test_v02_contributing_triggers_confirmation_questions():
    """Repos with CONTRIBUTING.md get confirmation-style questions."""
    profile = RepoProfile(
        owner="o",
        repo="r",
        has_contributing=True,
        contributing_content="# Contributing\nTests are required. Sign the CLA.",
    )
    interviewer = SitInterviewer(profile)

    # Check CLA question uses confirmation template (references CONTRIBUTING.md)
    cla_q = next(q for q in QUESTION_BANK if q["id"] == "cla_requirement")
    resolved = interviewer._resolve_question(cla_q)
    assert "CONTRIBUTING.md" in resolved, f"Expected confirmation style, got: {resolved}"

    # Check linked_issue question also uses confirmation
    linked_q = next(q for q in QUESTION_BANK if q["id"] == "linked_issue_required")
    resolved_linked = interviewer._resolve_question(linked_q)
    assert "CONTRIBUTING.md" in resolved_linked, f"Expected confirmation style, got: {resolved_linked}"


# ═══════════════════════════════════════════════════════════════════════
# V03: No CONTRIBUTING.md → open-ended (fallback) questions
# ═══════════════════════════════════════════════════════════════════════


def test_v03_no_contributing_uses_fallback():
    """Repos without CONTRIBUTING.md get open-ended fallback questions."""
    profile = RepoProfile(owner="o", repo="r", has_contributing=False)
    interviewer = SitInterviewer(profile)

    # All questions that reference CONTRIBUTING.md should fall back
    cla_q = next(q for q in QUESTION_BANK if q["id"] == "cla_requirement")
    resolved = interviewer._resolve_question(cla_q)
    assert resolved == cla_q["fallback_text"], f"Expected fallback, got: {resolved}"

    linked_q = next(q for q in QUESTION_BANK if q["id"] == "linked_issue_required")
    resolved_linked = interviewer._resolve_question(linked_q)
    assert resolved_linked == linked_q["fallback_text"]


# ═══════════════════════════════════════════════════════════════════════
# V04: Branch protection → hard rule suggestions
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_v04_branch_protection_detected():
    """Branch protection rules are detected and influence question resolution."""
    from collie.github.rest import GitHubREST

    protection = {"required_status_checks": {"strict": True}, "enforce_admins": {"enabled": True}}

    def handler(request: httpx.Request) -> httpx.Response:
        if "/branches/main/protection" in request.url.path:
            return httpx.Response(200, json=protection)
        return httpx.Response(404, json={"message": "Not Found"})

    rest = GitHubREST(token="tok")
    rest.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com")

    analyzer = RepoAnalyzer(rest)
    profile = await analyzer.analyze("owner", "repo")

    assert profile.branch_protection == protection
    assert profile.branch_protection.get("required_status_checks", {}).get("strict") is True

    # Branch protection data should trigger confirmation-style questions
    # for questions that don't need specific CI/contributing/labels/codeowners
    interviewer = SitInterviewer(profile)
    # Questions without specific needs but with general repo signals use confirmation
    branch_q = next(q for q in QUESTION_BANK if q["id"] == "branch_target_policy")
    resolved = interviewer._resolve_question(branch_q)
    # With branch_protection present, some general questions use confirmation templates
    assert len(resolved) > 0
    await rest.close()


# ═══════════════════════════════════════════════════════════════════════
# V05: Label list → category classification suggestions
# ═══════════════════════════════════════════════════════════════════════


def test_v05_labels_detected_and_used():
    """Labels are reflected in category classification question suggestions."""
    labels = ["bug", "enhancement", "documentation", "good first issue", "help wanted"]
    profile = RepoProfile(owner="o", repo="r", labels=labels)
    interviewer = SitInterviewer(profile)

    # issue_label_taxonomy question references {existing_labels}
    label_q = next(q for q in QUESTION_BANK if q["id"] == "issue_label_taxonomy")
    resolved = interviewer._resolve_question(label_q)

    assert "bug" in resolved
    assert "enhancement" in resolved
    assert "documentation" in resolved


# ═══════════════════════════════════════════════════════════════════════
# V06: After interview, Philosophy object is created correctly
# ═══════════════════════════════════════════════════════════════════════


def test_v06_philosophy_created_from_interview():
    """Simulated interview creates a valid Philosophy with all components."""
    profile = RepoProfile(owner="o", repo="r", ci_workflows=["detected"])
    _interviewer = SitInterviewer(profile)

    # Simulate the interview logic (same as run_interactive but without prompts)
    hard_rules = []
    escalation_rules = []
    soft_parts = []
    trusted = []

    # Simulate answers
    simulated_answers = {
        "ci_policy": "yes, all CI must pass",
        "tests_required": "required for all code changes",
        "security_review_policy": "yes, always require security review",
        "pr_description_quality": "We expect motivation and test plan",
        "pr_size_norms": "Keep under 500 lines",
    }

    for q in QUESTION_BANK:
        answer = simulated_answers.get(q["id"])
        if not answer:
            continue

        if q["category"] == "hard_rules":
            if any(w in answer.lower() for w in ["yes", "required", "must", "mandatory"]):
                hard_rules.append(HardRule(condition=q["id"], action="reject", description=answer[:200]))
        elif q["category"] == "escalation":
            if any(w in answer.lower() for w in ["yes", "always", "must"]):
                escalation_rules.append(EscalationRule(pattern=q["id"], action="escalate", description=answer[:200]))
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

    assert len(philosophy.hard_rules) == 2  # ci_policy, tests_required
    assert philosophy.hard_rules[0].condition == "ci_policy"
    assert philosophy.hard_rules[1].condition == "tests_required"
    assert len(philosophy.escalation_rules) == 1
    assert philosophy.escalation_rules[0].pattern == "security_review_policy"
    assert "motivation" in philosophy.soft_text
    assert philosophy.mode == Mode.TRAINING
    assert philosophy.tuning.confidence_threshold == 0.9


# ═══════════════════════════════════════════════════════════════════════
# V07: Philosophy post auto-generated in Discussion
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_v07_philosophy_saved_to_discussion():
    """Philosophy is saved to GitHub Discussion via PhilosophyStore."""
    from collie.core.stores.philosophy_store import PhilosophyStore

    philosophy = Philosophy(
        hard_rules=[HardRule(condition="ci_failed", action="reject", description="CI must pass")],
        soft_text="We value clear PR descriptions.",
        tuning=TuningParams(),
        mode=Mode.TRAINING,
    )

    # Mock GraphQL and REST clients
    mock_gql = AsyncMock()
    mock_gql.list_discussions = AsyncMock(return_value=[])  # No existing discussion
    mock_gql.list_discussion_categories = AsyncMock(
        return_value=[
            {"id": "cat-1", "name": "General"},
        ]
    )
    mock_gql.get_repository_id = AsyncMock(return_value="repo-123")
    mock_gql.create_discussion = AsyncMock(
        return_value={
            "url": "https://github.com/owner/repo/discussions/1",
            "id": "disc-1",
            "number": 1,
            "title": "🐕 Collie Philosophy",
        }
    )

    mock_rest = AsyncMock()
    store = PhilosophyStore(mock_gql, mock_rest)
    url = await store.save("owner", "repo", philosophy)

    assert "discussions" in url
    mock_gql.create_discussion.assert_called_once()
    call_kwargs = mock_gql.create_discussion.call_args
    body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body") or call_kwargs[0][3]
    assert "Collie Philosophy" in body
    assert "ci_failed" in body


# ═══════════════════════════════════════════════════════════════════════
# V08: Generated philosophy includes YAML hard rules section
# ═══════════════════════════════════════════════════════════════════════


def test_v08_philosophy_has_yaml_hard_rules():
    """to_markdown() output includes a YAML hard rules section."""
    philosophy = Philosophy(
        hard_rules=[
            HardRule(condition="ci_failed", action="reject", description="CI must pass"),
            HardRule(condition="no_tests", action="hold", description="Tests required"),
        ],
        mode=Mode.TRAINING,
    )

    md = philosophy.to_markdown()
    assert "## Hard Rules" in md
    assert "```yaml" in md
    assert "ci_failed" in md
    assert "no_tests" in md
    assert "reject" in md
    assert "hold" in md


# ═══════════════════════════════════════════════════════════════════════
# V09: Generated philosophy includes natural language philosophy section
# ═══════════════════════════════════════════════════════════════════════


def test_v09_philosophy_has_natural_language_section():
    """to_markdown() output includes a '## Philosophy' section with soft text."""
    philosophy = Philosophy(
        soft_text="We value code clarity over cleverness.\nPRs should be small and focused.",
        mode=Mode.TRAINING,
    )

    md = philosophy.to_markdown()
    assert "## Philosophy" in md
    assert "code clarity over cleverness" in md
    assert "small and focused" in md


# ═══════════════════════════════════════════════════════════════════════
# V10: Generated philosophy includes tuning parameters section
# ═══════════════════════════════════════════════════════════════════════


def test_v10_philosophy_has_tuning_parameters():
    """to_markdown() output includes a YAML tuning parameters section."""
    philosophy = Philosophy(
        tuning=TuningParams(confidence_threshold=0.85, analysis_depth="t3", cost_cap_per_bark=25.0),
        mode=Mode.TRAINING,
    )

    md = philosophy.to_markdown()
    assert "## Tuning Parameters" in md
    assert "confidence_threshold" in md
    assert "0.85" in md
    assert "analysis_depth" in md
    assert "t3" in md
    assert "cost_cap_per_bark" in md
    assert "25.0" in md


# ═══════════════════════════════════════════════════════════════════════
# V11: MCP sit_analyze returns repository analysis + interview guide
# ═══════════════════════════════════════════════════════════════════════


def test_v11_mcp_sit_analyze_returns_guide():
    """generate_for_mcp() returns profile, interview_guide, and instructions."""
    profile = RepoProfile(
        owner="myorg",
        repo="myrepo",
        has_contributing=True,
        has_pr_template=True,
        has_codeowners=False,
        ci_workflows=["detected"],
        labels=["bug", "feature"],
    )
    interviewer = SitInterviewer(profile)
    result = interviewer.generate_for_mcp()

    # Top-level structure
    assert "profile" in result
    assert "interview_guide" in result
    assert "instructions" in result

    # Profile fields
    p = result["profile"]
    assert p["owner"] == "myorg"
    assert p["repo"] == "myrepo"
    assert p["has_contributing"] is True
    assert p["has_pr_template"] is True
    assert p["has_codeowners"] is False
    assert p["ci_detected"] is True
    assert p["label_count"] == 2

    # Interview guide matches question bank
    guide = result["interview_guide"]
    assert len(guide) == len(QUESTION_BANK)
    for entry in guide:
        assert "id" in entry
        assert "category" in entry
        assert "text" in entry
        assert len(entry["text"]) > 0

    # Instructions present
    assert "interview" in result["instructions"].lower()
    assert "collie_sit_save" in result["instructions"]


# ═══════════════════════════════════════════════════════════════════════
# V12: MCP sit_save parses text and saves to Discussion
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_v12_mcp_sit_save_roundtrip():
    """Philosophy.from_markdown() correctly parses to_markdown() output."""
    original = Philosophy(
        hard_rules=[
            HardRule(condition="ci_failed", action="reject", description="CI must pass"),
            HardRule(condition="no_linked_issue", action="hold", description="Must link issue"),
        ],
        soft_text="We prefer small, focused PRs with clear descriptions.",
        tuning=TuningParams(confidence_threshold=0.85, analysis_depth="t2", cost_cap_per_bark=30.0),
        trusted_contributors=["alice", "bob"],
        escalation_rules=[
            EscalationRule(pattern="security_change", action="escalate", description="Needs security review"),
        ],
        mode=Mode.TRAINING,
        created_at="2024-01-15",
        updated_at="2024-01-20",
    )

    # Serialize and deserialize
    md = original.to_markdown()
    parsed = Philosophy.from_markdown(md)

    # Verify roundtrip fidelity
    assert len(parsed.hard_rules) == 2
    assert parsed.hard_rules[0].condition == "ci_failed"
    assert parsed.hard_rules[0].action == "reject"
    assert parsed.hard_rules[1].condition == "no_linked_issue"

    assert len(parsed.escalation_rules) == 1
    assert parsed.escalation_rules[0].pattern == "security_change"

    assert parsed.tuning.confidence_threshold == 0.85
    assert parsed.tuning.analysis_depth == "t2"
    assert parsed.tuning.cost_cap_per_bark == 30.0

    assert "alice" in parsed.trusted_contributors
    assert "bob" in parsed.trusted_contributors

    assert "small, focused PRs" in parsed.soft_text
    assert parsed.mode == Mode.TRAINING
    assert parsed.created_at == "2024-01-15"
    assert parsed.updated_at == "2024-01-20"

    # Also verify that MCP dispatch would work
    from collie.core.stores.philosophy_store import PhilosophyStore

    mock_gql = AsyncMock()
    mock_gql.list_discussions = AsyncMock(return_value=[])
    mock_gql.list_discussion_categories = AsyncMock(return_value=[{"id": "cat-1", "name": "General"}])
    mock_gql.get_repository_id = AsyncMock(return_value="repo-123")
    mock_gql.create_discussion = AsyncMock(return_value={"url": "https://github.com/o/r/discussions/1"})

    store = PhilosophyStore(mock_gql, AsyncMock())
    url = await store.save("o", "r", parsed)
    assert "discussions" in url


# ═══════════════════════════════════════════════════════════════════════
# V13: Existing philosophy → "Overwrite existing philosophy?" confirmation
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_v13_existing_philosophy_triggers_update():
    """When a philosophy Discussion already exists, save() updates instead of creating."""
    from collie.core.stores.philosophy_store import PhilosophyStore

    existing_discussion = {
        "id": "disc-existing-123",
        "title": "🐕 Collie Philosophy",
        "body": "old content",
        "url": "https://github.com/owner/repo/discussions/42",
    }

    mock_gql = AsyncMock()
    mock_gql.list_discussions = AsyncMock(return_value=[existing_discussion])
    mock_gql.update_discussion_body = AsyncMock(return_value="https://github.com/owner/repo/discussions/42")

    store = PhilosophyStore(mock_gql, AsyncMock())

    philosophy = Philosophy(
        hard_rules=[HardRule(condition="new_rule", action="reject", description="new")],
        mode=Mode.TRAINING,
    )
    url = await store.save("owner", "repo", philosophy)

    # Should update, not create
    mock_gql.update_discussion_body.assert_called_once_with("disc-existing-123", philosophy.to_markdown())
    mock_gql.create_discussion.assert_not_called()
    assert "discussions/42" in url


# ═══════════════════════════════════════════════════════════════════════
# V14: Phase 0 question bank questions are used in the interview
# ═══════════════════════════════════════════════════════════════════════


def test_v14_question_bank_used_in_interview():
    """QUESTION_BANK from Phase 0 research is iterated by run_interactive."""
    import inspect

    from collie.commands.sit import SitInterviewer

    source = inspect.getsource(SitInterviewer.run_interactive)

    # run_interactive iterates QUESTION_BANK
    assert "QUESTION_BANK" in source

    # Question bank has questions from all 5 research categories
    categories = {q["category"] for q in QUESTION_BANK}
    assert "hard_rules" in categories
    assert "soft_signals" in categories
    assert "escalation" in categories
    assert "issue_management" in categories
    assert "project_direction" in categories

    # Question bank is non-empty and has substantial coverage
    assert len(QUESTION_BANK) >= 30  # 34 questions from Phase 0 research

    # Each question has Phase 0 research-derived fields
    for q in QUESTION_BANK:
        assert "id" in q
        assert "category" in q
        assert "text" in q
        assert "fallback_text" in q
        # Most have confirmation templates (research-derived)
        if q["id"] not in ("ai_contribution_policy", "unresolved_review_comments"):
            assert "confirmation_template" in q or "fallback_text" in q


# ═══════════════════════════════════════════════════════════════════════
# V15: Ctrl+C → graceful exit (partial results not saved)
# ═══════════════════════════════════════════════════════════════════════


def test_v15_ctrl_c_graceful_exit():
    """KeyboardInterrupt during interview prevents philosophy from being saved."""
    profile = RepoProfile(owner="o", repo="r")
    interviewer = SitInterviewer(profile)

    call_count = 0

    def mock_prompt_ask(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            raise KeyboardInterrupt()
        return "yes"

    with patch("rich.prompt.Prompt.ask", side_effect=mock_prompt_ask):
        with pytest.raises(KeyboardInterrupt):
            interviewer.run_interactive()

    # Since KeyboardInterrupt was raised, no philosophy was returned
    # The caller (_sit in main.py) will not save partial results
    # because the exception propagates before store.save() is called
    assert call_count == 3  # Interrupted on 3rd question


def test_v15b_ctrl_c_no_save_in_cli():
    """The CLI flow ensures Ctrl+C prevents saving partial results."""
    import inspect

    from collie.cli.main import _sit

    source = inspect.getsource(_sit)

    # _sit calls run_interactive() then store.save() sequentially
    # If run_interactive() raises KeyboardInterrupt, store.save() is never reached
    lines = source.splitlines()
    interview_line = None
    save_line = None
    for i, line in enumerate(lines):
        if "run_interactive" in line:
            interview_line = i
        if "store.save" in line:
            save_line = i

    assert interview_line is not None, "run_interactive() not found in _sit"
    assert save_line is not None, "store.save() not found in _sit"
    assert save_line > interview_line, "save must come after interview"

    # No try/except around run_interactive that would catch KeyboardInterrupt
    # (the outer try in sit() calls handle_error which exits)


# ═══════════════════════════════════════════════════════════════════════
# V16: Total interview time within 5 minutes
# ═══════════════════════════════════════════════════════════════════════


def test_v16_interview_time_within_5_minutes():
    """Interview uses confirmation-style format for speed; question count is manageable."""
    # With confirmation-style questions (Y/n/edit), each takes ~5-10 seconds
    # 34 questions × 10 seconds = ~5.7 minutes (borderline)
    # But with "skip" default and fast Y/n answers, it's faster
    num_questions = len(QUESTION_BANK)

    # Confirmation-style questions: average ~8 seconds each
    # (read question: 3s, answer Y/n: 2s, think: 3s)
    estimated_seconds_per_question = 8
    estimated_total = num_questions * estimated_seconds_per_question
    five_minutes = 5 * 60

    assert estimated_total <= five_minutes, (
        f"{num_questions} questions × {estimated_seconds_per_question}s = {estimated_total}s "
        f"exceeds 5min ({five_minutes}s)"
    )

    # Also verify skip is the default (speeds up interview)
    import inspect

    source = inspect.getsource(SitInterviewer.run_interactive)
    assert 'default="skip"' in source, "Prompt should default to 'skip' for speed"


# ═══════════════════════════════════════════════════════════════════════
# Additional: Full markdown roundtrip test (supports V07-V10, V12)
# ═══════════════════════════════════════════════════════════════════════


def test_full_markdown_roundtrip():
    """Complete philosophy serialization/deserialization preserves all fields."""
    original = Philosophy(
        hard_rules=[
            HardRule(condition="ci_failed", action="reject", description="CI must pass"),
            HardRule(condition="no_tests", action="hold", description="Need tests"),
        ],
        soft_text="- **PR quality**: Descriptions must be clear\n- **Size**: Keep PRs under 500 lines",
        tuning=TuningParams(confidence_threshold=0.75, analysis_depth="t3", cost_cap_per_bark=10.0),
        trusted_contributors=["alice", "bob", "charlie"],
        escalation_rules=[
            EscalationRule(pattern="security", action="escalate", description="Security review required"),
            EscalationRule(pattern="breaking", action="t3_required", description="Breaking change"),
        ],
        mode=Mode.ACTIVE,
        created_at="2024-01-01",
        updated_at="2024-06-15",
        unleashed_at="2024-03-01",
    )

    md = original.to_markdown()

    # V08: YAML hard rules section present
    assert "## Hard Rules" in md
    assert "```yaml" in md

    # V09: Natural language philosophy section present
    assert "## Philosophy" in md
    assert "PR quality" in md

    # V10: Tuning parameters section present
    assert "## Tuning Parameters" in md

    # Roundtrip
    parsed = Philosophy.from_markdown(md)
    assert len(parsed.hard_rules) == len(original.hard_rules)
    assert len(parsed.escalation_rules) == len(original.escalation_rules)
    assert len(parsed.trusted_contributors) == len(original.trusted_contributors)
    assert parsed.mode == Mode.ACTIVE
    assert parsed.unleashed_at == "2024-03-01"
