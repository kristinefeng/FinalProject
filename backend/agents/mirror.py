"""Mirror: turns grounded patterns into one short reflection and one question,
and listens when the person pushes back.

In Reflect Back, the Mirror may suggest a change to the North Star with the
propose_north_star_update tool. The tool only stages a proposal. Nothing
changes until the person clicks Accept, so the AI never rewrites what someone
says matters to them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from agents.common import run_step
from agents.pattern_finder import north_star_block
from config import load_prompt
from ledger import Ledger


class Reflection(BaseModel):
    headline: str = Field(description="At most 10 words.")
    reflection: str = Field(description="90-150 words, second person.")
    question: str = Field(description="One open question to sit with.")


reflect_agent = Agent(output_type=Reflection, instructions=load_prompt("mirror"))


def patterns_block(patterns: list[dict[str, Any]]) -> str:
    lines = []
    for i, p in enumerate(patterns, 1):
        quotes = "; ".join(f'"{ev["quote"]}" ({ev["title"]}, {ev["date"]})' for ev in p["evidence"])
        lines.append(f"{i}. [{p['kind']}] {p['title']} (value: {p.get('value') or 'none'})\n   {p['observation']}\n   Evidence: {quotes}")
    return "\n".join(lines)


async def write_reflection(ns: dict[str, Any], focus: str, patterns: list[dict[str, Any]], ledger: Ledger) -> tuple[Reflection, dict]:
    prompt = f"{north_star_block(ns)}\n\nFocus: {focus}\n\nVerified patterns:\n{patterns_block(patterns)}"
    out, trace, _ = await run_step(reflect_agent, prompt, name="Mirror", ledger=ledger, request_limit=2)
    trace["step"] = "Write the reflection and one question"
    return out, trace


# ---------- Reflect Back ----------

@dataclass
class ReflectDeps:
    value_names: list[str]
    proposals: list[dict[str, Any]] = field(default_factory=list)


class FollowUp(BaseModel):
    reply: str = Field(description="2-4 sentences.")
    follow_up_question: str


respond_agent = Agent(deps_type=ReflectDeps, output_type=FollowUp, instructions=load_prompt("mirror_reflect_back"))


@respond_agent.tool
def propose_north_star_update(
    ctx: RunContext[ReflectDeps],
    action: Literal["add_value", "reword_value", "add_intention"],
    value_name: str,
    new_text: str,
    reason: str,
) -> str:
    """Suggest one change to the person's North Star. This does NOT change anything:
    it shows the person a card they can accept or dismiss. Use at most once."""
    if ctx.deps.proposals:
        return "A suggestion is already waiting for the person. Don't make another."
    ctx.deps.proposals.append({"action": action, "value_name": value_name.strip()[:40], "new_text": new_text.strip()[:240], "reason": reason.strip()[:240]})
    return "Suggestion staged. The person will decide whether to accept it."


async def reflect_back(ns: dict[str, Any], pattern: dict[str, Any], verdict: str, note: str, ledger: Ledger) -> tuple[FollowUp, dict | None, dict]:
    deps = ReflectDeps(value_names=[v.get("name", "") for v in ns.get("values", [])])
    verdict_text = {"resonates": "This resonates with me.", "partly": "This is partly true.", "not_me": "This doesn't feel like me."}[verdict]
    prompt = (
        f"{north_star_block(ns)}\n\nThe pattern you showed them:\n{patterns_block([pattern])}\n\n"
        f"Their response: {verdict_text}\n<their_words>{note.strip()[:1000] or '(no words added)'}</their_words>"
    )
    out, trace, _ = await run_step(respond_agent, prompt, name="Mirror", ledger=ledger, deps=deps, request_limit=3)
    trace["step"] = "Listen to the response and adjust"
    return out, (deps.proposals[0] if deps.proposals else None), trace
