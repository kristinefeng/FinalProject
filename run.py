"""Start Throughline: python run.py, then open http://127.0.0.1:8000"""

import os
import threading
import webbrowser
from pathlib import Path

import uvicorn

BACKEND = Path(__file__).resolve().parent / "backend"
PORT = int(os.getenv("PORT", "8000"))

if __name__ == "__main__":
    url = f"http://127.0.0.1:{PORT}"
    print(f"\n  Throughline is starting at {url}  (Ctrl+C to stop)\n")
    if not os.getenv("NO_BROWSER"):
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("main:app", app_dir=str(BACKEND), host="127.0.0.1", port=PORT, log_level="warning")
