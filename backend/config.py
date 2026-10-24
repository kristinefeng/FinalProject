"""Model and environment configuration.

The .env file is looked up in two places, in this order: the repo folder, then
the folder above it (where the teaching staff keep theirs). The first value
found for a key wins. The key itself is never printed or logged.

gpt-6-luna needs the Responses API for function tools, so every agent uses
OpenAIResponsesModel through Portkey's OpenAI-compatible gateway.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
ENV_FILES = [REPO_ROOT / ".env", REPO_ROOT.parent / ".env"]
for env_file in ENV_FILES:
    if env_file.exists():
        load_dotenv(env_file, override=False)

DATA_DIR = Path(os.getenv("THROUGHLINE_DATA_DIR", REPO_ROOT / "data"))
DEMO_DIR = REPO_ROOT / "demo_data"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
PROMPTS_DIR = BACKEND_DIR / "prompts"

# The course key only allows gpt-6-luna.
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-6-luna").strip() or "gpt-6-luna"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")


def key_is_set() -> bool:
    return bool(os.getenv("PORTKEY_API_KEY", "").strip())


def env_source() -> str | None:
    """Which .env file supplied the key ("repo" or "parent"), for the setup check."""
    for label, env_file in zip(("repo", "parent"), ENV_FILES):
        if env_file.exists() and "PORTKEY_API_KEY" in env_file.read_text(encoding="utf-8", errors="ignore"):
            return label
    return "environment" if key_is_set() else None


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "PORTKEY_API_KEY is missing. Put it in a .env file in the repo folder or the folder above it."
        )
    return key


@lru_cache(maxsize=2)
def build_model(model_name: str = MODEL_NAME) -> OpenAIResponsesModel:
    key = require_api_key()
    headers = {"x-portkey-api-key": key, "x-portkey-provider": "openai"}
    # Portkey can answer an identical request from its response cache. For
    # experiments that need independent trials, PORTKEY_CACHE_FORCE_REFRESH=1
    # makes every request go to the model.
    if os.getenv("PORTKEY_CACHE_FORCE_REFRESH"):
        headers["x-portkey-cache-force-refresh"] = "true"
    client = AsyncOpenAI(api_key=key, base_url=PORTKEY_BASE_URL, default_headers=headers)
    return OpenAIResponsesModel(model_name, provider=OpenAIProvider(openai_client=client))


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
