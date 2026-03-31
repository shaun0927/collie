"""Tests for CostTracker."""

from collie.core.cost_tracker import CostTracker


def test_can_afford_within_budget():
    ct = CostTracker(cap_usd=10.0)
    assert ct.can_afford(4000) is True


def test_can_afford_exceeds_budget():
    ct = CostTracker(cap_usd=0.001)
    ct.record(1_000_000, 1_000_000)
    assert ct.can_afford(4000) is False


def test_record_updates_totals():
    ct = CostTracker(cap_usd=50.0)
    ct.record(1000, 500)
    assert ct.total_input_tokens == 1000
    assert ct.total_output_tokens == 500
    assert ct.call_count == 1
    assert ct.total_cost_usd > 0


def test_summary_format():
    ct = CostTracker(cap_usd=50.0)
    ct.record(1000, 500)
    s = ct.summary()
    assert "calls" in s
    assert "tokens" in s
    assert "$" in s


def test_budget_remaining():
    ct = CostTracker(cap_usd=50.0)
    assert ct.budget_remaining == 50.0
    ct.record(1_000_000, 500_000)
    assert ct.budget_remaining < 50.0


def test_zero_budget():
    ct = CostTracker(cap_usd=0.0)
    assert ct.can_afford(1) is False
    assert ct.budget_used_pct == 100.0


def test_multiple_records():
    ct = CostTracker(cap_usd=50.0)
    ct.record(1000, 500)
    ct.record(2000, 1000)
    assert ct.call_count == 2
    assert ct.total_input_tokens == 3000
    assert ct.total_output_tokens == 1500
