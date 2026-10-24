"""Memory Keeper: indexes each moment when it's saved, and gathers the right
moments when the person asks to zoom out.

Two jobs, two small agents sharing one role:
- tag_entry(): one request per saved entry. Writes a summary, tags, and (if
  there is a photo) a one-line description of the photo. This runs once, so
  later steps can work from cheap text instead of re-reading images.
- find_memories(): an agent loop with read-only search tools. It decides what
  to search for, reads the results, and returns the IDs it picked.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image
from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent, RunContext

import db
import retrieval
from agents.common import run_step
from config import load_prompt
from ledger import Ledger
from safety.injection import as_data

# Photos are shrunk before the model sees them: image tokens scale with size,
# and a 768px image is plenty to describe a scene.
PHOTO_MAX_PX = 768


class EntryTags(BaseModel):
    summary: str = Field(description="One plain sentence: what happened and how it felt.")
    themes: list[str] = Field(description="2-5 short lowercase themes.")
    values: list[str] = Field(description="Names from the person's value list that this entry clearly touches.")
    feelings: list[str] = Field(description="1-4 feelings the person expressed or clearly implied.")
    people: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    photo_description: str | None = Field(default=None, description="One sentence describing the photo, or null.")


tag_agent = Agent(output_type=EntryTags, instructions=load_prompt("memory_keeper_tag"))


def photo_for_model(path: Path) -> BinaryContent:
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((PHOTO_MAX_PX, PHOTO_MAX_PX))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
    return BinaryContent(data=buf.getvalue(), media_type="image/jpeg")


async def tag_entry(entry: dict[str, Any], value_names: list[str], photo_path: Path | None, ledger: Ledger) -> tuple[EntryTags, dict]:
    prompt: list[Any] = [
        f"The person's values: {', '.join(value_names) or '(none set yet)'}\n\n{as_data(entry)}"
    ]
    if photo_path and photo_path.exists():
        prompt.append("The photo attached to this entry:")
        prompt.append(photo_for_model(photo_path))
    tags, trace, _ = await run_step(tag_agent, prompt, name="Memory Keeper", ledger=ledger, request_limit=2)
    trace["step"] = "Index the new moment"
    return tags, trace


# ---------- finding memories for Zoom Out ----------

@dataclass
class FindDeps:
    space: str
    since: str | None
    seen: set[str]


class Selection(BaseModel):
    memory_ids: list[str] = Field(description="5-8 entry IDs, taken only from tool results.")
    search_notes: str = Field(description="One sentence on how you searched and why these moments.")


find_agent = Agent(deps_type=FindDeps, output_type=Selection, instructions=load_prompt("memory_keeper_find"))


@find_agent.tool
def search_memories(ctx: RunContext[FindDeps], query: str, since: str | None = None, until: str | None = None) -> list[dict]:
    """Search the person's saved moments by keywords, themes, values or feelings.
    Dates are YYYY-MM-DD. Returns short cards (id, date, title, summary, themes, values)."""
    results = retrieval.search(ctx.deps.space, query, since=since or ctx.deps.since, until=until, limit=6)
    ctx.deps.seen.update(r["id"] for r in results)
    return results


@find_agent.tool
def recent_memories(ctx: RunContext[FindDeps], n: int = 6) -> list[dict]:
    """The person's most recent moments, newest first (max 10)."""
    results = [r for r in retrieval.recent(ctx.deps.space, min(max(n, 1), 10)) if not ctx.deps.since or r["date"] >= ctx.deps.since]
    ctx.deps.seen.update(r["id"] for r in results)
    return results


async def find_memories(space: str, focus: str, since: str | None, value_names: list[str], ledger: Ledger) -> tuple[list[str], str, dict]:
    deps = FindDeps(space=space, since=since, seen=set())
    window = f"Only consider moments on or after {since}." if since else "Consider their whole journal."
    prompt = f"Focus for this Zoom Out: {focus}\n{window}\nTheir values: {', '.join(value_names) or '(none set)'}"
    selection, trace, _ = await run_step(find_agent, prompt, name="Memory Keeper", ledger=ledger, deps=deps)

    # Only keep IDs the tools actually returned: the agent can't invent a memory.
    valid = {e["id"] for e in db.list_entries(space) if retrieval.ai_visible(e)}
    chosen = [i for i in dict.fromkeys(selection.memory_ids) if i in deps.seen and i in valid][:8]
    rejected = [i for i in selection.memory_ids if i not in chosen]
    if len(chosen) < 3:  # fall back to the most recent moments rather than fail
        for card in retrieval.recent(space, 8):
            if card["id"] not in chosen and (not since or card["date"] >= since):
                chosen.append(card["id"])
            if len(chosen) >= 6:
                break
    trace["step"] = "Gather the moments that matter for this focus"
    trace["output"] = {"memory_ids": chosen, "notes": selection.search_notes, "rejected_ids": rejected}
    return chosen, selection.search_notes, trace
