"""One place to configure logging, for every entry point.

`LOG_DIR` was previously created and then never written to — all logging went
to stderr, which the Streamlit-hosted worker swallows entirely. That made the
one thing you actually need when a run misbehaves (what the model returned,
which engine the voiceover fell back to, why a render warned) unavailable after
the fact.

Console output stays human-readable; the file handler rotates so a long-running
worker cannot fill a disk.
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from config.settings import LOG_BACKUP_COUNT, LOG_DIR, LOG_LEVEL, LOG_MAX_BYTES

CONSOLE_FORMAT = "%(levelname)s %(name)s: %(message)s"
FILE_FORMAT = "%(asctime)s %(levelname)-8s %(name)s [%(threadName)s]: %(message)s"

# Third-party loggers that are informative at DEBUG and pure noise at INFO.
_NOISY_LOGGERS = ("httpx", "httpcore", "urllib3", "PIL", "matplotlib", "google_genai")

_configured = False


def configure_logging(*, force: bool = False) -> Path:
    """Attach console and rotating-file handlers to the root logger, once.

    Idempotent: the Streamlit app re-runs its script on every interaction, and
    re-adding handlers each time would multiply every log line.
    """
    global _configured
    if _configured and not force:
        return LOG_DIR / "app.log"

    log_path = LOG_DIR / "app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    root.addHandler(file_handler)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(max(logging.WARNING, root.level))

    _configured = True
    logging.getLogger(__name__).debug("Logging configured at %s -> %s", LOG_LEVEL, log_path)
    return log_path
