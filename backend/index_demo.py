"""Run the Memory Keeper over Maya's demo journal once and save its notes.

    python backend/index_demo.py

Writes demo_data/maya_index.json, which is committed so the demo loads
instantly for anyone who clones the repo. Each indexing run is also logged
in the runs table like any other save, so its token use counts in the
cost numbers.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402
import moments  # noqa: E402


async def main() -> None:
    db.init_db()
    if moments.DEMO_INDEX.exists():
        moments.DEMO_INDEX.unlink()
    moments.seed_demo(force=True)
    entries = sorted(db.list_entries("demo"), key=lambda e: e["date"])
    total = 0.0
    for e in entries:
        result = await moments.index_entry("demo", e)
        cost = result["ledger"]["total_cost_usd"]
        total += cost
        tokens = result["ledger"]["totals"]
        print(f"{e['id']}  {e['date']}  photo={'yes' if e.get('photo') else 'no '}  in={tokens['input_tokens']:>5}  out={tokens['output_tokens']:>4}  ${cost:.6f}")
    index = {
        e["id"]: {"summary": e["summary"], "tags": e["tags"], "photo_desc": e["photo_desc"]}
        for e in db.list_entries("demo")
    }
    moments.DEMO_INDEX.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nIndexed {len(index)} moments for ${total:.6f}. Wrote {moments.DEMO_INDEX.name}.")


if __name__ == "__main__":
    asyncio.run(main())
