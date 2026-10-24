"""Defense 2: no invented memories.

The Pattern Finder must back every pattern with evidence: an entry ID plus a
short quote copied from that entry. This module checks each piece of evidence
in plain code before anything reaches the person:

- the entry ID must be one the agent was actually shown, and
- the quote must appear in that entry's text (ignoring case, spacing and
  curly-vs-straight punctuation).

Evidence that fails is dropped. A pattern left with no evidence is dropped.
Everything dropped is recorded so the app can show the check working.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

MIN_QUOTE_WORDS = 3

_PUNCT = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "—": "-", "–": "-", "…": "..."})


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").translate(_PUNCT).lower()
    text = re.sub(r"[\"']", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def check_evidence(memory_id: str, quote: str, entries: dict[str, dict[str, Any]]) -> str | None:
    """None if the evidence holds up, otherwise the reason it failed."""
    entry = entries.get(memory_id)
    if entry is None:
        return "cites an entry the agent was never shown"
    q = normalize(quote)
    if len(q.split()) < MIN_QUOTE_WORDS:
        return "quote is too short to check"
    if q not in normalize(entry.get("text", "")):
        return "quote does not appear in that entry"
    return None


def ground_patterns(patterns: list[dict[str, Any]], entries: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (patterns that survive, everything that was dropped and why)."""
    kept, dropped = [], []
    for p in patterns:
        good = []
        for ev in p.get("evidence", []):
            reason = check_evidence(ev.get("memory_id", ""), ev.get("quote", ""), entries)
            if reason:
                dropped.append({"pattern": p.get("title", ""), "memory_id": ev.get("memory_id"), "quote": ev.get("quote"), "reason": reason})
            else:
                good.append(ev)
        if good:
            kept.append({**p, "evidence": good})
        else:
            dropped.append({"pattern": p.get("title", ""), "memory_id": None, "quote": None, "reason": "no evidence survived, pattern removed"})
    return kept, dropped
