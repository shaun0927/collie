"""Tests for data models."""

from __future__ import annotations

from collie.core.models import (
    EscalationRule,
    HardRule,
    ItemType,
    Mode,
    Philosophy,
    Recommendation,
    RecommendationAction,
    RecommendationStatus,
    TuningParams,
)


def test_philosophy_roundtrip():
    """Test that to_markdown() -> from_markdown() preserves data."""
    p = Philosophy(
        hard_rules=[HardRule("ci_failed", "reject", "CI must pass")],
        soft_text="We prioritize backward compatibility.",
        tuning=TuningParams(confidence_threshold=0.85),
        trusted_contributors=["alice", "bob"],
        mode=Mode.TRAINING,
    )
    markdown = p.to_markdown()
    parsed = Philosophy.from_markdown(markdown)
    assert len(parsed.hard_rules) == 1
    assert parsed.hard_rules[0].condition == "ci_failed"
    assert parsed.hard_rules[0].action == "reject"
    assert parsed.hard_rules[0].description == "CI must pass"
    assert parsed.soft_text == "We prioritize backward compatibility."
    assert parsed.tuning.confidence_threshold == 0.85
    assert parsed.trusted_contributors == ["alice", "bob"]
    assert parsed.mode == Mode.TRAINING


def test_philosophy_empty_roundtrip():
    """Empty philosophy roundtrip preserves defaults."""
    p = Philosophy()
    markdown = p.to_markdown()
    parsed = Philosophy.from_markdown(markdown)
    assert parsed.hard_rules == []
    assert parsed.soft_text == ""
    assert parsed.trusted_contributors == []
    assert parsed.escalation_rules == []
    assert parsed.mode == Mode.TRAINING
    assert parsed.tuning.confidence_threshold == 0.9
    assert parsed.tuning.analysis_depth == "t2"
    assert parsed.tuning.cost_cap_per_bark == 50.0


def test_philosophy_multiple_hard_rules():
    """Multiple hard rules survive roundtrip."""
    p = Philosophy(
        hard_rules=[
            HardRule("ci_failed", "reject", "CI must pass"),
            HardRule("no_tests", "hold", "PRs should include tests"),
            HardRule("breaking_change", "escalate", "Escalate breaking changes"),
        ],
    )
    markdown = p.to_markdown()
    parsed = Philosophy.from_markdown(markdown)
    assert len(parsed.hard_rules) == 3
    conditions = [r.condition for r in parsed.hard_rules]
    assert "ci_failed" in conditions
    assert "no_tests" in conditions
    assert "breaking_change" in conditions


def test_philosophy_with_escalation_rules():
    """Escalation rules survive roundtrip."""
    p = Philosophy(
        escalation_rules=[
            EscalationRule("security/*", "escalate", "Security changes need review"),
            EscalationRule("crypto/", "t3_required"),
        ],
    )
    markdown = p.to_markdown()
    parsed = Philosophy.from_markdown(markdown)
    assert len(parsed.escalation_rules) == 2
    patterns = [r.pattern for r in parsed.escalation_rules]
    assert "security/*" in patterns
    assert "crypto/" in patterns


def test_philosophy_active_mode():
    """Active mode is preserved in roundtrip."""
    p = Philosophy(mode=Mode.ACTIVE)
    markdown = p.to_markdown()
    parsed = Philosophy.from_markdown(markdown)
    assert parsed.mode == Mode.ACTIVE


def test_philosophy_tuning_roundtrip():
    """All tuning params survive roundtrip."""
    p = Philosophy(
        tuning=TuningParams(confidence_threshold=0.75, analysis_depth="t3", cost_cap_per_bark=100.0),
    )
    markdown = p.to_markdown()
    parsed = Philosophy.from_markdown(markdown)
    assert parsed.tuning.confidence_threshold == 0.75
    assert parsed.tuning.analysis_depth == "t3"
    assert parsed.tuning.cost_cap_per_bark == 100.0


def test_philosophy_with_timestamps():
    """Timestamps survive roundtrip."""
    p = Philosophy(
        created_at="2026-04-01",
        updated_at="2026-04-02",
        unleashed_at="2026-04-03",
    )
    markdown = p.to_markdown()
    parsed = Philosophy.from_markdown(markdown)
    assert parsed.created_at == "2026-04-01"
    assert parsed.updated_at == "2026-04-02"
    assert parsed.unleashed_at == "2026-04-03"


def test_philosophy_to_markdown_contains_sections():
    """to_markdown includes all expected section headers."""
    p = Philosophy()
    md = p.to_markdown()
    assert "# 🐕 Collie Philosophy" in md
    assert "## Hard Rules" in md
    assert "## Trusted Contributors" in md
    assert "## Escalation Rules" in md
    assert "## Tuning Parameters" in md
    assert "## Philosophy" in md


def test_recommendation_dataclass():
    """Recommendation dataclass stores fields correctly."""
    r = Recommendation(
        number=142,
        item_type=ItemType.PR,
        action=RecommendationAction.MERGE,
        reason="CI passed, 2 reviews",
        title="Add dark mode",
    )
    assert r.number == 142
    assert r.item_type == ItemType.PR
    assert r.action == RecommendationAction.MERGE
    assert r.status == RecommendationStatus.PENDING
    assert r.title == "Add dark mode"
    assert r.suggested_labels == []
    assert r.linked_pr is None
