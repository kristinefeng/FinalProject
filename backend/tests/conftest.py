"""Tests run against a throwaway database, never the real one in data/."""

import os
import sys
import tempfile
from pathlib import Path

os.environ["THROUGHLINE_DATA_DIR"] = tempfile.mkdtemp(prefix="throughline-test-")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

import db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    db.init_db()
    for space in db.SPACES:
        db.reset_space(space)
    with db.connect() as conn:
        conn.execute("DELETE FROM runs")
    yield


@pytest.fixture
def no_model(monkeypatch):
    """Fail loudly if anything tries to call the model."""
    import agents.common as common

    def boom(*a, **k):
        raise AssertionError("A model call was made, but this path must not reach the model.")

    monkeypatch.setattr(common, "build_model", boom)
