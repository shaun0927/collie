"""Core data models for Collie."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

import yaml


class Mode(str, Enum):
    TRAINING = "training"
    ACTIVE = "active"


class ItemType(str, Enum):
    PR = "pr"
    ISSUE = "issue"


class RecommendationAction(str, Enum):
    MERGE = "merge"
    CLOSE = "close"
    HOLD = "hold"
    ESCALATE = "escalate"
    LABEL = "label"
    COMMENT = "comment"
    LINK_TO_PR = "link_to_pr"


class RecommendationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTED = "executed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class HardRule:
    condition: str  # e.g., "ci_failed", "no_tests"
    action: str  # e.g., "reject", "hold"
    description: str = ""


@dataclass
class EscalationRule:
    pattern: str  # e.g., "security/*", "crypto/"
    action: str  # e.g., "escalate", "t3_required"
    description: str = ""


@dataclass
class TuningParams:
    confidence_threshold: float = 0.9
    analysis_depth: str = "t2"  # t1, t2, t3
    cost_cap_per_bark: float = 50.0  # USD


@dataclass
class Philosophy:
    hard_rules: list[HardRule] = field(default_factory=list)
    soft_text: str = ""
    tuning: TuningParams = field(default_factory=TuningParams)
    trusted_contributors: list[str] = field(default_factory=list)
    escalation_rules: list[EscalationRule] = field(default_factory=list)
    mode: Mode = Mode.TRAINING
    created_at: str = ""
    updated_at: str = ""
    unleashed_at: str | None = None

    def to_markdown(self) -> str:
        """Serialize to Discussion-friendly markdown."""
        lines = []

        # Header
        mode_val = self.mode.value if isinstance(self.mode, Mode) else self.mode
        lines.append("# 🐕 Collie Philosophy")
        meta_parts = [f"Mode: {mode_val}"]
        if self.created_at:
            meta_parts.append(f"Created: {self.created_at}")
        if self.updated_at:
            meta_parts.append(f"Updated: {self.updated_at}")
        if self.unleashed_at:
            meta_parts.append(f"Unleashed: {self.unleashed_at}")
        lines.append(f"> {' | '.join(meta_parts)}")
        lines.append("")

        # Hard Rules
        lines.append("## Hard Rules")
        if self.hard_rules:
            rules_data = {
                "rules": [
                    {"condition": r.condition, "action": r.action, "description": r.description}
                    for r in self.hard_rules
                ]
            }
            lines.append("```yaml")
            lines.append(yaml.dump(rules_data, default_flow_style=False).rstrip())
            lines.append("```")
        else:
            lines.append("```yaml")
            lines.append("rules: []")
            lines.append("```")
        lines.append("")

        # Trusted Contributors
        lines.append("## Trusted Contributors")
        if self.trusted_contributors:
            for contributor in self.trusted_contributors:
                lines.append(f"- {contributor}")
        else:
            lines.append("_None_")
        lines.append("")

        # Escalation Rules
        lines.append("## Escalation Rules")
        if self.escalation_rules:
            escalation_data = {
                "escalation": [
                    {"pattern": r.pattern, "action": r.action, "description": r.description}
                    for r in self.escalation_rules
                ]
            }
            lines.append("```yaml")
            lines.append(yaml.dump(escalation_data, default_flow_style=False).rstrip())
            lines.append("```")
        else:
            lines.append("```yaml")
            lines.append("escalation: []")
            lines.append("```")
        lines.append("")

        # Tuning Parameters
        lines.append("## Tuning Parameters")
        tuning_data = {
            "tuning": {
                "confidence_threshold": self.tuning.confidence_threshold,
                "analysis_depth": self.tuning.analysis_depth,
                "cost_cap_per_bark": self.tuning.cost_cap_per_bark,
            }
        }
        lines.append("```yaml")
        lines.append(yaml.dump(tuning_data, default_flow_style=False).rstrip())
        lines.append("```")
        lines.append("")

        # Philosophy (soft text)
        lines.append("## Philosophy")
        if self.soft_text:
            lines.append(self.soft_text)
        else:
            lines.append("_No philosophy defined yet._")

        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, text: str) -> "Philosophy":
        """Parse from Discussion markdown."""
        hard_rules: list[HardRule] = []
        soft_text = ""
        tuning = TuningParams()
        trusted_contributors: list[str] = []
        escalation_rules: list[EscalationRule] = []
        mode = Mode.TRAINING
        created_at = ""
        updated_at = ""
        unleashed_at = None

        # Parse metadata from header line
        meta_match = re.search(r"^>\s*(.+)$", text, re.MULTILINE)
        if meta_match:
            meta_line = meta_match.group(1)
            mode_m = re.search(r"Mode:\s*(\w+)", meta_line)
            if mode_m:
                try:
                    mode = Mode(mode_m.group(1).lower())
                except ValueError:
                    mode = Mode.TRAINING
            created_m = re.search(r"Created:\s*([^|]+)", meta_line)
            if created_m:
                created_at = created_m.group(1).strip()
            updated_m = re.search(r"Updated:\s*([^|]+)", meta_line)
            if updated_m:
                updated_at = updated_m.group(1).strip()
            unleashed_m = re.search(r"Unleashed:\s*([^|]+)", meta_line)
            if unleashed_m:
                unleashed_at = unleashed_m.group(1).strip()

        # Extract YAML code blocks by section
        # Split into sections by ## headings
        sections: dict[str, str] = {}
        current_section = None
        current_lines: list[str] = []

        for line in text.splitlines():
            heading_match = re.match(r"^##\s+(.+)$", line)
            if heading_match:
                if current_section is not None:
                    sections[current_section] = "\n".join(current_lines)
                current_section = heading_match.group(1).strip()
                current_lines = []
            elif current_section is not None:
                current_lines.append(line)

        if current_section is not None:
            sections[current_section] = "\n".join(current_lines)

        # Parse Hard Rules
        if "Hard Rules" in sections:
            yaml_content = _extract_yaml_block(sections["Hard Rules"])
            if yaml_content:
                data = yaml.safe_load(yaml_content)
                if data and "rules" in data and data["rules"]:
                    for r in data["rules"]:
                        hard_rules.append(
                            HardRule(
                                condition=r.get("condition", ""),
                                action=r.get("action", ""),
                                description=r.get("description", ""),
                            )
                        )

        # Parse Trusted Contributors
        if "Trusted Contributors" in sections:
            for line in sections["Trusted Contributors"].splitlines():
                m = re.match(r"^-\s+(.+)$", line.strip())
                if m:
                    trusted_contributors.append(m.group(1).strip())

        # Parse Escalation Rules
        if "Escalation Rules" in sections:
            yaml_content = _extract_yaml_block(sections["Escalation Rules"])
            if yaml_content:
                data = yaml.safe_load(yaml_content)
                if data and "escalation" in data and data["escalation"]:
                    for r in data["escalation"]:
                        escalation_rules.append(
                            EscalationRule(
                                pattern=r.get("pattern", ""),
                                action=r.get("action", ""),
                                description=r.get("description", ""),
                            )
                        )

        # Parse Tuning Parameters
        if "Tuning Parameters" in sections:
            yaml_content = _extract_yaml_block(sections["Tuning Parameters"])
            if yaml_content:
                data = yaml.safe_load(yaml_content)
                if data and "tuning" in data and data["tuning"]:
                    t = data["tuning"]
                    tuning = TuningParams(
                        confidence_threshold=float(t.get("confidence_threshold", 0.9)),
                        analysis_depth=str(t.get("analysis_depth", "t2")),
                        cost_cap_per_bark=float(t.get("cost_cap_per_bark", 50.0)),
                    )

        # Parse Philosophy (soft text)
        if "Philosophy" in sections:
            raw = sections["Philosophy"].strip()
            if raw and raw != "_No philosophy defined yet._":
                soft_text = raw

        return cls(
            hard_rules=hard_rules,
            soft_text=soft_text,
            tuning=tuning,
            trusted_contributors=trusted_contributors,
            escalation_rules=escalation_rules,
            mode=mode,
            created_at=created_at,
            updated_at=updated_at,
            unleashed_at=unleashed_at,
        )


def _extract_yaml_block(text: str) -> str | None:
    """Extract content from first ```yaml ... ``` block in text."""
    m = re.search(r"```yaml\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1)
    return None


@dataclass
class Recommendation:
    number: int
    item_type: ItemType
    action: RecommendationAction
    reason: str
    status: RecommendationStatus = RecommendationStatus.PENDING
    title: str = ""
    analysis_coverage: str = ""  # e.g., "120/150 files analyzed"
    suggested_comment: str = ""  # for comment actions
    suggested_labels: list[str] = field(default_factory=list)  # for label actions
    linked_pr: int | None = None  # for link_to_pr actions
    created_at: str = ""
    executed_at: str = ""
    failure_reason: str = ""
