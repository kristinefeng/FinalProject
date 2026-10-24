"""Zoom Out: the hand-off between the three agents, run in a fixed order.

    safety checks (code) -> Memory Keeper (finds moments, tools)
                         -> Pattern Finder (names throughlines, tools)
                         -> grounding check (code; drops unverifiable quotes)
                         -> Mirror (writes the reflection)

The order is fixed in code rather than chosen by a boss agent: every Zoom Out
needs the same three steps, a fixed pipeline is cheaper and predictable, and
each step's output can be checked before the next one starts.
"""

from __future__ import annotations

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


def _since(entries: list[dict[str, Any]], days: int | None) -> str | None:
    """The window is measured back from the newest moment, not from today, so an
    older journal (like the demo) still has a "this season"."""
    if not days or not entries:
        return None
    newest = max(date.fromisoformat(e["date"]) for e in entries)
    return (newest - timedelta(days=days)).isoformat()


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
    try:
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
        run_id = _finish(space, "zoom_out", ledger, trace, "stopped")
        return {"status": "stopped", "message": "One of the agents hit its step limit, so Zoom Out stopped instead of looping.", "trace": trace, "ledger": ledger.snapshot(), "run_id": run_id}

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
