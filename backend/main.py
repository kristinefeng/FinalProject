"""Throughline API + the built web app, served from one process."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date as date_cls
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import db
import moments
from agents import zoom_out as zo
from config import FRONTEND_DIST, MODEL_NAME, env_source, key_is_set
from ledger import DAILY_BUDGET_USD, RUN_BUDGET_USD

MAX_PHOTO_BYTES = 12 * 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    moments.seed_demo()
    yield


app = FastAPI(title="Throughline", lifespan=lifespan)


def space_or_404(space: str) -> str:
    if space not in db.SPACES:
        raise HTTPException(404, "Unknown space")
    return space


def public_entry(e: dict[str, Any], space: str) -> dict[str, Any]:
    return {
        **{k: e[k] for k in ("id", "date", "title", "text", "summary", "tags", "photo_desc", "care_flag", "injection_flags")},
        "photo_url": f"/photos/{space}/{e['photo']}" if e.get("photo") else None,
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "key_set": key_is_set(), "env_source": env_source(), "model": MODEL_NAME}


@app.get("/api/{space}/state")
def state(space: str) -> dict[str, Any]:
    space_or_404(space)
    entries = db.list_entries(space)
    return {
        "space": space,
        "north_star": db.get_north_star(space),
        "entries": [public_entry(e, space) for e in entries],
        "insights": [
            {k: i.get(k) for k in ("id", "headline", "focus", "question")} for i in db.list_insights(space, 5)
        ],
    }


@app.post("/api/demo/reset")
def reset_demo() -> dict[str, Any]:
    return {"entries": moments.seed_demo(force=True)}


@app.post("/api/me/reset")
def reset_me() -> dict[str, Any]:
    db.reset_space("me")
    folder = db.UPLOADS_DIR / "me"  # photos go with the moments
    if folder.exists():
        for f in folder.iterdir():
            if f.is_file():
                f.unlink()
    return {"ok": True}


@app.post("/api/{space}/entries")
async def create_entry(
    space: str,
    text: str = Form(...),
    title: str = Form(""),
    date: str = Form(""),
    photo: UploadFile | None = File(None),
) -> dict[str, Any]:
    space_or_404(space)
    data = None
    if photo is not None and photo.filename:
        data = await photo.read()
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(413, "That photo is over 12 MB.")
    try:
        day = date_cls.fromisoformat(date).isoformat() if date else date_cls.today().isoformat()
        result = await moments.save_moment(space, date=day, title=title, text=text, photo=data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    result["entry"] = public_entry(result["entry"], space)
    return result


@app.post("/api/{space}/entries/{entry_id}/release")
async def release_entry(space: str, entry_id: str) -> dict[str, Any]:
    space_or_404(space)
    try:
        result = await moments.release_moment(space, entry_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    result["entry"] = public_entry(result["entry"], space)
    return result


@app.delete("/api/{space}/entries/{entry_id}")
def remove_entry(space: str, entry_id: str) -> dict[str, Any]:
    space_or_404(space)
    entry = db.delete_entry(space, entry_id)
    if not entry:
        raise HTTPException(404, "No such moment")
    # Uploaded photos are deleted with the moment; bundled demo photos stay.
    if entry.get("photo"):
        p = db.UPLOADS_DIR / space / entry["photo"]
        if p.exists():
            p.unlink()
    return {"deleted": entry_id}


class NorthStarIn(BaseModel):
    values: list[dict[str, str]] = Field(default_factory=list)
    vision: str = ""
    intentions: list[str] = Field(default_factory=list)


@app.put("/api/{space}/north_star")
def put_north_star(space: str, body: NorthStarIn) -> dict[str, Any]:
    space_or_404(space)
    values = [
        {"name": v.get("name", "").strip()[:40], "meaning": v.get("meaning", "").strip()[:300]}
        for v in body.values if v.get("name", "").strip()
    ][:8]
    intentions = [i.strip()[:240] for i in body.intentions if i.strip()][:6]
    return db.save_north_star(space, values, body.vision.strip()[:1200], intentions)


class ZoomOutIn(BaseModel):
    preset: str = "week"
    question: str | None = None


@app.post("/api/{space}/zoom_out")
async def post_zoom_out(space: str, body: ZoomOutIn) -> dict[str, Any]:
    space_or_404(space)
    if not key_is_set():
        raise HTTPException(503, "No PORTKEY_API_KEY found. Put a .env file in the repo folder or the folder above it.")
    return await zo.zoom_out(space, body.preset, body.question)


@app.get("/api/{space}/insights/{insight_id}")
def get_insight(space: str, insight_id: str) -> dict[str, Any]:
    space_or_404(space)
    insight = db.get_insight(space, insight_id)
    if not insight:
        raise HTTPException(404, "No such reflection")
    return insight


class FeedbackIn(BaseModel):
    pattern_index: int
    verdict: str
    note: str = ""


@app.post("/api/{space}/insights/{insight_id}/feedback")
async def post_feedback(space: str, insight_id: str, body: FeedbackIn) -> dict[str, Any]:
    space_or_404(space)
    try:
        return await zo.respond(space, insight_id, body.pattern_index, body.verdict, body.note)
    except (LookupError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/{space}/proposals/{proposal_id}/{decision}")
def decide_proposal(space: str, proposal_id: str, decision: str) -> dict[str, Any]:
    space_or_404(space)
    found = db.get_proposal(space, proposal_id)
    if not found or found["status"] != "pending":
        raise HTTPException(404, "No pending suggestion")
    if decision == "dismiss":
        db.set_proposal_status(space, proposal_id, "dismissed")
        return {"status": "dismissed", "north_star": db.get_north_star(space)}
    if decision != "accept":
        raise HTTPException(400, "decision must be accept or dismiss")
    p = found["proposal"]
    ns = db.get_north_star(space)
    values, intentions = ns["values"], ns["intentions"]
    if p["action"] == "add_value" and not any(v["name"].lower() == p["value_name"].lower() for v in values):
        values.append({"name": p["value_name"], "meaning": p["new_text"]})
    elif p["action"] == "reword_value":
        for v in values:
            if v["name"].lower() == p["value_name"].lower():
                v["meaning"] = p["new_text"]
    elif p["action"] == "add_intention":
        intentions.append(p["new_text"])
    db.set_proposal_status(space, proposal_id, "accepted")
    return {"status": "accepted", "north_star": db.save_north_star(space, values, ns["vision"], intentions)}


@app.get("/api/usage")
def usage() -> dict[str, Any]:
    runs = db.list_runs()
    return {
        "model": MODEL_NAME,
        "run_budget_usd": RUN_BUDGET_USD,
        "daily_budget_usd": DAILY_BUDGET_USD,
        "spent_today_usd": round(db.spent_today(), 8),
        "runs": runs,
    }


class StudyIn(BaseModel):
    participant: str
    phase: str
    answers: dict[str, int]
    comment: str = ""


@app.post("/api/study")
def post_study(body: StudyIn) -> dict[str, Any]:
    if body.phase not in ("before", "after"):
        raise HTTPException(400, "phase must be before or after")
    return {"id": db.save_study(body.participant.strip()[:40] or "anonymous", body.phase, body.answers, body.comment.strip()[:2000])}


@app.get("/api/study")
def get_study() -> dict[str, Any]:
    return {"responses": db.list_study()}


@app.get("/photos/{space}/{filename}")
def photo(space: str, filename: str):
    space_or_404(space)
    p = moments.photo_path(space, filename)
    if not p:
        raise HTTPException(404, "No such photo")
    return FileResponse(p, headers={"Cache-Control": "private, max-age=3600"})


# ---------- the web app ----------

if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    candidate = (FRONTEND_DIST / path).resolve()
    if path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
        return FileResponse(candidate)
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"detail": "Frontend not built. Run `npm run build` in frontend/."}, status_code=500)
