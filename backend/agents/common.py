"""Shared plumbing: run one agent step, bill every request, record a trace.

The trace is what the "How this was made" panel shows: which agent ran,
which tools it called with which arguments, what came back, and what each
step cost. The same trace is saved with the run for the report.
"""

from __future__ import annotations

import json
import time
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.openai import OpenAIResponsesModelSettings
from pydantic_ai.usage import UsageLimits

from config import build_model
from ledger import REQUEST_LIMIT, Ledger


class StepFailed(Exception):
    def __init__(self, message: str, trace: dict[str, Any]) -> None:
        super().__init__(message)
        self.trace = trace


def settings(effort: str = "low") -> OpenAIResponsesModelSettings:
    return OpenAIResponsesModelSettings(openai_reasoning_effort=effort)


def _short(value: Any, limit: int = 400) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + "…"


async def run_step(
    agent: Agent,
    prompt: Any,
    *,
    name: str,
    ledger: Ledger,
    deps: Any = None,
    effort: str = "low",
    request_limit: int = REQUEST_LIMIT,
    message_history: list | None = None,
) -> tuple[Any, dict[str, Any], list]:
    """Run `agent` once. Returns (output, trace step, all messages)."""
    ledger.check()
    started = time.perf_counter()
    try:
        result = await agent.run(
            prompt,
            model=build_model(),
            deps=deps,
            model_settings=settings(effort),
            usage_limits=UsageLimits(request_limit=request_limit),
            message_history=message_history,
        )
    except UsageLimitExceeded as exc:
        trace = {"agent": name, "status": "stopped", "reason": f"request limit of {request_limit} reached", "tools": []}
        raise StepFailed(str(exc), trace) from exc

    tools: list[dict[str, Any]] = []
    by_call: dict[str, dict[str, Any]] = {}
    tokens = {"input": 0, "cached_input": 0, "cache_write": 0, "output": 0, "reasoning": 0}
    cost = 0.0
    requests = 0
    for msg in result.new_messages():
        if isinstance(msg, ModelResponse):
            charge = ledger.charge(name, msg.usage)
            requests += 1
            cost += charge["cost_usd"]
            tokens["input"] += charge["input_tokens"]
            tokens["cached_input"] += charge["cache_read_tokens"]
            tokens["cache_write"] += charge["cache_write_tokens"]
            tokens["output"] += charge["output_tokens"]
            tokens["reasoning"] += charge["reasoning_tokens"]
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    call = {"tool": part.tool_name, "args": part.args_as_dict(), "result": None}
                    by_call[part.tool_call_id] = call
                    tools.append(call)
        elif isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, ToolReturnPart) and part.tool_call_id in by_call:
                    by_call[part.tool_call_id]["result"] = _short(part.content)

    trace = {
        "agent": name,
        "status": "ok",
        "requests": requests,
        "tools": [t for t in tools if t["tool"] != "final_result"],
        "tokens": tokens,
        "cost_usd": round(cost, 8),
        "seconds": round(time.perf_counter() - started, 2),
    }
    return result.output, trace, result.all_messages()
