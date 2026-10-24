"""Pattern Finder: reads the gathered moments next to the person's North Star
and names up to three throughlines, each backed by quotes from real entries.

Every quote is checked in code (safety/grounding.py) before it's shown. If
nothing survives, the agent gets one retry with the reasons it failed.

Prompt order matters for cost: the long fixed instructions and the person's
North Star come first and rarely change, so repeat runs read them from the
prompt cache at a tenth of the price. The moments come last.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

import db
import retrieval
from agents.common import run_step
from config import load_prompt
from ledger import Ledger
from safety.grounding import ground_patterns
from safety.injection import as_data


class Evidence(BaseModel):
    memory_id: str
    quote: str = Field(description="4-20 words copied exactly from that entry's text.")


class Pattern(BaseModel):
    title: str = Field(description="At most 8 words.")
    kind: Literal["alignment", "tension", "growth", "forgotten"]
    observation: str = Field(description="2-3 tentative sentences, second person.")
    value: str | None = Field(default=None, description="The North Star value this relates to, if any.")
    evidence: list[Evidence] = Field(description="2-4 pieces of evidence from different entries.")


class Patterns(BaseModel):
    patterns: list[Pattern] = Field(description="1-3 patterns.")


@dataclass
class PatternDeps:
    space: str
    shown: dict[str, dict[str, Any]] = field(default_factory=dict)


agent = Agent(deps_type=PatternDeps, output_type=Patterns, instructions=load_prompt("pattern_finder"))


@agent.tool
def get_memory(ctx: RunContext[PatternDeps], memory_id: str) -> str:
    """Read the full text of one more saved moment by its ID."""
    entry = db.get_entry(ctx.deps.space, memory_id)
    if not entry or not retrieval.ai_visible(entry):
        return f"No moment with id {memory_id}."
    ctx.deps.shown[entry["id"]] = entry
    return as_data(entry)


@agent.tool
def get_past_feedback(ctx: RunContext[PatternDeps]) -> list[dict]:
    """What the person said about earlier reflections (resonates / partly / not me).
    Use it so you don't repeat a pattern they rejected."""
    return db.list_feedback(ctx.deps.space, limit=8)


def north_star_block(ns: dict[str, Any]) -> str:
    values = "\n".join(f"- {v.get('name')}: {v.get('meaning', '')}" for v in ns.get("values", []))
    intentions = "\n".join(f"- {i}" for i in ns.get("intentions", []))
    return f"<north_star>\nValues:\n{values or '- (none yet)'}\nVision: {ns.get('vision') or '(not written yet)'}\nIntentions:\n{intentions or '- (none)'}\n</north_star>"


async def find_patterns(space: str, focus: str, memory_ids: list[str], ledger: Ledger) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (grounded patterns, dropped evidence, trace steps)."""
    deps = PatternDeps(space=space)
    for mid in memory_ids:
        entry = db.get_entry(space, mid)
        if entry and retrieval.ai_visible(entry):
            deps.shown[mid] = entry

    ns = db.get_north_star(space)
    moments = "\n\n".join(as_data(e) for e in sorted(deps.shown.values(), key=lambda e: e["date"]))
    prompt = f"{north_star_block(ns)}\n\nFocus: {focus}\n\nThe moments to read:\n\n{moments}"

    output, trace, messages = await run_step(agent, prompt, name="Pattern Finder", ledger=ledger, deps=deps, effort="medium")
    trace["step"] = "Find the throughlines and back each with quotes"
    steps = [trace]
    raw = [p.model_dump() for p in output.patterns]
    kept, dropped = ground_patterns(raw, deps.shown)
    trace["output"] = {"proposed": len(raw), "kept": len(kept), "dropped_evidence": len(dropped)}

    if not kept:  # one corrective retry, telling the agent exactly what failed
        reasons = json.dumps(dropped[:6])
        retry_prompt = (
            "None of your evidence could be verified against the entries. Problems: "
            f"{reasons}\nTry again. Copy each quote exactly, word for word, from the entry it cites."
        )
        output, retry_trace, _ = await run_step(
            agent, retry_prompt, name="Pattern Finder", ledger=ledger, deps=deps, effort="medium", message_history=messages
        )
        retry_trace["step"] = "Retry after the grounding check rejected every quote"
        raw = [p.model_dump() for p in output.patterns]
        kept, dropped_again = ground_patterns(raw, deps.shown)
        retry_trace["output"] = {"proposed": len(raw), "kept": len(kept), "dropped_evidence": len(dropped_again)}
        dropped += dropped_again
        steps.append(retry_trace)

    # Attach what the UI needs to show each piece of evidence.
    for p in kept:
        for ev in p["evidence"]:
            e = deps.shown[ev["memory_id"]]
            ev.update({"date": e["date"], "title": e.get("title") or "", "photo": e.get("photo")})
    return kept[:3], dropped, steps
