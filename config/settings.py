"""Central configuration loaded from environment variables (.env)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve(env_var: str, default: str) -> Path:
    """Resolve a configured path against BASE_DIR, not the process cwd.

    Streamlit/CLI entry points can be launched from different working
    directories; anchoring to BASE_DIR keeps every entry point pointing at
    the same database and output files.
    """
    raw = Path(os.getenv(env_var, default))
    return raw if raw.is_absolute() else (BASE_DIR / raw).resolve()


DATABASE_PATH = _resolve("DATABASE_PATH", "./data/app.db")
OUTPUT_DIR = _resolve("OUTPUT_DIR", "./output")
LOG_DIR = _resolve("LOG_DIR", "./logs")
BRAND_DIR = _resolve("BRAND_DIR", "./brand")
ASSET_CACHE_DIR = _resolve("ASSET_CACHE_DIR", "./data/assets")

WORKER_POLL_INTERVAL_SECONDS = int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "10"))

# --- LLM ---------------------------------------------------------------------
# The default key is a deliberate placeholder: with it, every agent call fails
# authentication, each node catches that and emits its documented stub output,
# and the pipeline still runs end to end. Drop a real key into .env to go live —
# no code changes anywhere.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "sk-ant-dummy-key-not-a-real-key")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8000"))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))

# --- Media -------------------------------------------------------------------
VIDEO_ASPECT = os.getenv("VIDEO_ASPECT", "vertical")  # vertical | square | landscape
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "30"))
VIDEO_RENDER_THREADS = int(os.getenv("VIDEO_RENDER_THREADS", "4"))
VOICEOVER_SAMPLE_RATE = int(os.getenv("VOICEOVER_SAMPLE_RATE", "44100"))
# When TTS is unavailable the voiceover track is rendered as digital silence of
# the script's estimated spoken duration, so video timing is already correct.
ENABLE_TTS = os.getenv("ENABLE_TTS", "false").lower() in ("1", "true", "yes")

DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
ASSET_CACHE_DIR.mkdir(parents=True, exist_ok=True)
