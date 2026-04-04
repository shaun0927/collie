"""Core data models for Collie."""

from __future__ import annotations

import hashlib
import json
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
class GitHubItemMetadata:
    pull_request_id: str = ""
    author_association: str = "UNKNOWN"
    is_draft: bool = False
    review_decision: str = "UNKNOWN"
    mergeable: str = "UNKNOWN"
    auto_merge_enabled: bool = False
    merge_queue_required: bool = False
    required_check_state: str = "UNKNOWN"
    base_ref_name: str = ""
    head_ref_name: str = ""
    head_sha: str = ""
    linked_issue_numbers: list[int] = field(default_factory=list)
    repository_owner: str = ""
    repository_name: str = ""

    def to_dict(self) -> dict:
        return {
            "pull_request_id": self.pull_request_id,
            "author_association": self.author_association,
            "is_draft": self.is_draft,
            "review_decision": self.review_decision,
            "mergeable": self.mergeable,
            "auto_merge_enabled": self.auto_merge_enabled,
            "merge_queue_required": self.merge_queue_required,
            "required_check_state": self.required_check_state,
            "base_ref_name": self.base_ref_name,
            "head_ref_name": self.head_ref_name,
            "head_sha": self.head_sha,
            "linked_issue_numbers": list(self.linked_issue_numbers),
            "repository_owner": self.repository_owner,
            "repository_name": self.repository_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GitHubItemMetadata":
        return cls(
            pull_request_id=str(data.get("pull_request_id", "")),
            author_association=str(data.get("author_association", "UNKNOWN")),
            is_draft=bool(data.get("is_draft", False)),
            review_decision=str(data.get("review_decision", "UNKNOWN")),
            mergeable=str(data.get("mergeable", "UNKNOWN")),
            auto_merge_enabled=bool(data.get("auto_merge_enabled", False)),
            merge_queue_required=bool(data.get("merge_queue_required", False)),
            required_check_state=str(data.get("required_check_state", "UNKNOWN")),
            base_ref_name=str(data.get("base_ref_name", "")),
            head_ref_name=str(data.get("head_ref_name", "")),
            head_sha=str(data.get("head_sha", "")),
            linked_issue_numbers=[int(num) for num in data.get("linked_issue_numbers", [])],
            repository_owner=str(data.get("repository_owner", "")),
            repository_name=str(data.get("repository_name", "")),
        )

    @classmethod
    def from_github_item(cls, item: dict) -> "GitHubItemMetadata":
        linked = item.get("closingIssuesReferences", {}).get("nodes", [])
        commits = item.get("commits", {}).get("nodes", [])
        head_sha = ""
        required_check_state = "UNKNOWN"
        if commits:
            commit = commits[0].get("commit", {})
            head_sha = commit.get("oid", "")
            rollup = commit.get("statusCheckRollup") or {}
            required_check_state = rollup.get("state", "UNKNOWN")

        auto_merge = item.get("autoMergeRequest")
        repository = item.get("repository", {})
        owner = repository.get("owner", {}).get("login", "")

        return cls(
            pull_request_id=str(item.get("id", "")),
            author_association=str(item.get("authorAssociation", "UNKNOWN")),
            is_draft=bool(item.get("isDraft", False)),
            review_decision=str(item.get("reviewDecision", "UNKNOWN")),
            mergeable=str(item.get("mergeable", "UNKNOWN")),
            auto_merge_enabled=auto_merge is not None,
            merge_queue_required=bool(item.get("mergeQueueRequired", False)),
            required_check_state=required_check_state,
            base_ref_name=str(item.get("baseRefName", "")),
            head_ref_name=str(item.get("headRefName", "")),
            head_sha=head_sha,
            linked_issue_numbers=[int(node["number"]) for node in linked if node.get("number") is not None],
            repository_owner=str(owner),
            repository_name=str(repository.get("name", "")),
        )


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
    execution_path: str = ""
    github_metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "item_type": self.item_type.value,
            "action": self.action.value,
            "reason": self.reason,
            "status": self.status.value,
            "title": self.title,
            "analysis_coverage": self.analysis_coverage,
            "suggested_comment": self.suggested_comment,
            "suggested_labels": list(self.suggested_labels),
            "linked_pr": self.linked_pr,
            "created_at": self.created_at,
            "executed_at": self.executed_at,
            "failure_reason": self.failure_reason,
            "execution_path": self.execution_path,
            "github_metadata": self.github_metadata,
        }

    def payload_hash(self) -> str:
        payload = self.to_dict()
        payload.pop("status", None)
        payload.pop("created_at", None)
        payload.pop("executed_at", None)
        payload.pop("failure_reason", None)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    @classmethod
    def from_dict(cls, data: dict) -> "Recommendation":
        item_type_raw = data.get("item_type", ItemType.PR.value)
        action_raw = data.get("action", RecommendationAction.HOLD.value)
        status_raw = data.get("status", RecommendationStatus.PENDING.value)

        return cls(
            number=int(data["number"]),
            item_type=ItemType(item_type_raw),
            action=RecommendationAction(action_raw),
            reason=str(data.get("reason", "")),
            status=RecommendationStatus(status_raw),
            title=str(data.get("title", "")),
            analysis_coverage=str(data.get("analysis_coverage", "")),
            suggested_comment=str(data.get("suggested_comment", "")),
            suggested_labels=list(data.get("suggested_labels", [])),
            linked_pr=data.get("linked_pr"),
            created_at=str(data.get("created_at", "")),
            executed_at=str(data.get("executed_at", "")),
            failure_reason=str(data.get("failure_reason", "")),
            execution_path=str(data.get("execution_path", "")),
            github_metadata=dict(data.get("github_metadata", {})),
        )


@dataclass
class ApprovalRecord:
    number: int
    approver: str
    approved_payload_hash: str
    approved_at: str
    source: str = "cli"

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "approver": self.approver,
            "approved_payload_hash": self.approved_payload_hash,
            "approved_at": self.approved_at,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ApprovalRecord":
        return cls(
            number=int(data["number"]),
            approver=str(data["approver"]),
            approved_payload_hash=str(data["approved_payload_hash"]),
            approved_at=str(data["approved_at"]),
            source=str(data.get("source", "cli")),
        )
