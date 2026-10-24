"""Defense 2: evidence that isn't really in the journal is dropped."""

from safety.grounding import ground_patterns

ENTRIES = {
    "e1": {"id": "e1", "text": "Priya and I got lost on the trail and ended up laughing for an hour. I felt free."},
    "e2": {"id": "e2", "text": "I haven’t run in three weeks. My shoes are by the door where I left them."},
}


def pattern(*evidence):
    return {"title": "Test", "kind": "alignment", "observation": "...", "evidence": [{"memory_id": m, "quote": q} for m, q in evidence]}


def test_real_quotes_survive_even_with_curly_apostrophes():
    kept, dropped = ground_patterns([pattern(("e1", "ended up laughing for an hour"), ("e2", "I haven't run in three weeks"))], ENTRIES)
    assert len(kept) == 1 and len(kept[0]["evidence"]) == 2 and dropped == []


def test_invented_quote_is_dropped():
    kept, dropped = ground_patterns([pattern(("e1", "ended up laughing for an hour"), ("e2", "running is the only thing that keeps me sane"))], ENTRIES)
    assert len(kept[0]["evidence"]) == 1
    assert dropped[0]["reason"] == "quote does not appear in that entry"


def test_quote_attributed_to_wrong_entry_is_dropped():
    kept, dropped = ground_patterns([pattern(("e2", "ended up laughing for an hour"))], ENTRIES)
    assert kept == []
    assert any(d["reason"] == "quote does not appear in that entry" for d in dropped)


def test_unknown_entry_id_is_dropped():
    kept, dropped = ground_patterns([pattern(("e99", "ended up laughing for an hour"))], ENTRIES)
    assert kept == [] and dropped[0]["reason"] == "cites an entry the agent was never shown"


def test_pattern_with_no_surviving_evidence_is_removed():
    kept, dropped = ground_patterns([pattern(("e1", "we climbed a mountain at dawn together"))], ENTRIES)
    assert kept == []
    assert dropped[-1]["reason"] == "no evidence survived, pattern removed"
