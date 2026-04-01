"""Tests for GitHub Action configuration."""

import yaml


def test_action_yml_valid():
    """action.yml is valid YAML with required fields."""
    with open("action.yml") as f:
        action = yaml.safe_load(f)
    assert action["name"] == "Collie Bark"
    assert "inputs" in action
    assert "github-token" in action["inputs"]
    assert action["inputs"]["github-token"]["required"] is True
    assert "runs" in action
    assert action["runs"]["using"] == "composite"


def test_action_has_anthropic_key_input():
    with open("action.yml") as f:
        action = yaml.safe_load(f)
    assert "anthropic-api-key" in action["inputs"]
    # Not required — LLM is optional
    assert action["inputs"]["anthropic-api-key"]["required"] is False


def test_action_has_cost_cap():
    with open("action.yml") as f:
        action = yaml.safe_load(f)
    assert "cost-cap" in action["inputs"]
    assert action["inputs"]["cost-cap"]["default"] == "50"


def test_example_workflow_valid():
    with open(".github/workflows/collie-example.yml") as f:
        wf = yaml.safe_load(f)
    # YAML parses bare `on:` as boolean True
    on_key = True if True in wf else "on"
    assert on_key in wf
    triggers = wf[on_key]
    assert "schedule" in triggers
    assert "workflow_dispatch" in triggers
    assert "jobs" in wf
    assert "triage" in wf["jobs"]
