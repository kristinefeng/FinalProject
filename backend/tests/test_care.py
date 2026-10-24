"""Defense 3: crisis language gets resources, not AI interpretation."""

import asyncio

import db
from agents import zoom_out
from safety import care


def test_crisis_language_is_caught():
    for text in [
        "Some nights I don't want to be alive anymore.",
        "I keep thinking about killing myself.",
        "Everyone would be better off without me.",
        "I've been hurting myself again.",
    ]:
        assert care.check(text), text


def test_everyday_language_is_not():
    for text in [
        "I'm dying to try that new ramen place.",
        "I want to end my day with tea and a book.",
        "The exam killed me but I survived.",
        "Self-care Sunday: long bath, no laptop.",
    ]:
        assert not care.check(text), text


def test_zoom_out_pauses_without_calling_the_model(no_model):
    for i, day in enumerate(["2026-10-10", "2026-10-12", "2026-10-14"]):
        db.insert_entry("me", {"id": f"e{i}", "date": day, "text": "A long walk and a good talk with Sam."})
    db.insert_entry("me", {"id": "hard", "date": "2026-10-20", "text": "I don't want to be alive.", "care_flag": True})
    result = asyncio.run(zoom_out.zoom_out("me", "story"))
    assert result["status"] == "care"
    assert any("988" in o["label"] for o in result["care"]["options"])
