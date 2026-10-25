"""Measure the default "This week" Zoom Out with independent runs.

    PORTKEY_CACHE_FORCE_REFRESH=1 python backend/experiments/week_runs.py

Runs in a throwaway database seeded with Maya's demo journal. Results go to
docs/evidence/week_runs.json for the tokenomics section.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics as st
import sys
import tempfile
import time
from pathlib import Path

os.environ["THROUGHLINE_DATA_DIR"] = tempfile.mkdtemp(prefix="throughline-week-")
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import db  # noqa: E402
import moments  # noqa: E402
from agents import zoom_out  # noqa: E402

RUNS = int(os.getenv("RUNS", "3"))
OUT = BACKEND.parent / "docs" / "evidence" / "week_runs.json"


async def main() -> None:
    db.init_db()
    moments.seed_demo(force=True)
    rows = []
    for i in range(RUNS):
        started = time.perf_counter()
        r = await zoom_out.zoom_out("demo", "week")
        t = r["ledger"]["totals"]
        row = {
            "run": i + 1,
            "status": r["status"],
            "seconds": round(time.perf_counter() - started, 1),
            "cost_usd": r["ledger"]["total_cost_usd"],
            "requests": t["requests"],
            "input_tokens": t["input_tokens"],
            "cached_input_tokens": t["cache_read_tokens"],
            "output_tokens": t["output_tokens"],
            "headline": r.get("headline"),
            "throughlines": [f"{p['kind']}: {p['title']}" for p in r.get("patterns", [])],
            "quotes_dropped": len([d for d in r.get("dropped", []) if d.get("quote")]),
        }
        rows.append(row)
        print(f"run {i + 1}: {row['status']} {row['seconds']}s ${row['cost_usd']:.5f} in={row['input_tokens']} cached={row['cached_input_tokens']} out={row['output_tokens']} | {row['headline']} | {row['throughlines']}")
    ok = [r for r in rows if r["status"] == "ok"]
    summary = {k: round(st.mean(r[k] for r in ok), 6) for k in ("seconds", "cost_usd", "requests", "input_tokens", "cached_input_tokens", "output_tokens", "quotes_dropped")}
    OUT.write_text(json.dumps({"runs": rows, "average": summary}, indent=2, ensure_ascii=False), encoding="utf-8")
    print("average:", summary)


if __name__ == "__main__":
    asyncio.run(main())
