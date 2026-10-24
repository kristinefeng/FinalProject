"""SQLite storage. Everything stays on the user's machine in data/throughline.db.

Two "spaces" share one database: `demo` (the fictional user Maya, reseeded on
request) and `me` (the person using the app). Every query is scoped to one
space, and the agents' tools receive the space from the server, never from
the model, so one space can't read the other.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Iterator

from config import DATA_DIR

SPACES = ("demo", "me")
DB_PATH = DATA_DIR / "throughline.db"
UPLOADS_DIR = DATA_DIR / "uploads"

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,
    space TEXT NOT NULL,
    date TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    photo TEXT,
    photo_desc TEXT,
    summary TEXT,
    tags TEXT NOT NULL DEFAULT '{}',
    injection_flags TEXT NOT NULL DEFAULT '[]',
    care_flag INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS north_star (
    space TEXT PRIMARY KEY,
    values_json TEXT NOT NULL DEFAULT '[]',
    vision TEXT NOT NULL DEFAULT '',
    intentions_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,
    space TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    space TEXT NOT NULL,
    insight_id TEXT NOT NULL,
    pattern_index INTEGER NOT NULL,
    pattern_title TEXT NOT NULL,
    verdict TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    reply TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    space TEXT NOT NULL,
    feedback_id TEXT NOT NULL,
    proposal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    space TEXT NOT NULL,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    day TEXT NOT NULL,
    model TEXT NOT NULL,
    cost_usd REAL NOT NULL,
    ledger TEXT NOT NULL,
    trace TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'ok'
);
CREATE TABLE IF NOT EXISTS study (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    participant TEXT NOT NULL,
    phase TEXT NOT NULL,
    answers TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT ''
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


def check_space(space: str) -> str:
    if space not in SPACES:
        raise ValueError(f"Unknown space {space!r}")
    return space


# ---------- entries ----------

def _entry_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["tags"] = json.loads(d["tags"] or "{}")
    d["injection_flags"] = json.loads(d["injection_flags"] or "[]")
    d["care_flag"] = bool(d["care_flag"])
    return d


def insert_entry(space: str, entry: dict[str, Any]) -> dict[str, Any]:
    check_space(space)
    row = {
        "id": entry.get("id") or new_id("e"),
        "space": space,
        "date": entry.get("date") or date.today().isoformat(),
        "title": entry.get("title", ""),
        "text": entry["text"],
        "photo": entry.get("photo"),
        "photo_desc": entry.get("photo_desc"),
        "summary": entry.get("summary"),
        "tags": json.dumps(entry.get("tags") or {}),
        "injection_flags": json.dumps(entry.get("injection_flags") or []),
        "care_flag": int(bool(entry.get("care_flag"))),
        "created_at": entry.get("created_at") or now_iso(),
    }
    with connect() as conn:
        conn.execute(
            f"INSERT OR REPLACE INTO entries ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
            list(row.values()),
        )
    return get_entry(space, row["id"])  # type: ignore[return-value]


def update_entry_ai(space: str, entry_id: str, *, summary: str, tags: dict, photo_desc: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE entries SET summary = ?, tags = ?, photo_desc = COALESCE(?, photo_desc) WHERE space = ? AND id = ?",
            (summary, json.dumps(tags), photo_desc, space, entry_id),
        )


def get_entry(space: str, entry_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM entries WHERE space = ? AND id = ?", (check_space(space), entry_id)).fetchone()
    return _entry_row(row) if row else None


def list_entries(space: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM entries WHERE space = ? ORDER BY date DESC, created_at DESC", (check_space(space),)
        ).fetchall()
    return [_entry_row(r) for r in rows]


def delete_entry(space: str, entry_id: str) -> dict[str, Any] | None:
    entry = get_entry(space, entry_id)
    if entry:
        with connect() as conn:
            conn.execute("DELETE FROM entries WHERE space = ? AND id = ?", (space, entry_id))
    return entry


# ---------- north star ----------

def get_north_star(space: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM north_star WHERE space = ?", (check_space(space),)).fetchone()
    if not row:
        return {"values": [], "vision": "", "intentions": [], "updated_at": None}
    return {
        "values": json.loads(row["values_json"]),
        "vision": row["vision"],
        "intentions": json.loads(row["intentions_json"]),
        "updated_at": row["updated_at"],
    }


def save_north_star(space: str, values: list[dict], vision: str, intentions: list[str]) -> dict[str, Any]:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO north_star (space, values_json, vision, intentions_json, updated_at) VALUES (?, ?, ?, ?, ?)",
            (check_space(space), json.dumps(values), vision, json.dumps(intentions), now_iso()),
        )
    return get_north_star(space)


# ---------- insights, feedback, proposals ----------

def save_insight(space: str, payload: dict[str, Any]) -> str:
    insight_id = payload.get("id") or new_id("i")
    payload["id"] = insight_id
    with connect() as conn:
        conn.execute(
            "INSERT INTO insights (id, space, created_at, payload) VALUES (?, ?, ?, ?)",
            (insight_id, check_space(space), now_iso(), json.dumps(payload)),
        )
    return insight_id


def get_insight(space: str, insight_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM insights WHERE space = ? AND id = ?", (check_space(space), insight_id)).fetchone()
    return json.loads(row["payload"]) if row else None


def list_insights(space: str, limit: int = 20) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT payload FROM insights WHERE space = ? ORDER BY created_at DESC LIMIT ?", (check_space(space), limit)
        ).fetchall()
    return [json.loads(r["payload"]) for r in rows]


def save_feedback(space: str, insight_id: str, pattern_index: int, pattern_title: str, verdict: str, note: str, reply: str) -> str:
    feedback_id = new_id("f")
    with connect() as conn:
        conn.execute(
            "INSERT INTO feedback (id, space, insight_id, pattern_index, pattern_title, verdict, note, reply, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (feedback_id, check_space(space), insight_id, pattern_index, pattern_title, verdict, note, reply, now_iso()),
        )
    return feedback_id


def list_feedback(space: str, limit: int = 10) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT pattern_title, verdict, note, created_at FROM feedback WHERE space = ? ORDER BY created_at DESC LIMIT ?",
            (check_space(space), limit),
        ).fetchall()
    return [dict(r) for r in rows]


def save_proposal(space: str, feedback_id: str, proposal: dict[str, Any]) -> str:
    proposal_id = new_id("p")
    with connect() as conn:
        conn.execute(
            "INSERT INTO proposals (id, space, feedback_id, proposal, created_at) VALUES (?, ?, ?, ?, ?)",
            (proposal_id, check_space(space), feedback_id, json.dumps(proposal), now_iso()),
        )
    return proposal_id


def get_proposal(space: str, proposal_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM proposals WHERE space = ? AND id = ?", (check_space(space), proposal_id)).fetchone()
    if not row:
        return None
    return {"id": row["id"], "status": row["status"], "proposal": json.loads(row["proposal"])}


def set_proposal_status(space: str, proposal_id: str, status: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE proposals SET status = ? WHERE space = ? AND id = ?", (status, space, proposal_id))


# ---------- runs (token + cost log) ----------

def save_run(space: str, kind: str, model: str, cost_usd: float, ledger: dict, trace: list, status: str = "ok") -> str:
    run_id = new_id("r")
    with connect() as conn:
        conn.execute(
            "INSERT INTO runs (id, space, kind, created_at, day, model, cost_usd, ledger, trace, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, space, kind, now_iso(), date.today().isoformat(), model, cost_usd, json.dumps(ledger), json.dumps(trace), status),
        )
    return run_id


def spent_today() -> float:
    with connect() as conn:
        row = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) AS s FROM runs WHERE day = ?", (date.today().isoformat(),)).fetchone()
    return float(row["s"])


def list_runs(limit: int = 200) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, space, kind, created_at, model, cost_usd, ledger, status FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["ledger"] = json.loads(d["ledger"])
        out.append(d)
    return out


# ---------- before/after study ----------

def save_study(participant: str, phase: str, answers: dict, comment: str) -> str:
    sid = new_id("s")
    with connect() as conn:
        conn.execute(
            "INSERT INTO study (id, created_at, participant, phase, answers, comment) VALUES (?, ?, ?, ?, ?, ?)",
            (sid, now_iso(), participant, phase, json.dumps(answers), comment),
        )
    return sid


def list_study() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM study ORDER BY created_at").fetchall()
    return [{**dict(r), "answers": json.loads(r["answers"])} for r in rows]


def reset_space(space: str) -> None:
    with connect() as conn:
        for table in ("entries", "north_star", "insights", "feedback", "proposals"):
            conn.execute(f"DELETE FROM {table} WHERE space = ?", (check_space(space),))
