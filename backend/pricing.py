"""Token prices and cost math (adapted from the Lecture 11 tokenomics starter).

Rates are US dollars per 1,000,000 tokens, from the published GPT-6 pricing:

                   input    cached input   cache write   output
    gpt-6-luna      0.10        0.01          0.125       0.50

`input_tokens` from the SDK is an inclusive total: cache reads and cache
writes are already inside it, so only the remainder is billed at the full
input rate. Cost is computed per request and summed, never from a run total,
because the long-context surcharge applies per request.
"""

from __future__ import annotations

from typing import Any

PRICES: dict[str, dict[str, float]] = {
    "gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "cache_write": 0.125, "output": 0.50},
}
DEFAULT_MODEL = "gpt-6-luna"

LONG_CONTEXT_THRESHOLD = 272_000
LONG_CONTEXT_INPUT_MULTIPLIER = 2.0
LONG_CONTEXT_OUTPUT_MULTIPLIER = 1.5


def rates_for(model: str) -> dict[str, float]:
    return PRICES.get(model, PRICES[DEFAULT_MODEL])


def cost_for_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> dict[str, Any]:
    """Cost of ONE request, with the billed breakdown."""
    rates = rates_for(model)
    cache_read = max(0, cache_read_tokens)
    cache_write = max(0, cache_write_tokens)
    uncached_input = max(0, input_tokens - cache_read - cache_write)

    long_context = input_tokens > LONG_CONTEXT_THRESHOLD
    in_mult = LONG_CONTEXT_INPUT_MULTIPLIER if long_context else 1.0
    out_mult = LONG_CONTEXT_OUTPUT_MULTIPLIER if long_context else 1.0

    cost = (
        uncached_input * rates["input"] * in_mult
        + cache_read * rates["cached_input"] * in_mult
        + cache_write * rates["cache_write"] * in_mult
        + max(0, output_tokens) * rates["output"] * out_mult
    ) / 1_000_000

    return {
        "cost_usd": cost,
        "billed_input_tokens": uncached_input,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
        "output_tokens": max(0, output_tokens),
        "long_context": long_context,
    }


def fmt_usd(amount: float) -> str:
    """Dollars that still show sub-cent spend."""
    if amount >= 0.01 or amount == 0:
        return f"${amount:,.2f}"
    if amount >= 0.0001:
        return f"${amount:.4f}"
    return f"${amount:.6f}"
