"""Memory search without embeddings (the course key allows only gpt-6-luna).

"Search by meaning" works in two halves: when an entry is saved, the Memory
Keeper writes a summary and tags (themes, values, feelings, people, places,
photo description). At search time the agent turns a question into a few
keyword queries, and this module ranks entries with BM25 over the entry text
plus those AI-written fields. Tags count double, because they carry meaning
the raw text only implies.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

import db

STOPWORDS = set(
    """a about above after again against all am an and any are as at be because been before being below
    between both but by can could did do does doing down during each few for from further had has have having
    he her here hers herself him himself his how i if in into is it its itself just me more most my myself no
    nor not now of off on once only or other our ours out over own same she should so some such than that the
    their theirs them themselves then there these they this those through to too under until up very was we
    were what when where which while who whom why will with would you your yours yourself yourselves felt feel
    feeling time times really also today got get went go""".split()
)
_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def tokenize(text: str) -> list[str]:
    words = [w for w in _WORD.findall(text.lower()) if w not in STOPWORDS and len(w) > 1]
    # Light stemming so "hiking"/"hiked"/"hikes" meet.
    out = []
    for w in words:
        for suffix in ("ing", "ed", "es", "s"):
            if len(w) > len(suffix) + 3 and w.endswith(suffix):
                w = w[: -len(suffix)]
                break
        out.append(w)
    return out


def _doc_tokens(entry: dict[str, Any]) -> list[str]:
    tags = entry.get("tags") or {}
    tag_words = " ".join(" ".join(v) if isinstance(v, list) else str(v) for v in tags.values())
    body = " ".join([entry.get("title") or "", entry.get("text") or "", entry.get("photo_desc") or ""])
    meta = " ".join([entry.get("summary") or "", tag_words])
    return tokenize(body) + tokenize(meta) * 2


def ai_visible(entry: dict[str, Any]) -> bool:
    """Entries held back by a safety check never reach the agents."""
    return not entry.get("injection_flags") and not entry.get("care_flag")


def search(space: str, query: str, since: str | None = None, until: str | None = None, limit: int = 6) -> list[dict[str, Any]]:
    entries = [e for e in db.list_entries(space) if ai_visible(e)]
    if since:
        entries = [e for e in entries if e["date"] >= since]
    if until:
        entries = [e for e in entries if e["date"] <= until]
    if not entries:
        return []

    docs = [_doc_tokens(e) for e in entries]
    n = len(docs)
    avgdl = sum(len(d) for d in docs) / n or 1
    df = Counter(t for d in docs for t in set(d))
    q_terms = tokenize(query)
    k1, b = 1.4, 0.75

    scored = []
    for entry, doc in zip(entries, docs):
        tf = Counter(doc)
        score = 0.0
        for t in q_terms:
            if t not in tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(doc) / avgdl))
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [card(e, score) for score, e in scored[:limit]]


def card(entry: dict[str, Any], score: float | None = None) -> dict[str, Any]:
    """The compact view agents see in search results (not the full text)."""
    tags = entry.get("tags") or {}
    out = {
        "id": entry["id"],
        "date": entry["date"],
        "title": entry.get("title") or "",
        "summary": entry.get("summary") or (entry.get("text") or "")[:160],
        "themes": tags.get("themes", []),
        "values": tags.get("values", []),
        "has_photo": bool(entry.get("photo")),
    }
    if score is not None:
        out["score"] = round(score, 2)
    return out


def recent(space: str, n: int = 8) -> list[dict[str, Any]]:
    return [card(e) for e in db.list_entries(space) if ai_visible(e)][:n]
