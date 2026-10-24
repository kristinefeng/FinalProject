"""Does cutting cost hurt quality? Runs in a throwaway database.

    python backend/experiments/cost_experiment.py

A. Retrieval (the shipped design): the Memory Keeper picks 5-8 moments, and
   only those go to the Pattern Finder.
B. No retrieval: every moment in the journal goes to the Pattern Finder.
C. Photo size: index one photo moment at 768px (shipped) vs 1600px.

Quality proxies: how many patterns survive the grounding check, how much
evidence is dropped as unverifiable, and how many distinct moments are cited.
Results go to docs/evidence/cost_experiment.json.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["THROUGHLINE_DATA_DIR"] = tempfile.mkdtemp(prefix="throughline-exp-")
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import db  # noqa: E402
import moments  # noqa: E402
from agents import memory_keeper  # noqa: E402
from agents.memory_keeper import find_memories, tag_entry  # noqa: E402
from agents.mirror import write_reflection  # noqa: E402
from agents.pattern_finder import find_patterns  # noqa: E402
from config import MODEL_NAME  # noqa: E402
from ledger import Ledger  # noqa: E402
from retrieval import ai_visible  # noqa: E402

TRIALS = int(os.getenv("TRIALS", "3"))
FOCUS = "The whole story so far"
OUT = BACKEND.parent / "docs" / "evidence" / "cost_experiment.json"


async def one_run(mode: str) -> dict:
    ledger = Ledger(MODEL_NAME, budget_usd=1.0)
    ns = db.get_north_star("demo")
    names = [v["name"] for v in ns["values"]]
    if mode == "retrieval":
        ids, _, _ = await find_memories("demo", FOCUS, None, names, ledger)
    else:
        ids = [e["id"] for e in db.list_entries("demo") if ai_visible(e)]
    patterns, dropped, _ = await find_patterns("demo", FOCUS, ids, ledger)
    if patterns:
        await write_reflection(ns, FOCUS, patterns, ledger)
    t = ledger.totals()
    return {
        "mode": mode,
        "moments_sent": len(ids),
        "cost_usd": ledger.total_cost_usd,
        "input_tokens": t["input_tokens"],
        "cached_input_tokens": t["cache_read_tokens"],
        "output_tokens": t["output_tokens"],
        "patterns_kept": len(patterns),
        "evidence_kept": sum(len(p["evidence"]) for p in patterns),
        "evidence_dropped": len([d for d in dropped if d.get("quote")]),
        "distinct_moments_cited": len({e["memory_id"] for p in patterns for e in p["evidence"]}),
        "kinds": [p["kind"] for p in patterns],
    }


def mean(rows: list[dict], key: str) -> float:
    return sum(r[key] for r in rows) / len(rows)


async def main() -> None:
    db.init_db()
    moments.seed_demo(force=True)
    runs = []
    for i in range(TRIALS):
        for mode in ("retrieval", "all_entries"):
            r = await one_run(mode)
            print(f"trial {i + 1} {mode:<11} moments={r['moments_sent']:>2} in={r['input_tokens']:>6} cached={r['cached_input_tokens']:>6} out={r['output_tokens']:>5} ${r['cost_usd']:.5f} patterns={r['patterns_kept']} kept_ev={r['evidence_kept']} dropped_ev={r['evidence_dropped']} kinds={r['kinds']}")
            runs.append(r)

    summary = {}
    for mode in ("retrieval", "all_entries"):
        rows = [r for r in runs if r["mode"] == mode]
        summary[mode] = {k: round(mean(rows, k), 6) for k in ("moments_sent", "cost_usd", "input_tokens", "cached_input_tokens", "output_tokens", "patterns_kept", "evidence_kept", "evidence_dropped", "distinct_moments_cited")}
        summary[mode]["tension_or_growth_found_in"] = f"{sum(1 for r in rows if set(r['kinds']) & {'tension', 'growth'})}/{len(rows)} runs"

    # C. photo size
    entry = db.get_entry("demo", "e01")
    photo = moments.photo_path("demo", entry["photo"])
    photo_rows = {}
    for px in (768, 1600):
        memory_keeper.PHOTO_MAX_PX = px
        ledger = Ledger(MODEL_NAME, budget_usd=1.0)
        tags, _ = await tag_entry(entry, [], photo, ledger)
        photo_rows[f"{px}px"] = {"input_tokens": ledger.totals()["input_tokens"], "cost_usd": ledger.total_cost_usd, "photo_description": tags.photo_description}
        print(f"photo {px}px: in={ledger.totals()['input_tokens']} ${ledger.total_cost_usd:.6f} :: {tags.photo_description}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"model": MODEL_NAME, "trials": TRIALS, "summary": summary, "photo_size": photo_rows, "runs": runs}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
