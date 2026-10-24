"""Saving, releasing and seeding moments (journal entries with optional photos)."""

from __future__ import annotations

import io
import json
import uuid
from pathlib import Path
from typing import Any

from PIL import Image

import db
from agents.memory_keeper import tag_entry
from config import DEMO_DIR, MODEL_NAME, key_is_set
from ledger import BudgetExceeded, Ledger
from safety import care, injection

MAX_PHOTO_PX = 1600
DEMO_PHOTOS = DEMO_DIR / "photos"
DEMO_INDEX = DEMO_DIR / "maya_index.json"


def photo_path(space: str, filename: str | None) -> Path | None:
    if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
        return None
    for folder in (db.UPLOADS_DIR / space, DEMO_PHOTOS):
        p = folder / filename
        if p.exists():
            return p
    return None


def store_photo(space: str, data: bytes) -> str:
    """Re-encode the upload as a JPEG (drops EXIF location data, caps size)."""
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_PHOTO_PX, MAX_PHOTO_PX))
        folder = db.UPLOADS_DIR / space
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex[:12]}.jpg"
        img.save(folder / name, "JPEG", quality=85)
    return name


async def index_entry(space: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Run the Memory Keeper on one entry and store its notes."""
    ns = db.get_north_star(space)
    ledger = Ledger(MODEL_NAME, spent_today_usd=db.spent_today())
    tags, trace = await tag_entry(entry, [v.get("name", "") for v in ns.get("values", [])], photo_path(space, entry.get("photo")), ledger)
    tag_dict = {k: getattr(tags, k) for k in ("themes", "values", "feelings", "people", "places")}
    db.update_entry_ai(space, entry["id"], summary=tags.summary, tags=tag_dict, photo_desc=tags.photo_description)
    db.save_run(space, "index_moment", MODEL_NAME, ledger.total_cost_usd, ledger.snapshot(), [trace])
    return {"trace": [trace], "ledger": ledger.snapshot()}


async def save_moment(space: str, *, date: str, title: str, text: str, photo: bytes | None) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("Write a few words about the moment first.")
    photo_name = store_photo(space, photo) if photo else None
    care_flag = care.check(f"{title}\n{text}")
    flags = injection.scan(f"{title}\n{text}")
    entry = db.insert_entry(space, {
        "date": date, "title": title.strip()[:120], "text": text[:6000], "photo": photo_name,
        "injection_flags": flags, "care_flag": care_flag,
    })
    result: dict[str, Any] = {"entry": entry, "care": None, "held_back": None, "indexed": False}
    if care_flag:
        result["care"] = care.RESOURCES
        return result
    if flags:
        result["held_back"] = flags
        return result
    if not key_is_set():
        result["warning"] = "Saved. AI notes were skipped because no PORTKEY_API_KEY was found."
        return result
    try:
        result.update(await index_entry(space, entry))
        result["indexed"] = True
    except BudgetExceeded as exc:
        result["warning"] = f"Saved without AI notes: {exc}"
    except Exception as exc:  # the moment is saved either way
        result["warning"] = f"Saved without AI notes ({type(exc).__name__})."
    result["entry"] = db.get_entry(space, entry["id"])
    return result


async def release_moment(space: str, entry_id: str) -> dict[str, Any]:
    """The person reviewed a held-back entry and chose to let the agents read it.
    It still reaches them only inside the escaped <memory> wrapper."""
    entry = db.get_entry(space, entry_id)
    if not entry:
        raise LookupError("No such moment.")
    if entry["care_flag"]:
        raise ValueError("This moment stays private to you; Throughline won't analyze it.")
    with db.connect() as conn:
        conn.execute("UPDATE entries SET injection_flags = '[]' WHERE space = ? AND id = ?", (space, entry_id))
    entry = db.get_entry(space, entry_id)
    result: dict[str, Any] = {"entry": entry}
    if key_is_set():
        try:
            result.update(await index_entry(space, entry))
        except Exception as exc:  # released either way; indexing can be retried
            result["warning"] = f"Released, but AI notes were skipped ({exc})."
        result["entry"] = db.get_entry(space, entry_id)
    return result


def seed_demo(force: bool = False) -> int:
    """Load the fictional user Maya. Uses the saved Memory Keeper notes in
    maya_index.json when present, so graders don't wait or pay for indexing."""
    source = DEMO_DIR / "maya.json"
    if not source.exists() or (not force and db.list_entries("demo")):
        return 0
    data = json.loads(source.read_text(encoding="utf-8"))
    index = json.loads(DEMO_INDEX.read_text(encoding="utf-8")) if DEMO_INDEX.exists() else {}
    db.reset_space("demo")
    ns = data["north_star"]
    db.save_north_star("demo", ns["values"], ns.get("vision", ""), ns.get("intentions", []))
    for e in data["entries"]:
        notes = index.get(e["id"], {})
        db.insert_entry("demo", {
            **e,
            "summary": notes.get("summary"),
            "tags": notes.get("tags"),
            "photo_desc": notes.get("photo_desc"),
            "created_at": f"{e['date']}T20:00:00+00:00",
        })
    return len(data["entries"])
