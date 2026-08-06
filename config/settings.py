"""Central configuration, loaded and validated from environment variables (.env).

Every value is read through a typed helper that fails at import with the
variable's name in the message. A typo like `VIDEO_FPS=thirty` should stop the
process immediately, not surface eight minutes into a render as a `ValueError`
from inside ffmpeg.

Nothing here has a "safe" fake default. In particular the API keys default to
empty, not to a placeholder string: an unset key must look unset, so the error
says "GEMINI_API_KEY is not set" rather than surfacing a provider's 401.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    """A configuration value is missing or unusable."""


# --- typed readers -----------------------------------------------------------

def _raw(name: str, default: str = "") -> str:
    value = os.getenv(name)
    # Strip inline `# comment` tails: .env files are edited by hand and the
    # example file documents options that way, so `VIDEO_FPS=30  # or 60` is a
    # realistic thing to find here.
    if value is not None and "#" in value:
        value = value.split("#", 1)[0]
    return (value if value is not None else default).strip()


def _path(name: str, default: str) -> Path:
    """Resolve a configured path against BASE_DIR, not the process cwd.

    Streamlit and the CLI entry points get launched from different working
    directories; anchoring to BASE_DIR keeps every entry point pointing at the
    same database and output files.
    """
    raw = Path(_raw(name, default) or default)
    return raw if raw.is_absolute() else (BASE_DIR / raw).resolve()


def _int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = _raw(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}, got {value}")
    return value


def _float(name: str, default: float, *, minimum: float | None = None) -> float:
    raw = _raw(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}, got {value}")
    return value


def _choice(name: str, default: str, allowed: tuple[str, ...]) -> str:
    value = (_raw(name, default) or default).lower()
    if value not in allowed:
        raise ConfigError(f"{name} must be one of {', '.join(allowed)}, got {value!r}")
    return value


def _csv(name: str, default: str) -> tuple[str, ...]:
    raw = _raw(name) if os.getenv(name) is not None else default
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())


# --- paths -------------------------------------------------------------------

DATABASE_PATH = _path("DATABASE_PATH", "./data/app.db")
OUTPUT_DIR = _path("OUTPUT_DIR", "./output")
LOG_DIR = _path("LOG_DIR", "./logs")
BRAND_DIR = _path("BRAND_DIR", "./brand")
ASSET_CACHE_DIR = _path("ASSET_CACHE_DIR", "./data/assets")

# --- logging -----------------------------------------------------------------

LOG_LEVEL = _choice("LOG_LEVEL", "INFO", ("debug", "info", "warning", "error")).upper()
LOG_MAX_BYTES = _int("LOG_MAX_BYTES", 5_000_000, minimum=10_000)
LOG_BACKUP_COUNT = _int("LOG_BACKUP_COUNT", 5, minimum=0)

# --- worker ------------------------------------------------------------------

WORKER_POLL_INTERVAL_SECONDS = _int("WORKER_POLL_INTERVAL_SECONDS", 5, minimum=1)

# --- LLM ---------------------------------------------------------------------
# LLM_PROVIDER selects which block below is active. Switching provider or model
# is a .env change only — see docs/architecture/llm-providers.md.
LLM_PROVIDER = _choice("LLM_PROVIDER", "gemini", ("openai", "gemini", "anthropic"))

OPENAI_API_KEY = _raw("OPENAI_API_KEY")
OPENAI_MODEL = _raw("OPENAI_MODEL", "gpt-5.1")
OPENAI_BASE_URL = _raw("OPENAI_BASE_URL") or None

GEMINI_API_KEY = _raw("GEMINI_API_KEY")
GEMINI_MODEL = _raw("GEMINI_MODEL", "gemini-2.5-pro")
GEMINI_BASE_URL = _raw("GEMINI_BASE_URL") or None

ANTHROPIC_API_KEY = _raw("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _raw("ANTHROPIC_MODEL", "claude-opus-5")
ANTHROPIC_BASE_URL = _raw("ANTHROPIC_BASE_URL") or None

LLM_MAX_TOKENS = _int("LLM_MAX_TOKENS", 8000, minimum=256)
LLM_TIMEOUT_SECONDS = _float("LLM_TIMEOUT_SECONDS", 120, minimum=5)
# Transport-level retries (connection reset, 429, 5xx), handled by the provider
# client itself.
LLM_MAX_RETRIES = _int("LLM_MAX_RETRIES", 3, minimum=0)
# Shape-level attempts: how many times a node may re-ask after the model
# returned something that didn't parse or didn't validate. The retry includes
# the specific error, so 2 is usually enough and 3 is generous.
LLM_JSON_ATTEMPTS = _int("LLM_JSON_ATTEMPTS", 3, minimum=1)

# --- media -------------------------------------------------------------------

VIDEO_ASPECT = _choice("VIDEO_ASPECT", "vertical", ("vertical", "square", "landscape"))
VIDEO_FPS = _int("VIDEO_FPS", 30, minimum=1)
VIDEO_RENDER_THREADS = _int("VIDEO_RENDER_THREADS", 4, minimum=1)
VOICEOVER_SAMPLE_RATE = _int("VOICEOVER_SAMPLE_RATE", 44100, minimum=8000)

# Ordered TTS engine chain; the first one that works wins. Set to an empty
# value to skip synthesis entirely and always write a silent track. Registry
# and instructions for adding a paid engine: media/voice.py.
TTS_ENGINES = _csv("TTS_ENGINES", "piper,pyttsx3")
# Local/offline neural voice for the `piper` engine: path to a downloaded
# .onnx file, with its .onnx.json sidecar alongside it.
PIPER_MODEL_PATH = _raw("PIPER_MODEL_PATH") or None

# --- scraping ----------------------------------------------------------------

HTTP_TIMEOUT_SECONDS = _float("HTTP_TIMEOUT_SECONDS", 20, minimum=1)
HTTP_MAX_RETRIES = _int("HTTP_MAX_RETRIES", 3, minimum=0)


def ensure_directories() -> None:
    """Create the directories the app writes to. Called at import and by tests."""
    for directory in (DATABASE_PATH.parent, OUTPUT_DIR, LOG_DIR, ASSET_CACHE_DIR):
        directory.mkdir(parents=True, exist_ok=True)


ensure_directories()
