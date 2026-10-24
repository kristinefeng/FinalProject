"""Overspending: caps stop work before the model is called."""

import asyncio

import pytest

import db
from agents import zoom_out
from ledger import BudgetExceeded, Ledger


class Usage:
    def __init__(self, inp, out):
        self.input_tokens, self.output_tokens = inp, out
        self.cache_read_tokens = self.cache_write_tokens = 0
        self.details = {}


def test_per_run_cap_trips():
    ledger = Ledger("gpt-6-luna", budget_usd=0.001)
    ledger.check()
    ledger.charge("Pattern Finder", Usage(2_000_000, 1_000))  # $0.20 of input
    with pytest.raises(BudgetExceeded):
        ledger.check()


def test_cost_math_matches_the_price_card():
    ledger = Ledger("gpt-6-luna")
    u = Usage(10_000, 2_000)
    u.cache_read_tokens = 4_000
    charge = ledger.charge("Mirror", u)
    # 6,000 uncached x $0.10/M + 4,000 cached x $0.01/M + 2,000 out x $0.50/M
    assert charge["cost_usd"] == pytest.approx((6_000 * 0.10 + 4_000 * 0.01 + 2_000 * 0.50) / 1e6)


def test_daily_cap_stops_zoom_out_before_any_model_call(no_model):
    for i in range(3):
        db.insert_entry("me", {"id": f"e{i}", "date": f"2026-10-1{i}", "text": "Dinner with friends, laughing a lot."})
    db.save_run("me", "zoom_out", "gpt-6-luna", 5.00, {}, [])  # pretend today's budget is used up
    result = asyncio.run(zoom_out.zoom_out("me", "story"))
    assert result["status"] == "budget"
    assert "Daily budget" in result["message"]
