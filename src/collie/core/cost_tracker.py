"""Cost tracking for LLM API usage."""

from __future__ import annotations

from dataclasses import dataclass

# Approximate pricing per 1M tokens (Anthropic Claude)
PRICING = {
    "claude-sonnet": {"input": 3.0, "output": 15.0},
    "claude-haiku": {"input": 0.25, "output": 1.25},
    "claude-opus": {"input": 15.0, "output": 75.0},
    "default": {"input": 3.0, "output": 15.0},
}


@dataclass
class CostTracker:
    """Track and limit LLM API costs within a bark run."""

    cap_usd: float = 50.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    model: str = "default"
    call_count: int = 0

    def can_afford(self, estimated_tokens: int = 4000) -> bool:
        """Check if we can afford another LLM call."""
        pricing = PRICING.get(self.model, PRICING["default"])
        estimated_cost = (estimated_tokens / 1_000_000) * (pricing["input"] + pricing["output"])
        return (self.total_cost_usd + estimated_cost) <= self.cap_usd

    def record(self, input_tokens: int, output_tokens: int):
        """Record usage from an LLM call."""
        pricing = PRICING.get(self.model, PRICING["default"])
        cost = (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost
        self.call_count += 1

    def summary(self) -> str:
        """Human-readable cost summary."""
        return (
            f"LLM Usage: {self.call_count} calls, "
            f"{self.total_input_tokens + self.total_output_tokens:,} tokens, "
            f"${self.total_cost_usd:.2f} / ${self.cap_usd:.2f} budget"
        )

    @property
    def budget_remaining(self) -> float:
        return max(0, self.cap_usd - self.total_cost_usd)

    @property
    def budget_used_pct(self) -> float:
        if self.cap_usd == 0:
            return 100.0
        return (self.total_cost_usd / self.cap_usd) * 100
