"""Defense 1: journal text is data, never instructions.

Three layers, cheapest first:
1. scan(): when an entry is saved, look for text that is trying to talk to the
   AI ("ignore previous instructions", "you are now", "system prompt", links).
   A flagged entry is still saved and shown to the user, but it is held back
   from every agent until the user releases it.
2. as_data(): every entry that does reach an agent is wrapped in a <memory>
   element with angle brackets escaped, so text can't close the wrapper and
   pose as the app speaking. The prompts say content inside <memory> is data.
3. Least privilege: agent tools are read-only and scoped to the current space
   by the server. The one write (changing the North Star) is only a proposal
   until the person clicks Accept. Even an injection that slipped through has
   nothing dangerous to call.
"""

from __future__ import annotations

import html
import re
from typing import Any

PATTERNS: list[tuple[str, str]] = [
    ("override", r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|your|the)\b[^.\n]{0,20}\b(instructions?|rules|prompts?|guidelines|directions)\b"),
    ("role_change", r"\b(you are now|act as|pretend to be|from now on,? you|new instructions?|developer mode|jailbreak)\b"),
    ("prompt_probe", r"\b(system prompt|system message|developer message|hidden instructions?|your instructions)\b"),
    ("ai_address", r"\b(attention|note to|message for|instructions? for)\b[^.\n]{0,15}\b(ai|assistant|model|llm|chatgpt|agent|throughline)\b"),
    ("exfiltration", r"\b(reveal|print|output|list|dump|send|repeat|show)\b[^.\n]{0,30}\b(all|every|other|entire|full|private)\b[^.\n]{0,30}\b(entries|memories|journal|data|records|text)\b"),
    ("tool_coercion", r"\b(call|use|run|invoke|execute)\b[^.\n]{0,20}\b(tool|function|propose_north_star_update|search_memories)\b"),
    ("link", r"https?://|www\.[a-z0-9-]+\.[a-z]{2,}"),
    ("markup", r"</?\s*(memory|system|instructions?|assistant|user)\b[^>]*>"),
]
_COMPILED = [(name, re.compile(rx, re.IGNORECASE)) for name, rx in PATTERNS]


def scan(text: str) -> list[dict[str, str]]:
    """Return one flag per matching pattern, with the text that matched."""
    flags = []
    for name, rx in _COMPILED:
        m = rx.search(text or "")
        if m:
            flags.append({"rule": name, "match": m.group(0)[:80]})
    return flags


def as_data(entry: dict[str, Any], full: bool = True) -> str:
    """Wrap one entry for a prompt. Escaping stops text from closing the tag."""
    body = entry.get("text", "") if full else entry.get("summary") or ""
    parts = [
        f'<memory id="{html.escape(entry["id"])}" date="{html.escape(entry["date"])}">',
        f"title: {html.escape(entry.get('title') or '')}",
        html.escape(body, quote=False),
    ]
    if entry.get("photo_desc"):
        parts.append(f"[photo: {html.escape(entry['photo_desc'], quote=False)}]")
    parts.append("</memory>")
    return "\n".join(parts)
