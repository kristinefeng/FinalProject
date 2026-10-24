"""Per-run money meter. Every model request is charged the moment it returns.

Three caps stop runaway spend:
- RUN_BUDGET_USD: one Zoom Out (or one save) can't cost more than this.
- DAILY_BUDGET_USD: all runs in a day, summed from the runs table.
- REQUEST_LIMIT: each agent gets a fixed number of model requests, so a tool
  loop can't spin forever (enforced with pydantic-ai UsageLimits).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from pricing import cost_for_usage, rates_for

RUN_BUDGET_USD = float(os.getenv("RUN_BUDGET_USD", "0.05"))
DAILY_BUDGET_USD = float(os.getenv("DAILY_BUDGET_USD", "1.00"))
REQUEST_LIMIT = int(os.getenv("REQUEST_LIMIT", "6"))


class BudgetExceeded(Exception):
    def __init__(self, scope: str, spent: float, budget: float) -> None:
        super().__init__(f"{scope} budget of ${budget:,.2f} reached (spent ${spent:,.4f}).")
        self.scope = scope
        self.spent = spent
        self.budget = budget


@dataclass
class AgentSpend:
    agent: str
    requests: int = 0
    input_tokens: int = 0
    billed_input_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "cost_usd": round(self.cost_usd, 8)}


@dataclass
class Ledger:
    model: str
    budget_usd: float = RUN_BUDGET_USD
    spent_today_usd: float = 0.0
    daily_budget_usd: float = DAILY_BUDGET_USD
    agents: dict[str, AgentSpend] = field(default_factory=dict)
    total_cost_usd: float = 0.0

    def check(self) -> None:
        """Raise before starting more work if either cap is already reached."""
        if self.total_cost_usd >= self.budget_usd:
            raise BudgetExceeded("Per-run", self.total_cost_usd, self.budget_usd)
        if self.spent_today_usd + self.total_cost_usd >= self.daily_budget_usd:
            raise BudgetExceeded("Daily", self.spent_today_usd + self.total_cost_usd, self.daily_budget_usd)

    def charge(self, agent: str, usage: Any) -> dict[str, Any]:
        """Bill one model request (a RequestUsage) to `agent`."""
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        cache_read = int(getattr(usage, "cache_read_tokens", 0) or 0)
        cache_write = int(getattr(usage, "cache_write_tokens", 0) or 0)
        details = getattr(usage, "details", None) or {}
        reasoning = int(details.get("reasoning_tokens", 0) or 0)

        charge = cost_for_usage(self.model, input_tokens, output_tokens, cache_read, cache_write)
        spend = self.agents.setdefault(agent, AgentSpend(agent=agent))
        spend.requests += 1
        spend.input_tokens += input_tokens
        spend.billed_input_tokens += charge["billed_input_tokens"]
        spend.cache_read_tokens += cache_read
        spend.cache_write_tokens += cache_write
        spend.output_tokens += output_tokens
        spend.reasoning_tokens += reasoning
        spend.cost_usd += charge["cost_usd"]
        self.total_cost_usd += charge["cost_usd"]
        return {**charge, "agent": agent, "input_tokens": input_tokens, "reasoning_tokens": reasoning}

    def totals(self) -> dict[str, int]:
        keys = ("requests", "input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens")
        return {k: sum(getattr(s, k) for s in self.agents.values()) for k in keys}

    def snapshot(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "rates": rates_for(self.model),
            "budget_usd": self.budget_usd,
            "daily_budget_usd": self.daily_budget_usd,
            "spent_today_usd": round(self.spent_today_usd + self.total_cost_usd, 8),
            "total_cost_usd": round(self.total_cost_usd, 8),
            "totals": self.totals(),
            "agents": [s.as_dict() for s in self.agents.values()],
        }
