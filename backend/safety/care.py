"""Defense 3: Throughline is not a therapist.

If an entry contains language about self-harm or not wanting to be alive, the
app does not tag it, reflect on it, or send it to the model. It shows support
resources instead, and Zoom Out pauses while such an entry is recent. This is
a deliberately simple, deterministic check: it costs nothing, can't be talked
out of firing, and errs on the side of showing resources.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

PHRASES = [
    r"kill(ing)? myself",
    r"end(ing)? (it all|my life)\b",
    r"suicid",
    r"self[- ]?harm",
    r"hurt(ing)? myself",
    r"cut(ting)? myself",
    r"(don'?t|do not) want to (be alive|live|exist|wake up)",
    r"no (reason|point) (to|in) (live|living|going on)",
    r"better off (dead|without me)",
    r"want to die",
    r"overdose",
]
_RX = re.compile("|".join(PHRASES), re.IGNORECASE)

PAUSE_DAYS = 14

RESOURCES = {
    "title": "You don't have to carry this alone.",
    "body": (
        "It sounds like you might be going through something really hard. Throughline is a reflection "
        "tool, not a counselor, so it won't try to interpret this entry. Talking to a person can help."
    ),
    "options": [
        {"label": "Call or text 988", "detail": "Suicide & Crisis Lifeline (US), 24/7", "href": "tel:988"},
        {"label": "Text HOME to 741741", "detail": "Crisis Text Line (US), 24/7", "href": "sms:741741?body=HOME"},
        {"label": "Emergency", "detail": "Call 911 if you are in immediate danger", "href": "tel:911"},
    ],
}


def check(text: str) -> bool:
    return bool(_RX.search(text or ""))


def recent_care_entry(entries: list[dict[str, Any]], today: date | None = None) -> dict[str, Any] | None:
    """The newest care-flagged entry from the last PAUSE_DAYS, if any."""
    cutoff = ((today or date.today()) - timedelta(days=PAUSE_DAYS)).isoformat()
    for e in entries:
        if e.get("care_flag") and e["date"] >= cutoff:
            return e
    return None
