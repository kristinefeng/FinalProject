"""Zoom Out: the hand-off between the three agents, run in a fixed order.

    safety checks (code) -> router (code): read in full, or search?
                         -> Memory Keeper (searches, tools) when searching
                         -> Pattern Finder (names throughlines, tools)
                         -> grounding check (code; drops unverifiable quotes)
                         -> Mirror (writes the reflection)

The order is fixed in code rather than chosen by a boss agent: every Zoom Out
needs the same steps, a fixed pipeline is cheaper and predictable, and each
step's output can be checked before the next one starts.

Why the router: in backend/experiments/cost_experiment.py, sending all 18 demo
moments cost ~35% less than letting the Memory Keeper search (the full journal
is an identical, chronological prompt, so ~87% of it is read from the prompt
cache) and cited more moments, with no loss in grounding. Search earns its
keep for a specific question, or once a journal is too long to read in full.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import db
from agents.common import StepFailed
from agents.memory_keeper import find_memories
from agents.mirror import reflect_back, write_reflection
from agents.pattern_finder import find_patterns
from config import MODEL_NAME
from ledger import BudgetExceeded, Ledger
from retrieval import ai_visible
from safety import care

FOCUS_PRESETS = {
    "season": ("This season of my life (the last three months)", 92),
    "story": ("The whole story so far", None),
}
# Up to this many moments (~10K tokens of journal), Zoom Out reads them all.
FULL_READ_MAX = int(os.getenv("FULL_READ_MAX", "40"))


def _since(entries: list[dict[str, Any]], days: int | None) -> str | None:
    """The window is measured back from the newest moment, not from today, so an
    older journal (like the demo) still has a "this season"."""
    if not days or not entries:
        return None
    newest = max(date.fromisoformat(e["date"]) for e in entries)
    return (newest - timedelta(days=days)).isoformat()


def stop_message(step: dict[str, Any]) -> str:
    if step.get("status") == "blocked":
        return ("The AI provider's safety filter declined this Zoom Out. That usually means one of your moments "
                "contains text that reads like instructions to an AI. Nothing was shared or changed. Try "
                "'Ask your own question', or review moments you released earlier.")
    if step.get("status") == "error":
        return "The AI provider had a problem just now. Nothing was changed; please try again in a moment."
    return "One of the agents hit its step limit, so Zoom Out stopped instead of looping."


def _finish(space: str, kind: str, ledger: Ledger, trace: list, status: str) -> str:
    return db.save_run(space, kind, ledger.model, ledger.total_cost_usd, ledger.snapshot(), trace, status)


async def zoom_out(space: str, preset: str = "season", question: str | None = None) -> dict[str, Any]:
    entries = db.list_entries(space)
    held = care.recent_care_entry(entries)
    if held:
        return {"status": "care", "care": care.RESOURCES, "entry_id": held["id"]}

    visible = [e for e in entries if ai_visible(e)]
    if len(visible) < 3:
        return {"status": "too_few", "message": "Save at least three moments first. Zoom Out needs a few to connect."}

    label, days = FOCUS_PRESETS.get(preset, FOCUS_PRESETS["season"])
    focus = question.strip()[:300] if question and question.strip() else label
    since = None if question and question.strip() else _since(visible, days)
    ns = db.get_north_star(space)
    value_names = [v.get("name", "") for v in ns.get("values", [])]

    ledger = Ledger(MODEL_NAME, spent_today_usd=db.spent_today())
    trace: list[dict[str, Any]] = []
    in_window = sorted((e for e in visible if not since or e["date"] >= since), key=lambda e: e["date"])
    if len(in_window) < 3:  # a quiet season: widen to the whole journal
        since, in_window = None, sorted(visible, key=lambda e: e["date"])
    read_in_full = not (question and question.strip()) and len(in_window) <= FULL_READ_MAX
    try:
        if read_in_full:
            memory_ids = [e["id"] for e in in_window]
            notes = f"All {len(memory_ids)} moments in this window were read in full."
            trace.append({
                "agent": "Router",
                "step": "Decide how to gather moments (plain code, no AI)",
                "status": "ok",
                "output": {"memory_ids": memory_ids, "note": (
                    f"{len(memory_ids)} moments fit comfortably, so they are read in full instead of searched: "
                    f"cheaper (the journal prompt is cached) and nothing gets missed. The Memory Keeper searches "
                    f"when you ask your own question or a journal passes {FULL_READ_MAX} moments.")},
                "tokens": None,
                "cost_usd": 0,
            })
        else:
            memory_ids, notes, step = await find_memories(space, focus, since, value_names, ledger)
            trace.append(step)
        patterns, dropped, steps = await find_patterns(space, focus, memory_ids, ledger)
        trace.extend(steps)
        trace.append({
            "agent": "Grounding check",
            "step": "Verify every quote against the entry it cites (plain code, no AI)",
            "status": "ok",
            "output": {"kept_patterns": len(patterns), "dropped": dropped},
            "tokens": None,
            "cost_usd": 0,
        })
        if not patterns:
            run_id = _finish(space, "zoom_out", ledger, trace, "no_patterns")
            return {"status": "no_patterns", "message": "Throughline couldn't find a pattern it could back up with your own words. Try the whole story, or save a few more moments.", "trace": trace, "ledger": ledger.snapshot(), "run_id": run_id}
        reflection, step = await write_reflection(ns, focus, patterns, ledger)
        trace.append(step)
    except BudgetExceeded as exc:
        trace.append({"agent": "Budget guard", "step": "Stop before spending more", "status": "stopped", "reason": str(exc)})
        run_id = _finish(space, "zoom_out", ledger, trace, "budget_stopped")
        return {"status": "budget", "message": str(exc), "trace": trace, "ledger": ledger.snapshot(), "run_id": run_id}
    except StepFailed as exc:
        trace.append(exc.trace)
        run_id = _finish(space, "zoom_out", ledger, trace, exc.trace.get("status", "stopped"))
        return {"status": "stopped", "message": stop_message(exc.trace), "trace": trace, "ledger": ledger.snapshot(), "run_id": run_id}

    run_id = _finish(space, "zoom_out", ledger, trace, "ok")
    payload = {
        "status": "ok",
        "focus": focus,
        "since": since,
        "headline": reflection.headline,
        "reflection": reflection.reflection,
        "question": reflection.question,
        "patterns": patterns,
        "memory_ids": memory_ids,
        "search_notes": notes,
        "dropped": dropped,
        "trace": trace,
        "ledger": ledger.snapshot(),
        "run_id": run_id,
    }
    db.save_insight(space, payload)
    return payload


async def respond(space: str, insight_id: str, pattern_index: int, verdict: str, note: str) -> dict[str, Any]:
    insight = db.get_insight(space, insight_id)
    if not insight or not (0 <= pattern_index < len(insight.get("patterns", []))):
        raise LookupError("That reflection no longer exists.")
    if verdict not in ("resonates", "partly", "not_me"):
        raise ValueError("verdict must be resonates, partly or not_me")
    pattern = insight["patterns"][pattern_index]
    ns = db.get_north_star(space)
    ledger = Ledger(MODEL_NAME, spent_today_usd=db.spent_today())
    try:
        out, proposal, step = await reflect_back(ns, pattern, verdict, note, ledger)
    except BudgetExceeded as exc:
        _finish(space, "reflect_back", ledger, [], "budget_stopped")
        return {"status": "budget", "message": str(exc)}
    except StepFailed as exc:
        _finish(space, "reflect_back", ledger, [exc.trace], exc.trace.get("status", "stopped"))
        return {"status": "stopped", "message": stop_message(exc.trace)}
    feedback_id = db.save_feedback(space, insight_id, pattern_index, pattern["title"], verdict, note, out.reply)
    proposal_id = db.save_proposal(space, feedback_id, proposal) if proposal else None
    run_id = _finish(space, "reflect_back", ledger, [step], "ok")
    return {
        "status": "ok",
        "reply": out.reply,
        "follow_up_question": out.follow_up_question,
        "proposal": {"id": proposal_id, **proposal} if proposal else None,
        "trace": [step],
        "ledger": ledger.snapshot(),
        "run_id": run_id,
    }
