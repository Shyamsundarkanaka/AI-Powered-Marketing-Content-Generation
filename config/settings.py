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

WORKER_POLL_INTERVAL_SECONDS = int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "10"))

DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
