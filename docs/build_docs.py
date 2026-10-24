"""Build docs/report.html and docs/slides.html as single self-contained files.

    python docs/build_docs.py

Screenshots from docs/screenshots/ and the diagram are embedded as data URIs,
so both files open by double-clicking on any computer with every image
showing. reveal.js is inlined from docs/vendor/, so the slides also work offline.
"""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path

from PIL import Image

DOCS = Path(__file__).resolve().parent
SHOTS = DOCS / "screenshots"
PHOTOS = DOCS.parent / "demo_data" / "photos"
MAX_WIDTH = 1500


def image_uri(path: Path, max_width: int = MAX_WIDTH, quality: int = 78) -> str:
    with Image.open(path) as img:
        img = img.convert("RGB")
        if img.width > max_width:
            img = img.resize((max_width, round(img.height * max_width / img.width)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def render(src: str) -> str:
    diagram = (DOCS / "diagram.svg").read_text(encoding="utf-8")
    src = src.replace("{{diagram}}", diagram)
    src = re.sub(r"\{\{img:([\w.-]+)\}\}", lambda m: image_uri(SHOTS / f"{m.group(1)}.jpg"), src)
    src = re.sub(r"\{\{photo:([\w.-]+)\}\}", lambda m: image_uri(PHOTOS / m.group(1), max_width=900), src)
    leftover = [m for m in re.findall(r"\{\{[^}]+\}\}", src) if not m.startswith("{{vendor:")]
    if leftover:
        raise SystemExit(f"Unfilled placeholders: {leftover}")
    # Vendored libraries go in last, so their own code is never scanned for placeholders.
    return re.sub(r"\{\{vendor:([\w./-]+)\}\}", lambda m: (DOCS / "vendor" / m.group(1)).read_text(encoding="utf-8"), src)


if __name__ == "__main__":
    for name in ("report", "slides"):
        src_path = DOCS / f"{name}_src.html"
        if src_path.exists():
            out = DOCS / f"{name}.html"
            out.write_text(render(src_path.read_text(encoding="utf-8")), encoding="utf-8")
            print(f"wrote {out.name} ({out.stat().st_size / 1e6:.1f} MB)")
