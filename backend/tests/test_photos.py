"""Photo uploads: iPhone photos work, and unreadable files never crash a save."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import db
import main
import moments


def heic_bytes() -> bytes:
    """A real HEIC image, the iPhone's default photo format."""
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (90, 140, 110)).save(buf, format="HEIF")
    return buf.getvalue()


def test_iphone_heic_photo_is_saved_as_jpeg():
    name = moments.store_photo("me", heic_bytes())
    path = db.UPLOADS_DIR / "me" / name
    assert name.endswith(".jpg") and path.exists()
    with Image.open(path) as img:
        assert img.format == "JPEG" and img.size == (64, 48)


def test_unreadable_photo_gives_a_clear_message():
    with pytest.raises(ValueError, match="couldn't read that photo"):
        moments.store_photo("me", b"\x00\x00\x00\x18ftypheic" + b"\x00" * 200)


def test_unreadable_photo_returns_400_not_a_crash(no_model):
    with TestClient(main.app, raise_server_exceptions=False) as client:
        r = client.post(
            "/api/me/entries",
            data={"text": "A walk by the water.", "date": "2026-10-24"},
            files={"photo": ("IMG_0001.HEIC", b"not really an image", "image/heic")},
        )
    assert r.status_code == 400
    assert "couldn't read that photo" in r.json()["detail"]
    assert db.list_entries("me") == []  # nothing half-saved
